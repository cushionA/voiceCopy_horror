#!/usr/bin/env python3
"""
diag_hift8.py — "expecting 4, got 3" を引き起こすノードを特定する

DeclareRank(3) を実行する可能性のあるノード:
- Transpose: DeclareRank(permutations.Length)
- Tile: DeclareRank(repeats.length)
- Pad: DeclareRank(shapePads[0] / 2)
- Resize: DeclareRank(scalesOrSizes.shape[0])
- Flatten: DeclareRank(rank.value)
- ScatterND: DeclareRank(shapeUpdates.rank - ...)
- LSTM/GRU: DeclareRank(3) on X, W, R, initialH, initialC

チェック: 上記ノードの入力テンソルが value_info で rank=4 の場合 → DeclareRank(3) → エラー
"""
import onnx
from onnx import numpy_helper
import numpy as np
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL = REPO_ROOT / "voice_Horror_Game" / "Assets" / "SentisSpike" / "Models" / "hift.fixed.fp32.onnx"

print(f"Loading {MODEL}...")
m = onnx.load(str(MODEL))

# ─── vi_map 構築（全テンソルの rank） ─────────────────────────────────────────
vi_map = {}
for init in m.graph.initializer:
    vi_map[init.name] = len(init.dims)
for vi in m.graph.value_info:
    if vi.type.HasField("tensor_type") and vi.type.tensor_type.HasField("shape"):
        vi_map[vi.name] = len(vi.type.tensor_type.shape.dim)
for inp in m.graph.input:
    if inp.type.HasField("tensor_type") and inp.type.tensor_type.HasField("shape"):
        vi_map[inp.name] = len(inp.type.tensor_type.shape.dim)

# initializer dict
init_by_name = {init.name: init for init in m.graph.initializer}

def get_attrs(node):
    """ノードのアトリビュートを辞書化"""
    attrs = {}
    for a in node.attribute:
        if a.type == onnx.AttributeProto.INT:
            attrs[a.name] = a.i
        elif a.type == onnx.AttributeProto.INTS:
            attrs[a.name] = list(a.ints)
        elif a.type == onnx.AttributeProto.FLOAT:
            attrs[a.name] = a.f
        elif a.type == onnx.AttributeProto.STRING:
            attrs[a.name] = a.s
    return attrs

print("\n=== Transpose: perm.length != input_rank (→ DeclareRank(perm.length) on rank-4 tensor) ===")
for node in m.graph.node:
    if node.op_type == "Transpose":
        attrs = get_attrs(node)
        perm = attrs.get("perm", None)
        inp = node.input[0] if node.input else ""
        inp_rank = vi_map.get(inp, "?")
        if perm is not None:
            perm_len = len(perm)
            if isinstance(inp_rank, int) and perm_len != inp_rank:
                print(f"  MISMATCH out={node.output[0]!r}, perm={perm}(len={perm_len}), input {inp!r}(rank={inp_rank})")
            elif inp_rank == 4 and perm_len == 3:
                print(f"  TRIGGER out={node.output[0]!r}, perm={perm}(len=3), input {inp!r}(rank=4)")

print("\n=== Tile: repeats_len != input_rank ===")
for node in m.graph.node:
    if node.op_type == "Tile":
        inp = node.input[0] if len(node.input) > 0 else ""
        repeats = node.input[1] if len(node.input) > 1 else ""
        inp_rank = vi_map.get(inp, "?")
        # repeats は 1D テンソル、長さ = 繰り返し次元数 = 入力の rank
        if repeats in init_by_name:
            rep_data = numpy_helper.to_array(init_by_name[repeats])
            rep_len = len(rep_data)
            if isinstance(inp_rank, int) and rep_len != inp_rank:
                print(f"  MISMATCH out={node.output[0]!r}, repeats len={rep_len}, input {inp!r}(rank={inp_rank})")
        else:
            # repeats が value_info のテンソル (shape で推測)
            rep_rank = vi_map.get(repeats, "?")
            print(f"  Tile: input {inp!r}(rank={inp_rank}), repeats={repeats!r}(rank={rep_rank})")

print("\n=== Pad: pads_len/2 != input_rank ===")
for node in m.graph.node:
    if node.op_type == "Pad":
        inp = node.input[0] if len(node.input) > 0 else ""
        inp_rank = vi_map.get(inp, "?")
        # opset 11+: pads is input[1] tensor
        if len(node.input) > 1:
            pads_inp = node.input[1]
            if pads_inp in init_by_name:
                pads_data = numpy_helper.to_array(init_by_name[pads_inp])
                pads_len = len(pads_data)
                expected_rank = pads_len // 2
                if isinstance(inp_rank, int) and expected_rank != inp_rank:
                    print(f"  MISMATCH out={node.output[0]!r}, pads_len={pads_len}(rank_expect={expected_rank}), input {inp!r}(rank={inp_rank})")
        else:
            # opset < 11: pads is attribute
            attrs = get_attrs(node)
            pads = attrs.get("pads", [])
            expected_rank = len(pads) // 2
            if isinstance(inp_rank, int) and expected_rank != inp_rank:
                print(f"  MISMATCH out={node.output[0]!r}, pads attr len={len(pads)}(rank_expect={expected_rank}), input {inp!r}(rank={inp_rank})")

