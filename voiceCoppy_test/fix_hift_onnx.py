#!/usr/bin/env python3
"""
fix_hift_onnx.py — hift ONNX の rank-0 テンソルを Sentis 互換に修正
voice_horror Phase 3 fix v6

v6 (2026-05-07) — Gather scalar-index 問題を修正
  v5 の Step 1 で rank-0 initializer を全て rank-1 に変更した副作用:
    val_85(=0), val_86(=1) など scalar index として使われていた initializer が
    rank-1 になったことで Gather 出力 rank が data_rank-1 → data_rank に変わり、
    下流で 77 件の rank 衝突が発生していた (diag_hift12.py で確認)。
  修正: 新 Step 2.5 で、元 rank-0 initializer を index とする Gather ノードの
  直後に Squeeze(axes=[gather_axis]) を挿入して出力 rank を元に戻す。

v5 (2026-05-06):
  全 value_info を除去して DynamicRank スタートを保証。

v4:
  1. rank-0 initializer → rank-1
  2. Squeeze(val_0)->sym_size_int_187 を Identity に置換
  3. Range ノード入力に Squeeze(axes=[0]) を挿入
  4. value_info を全除去
  5. graph.input/output の rank-0 を rank-1 に更新

Usage:
    pip install onnx
    cd voiceCoppy_test
    python fix_hift_onnx.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ONNX  = REPO_ROOT / "voiceCoppy_test" / "onnx_export" / "hift.fp32.onnx"
DST_ONNX  = REPO_ROOT / "voice_Horror_Game" / "Assets" / "SentisSpike" / "Models" / "hift.fixed.fp32.onnx"

def main():
    try:
        import onnx
        from onnx import helper, TensorProto, numpy_helper
        import numpy as np
    except ImportError:
        print("[ERROR] onnx が見つかりません。  pip install onnx  を実行してください。")
        sys.exit(1)

    src = SRC_ONNX
    if not src.exists():
        alt = REPO_ROOT / "voice_Horror_Game" / "Assets" / "SentisSpike" / "Models" / "hift.fp32.onnx"
        if alt.exists():
            src = alt
        else:
            print(f"[ERROR] 入力ファイルが見つかりません: {src}")
            sys.exit(1)

    print(f"[1/8] Loading: {src}")
    model = onnx.load(str(src))

    # opset バージョン確認
    opset_version = 11
    for op in model.opset_import:
        if op.domain == "" or op.domain == "ai.onnx":
            opset_version = op.version
            break
    print(f"      opset_version = {opset_version}")

    # opset 13+ では Squeeze の axes は tensor 入力、それ以前は属性
    use_tensor_axes = (opset_version >= 13)

    # ─── Step 1: rank-0 initializer → rank-1 ──────────────────────────────
    # NOTE: rank0_init_names を収集して Step 2.5 の Gather 修正に使う。
    print("[2/8] Fixing rank-0 initializers...")
    fixed_init = 0
    rank0_init_names: set = set()   # 元々 rank-0 だった initializer 名 (Step 2.5 で参照)
    for init in model.graph.initializer:
        if len(init.dims) == 0:
            rank0_init_names.add(init.name)
            del init.dims[:]
            init.dims.extend([1])
            fixed_init += 1
    print(f"      {fixed_init} initializer(s) fixed to rank-1.  "
          f"({len(rank0_init_names)} scalar-index names tracked for Step 2.5)")

    # ─── Step 2: Squeeze(val_0)->sym_size_int_187 を Identity に置換 ──────
    print("[3/8] Replacing Squeeze(val_0)->sym_size_int_187 with Identity...")
    new_nodes = []
    squeeze_replaced = 0
    for node in model.graph.node:
        if (node.op_type == "Squeeze"
                and len(node.input) >= 1
                and node.input[0] == "val_0"
                and len(node.output) >= 1
                and node.output[0] == "sym_size_int_187"):
            identity = helper.make_node(
                "Identity",
                inputs=["val_0"],
                outputs=["sym_size_int_187"],
                name="identity_sym_size_int_187"
            )
            new_nodes.append(identity)
            squeeze_replaced += 1
            print(f"      Replaced: Squeeze({node.input[0]}) -> Identity")
        else:
            new_nodes.append(node)
    del model.graph.node[:]
    model.graph.node.extend(new_nodes)
    if squeeze_replaced == 0:
        print("      [WARN] Squeeze(val_0)->sym_size_int_187 not found. Model may differ.")

    # ─── Step 2.5: Gather の scalar-index 問題を修正 ──────────────────────
    # ONNX Gather の意味論:
    #   rank-0 (scalar) index → 指定 axis を除去  → output rank = data_rank - 1
    #   rank-1 index (size=1) → axis を 1 で残す  → output rank = data_rank
    # Step 1 で scalar initializer を rank-1 にしたため、下流で rank が +1 ズレている。
    # 修正: 当該 Gather の出力直後に Squeeze(axes=[gather_axis]) を挿入して rank を元に戻す。
    print("[3.5/8] Fixing Gather nodes with originally-scalar (rank-0) indices...")

    # Pass 1: 修正が必要な Gather ノードと、その axis 値を洗い出す
    needed_gather_axes: set = set()
    for node in model.graph.node:
        if (node.op_type == "Gather"
                and len(node.input) > 1
                and node.input[1] in rank0_init_names):
            axis = 0
            for a in node.attribute:
                if a.name == "axis":
                    axis = int(a.i)
            needed_gather_axes.add(axis)

    # axis ごとの Constant ノード（Squeeze の axes 入力用、opset 13+）
    sg_axes_names: dict = {}   # axis_val → const_tensor_name
    sg_const_nodes = []
    for axis_val in sorted(needed_gather_axes):
        t_name = f"__sg_gather_axes_{axis_val}__"
        if use_tensor_axes:
            axes_t = helper.make_tensor(t_name, TensorProto.INT64, [1], [axis_val])
            sg_const_nodes.append(helper.make_node(
                "Constant", inputs=[], outputs=[t_name],
                name=f"const_sg_gather_axes_{axis_val}", value=axes_t
            ))
        sg_axes_names[axis_val] = t_name

    gather_squeeze_count = 0
    # Constant ノードをリスト先頭に置いてから他のノードを追加
    new_nodes_25 = sg_const_nodes[:]

    for node in model.graph.node:
        if (node.op_type == "Gather"
                and len(node.input) > 1
                and node.input[1] in rank0_init_names):
            axis = 0
            for a in node.attribute:
                if a.name == "axis":
                    axis = int(a.i)

            orig_outputs = list(node.output)   # 元の出力名を保存

            # Gather 出力名を tmp に付け替え（protobuf repeated string field は直接代入可）
            for i, o in enumerate(orig_outputs):
                if o:
                    node.output[i] = o + "__sg_tmp__"

            new_nodes_25.append(node)          # 変更済み Gather を追加

            # 直後に Squeeze を挿入：tmp → 元の名前 (rank を data_rank-1 に戻す)
            axes_const = sg_axes_names[axis]
            for orig_out in orig_outputs:
                if orig_out:
                    tmp_out = orig_out + "__sg_tmp__"
                    if use_tensor_axes:
                        sq = helper.make_node(
                            "Squeeze",
                            inputs=[tmp_out, axes_const],
                            outputs=[orig_out],
                            name=f"fix_sg_sq_{orig_out}"
                        )
                    else:
                        sq = helper.make_node(
                            "Squeeze",
                            inputs=[tmp_out],
                            outputs=[orig_out],
                            name=f"fix_sg_sq_{orig_out}",
                            axes=[axis]
                        )
                    new_nodes_25.append(sq)
                    gather_squeeze_count += 1
                    print(f"      Gather out={orig_out!r}  axis={axis}  → Squeeze inserted")
        else:
            new_nodes_25.append(node)

    del model.graph.node[:]
    model.graph.node.extend(new_nodes_25)
    print(f"      {gather_squeeze_count} Gather output(s) wrapped with Squeeze (scalar-index fix).")
    if gather_squeeze_count == 0:
        print("      [WARN] No Gather nodes with scalar indices found. Model may differ from expected.")

    # ─── Step 3: Range ノードの全入力に Squeeze を挿入 ────────────────────
    # Range.InferPartial は inputs を DeclareRank(0) する。
    # 全入力が rank-1 になっているので、Squeeze(axes=[0]) でスカラーに戻す。
    print("[4/8] Inserting Squeeze before all Range node inputs...")

    range_fixes_count = 0
    new_nodes = []

    # axes=[0] 用定数テンソルの名前（1つ共有、Step 2.5 の __sg_gather_axes_0__ とは別名）
    axes_const_name = "__sentis_squeeze_axes_0__"

    # グラフ先頭に axes 定数ノードを追加（opset 13+）
    if use_tensor_axes:
        axes_tensor = helper.make_tensor(
            axes_const_name, TensorProto.INT64, [1], [0]
        )
        axes_node = helper.make_node(
            "Constant",
            inputs=[],
            outputs=[axes_const_name],
            name="const_squeeze_axes_0",
            value=axes_tensor
        )
        new_nodes.append(axes_node)

    # 既に生成済みの Squeeze 出力名（重複防止）
    sq_outputs_added = set()

    for node in model.graph.node:
        if node.op_type == "Range":
            new_inputs = []
            for idx, inp in enumerate(node.input):
                sq_out = inp + "_sq0_for_range"
                if sq_out not in sq_outputs_added:
                    if use_tensor_axes:
                        sq_node = helper.make_node(
                            "Squeeze",
                            inputs=[inp, axes_const_name],
                            outputs=[sq_out],
                            name=f"squeeze_{inp}_for_range"
                        )
                    else:
                        sq_node = helper.make_node(
                            "Squeeze",
                            inputs=[inp],
                            outputs=[sq_out],
                            name=f"squeeze_{inp}_for_range",
                            axes=[0]
                        )
                    new_nodes.append(sq_node)
                    sq_outputs_added.add(sq_out)
                    range_fixes_count += 1
                new_inputs.append(sq_out)

            new_range = helper.make_node(
                "Range",
                inputs=new_inputs,
                outputs=list(node.output),
                name=node.name or f"range_{node.output[0]}"
            )
            new_nodes.append(new_range)
        else:
            new_nodes.append(node)

    del model.graph.node[:]
    model.graph.node.extend(new_nodes)
    print(f"      {range_fixes_count} Range input(s) wrapped with Squeeze.")

    # ─── Step 4: ALL value_info を除去 ───────────────────────────────────
    # Sentis は value_info を読んで中間テンソルの rank を事前宣言する。
    # rank 事前宣言 vs InferPartial の DeclareRank が衝突すると
    # "expecting 4, got 3" になる。全除去で全テンソルを DynamicRank スタートにする。
    print("[5/8] Stripping ALL intermediate value_info...")
    before = len(model.graph.value_info)
    del model.graph.value_info[:]
    print(f"      Removed all {before} value_info entries. Sentis will infer all ranks dynamically.")

    # ─── Step 5: graph.input / output の rank-0 を rank-1 に更新 ──────────
    print("[6/8] Fixing rank-0 entries in graph.input/output...")

    def _fix_rank0_type(vi, where: str):
        if not vi.type.HasField("tensor_type"):
            return False
        tt = vi.type.tensor_type
        if not tt.HasField("shape"):
            return False
        if len(tt.shape.dim) == 0:
            new_dim = tt.shape.dim.add()
            new_dim.dim_value = 1
            print(f"  {where}: {vi.name!r}  shape=[] -> [1]")
            return True
        return False

    fixed_vi  = sum(_fix_rank0_type(vi, "value_info") for vi in model.graph.value_info)
    fixed_in  = sum(_fix_rank0_type(vi, "input")      for vi in model.graph.input)
    fixed_out = sum(_fix_rank0_type(vi, "output")     for vi in model.graph.output)
    print(f"      fixed: value_info={fixed_vi}, input={fixed_in}, output={fixed_out}")

    # ─── Step 6: DFT inverse+onesided Sentis InferPartial バグを回避 ──────
    # 症状: Sentis の DFT.InferPartial が onesided ? N/2+1 : N を使うため、
    #   inverse=1, onesided=1, dft_length=16 → output_length=9 と誤推定する。
    #   正しくは output_length = dft_length = 16 (逆変換なので元の長さに戻る)。
    #   その結果 _fft_c2r の inferred shape = [A,C,9] になり、
    #   view_3=[1,1,16] との Mul で "broadcast dims must be equal or 1" が発生する。
    #
    # 修正方針: Hermitian 拡張 + DFT onesided=0 に変更
    #   1. DFT 入力 transpose_8: [A,C,9,2] (onesided spectrum, 9 bins)
    #   2. bins[1..7] を抽出 → 共役 (imag 符号反転) → 逆順 → [A,C,7,2]
    #   3. concat([transpose_8, reversed_conj]) = [A,C,16,2] (full Hermitian spectrum)
    #   4. DFT の入力を差し替え、onesided=0 に変更
    #   → InferPartial: output_length = dft_length = 16 ✓
    #   → Execute: full 16-bin IDFT ✓ (Hermitian input なので虚部≈0)
    print("[5.5/8] Fixing DFT inverse+onesided InferPartial bug (Hermitian extension)...")

    # ── Step 6 実装 ─────────────────────────────────────────────────────────
    dft_node_found = False
    for node in model.graph.node:
        if node.op_type == "DFT":
            # Check attributes
            has_inverse = any(a.name == "inverse" and int(a.i) == 1 for a in node.attribute)
            has_onesided = any(a.name == "onesided" and int(a.i) == 1 for a in node.attribute)
            if not (has_inverse and has_onesided):
                print(f"  [SKIP] DFT node does not have inverse=1 and onesided=1, skipping.")
                continue

            dft_node_found = True
            dft_input_name = node.input[0] if len(node.input) > 0 else ""
            print(f"  DFT node found: input={dft_input_name!r}, applying Hermitian extension...")

            # ── a) 定数ノード群を作成 ────────────────────────────────────────
            # 共役符号マスク: [1.0, -1.0] shape=[1,1,1,2]
            conj_sign_name = "__hift_dft_conj_sign__"
            conj_sign_tensor = helper.make_tensor(
                conj_sign_name, TensorProto.FLOAT, [1, 1, 1, 2], [1.0, -1.0])
            conj_sign_node = helper.make_node(
                "Constant", inputs=[], outputs=[conj_sign_name],
                name="const_hift_dft_conj_sign", value=conj_sign_tensor)

            # Slice1 用定数: bins[1..7] を抽出 (axis=2, start=1, end=8)
            s1_starts_name = "__hift_s1_starts__"
            s1_ends_name = "__hift_s1_ends__"
            s1_axes_name = "__hift_s1_axes__"
            s1_starts_node = helper.make_node("Constant", [], [s1_starts_name],
                name="const_hift_s1_starts",
                value=helper.make_tensor(s1_starts_name, TensorProto.INT64, [1], [1]))
            s1_ends_node = helper.make_node("Constant", [], [s1_ends_name],
                name="const_hift_s1_ends",
                value=helper.make_tensor(s1_ends_name, TensorProto.INT64, [1], [8]))
            s1_axes_node = helper.make_node("Constant", [], [s1_axes_name],
                name="const_hift_s1_axes",
                value=helper.make_tensor(s1_axes_name, TensorProto.INT64, [1], [2]))

            # Slice2 用定数: reversal (axis=2, start=6, end=-8, step=-1)
            s2_starts_name = "__hift_s2_starts__"
            s2_ends_name = "__hift_s2_ends__"
            s2_steps_name = "__hift_s2_steps__"
            s2_starts_node = helper.make_node("Constant", [], [s2_starts_name],
                name="const_hift_s2_starts",
                value=helper.make_tensor(s2_starts_name, TensorProto.INT64, [1], [6]))
            s2_ends_node = helper.make_node("Constant", [], [s2_ends_name],
                name="const_hift_s2_ends",
                value=helper.make_tensor(s2_ends_name, TensorProto.INT64, [1], [-8]))
            s2_steps_node = helper.make_node("Constant", [], [s2_steps_name],
                name="const_hift_s2_steps",
                value=helper.make_tensor(s2_steps_name, TensorProto.INT64, [1], [-1]))

            # ── b) Hermitian 拡張ノード群 ────────────────────────────────────
            # Slice: [A,C,9,2] → [A,C,7,2] (bins 1..7)
            conj_raw_name = "__hift_dft_conj_raw__"
            slice1_node = helper.make_node(
                "Slice",
                inputs=[dft_input_name, s1_starts_name, s1_ends_name, s1_axes_name],
                outputs=[conj_raw_name],
                name="hift_dft_slice_conj_raw")

            # Mul: conjugate by flipping imaginary part → [A,C,7,2]
            conj_name = "__hift_dft_conj__"
            conj_node = helper.make_node(
                "Mul",
                inputs=[conj_raw_name, conj_sign_name],
                outputs=[conj_name],
                name="hift_dft_conj")

            # Slice: reverse along axis 2 → [A,C,7,2] (bins 7..1 conjugated)
            conj_rev_name = "__hift_dft_conj_rev__"
            slice2_node = helper.make_node(
                "Slice",
                inputs=[conj_name, s2_starts_name, s2_ends_name, s1_axes_name, s2_steps_name],
                outputs=[conj_rev_name],
                name="hift_dft_slice_conj_rev")

            # Concat: [A,C,9,2] + [A,C,7,2] = [A,C,16,2] (full Hermitian spectrum)
            full_spectrum_name = "__hift_dft_full_spectrum__"
            concat_node = helper.make_node(
                "Concat",
                inputs=[dft_input_name, conj_rev_name],
                outputs=[full_spectrum_name],
                name="hift_dft_concat_full_spectrum",
                axis=2)

            # ── c) DFT ノードを書き換え ──────────────────────────────────────
            # input[0] を full_spectrum_name に差し替え
            node.input[0] = full_spectrum_name

            # onesided 属性を 0 に変更
            for a in node.attribute:
                if a.name == "onesided":
                    a.i = 0
                    print(f"  DFT.onesided: 1 → 0")

            # ── axis を input[2] として追加 ──────────────────────────────────
            # ONNX opset 17 では axis は attribute。Sentis converter は GetInput(2) で
            # axis を読むため、input[2] が存在しないと inputs[2]=-1 になり、
            # DFT.Execute の ctx.storage.GetInts(inputs[2])[0] で
            # IndexOutOfRangeException が発生する。
            # 修正: axis 属性値を Constant ノードとして入力に昇格する。
            dft_axis_val = 2  # default for hift (axis=2)
            for a in node.attribute:
                if a.name == "axis":
                    dft_axis_val = int(a.i)
            dft_axis_const_name = "__hift_dft_axis__"
            dft_axis_tensor = helper.make_tensor(
                dft_axis_const_name, TensorProto.INT64, [1], [dft_axis_val])
            dft_axis_node = helper.make_node(
                "Constant", inputs=[], outputs=[dft_axis_const_name],
                name="const_hift_dft_axis", value=dft_axis_tensor)

            # DFT node.input を [signal, dftLength, axis] に整える
            # input[1] = dftLength: 元のモデルに存在するならそのまま、なければ "" (省略)
            while len(node.input) < 2:
                node.input.append("")  # dftLength 省略 (実行時 signalTensor.shape[axis] を使用)
            if len(node.input) < 3:
                node.input.append(dft_axis_const_name)
            else:
                node.input[2] = dft_axis_const_name
            print(f"  DFT.axis attribute={dft_axis_val} → added as input[2]={dft_axis_const_name!r}")

            # ── d) 新ノードを DFT ノードの直前に挿入 (トポロジカル順序を保つ) ──
            # Constant ノードは依存なしなのでグラフ先頭でも良いが、
            # slice1/conj/slice2/concat は transpose_8 が確定した後に来る必要がある。
            # 最も安全な挿入位置 = DFT ノードの直前。
            const_nodes = [
                conj_sign_node,
                s1_starts_node, s1_ends_node, s1_axes_node,
                s2_starts_node, s2_ends_node, s2_steps_node,
                dft_axis_node,  # axis constant (opset 17 compat)
            ]
            compute_nodes = [slice1_node, conj_node, slice2_node, concat_node]

            existing_nodes = list(model.graph.node)
            del model.graph.node[:]

            # Constant ノードをグラフ先頭に追加（どこでも OK）
            model.graph.node.extend(const_nodes)

            # 残りのノードを DFT の直前に compute_nodes を挿入しながら追加
            for n in existing_nodes:
                if n is node:
                    model.graph.node.extend(compute_nodes)
                model.graph.node.append(n)
            print(f"  Inserted {len(const_nodes) + len(compute_nodes)} nodes for Hermitian extension.")
            print(f"  DFT input: {dft_input_name!r} (9 bins) → {full_spectrum_name!r} (16 bins)")
            print(f"  Fix: Sentis InferPartial will now see output_length = dft_length = 16 OK")

    if not dft_node_found:
        print("  [WARN] No DFT node with inverse=1 onesided=1 found — fix not applied.")

    # ─── Step 7: Clip ノードの欠落 min/max を ±inf 定数で補完 ───────────
    # 症状: "Compute shader (Clip): Property (Bptr) at kernel index (0) is not set"
    # 原因: opset 11+ の Clip は min/max がオプション入力。hift には min のみ or max のみ
    #       の Clip が存在し、Sentis は null をそのまま UseMax=false で dispatch するが、
    #       Unity の compute shader driver が全 kernel property のバインドを要求する
    #       → Bptr (max バッファ) が未設定で warning が出る。
    # 修正: 欠落している max → +inf、欠落している min → -inf を明示的に追加。
    #       ±inf にクリップするのは数学的に no-op なので精度への影響はゼロ。
    print("[6.5/8] Fixing Clip nodes with missing min/max inputs...")
    clip_inf_name    = "__clip_max_inf__"
    clip_neginf_name = "__clip_min_neginf__"

    # ±inf 初期化子を一度だけ追加
    def _has_init(m, name):
        return any(i.name == name for i in m.graph.initializer)

    if not _has_init(model, clip_inf_name):
        model.graph.initializer.append(
            numpy_helper.from_array(np.array(float("inf"), dtype=np.float32),
                                    name=clip_inf_name))
    if not _has_init(model, clip_neginf_name):
        model.graph.initializer.append(
            numpy_helper.from_array(np.array(float("-inf"), dtype=np.float32),
                                    name=clip_neginf_name))

    clip_fixed = 0
    for node in model.graph.node:
        if node.op_type != "Clip":
            continue
        # input[1] = min, input[2] = max
        while len(node.input) < 3:
            node.input.append("")
        changed = False
        if node.input[1] == "":    # missing min
            node.input[1] = clip_neginf_name
            changed = True
        if node.input[2] == "":    # missing max
            node.input[2] = clip_inf_name
            changed = True
        if changed:
            clip_fixed += 1
    print(f"      {clip_fixed} Clip node(s) had missing min/max filled with ±inf.")

    # ─── shape_inference はスキップ ──────────────────────────────────────
    import os
    if os.environ.get("HIFT_RUN_SHAPE_INFER") == "1":
        print("[6.5/8] Running shape inference (HIFT_RUN_SHAPE_INFER=1)...")
        try:
            model = onnx.shape_inference.infer_shapes(model)
        except Exception as e:
            print(f"  [WARN] shape inference failed (non-fatal): {e}")
    else:
        print("[6.5/8] Skipping shape inference (HIFT_RUN_SHAPE_INFER=1 で有効化)")

    # ─── 保存 ─────────────────────────────────────────────────────────────
    DST_ONNX.parent.mkdir(parents=True, exist_ok=True)
    print(f"[7/8] Saving: {DST_ONNX}")
    onnx.save(model, str(DST_ONNX))

    size_mb = DST_ONNX.stat().st_size / (1024 ** 2)
    print(f"[OK]  Done! {size_mb:.0f} MB  (v7)")
    print()
    print("次のステップ:")
    print("  1. Unity で Assets > Refresh (Ctrl+R)")
    print("  2. Assets/SentisSpike/Models/ に hift.fixed.fp32.onnx が")
    print("     ModelAsset として表示され broadcast エラーが消えることを確認")
    print("  3. SentisLoadTest の hift テストを実行")


if __name__ == "__main__":
    main()
