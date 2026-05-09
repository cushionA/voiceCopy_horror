#!/usr/bin/env python3
"""
merge_dit_chunked.py — DiT ONNX external-data を単一完全 ONNX ファイルに統合
voice_horror Phase 3 fix (v3: single ModelProto, no protobuf merge trick)

Sentis の protobuf パーサは embedded message の merge 仕様を実装していないため、
v2 の「mini ModelProto を複数連結」方式では graph が最後の 1 個だけになる。
v3 では graph フィールドのサイズを事前計算し、
1 つの完全な ModelProto (field 7 が 1 つ) として書く。

手書き protobuf エンコーダを使うことで SerializeToString による
ACCESS_VIOLATION (0xC0000005) を回避する。

Usage:
    pip install onnx
    cd voiceCoppy_test
    python merge_dit_chunked.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ONNX  = REPO_ROOT / "voiceCoppy_test" / "onnx_export" / "flow.decoder.estimator.fp32.onnx"
DST_ONNX  = REPO_ROOT / "voice_Horror_Game" / "Assets" / "SentisSpike" / "Models" / "flow.decoder.estimator.merged.fp32.onnx"


# ─── 純 Python protobuf ヘルパー ─────────────────────────────────────────────

def _read_varint(data: bytes, pos: int):
    """varint をデコードして (値, 次の位置) を返す。"""
    value = 0
    shift = 0
    while True:
        b = data[pos]
        pos += 1
        value |= (b & 0x7F) << shift
        shift += 7
        if not (b & 0x80):
            return value, pos


def _varint(value: int) -> bytes:
    """非負整数を protobuf varint にエンコード。"""
    result = []
    while True:
        bits = value & 0x7F
        value >>= 7
        result.append((0x80 | bits) if value else bits)
        if not value:
            break
    return bytes(result)


def _ld_header(field: int, length: int) -> bytes:
    """length-delimited フィールドのヘッダ (タグ + 長さ varint)。"""
    return _varint((field << 3) | 2) + _varint(length)


# ─── ModelProto 分解: graph 部分と非 graph 部分を分離 ─────────────────────────

def split_model_graph(model_bytes: bytes):
    """
    ModelProto バイナリを解析して
      (non_graph_bytes, graph_content)
    を返す。
    non_graph_bytes: field 7 (graph) 以外の全フィールドをそのままコピー
    graph_content:   field 7 の内容 (GraphProto バイナリ、タグ・長さを除く)
    """
    non_graph = bytearray()
    graph_content = None
    i = 0
    n = len(model_bytes)

    while i < n:
        field_start = i
        tag, i = _read_varint(model_bytes, i)
        field_number = tag >> 3
        wire_type = tag & 7

        if wire_type == 0:          # varint
            _, i = _read_varint(model_bytes, i)
            if field_number != 7:
                non_graph += model_bytes[field_start:i]

        elif wire_type == 1:        # 64-bit
            end = i + 8
            if field_number != 7:
                non_graph += model_bytes[field_start:end]
            i = end

        elif wire_type == 2:        # length-delimited
            length, i = _read_varint(model_bytes, i)
            end = i + length
            if field_number == 7:   # graph
                graph_content = model_bytes[i:end]
            else:
                non_graph += model_bytes[field_start:end]
            i = end

        elif wire_type == 5:        # 32-bit
            end = i + 4
            if field_number != 7:
                non_graph += model_bytes[field_start:end]
            i = end

        else:
            raise ValueError(f"Unsupported wire type {wire_type} at pos {field_start}")

    return bytes(non_graph), graph_content


# ─── TensorProto / GraphProto フィールドエンコード ───────────────────────────

def encode_initializer_graph_field(init) -> tuple:
    """
    initializer 1 個分を GraphProto.initializer フィールド (field 6) として
    書くためのバイト列を計算する。

    Returns (graph_field_hdr, tensor_meta, raw_data_hdr, raw_data_ref)
    raw_data_ref は init.raw_data への参照 (コピーしない)。
    合計サイズ = len(gfh) + len(tm) + len(rdh) + len(raw_data_ref)
    """
    raw_data_ref = init.raw_data   # 参照 (コピーしない)
    raw_len = len(raw_data_ref)

    # ── TensorProto メタデータ部分 ──────────────────────────────────────────
    tensor_meta = bytearray()

    # dims (field 1, wire 0 = varint, repeated)
    for dim in init.dims:
        v = dim if dim >= 0 else (dim & 0xFFFFFFFFFFFFFFFF)
        tensor_meta += _varint((1 << 3) | 0) + _varint(v)

    # data_type (field 2, wire 0 = varint)
    tensor_meta += _varint((2 << 3) | 0) + _varint(init.data_type)

    # name (field 8, wire 2 = LEN)
    if init.name:
        nb = init.name.encode("utf-8")
        tensor_meta += _ld_header(8, len(nb)) + nb

    # raw_data フィールドヘッダ (field 9, wire 2 = LEN)
    raw_data_hdr = _ld_header(9, raw_len)

    # ── GraphProto.initializer フィールドヘッダ (field 5, wire 2 = LEN) ────
    # ONNX proto3 では GraphProto.initializer は field 5 (field 6 ではない)
    # 旧版コードで field 6 にしていたため protobuf parser が unknown field
    # として読み飛ばし、onnx.load で initializers=0 になっていた。
    tensor_size = len(tensor_meta) + len(raw_data_hdr) + raw_len
    graph_field_hdr = _ld_header(5, tensor_size)

    return bytes(graph_field_hdr), bytes(tensor_meta), raw_data_hdr, raw_data_ref


# ─── メイン ─────────────────────────────────────────────────────────────────

def main():
    try:
        import onnx
        from onnx.external_data_helper import load_external_data_for_model
    except ImportError:
        print("[ERROR] onnx が見つかりません。  pip install onnx  を実行してください。")
        sys.exit(1)

    if not SRC_ONNX.exists():
        print(f"[ERROR] 入力ファイルが見つかりません: {SRC_ONNX}")
        sys.exit(1)

    # ─── 1. graph 構造をロード ───────────────────────────────────────────────
    print(f"[1/6] Loading graph structure: {SRC_ONNX}")
    m = onnx.load(str(SRC_ONNX), load_external_data=False)

    # ─── 2. external data を raw_data に展開 ─────────────────────────────────
    print(f"[2/6] Loading external data (1.3 GB)...")
    load_external_data_for_model(m, str(SRC_ONNX.parent))
    n_init = len(m.graph.initializer)
    total_raw_mb = sum(len(i.raw_data) for i in m.graph.initializer) / (1024 ** 2)
    print(f"      {n_init} initializers, {total_raw_mb:.0f} MB raw_data")

    # ─── 3. initializer を退避してモデルから除去 ────────────────────────────
    print(f"[3/6] Extracting initializers from model...")
    all_inits = list(m.graph.initializer)
    del m.graph.initializer[:]

    # ─── 3.5. stale value_info を除去 ───────────────────────────────────────
    # dynamo exporter が残す val_0 等の dangling 参照で
    # Sentis の "key 'val_0' was not present in the dictionary" 例外が出るので、
    # 実際の node 出力 / input / initializer に存在しない value_info を削除する。
    print(f"[3.5/6] Stripping stale value_info entries...")
    valid_names = set()
    for n in m.graph.node:
        valid_names.update(n.output)
    for i in m.graph.input:
        valid_names.add(i.name)
    for init in all_inits:                     # 退避済み initializer 名も含める
        valid_names.add(init.name)

    before = len(m.graph.value_info)
    cleaned = [vi for vi in m.graph.value_info if vi.name in valid_names]
    removed = before - len(cleaned)
    del m.graph.value_info[:]
    m.graph.value_info.extend(cleaned)
    print(f"      removed {removed} stale value_info entries (kept {len(cleaned)})")

    # ─── 4. スケルトン (initializer なし) をシリアライズ ─────────────────────
    print(f"[4/6] Serializing skeleton model (no initializers)...")
    skeleton = m.SerializeToString()   # initializer なしなので小さい
    print(f"      Skeleton: {len(skeleton) // 1024} KB")

    # ─── 5. サイズ計算 ──────────────────────────────────────────────────────
    print(f"[5/6] Computing sizes and building graph field table...")

    # スケルトンから non-graph bytes と graph content を分離
    non_graph_bytes, graph_content = split_model_graph(skeleton)
    print(f"      non_graph: {len(non_graph_bytes)} B, graph_content: {len(graph_content)} B")

    # 各 initializer のフィールドバイト情報を計算
    init_fields = []          # (gfh, tensor_meta, rdh, raw_ref) per initializer
    total_init_field_size = 0

    for init in all_inits:
        gfh, tm, rdh, raw_ref = encode_initializer_graph_field(init)
        field_size = len(gfh) + len(tm) + len(rdh) + len(raw_ref)
        init_fields.append((gfh, tm, rdh, raw_ref))
        total_init_field_size += field_size

    total_graph_size = len(graph_content) + total_init_field_size
    print(f"      Total graph size: {total_graph_size // (1024**2)} MB")

    # ─── 6. 単一完全 ONNX ファイルを書く ─────────────────────────────────────
    DST_ONNX.parent.mkdir(parents=True, exist_ok=True)
    print(f"[6/6] Writing complete single-file ONNX: {DST_ONNX}")

    with open(str(DST_ONNX), "wb") as f:
        # ModelProto の non-graph フィールド (opset, ir_version, etc.)
        f.write(non_graph_bytes)

        # ModelProto.graph (field 7) — 単一フィールド、正確なサイズ
        f.write(_ld_header(7, total_graph_size))

        # スケルトンの graph 内容 (node, input, output, value_info 等)
        f.write(graph_content)

        # 438 個の initializer を graph フィールド内に書く
        for i, (gfh, tm, rdh, raw_ref) in enumerate(init_fields):
            f.write(gfh)    # GraphProto.initializer フィールドヘッダ
            f.write(tm)     # TensorProto メタデータ (dims, dtype, name)
            f.write(rdh)    # raw_data フィールドヘッダ
            f.write(bytes(raw_ref) if not isinstance(raw_ref, (bytes, bytearray)) else raw_ref)

            if (i + 1) % 50 == 0 or (i + 1) == n_init:
                done_mb = sum(len(init_fields[j][3]) for j in range(i + 1)) / (1024 ** 2)
                print(f"      [{i+1:3d}/{n_init}] {done_mb:.0f} MB written")

    size_mb = DST_ONNX.stat().st_size / (1024 ** 2)
    print(f"[OK]  Done! {size_mb:.0f} MB → {DST_ONNX}")
    print()
    print("次のステップ:")
    print("  1. Unity で Assets > Refresh (Ctrl+R)")
    print("  2. Assets/SentisSpike/Models/ に flow.decoder.estimator.merged.fp32.onnx が")
    print("     ModelAsset として表示されることを確認")


if __name__ == "__main__":
    main()
