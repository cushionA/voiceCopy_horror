#!/usr/bin/env python3
"""
diag_hift_expand.py — Expand ノードと shape 計算チェーンをトレースして
"ValueError: broadcast dims must be equal or 1" の原因を特定する。

固定モデルと元モデルの両方を比較分析する。
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXED_MODEL = REPO_ROOT / "voice_Horror_Game" / "Assets" / "SentisSpike" / "Models" / "hift.fixed.fp32.onnx"
SRC_MODEL   = REPO_ROOT / "voiceCoppy_test" / "onnx_export" / "hift.fp32.onnx"

try:
    import onnx
    from onnx import numpy_helper
    import numpy as np
except ImportError:
    print("pip install onnx")
    sys.exit(1)


def analyze_model(path: Path, label: str):
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"  {path}")
    print(f"{'='*70}")

    m = onnx.load(str(path))

    # ── initializer map ──────────────────────────────────────────────────────
    init_map = {}
    for init in m.graph.initializer:
        try:
            init_map[init.name] = numpy_helper.to_array(init)
        except Exception:
            init_map[init.name] = None

    # ── graph.input shape map (non-initializer) ───────────────────────────
    input_shape_map = {}
    for inp in m.graph.input:
        if inp.name in init_map:
            continue
        if inp.type.HasField("tensor_type") and inp.type.tensor_type.HasField("shape"):
            dims = []
            for d in inp.type.tensor_type.shape.dim:
                if d.HasField("dim_value"):
                    dims.append(int(d.dim_value))
                else:
                    dims.append(d.dim_param or "?")
            input_shape_map[inp.name] = dims

    # ── producer map ─────────────────────────────────────────────────────────
    producer_map = {}
    for node in m.graph.node:
        for out in node.output:
            if out:
                producer_map[out] = node

    def get_attrs(node):
        attrs = {}
        for a in node.attribute:
            if a.type == onnx.AttributeProto.INT:
                attrs[a.name] = int(a.i)
            elif a.type == onnx.AttributeProto.INTS:
                attrs[a.name] = list(a.ints)
            elif a.type == onnx.AttributeProto.FLOAT:
                attrs[a.name] = float(a.f)
            elif a.type == onnx.AttributeProto.TENSOR:
                try:
                    attrs[a.name] = numpy_helper.to_array(a.t)
                except Exception:
                    pass
        return attrs

    # ── partial constant evaluator ────────────────────────────────────────────
    cache: dict = {}

    def eval_const(name: str, depth: int = 0):
        """テンソルを定数として評価できれば numpy array を返す。不可なら None。"""
        if depth > 50:
            return None
        if name in cache:
            return cache[name]
        if not name:
            cache[name] = None
            return None

        # initializer
        if name in init_map:
            v = init_map[name]
            cache[name] = v
            return v

        # graph input (dynamic)
        if name in input_shape_map:
            cache[name] = None
            return None

        if name not in producer_map:
            cache[name] = None
            return None

        node = producer_map[name]
        op   = node.op_type
        inp  = list(node.input)
        out  = list(node.output)
        attrs = get_attrs(node)

        result = None

        try:
            if op == "Constant":
                v = attrs.get("value")
                if v is not None:
                    result = v

            elif op == "Shape":
                # Can't evaluate without runtime shape
                pass

            elif op == "Gather":
                d   = eval_const(inp[0], depth+1) if len(inp) > 0 else None
                idx = eval_const(inp[1], depth+1) if len(inp) > 1 else None
                if d is not None and idx is not None:
                    axis = attrs.get("axis", 0)
                    result = np.take(d, idx, axis=axis)

            elif op == "Squeeze":
                x = eval_const(inp[0], depth+1) if len(inp) > 0 else None
                if x is not None:
                    axes_v = eval_const(inp[1], depth+1) if len(inp) > 1 else None
                    if axes_v is None:
                        axes_attr = attrs.get("axes")
                        if axes_attr is not None:
                            axes_v = np.array(axes_attr, dtype=np.int64)
                    if axes_v is not None:
                        axes_list = tuple(int(a) % (x.ndim + 1) for a in np.atleast_1d(axes_v))
                        result = np.squeeze(x, axis=axes_list)
                    else:
                        result = np.squeeze(x)

            elif op == "Unsqueeze":
                x = eval_const(inp[0], depth+1) if len(inp) > 0 else None
                if x is not None:
                    axes_v = eval_const(inp[1], depth+1) if len(inp) > 1 else None
                    if axes_v is None:
                        axes_attr = attrs.get("axes")
                        if axes_attr is not None:
                            axes_v = np.array(axes_attr, dtype=np.int64)
                    if axes_v is not None:
                        tmp = x
                        for a in sorted(int(ax) for ax in np.atleast_1d(axes_v)):
                            tmp = np.expand_dims(tmp, axis=a)
                        result = tmp

            elif op == "Reshape":
                x = eval_const(inp[0], depth+1) if len(inp) > 0 else None
                s = eval_const(inp[1], depth+1) if len(inp) > 1 else None
                if x is not None and s is not None:
                    result = x.reshape(s.astype(int))

            elif op == "Concat":
                axis = attrs.get("axis", 0)
                parts = [eval_const(i, depth+1) for i in inp if i]
                if all(p is not None for p in parts):
                    result = np.concatenate([np.atleast_1d(p) for p in parts], axis=axis)

            elif op in ("Add", "Sub", "Mul", "Div", "Pow"):
                a = eval_const(inp[0], depth+1) if len(inp) > 0 else None
                b = eval_const(inp[1], depth+1) if len(inp) > 1 else None
                if a is not None and b is not None:
                    ops = {"Add": np.add, "Sub": np.subtract,
                           "Mul": np.multiply, "Div": np.divide, "Pow": np.power}
                    result = ops[op](a, b)

            elif op == "Cast":
                x = eval_const(inp[0], depth+1) if len(inp) > 0 else None
                if x is not None:
                    to = attrs.get("to", 1)
                    dtype_map = {1: np.float32, 6: np.int32, 7: np.int64,
                                 10: np.float16, 11: np.float64}
                    if to in dtype_map:
                        result = x.astype(dtype_map[to])

            elif op == "Expand":
                # Expand 自体は評価しない（今回のデバッグ対象）
                pass

            elif op == "Slice":
                data  = eval_const(inp[0], depth+1) if len(inp) > 0 else None
                start = eval_const(inp[1], depth+1) if len(inp) > 1 else None
                end   = eval_const(inp[2], depth+1) if len(inp) > 2 else None
                axes  = eval_const(inp[3], depth+1) if len(inp) > 3 else None
                steps = eval_const(inp[4], depth+1) if len(inp) > 4 else None
                if data is not None and start is not None and end is not None:
                    if axes is None:
                        axes = np.arange(data.ndim, dtype=np.int64)
                    if steps is None:
                        steps = np.ones(len(np.atleast_1d(axes)), dtype=np.int64)
                    slices = [slice(None)] * data.ndim
                    for ax, st, en, sp in zip(
                            np.atleast_1d(axes), np.atleast_1d(start),
                            np.atleast_1d(end), np.atleast_1d(steps)):
                        slices[int(ax)] = slice(int(st), int(en), int(sp))
                    result = data[tuple(slices)]

        except Exception as e:
            pass  # 評価失敗は None を返す

        cache[name] = result
        return result

    def shape_info(name: str) -> str:
        if name in init_map:
            arr = init_map[name]
            return f"init shape={list(arr.shape) if arr is not None else '?'}"
        if name in input_shape_map:
            return f"graph.input dims={input_shape_map[name]}"
        if name in producer_map:
            return f"produced by {producer_map[name].op_type}"
        return "not found"

    # ── Expand ノード分析 ───────────────────────────────────────────────────
    expand_nodes = [n for n in m.graph.node if n.op_type == "Expand"]
    print(f"\n### Expand nodes: {len(expand_nodes)}")

    for i, node in enumerate(expand_nodes):
        inp_name   = node.input[0] if len(node.input) > 0 else ""
        shape_name = node.input[1] if len(node.input) > 1 else ""
        out_name   = node.output[0] if len(node.output) > 0 else ""

        print(f"\n  [Expand #{i+1}]  out={out_name!r}")
        print(f"    input tensor: {inp_name!r} → {shape_info(inp_name)}")

        # input tensor の具体 shape
        inp_concrete_shape = None
        if inp_name in init_map and init_map[inp_name] is not None:
            inp_concrete_shape = list(init_map[inp_name].shape)
            print(f"    input shape (concrete): {inp_concrete_shape}")
        elif inp_name in input_shape_map:
            print(f"    input shape (graph.input): {input_shape_map[inp_name]}")
        else:
            inp_val = eval_const(inp_name)
            if inp_val is not None:
                inp_concrete_shape = list(inp_val.shape)
                print(f"    input shape (evaluated): {inp_concrete_shape}")
            else:
                print(f"    input shape: DYNAMIC / not determinable statically")

        # shape tensor の評価
        shape_val = eval_const(shape_name)
        if shape_val is not None:
            shape_list = [int(x) for x in np.atleast_1d(shape_val)]
            print(f"    target shape (evaluated): {shape_list}")

            if inp_concrete_shape is not None:
                n = max(len(inp_concrete_shape), len(shape_list))
                pi = [1] * (n - len(inp_concrete_shape)) + inp_concrete_shape
                ps = [1] * (n - len(shape_list)) + shape_list
                errors = []
                for j, (a, b) in enumerate(zip(pi, ps)):
                    if isinstance(a, int) and isinstance(b, int):
                        if a != b and a != 1 and b != 1:
                            errors.append(f"dim[{j}]: inp={a} vs target={b}")
                if errors:
                    print(f"    *** BROADCAST MISMATCH: {errors} ***")
                else:
                    print(f"    Broadcast check: OK  ({inp_concrete_shape} → {shape_list})")
        else:
            print(f"    target shape: DYNAMIC (cannot evaluate statically)")

            # 2 段階トレース
            if shape_name in producer_map:
                p = producer_map[shape_name]
                print(f"    chain: {shape_name!r} ← {p.op_type}(inp={list(p.input)})")
                for sub in p.input:
                    if not sub:
                        continue
                    sub_val = eval_const(sub)
                    if sub_val is not None:
                        print(f"      {sub!r} = {sub_val} (shape={list(np.atleast_1d(sub_val).shape)})")
                    elif sub in producer_map:
                        p2 = producer_map[sub]
                        print(f"      {sub!r} ← {p2.op_type}({list(p2.input)}) [DYNAMIC]")
                    else:
                        print(f"      {sub!r} → {shape_info(sub)}")

    # ── CumSum axis チェック ─────────────────────────────────────────────────
    cumsum_nodes = [n for n in m.graph.node if n.op_type == "CumSum"]
    print(f"\n### CumSum nodes: {len(cumsum_nodes)}")
    for node in cumsum_nodes:
        data_name = node.input[0] if len(node.input) > 0 else ""
        axis_name = node.input[1] if len(node.input) > 1 else ""
        print(f"  CumSum: axis_tensor={axis_name!r}  {shape_info(axis_name)}")
        ax_val = eval_const(axis_name)
        if ax_val is not None:
            rank = np.atleast_1d(ax_val).ndim if ax_val.ndim > 0 else 0
            rank_label = "rank-0 scalar OK" if ax_val.ndim == 0 else "rank-1 [1] - Sentis may reject"
            print(f"    axis value: {ax_val},  actual rank: {ax_val.ndim}  ({rank_label})")

    # ── rank-0 initializer 使用箇所サマリー (val_86 focus) ───────────────────
    print(f"\n### val_86 usage (originally rank-0 scalar=1):")
    for node in m.graph.node:
        for idx, inp_name in enumerate(node.input):
            if inp_name == "val_86" or inp_name == "val_86__sg_tmp__":
                out_names = list(node.output)
                print(f"  op={node.op_type}, inp_slot={idx}, out={out_names}")
                if node.op_type == "Gather":
                    attrs = get_attrs(node)
                    print(f"    axis={attrs.get('axis', 0)}")


# ── main ──────────────────────────────────────────────────────────────────────
print("Loading models...")

if FIXED_MODEL.exists():
    analyze_model(FIXED_MODEL, "FIXED model (hift.fixed.fp32.onnx)")
else:
    print(f"FIXED model not found: {FIXED_MODEL}")

if SRC_MODEL.exists():
    analyze_model(SRC_MODEL, "SOURCE model (hift.fp32.onnx)")
else:
    print(f"SOURCE model not found: {SRC_MODEL}")
