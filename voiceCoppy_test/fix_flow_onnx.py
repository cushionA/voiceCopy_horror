#!/usr/bin/env python3
"""
fix_flow_onnx.py — flow.decoder.estimator.fp32.onnx を Sentis 2.5 互換に修正
voice_horror Phase 3 fix v2

エラーと修正:
  1. ValueError: broadcast dims must be equal or 1  [v1 で修正済み: value_info 全削除]
  2. Object reference not set to an instance of an object  [v2 で修正]
     原因: CosyVoice3 DiT は LayerNormalization を bias=False で export。
           Sentis ONNXModelConverter は常に GetInput(2) を参照するため null -> NullRef。
     修正: scale (input[1]) と同 shape の zero bias initializer を追加し、
           全 45 LN ノードの input[2] に設定する。

Steps:
  Step 1: rank-0 initializer -> rank-1 (scalar_tensor_default, val_36 等 10個)
  Step 2: rank-0 index を使う Gather の直後に Squeeze 挿入
  Step 3: LayerNormalization の bias (input[2]) が欠落 -> zero bias を追加  ★ NEW
  Step 4: 全 value_info を除去 (2627件、Sentis InferPartial との shape 衝突を防ぐ)
  Step 5: graph.input/output の rank-0 を rank-1 に更新

NOTE (v1 からの訂正):
  ReduceSum axes=input -> axes=attribute 変換は削除。
  Sentis は opset >= 13 で ReduceSum の axes を input[1] から読む (attribute は無視)。
  変換後は input[1] が消えて axes=null になり別のエラーが発生するため、変換しない。

NOTE: 外部データ (.data ファイル) が onnx と同じディレクトリにある必要があります。
      load_external_data=False でグラフ構造のみ読み込み、保存時も external data は
      変更しません (onnx.save は初期値テンソルの参照を保持する)。

Usage:
    pip install onnx numpy
    cd voiceCoppy_test
    python fix_flow_onnx.py
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR   = REPO_ROOT / "voiceCoppy_test" / "onnx_export"
DST_DIR   = REPO_ROOT / "voice_Horror_Game" / "Assets" / "SentisSpike" / "Models"

SRC_ONNX  = SRC_DIR / "flow.decoder.estimator.fp32.onnx"
DST_ONNX  = DST_DIR / "flow.decoder.estimator.fp32.onnx"


def main():
    try:
        import onnx
        from onnx import helper, TensorProto, numpy_helper, AttributeProto
        import numpy as np
    except ImportError:
        print("[ERROR] onnx / numpy が見つかりません。  pip install onnx numpy  を実行してください。")
        sys.exit(1)

    if not SRC_ONNX.exists():
        print(f"[ERROR] 入力ファイルが見つかりません: {SRC_ONNX}")
        sys.exit(1)

    # external data は同じディレクトリにある .data ファイルを参照する
    # load_external_data=False でグラフ構造のみ読み込む (重みは変更しない)
    print(f"[1/6] Loading: {SRC_ONNX} (graph-only, external data preserved)")
    model = onnx.load(str(SRC_ONNX), load_external_data=False)

    opset_version = 18
    for op in model.opset_import:
        if op.domain in ("", "ai.onnx"):
            opset_version = op.version
            break
    print(f"      opset={opset_version}, nodes={len(model.graph.node)}, "
          f"init={len(model.graph.initializer)}, value_info={len(model.graph.value_info)}")

    use_tensor_axes = (opset_version >= 13)

    # ── Step 1: rank-0 initializer → rank-1 ─────────────────────────────────
    print("[2/6] Fixing rank-0 initializers...")
    rank0_init_names: set = set()
    fixed_init = 0
    for init in model.graph.initializer:
        if len(init.dims) == 0:
            rank0_init_names.add(init.name)
            del init.dims[:]
            init.dims.extend([1])
            fixed_init += 1
    print(f"      {fixed_init} rank-0 initializer(s) fixed. "
          f"Tracking: {sorted(rank0_init_names)[:8]}")

    # ── Step 2: Gather scalar-index 問題を修正 ──────────────────────────────
    # rank-0 → rank-1 にした initializer を index に使う Gather は
    # 出力 rank が +1 されてしまうので、直後に Squeeze を挿入する
    print("[3/6] Fixing Gather nodes with originally-scalar (rank-0) indices...")

    needed_gather_axes: set = set()
    for node in model.graph.node:
        if (node.op_type == "Gather"
                and len(node.input) > 1
                and node.input[1] in rank0_init_names):
            axis = 0
            for a in node.attribute:
                if a.name == "axis" and a.type == AttributeProto.INT:
                    axis = int(a.i)
            needed_gather_axes.add(axis)

    sg_axes_names: dict = {}
    sg_const_nodes = []
    for axis_val in sorted(needed_gather_axes):
        t_name = f"__fg_gather_axes_{axis_val}__"
        if use_tensor_axes:
            axes_t = helper.make_tensor(t_name, TensorProto.INT64, [1], [axis_val])
            sg_const_nodes.append(helper.make_node(
                "Constant", inputs=[], outputs=[t_name],
                name=f"const_fg_gather_axes_{axis_val}", value=axes_t
            ))
        sg_axes_names[axis_val] = t_name

    gather_squeeze_count = 0
    new_nodes_step2 = sg_const_nodes[:]

    for node in model.graph.node:
        if (node.op_type == "Gather"
                and len(node.input) > 1
                and node.input[1] in rank0_init_names):
            axis = 0
            for a in node.attribute:
                if a.name == "axis" and a.type == AttributeProto.INT:
                    axis = int(a.i)

            orig_outputs = list(node.output)
            for i, o in enumerate(orig_outputs):
                if o:
                    node.output[i] = o + "__fg_tmp__"

            new_nodes_step2.append(node)

            axes_const = sg_axes_names[axis]
            for orig_out in orig_outputs:
                if orig_out:
                    tmp_out = orig_out + "__fg_tmp__"
                    if use_tensor_axes:
                        sq = helper.make_node(
                            "Squeeze",
                            inputs=[tmp_out, axes_const],
                            outputs=[orig_out],
                            name=f"fix_fg_sq_{orig_out}"
                        )
                    else:
                        sq = helper.make_node(
                            "Squeeze",
                            inputs=[tmp_out],
                            outputs=[orig_out],
                            name=f"fix_fg_sq_{orig_out}",
                            axes=[axis]
                        )
                    new_nodes_step2.append(sq)
                    gather_squeeze_count += 1
                    print(f"      Gather out={orig_out!r}  axis={axis}  -> Squeeze inserted")
        else:
            new_nodes_step2.append(node)

    del model.graph.node[:]
    model.graph.node.extend(new_nodes_step2)
    print(f"      {gather_squeeze_count} Gather output(s) wrapped with Squeeze.")

    # ── Step 3: LayerNormalization の bias (input[2]) を追加 ─────────────────
    # CosyVoice3 DiT は bias=False で export しているため全 LN ノードに bias がない。
    # Sentis の ONNXModelConverter.OnNode:
    #   case "LayerNormalization":
    #     SetOutput(gm.LayerNormalization(GetInput(0), GetInput(1), GetInput(2), epsilon));
    # GetInput(2) が null -> gm.LayerNormalization の内部で NullReferenceException。
    # 修正: scale (input[1]) と同じ shape の zero bias initializer を追加し、
    #       全 LN ノードの input[2] に設定する。
    print("[4/6] Adding zero bias to LayerNormalization nodes (NullRef fix)...")

    LN_BIAS_NAME = "__ln_zero_bias__"

    # ── scale tensor (val_55) の形状を特定する ──────────────────────────────
    # 外部データ非ロードでも TensorProto.dims は .onnx 内に保存されているので読める。
    scale_shape = None

    for init in model.graph.initializer:
        if init.name == "val_55":
            scale_shape = list(init.dims)
            print(f"      val_55 dims from initializer: {scale_shape}")
            break

    # initializer に見つからない場合は value_info から探す (まだ削除前)
    if scale_shape is None:
        for vi in model.graph.value_info:
            if vi.name == "val_55":
                if (vi.type.HasField("tensor_type")
                        and vi.type.tensor_type.HasField("shape")):
                    scale_shape = [int(d.dim_value)
                                   for d in vi.type.tensor_type.shape.dim]
                    print(f"      val_55 dims from value_info: {scale_shape}")
                    break

    # それでも分からなければ全 LN ノードの scale 名から推測
    if scale_shape is None:
        ln_scale_names = set()
        for node in model.graph.node:
            if node.op_type == "LayerNormalization" and len(node.input) >= 2:
                ln_scale_names.add(node.input[1])
        for init in model.graph.initializer:
            if init.name in ln_scale_names and len(init.dims) > 0:
                scale_shape = list(init.dims)
                print(f"      Found LN scale {init.name!r} dims: {scale_shape}")
                break

    if scale_shape is None:
        # フォールバック: CosyVoice3 0.5B DiT の隠れ次元は 512
        scale_shape = [512]
        print(f"      [WARNING] scale shape を特定できません。フォールバック: {scale_shape}")

    # ── zero bias initializer を作成 ────────────────────────────────────────
    zero_bias_np = np.zeros(scale_shape, dtype=np.float32)
    zero_bias_tensor = numpy_helper.from_array(zero_bias_np, name=LN_BIAS_NAME)
    model.graph.initializer.append(zero_bias_tensor)
    print(f"      Created zero bias: name={LN_BIAS_NAME!r}  shape={scale_shape}")

    # ── 全 LayerNormalization ノードに bias を追加 ──────────────────────────
    ln_fixed = 0
    for node in model.graph.node:
        if node.op_type != "LayerNormalization":
            continue
        if len(node.input) < 3:
            # input[2] が存在しない → append
            node.input.append(LN_BIAS_NAME)
            ln_fixed += 1
        elif not node.input[2]:
            # input[2] が空文字 → 上書き
            node.input[2] = LN_BIAS_NAME
            ln_fixed += 1
        # else: すでに bias あり → スキップ

    print(f"      {ln_fixed} LayerNormalization node(s) given zero bias.")

    # ── Step 4: 全 value_info を除去 ────────────────────────────────────────
    # value_info の shape 宣言が Sentis の InferPartial と衝突する。
    # 全除去で Sentis に動的 rank 推論させる。
    print("[5/6] Stripping ALL intermediate value_info...")
    before = len(model.graph.value_info)
    del model.graph.value_info[:]
    print(f"      Removed {before} value_info entries.")

    # ── Step 5: graph.input / graph.output の rank-0 を rank-1 に更新 ────────
    print("[5.5/6] Fixing rank-0 in graph.input / graph.output...")

    def _fix_rank0(vi, tag):
        if not vi.type.HasField("tensor_type"):
            return False
        tt = vi.type.tensor_type
        if not tt.HasField("shape"):
            return False
        if len(tt.shape.dim) == 0:
            tt.shape.dim.add().dim_value = 1
            print(f"        {tag}: {vi.name!r} [] -> [1]")
            return True
        return False

    fixed_in  = sum(_fix_rank0(vi, "input")  for vi in model.graph.input)
    fixed_out = sum(_fix_rank0(vi, "output") for vi in model.graph.output)
    print(f"      fixed: input={fixed_in}, output={fixed_out}")

    # ── 保存 ─────────────────────────────────────────────────────────────────
    # 注意: external data (.data ファイル) は SRC_DIR にあるが、
    #       保存先 DST_DIR は別ディレクトリ。
    #       load_external_data=False のまま save すると .onnx のみ書き換わり、
    #       .data は SRC_DIR を参照したまま（相対パスで保存される）。
    #       DST_DIR に .data コピーが既にある (前回コピー済み) ことを前提とする。
    DST_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[6/6] Saving: {DST_ONNX}")
    onnx.save(model, str(DST_ONNX))

    size_kb = DST_ONNX.stat().st_size / 1024
    print(f"[OK]  Done! {size_kb:.0f} KB  (graph-only; .data file unchanged)")
    print()
    print("次のステップ:")
    print("  1. Unity で Assets > Refresh (Ctrl+R)")
    print("  2. Console で NullReferenceException エラーが消えることを確認")
    print("  3. 消えない場合: 残りエラーを調査 (別 LN ノードが bias 名で検索できないケース等)")


if __name__ == "__main__":
    main()