print("\n=== Resize: sizes/scales len != input_rank ===")
for node in m.graph.node:
    if node.op_type == "Resize":
        inp = node.input[0] if len(node.input) > 0 else ""
        inp_rank = vi_map.get(inp, "?")
        # input[2] is scales, input[3] is sizes (opset 11+)
        scales = node.input[2] if len(node.input) > 2 else ""
        sizes = node.input[3] if len(node.input) > 3 else ""
        sz = sizes if sizes else scales
        if sz and sz in init_by_name:
            sz_data = numpy_helper.to_array(init_by_name[sz])
            sz_len = len(sz_data)
            if isinstance(inp_rank, int) and sz_len != inp_rank:
                print(f"  MISMATCH out={node.output[0]!r}, sizes/scales len={sz_len}, input {inp!r}(rank={inp_rank})")

print("\n=== LSTM/GRU: check if X/W/R is rank-4 ===")
for node in m.graph.node:
    if node.op_type in ("LSTM", "GRU", "RNN"):
        x = node.input[0] if len(node.input) > 0 else ""
        w = node.input[1] if len(node.input) > 1 else ""
        r = node.input[2] if len(node.input) > 2 else ""
        x_rank = vi_map.get(x, "?")
        w_rank = vi_map.get(w, "?")
        r_rank = vi_map.get(r, "?")
        issue = any(
            isinstance(rk, int) and rk == 4
            for rk in [x_rank, w_rank, r_rank]
        )
        if issue:
            print(f"  ISSUE op={node.op_type}, X={x!r}(rank={x_rank}), W={w!r}(rank={w_rank}), R={r!r}(rank={r_rank})")
        else:
            print(f"  OK op={node.op_type}, outputs={list(node.output)}, X rank={x_rank}, W rank={w_rank}, R rank={r_rank}")

# ─── 総合チェック: rank-4 input テンソルを消費するノードで DeclareRank(3) が走る可能性 ─
print("\n=== rank-4 テンソルを入力に取り DeclareRank(3) に相当する処理をするノード ===")
for node in m.graph.node:
    for i, inp in enumerate(node.input):
        if not inp:
            continue
        inp_rank = vi_map.get(inp, "?")
        if inp_rank != 4:
            continue

        # このノードが DeclareRank(3) を実行する可能性を調べる
        if node.op_type == "Transpose":
            attrs = get_attrs(node)
            perm = attrs.get("perm", [])
            if len(perm) == 3:
                print(f"  ⚠️  Transpose(perm len=3) on rank-4 input {inp!r} → out={node.output[0]!r}")

        elif node.op_type in ("LSTM", "GRU", "RNN") and i in (0, 1, 2):
            print(f"  ⚠️  {node.op_type}(DeclareRank(3)) on rank-4 input[{i}]={inp!r} → out={list(node.output)}")

        elif node.op_type == "Pad":
            # opset 11: pads is input[1]
            if len(node.input) > 1 and node.input[1] in init_by_name:
                pads_data = numpy_helper.to_array(init_by_name[node.input[1]])
                if len(pads_data) // 2 == 3:
                    print(f"  ⚠️  Pad(pads_len/2=3) on rank-4 input {inp!r} → out={node.output[0]!r}")

        elif node.op_type == "Tile":
            if len(node.input) > 1 and node.input[1] in init_by_name:
                rep_data = numpy_helper.to_array(init_by_name[node.input[1]])
                if len(rep_data) == 3:
                    print(f"  ⚠️  Tile(repeats len=3) on rank-4 input {inp!r} → out={node.output[0]!r}")

        elif node.op_type == "Conv" and i == 1:
            # Conv calls shapeKernel.DeclareRank(shapeX.rank)
            x_name = node.input[0]
            x_rank = vi_map.get(x_name, "?")
            if isinstance(x_rank, int) and x_rank == 3:
                print(f"  ⚠️  Conv(shapeX.rank=3→DeclareRank(3)) on rank-4 kernel {inp!r} → out={node.output[0]!r}")

        elif node.op_type == "ConvTranspose" and i == 1:
            x_name = node.input[0]
            x_rank = vi_map.get(x_name, "?")
            if isinstance(x_rank, int) and x_rank == 3:
                print(f"  ⚠️  ConvTranspose(shapeX.rank=3→DeclareRank(3)) on rank-4 kernel {inp!r} → out={node.output[0]!r}")

print("\nDone.")
