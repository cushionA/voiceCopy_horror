#!/usr/bin/env python3
"""
diag_hift_expand_v2.py  — Trace Expand / ConstantOfShape / Greater nodes
in hift.fixed.fp32.onnx to find the broadcast error source.
"""
import sys
from pathlib import Path
import onnx
from onnx import numpy_helper
import numpy as np

MODEL = Path(__file__).resolve().parent.parent / "voice_Horror_Game" / "Assets" / "SentisSpike" / "Models" / "hift.fixed.fp32.onnx"
print(f"Loading {MODEL}...")
m = onnx.load(str(MODEL))

# ── helper maps ──────────────────────────────────────────────────────────────
init_map = {}
for init in m.graph.initializer:
    try:
        init_map[init.name] = numpy_helper.to_array(init)
    except Exception:
        init_map[init.name] = None

producer_map = {}
for node in m.graph.node:
    for out in node.output:
        if out:
            producer_map[out] = node

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

# ── constant evaluator ───────────────────────────────────────────────────────
cache = {}

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

def eval_const(name, depth=0):
    if depth > 60:
        return None
    if name in cache:
        return cache[name]
    if not name:
        cache[name] = None
        return None
    if name in init_map:
        cache[name] = init_map[name]
        return init_map[name]
    if name in input_shape_map:
        cache[name] = None
        return None
    if name not in producer_map:
        cache[name] = None
        return None

    node = producer_map[name]
    op = node.op_type
    inp = list(node.input)
    attrs = get_attrs(node)
    result = None

    try:
        if op == "Constant":
            v = attrs.get("value")
            if v is not None:
                result = v
        elif op == "Gather":
            d = eval_const(inp[0], depth + 1) if len(inp) > 0 else None
            idx = eval_const(inp[1], depth + 1) if len(inp) > 1 else None
            if d is not None and idx is not None:
                axis = attrs.get("axis", 0)
                result = np.take(d, idx, axis=axis)
        elif op == "Unsqueeze":
            x = eval_const(inp[0], depth + 1) if len(inp) > 0 else None
            if x is not None:
                axes_v = eval_const(inp[1], depth + 1) if len(inp) > 1 else None
                if axes_v is None:
                    axes_attr = attrs.get("axes")
                    if axes_attr is not None:
                        axes_v = np.array(axes_attr, dtype=np.int64)
                if axes_v is not None:
                    tmp = x
                    for a in sorted(int(ax) for ax in np.atleast_1d(axes_v)):
                        tmp = np.expand_dims(tmp, axis=a)
                    result = tmp
        elif op == "Squeeze":
            x = eval_const(inp[0], depth + 1) if len(inp) > 0 else None
            if x is not None:
                axes_v = eval_const(inp[1], depth + 1) if len(inp) > 1 else None
                if axes_v is None:
                    axes_attr = attrs.get("axes")
                    if axes_attr is not None:
                        axes_v = np.array(axes_attr, dtype=np.int64)
                if axes_v is not None:
                    axes_list = tuple(int(a) % max(1, x.ndim) for a in np.atleast_1d(axes_v))
                    result = np.squeeze(x, axis=axes_list)
                else:
                    result = np.squeeze(x)
        elif op == "Reshape":
            x = eval_const(inp[0], depth + 1) if len(inp) > 0 else None
            s = eval_const(inp[1], depth + 1) if len(inp) > 1 else None
            if x is not None and s is not None:
                result = x.reshape(s.astype(int))
        elif op == "Concat":
            axis = attrs.get("axis", 0)
            parts = [eval_const(i, depth + 1) for i in inp if i]
            if all(p is not None for p in parts):
                result = np.concatenate([np.atleast_1d(p) for p in parts], axis=axis)
        elif op in ("Add", "Sub", "Mul", "Div", "Pow"):
            a = eval_const(inp[0], depth + 1) if len(inp) > 0 else None
            b = eval_const(inp[1], depth + 1) if len(inp) > 1 else None
            if a is not None and b is not None:
                ops = {"Add": np.add, "Sub": np.subtract,
                       "Mul": np.multiply, "Div": np.divide, "Pow": np.power}
                result = ops[op](a, b)
        elif op == "Cast":
            x = eval_const(inp[0], depth + 1) if len(inp) > 0 else None
            if x is not None:
                to = attrs.get("to", 1)
                dtype_map = {1: np.float32, 6: np.int32, 7: np.int64,
                             10: np.float16, 11: np.float64}
                if to in dtype_map:
                    result = x.astype(dtype_map[to])
        elif op == "Slice":
            data = eval_const(inp[0], depth + 1) if len(inp) > 0 else None
            start = eval_const(inp[1], depth + 1) if len(inp) > 1 else None
            end = eval_const(inp[2], depth + 1) if len(inp) > 2 else None
            axes = eval_const(inp[3], depth + 1) if len(inp) > 3 else None
            steps = eval_const(inp[4], depth + 1) if len(inp) > 4 else None
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
    except Exception:
        pass

    cache[name] = result
    return result


def source_info(name):
    if name in init_map:
        arr = init_map[name]
        if arr is not None:
            return f"init shape={list(arr.shape)} dtype={arr.dtype}"
        return "init (unreadable)"
    if name in input_shape_map:
        return f"graph.input dims={input_shape_map[name]}"
    if name in producer_map:
        return f"← {producer_map[name].op_type}"
    return "not found"


def deep_trace(name, prefix="  ", max_depth=4, cur=0):
    if cur > max_depth:
        return
    v = eval_const(name)
    if v is not None:
        print(f"{prefix}{name!r} = {np.atleast_1d(v).tolist()} shape={list(np.atleast_1d(v).shape)}")
        return
    src = source_info(name)
    if name in producer_map:
        p = producer_map[name]
        print(f"{prefix}{name!r} ← {p.op_type}({list(p.input)})  [{src}] DYNAMIC")
        for sub in p.input:
            if sub:
                deep_trace(sub, prefix + "  ", max_depth, cur + 1)
    else:
        print(f"{prefix}{name!r}: {src}")


# ── Expand ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("=== Expand node ===")
for node in m.graph.node:
    if node.op_type == "Expand":
        inp_name = node.input[0]
        shape_name = node.input[1]
        out_name = node.output[0]
        print(f"out={out_name!r}")

        inp_v = eval_const(inp_name)
        if inp_v is not None:
            print(f"  INPUT {inp_name!r}: concrete shape={list(inp_v.shape)}, val[:8]={inp_v.flatten()[:8].tolist()}")
        else:
            print(f"  INPUT {inp_name!r}: DYNAMIC  [{source_info(inp_name)}]")

        shape_v = eval_const(shape_name)
        if shape_v is not None:
            print(f"  SHAPE {shape_name!r}: concrete value={shape_v.tolist()}")
            # Now check broadcast
            inp_shape = list(inp_v.shape) if inp_v is not None else None
            target = [int(x) for x in shape_v]
            if inp_shape is not None:
                n = max(len(inp_shape), len(target))
                pi = [1] * (n - len(inp_shape)) + inp_shape
                pt = [1] * (n - len(target)) + target
                errs = []
                for j, (a, b) in enumerate(zip(pi, pt)):
                    if isinstance(a, int) and isinstance(b, int) and a != b and a != 1 and b != 1:
                        errs.append(f"dim[{j}]: input={a} vs target={b}")
                if errs:
                    print(f"  *** BROADCAST MISMATCH: {errs} ***")
                else:
                    print(f"  Broadcast check OK: {inp_shape} → {target}")
        else:
            print(f"  SHAPE {shape_name!r}: DYNAMIC")
            deep_trace(shape_name, "    ", max_depth=5)


# ── ConstantOfShape ──────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("=== ConstantOfShape node ===")
for node in m.graph.node:
    if node.op_type == "ConstantOfShape":
        shape_name = node.input[0]
        out_name = node.output[0]
        print(f"out={out_name!r}")
        for a in node.attribute:
            if a.name == "value":
                try:
                    print(f"  fill value: {numpy_helper.to_array(a.t)}")
                except Exception:
                    pass
        sv = eval_const(shape_name)
        if sv is not None:
            print(f"  SHAPE {shape_name!r}: concrete={sv.tolist()} → output shape={sv.tolist()}")
        else:
            print(f"  SHAPE {shape_name!r}: DYNAMIC")
            deep_trace(shape_name, "    ", max_depth=5)

        # Who uses val_919?
        print(f"  Users of {out_name!r}:")
        for n2 in m.graph.node:
            if out_name in n2.input:
                print(f"    {n2.op_type}({list(n2.input)}) → {list(n2.output)}")


# ── Greater ──────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("=== Greater node ===")
for node in m.graph.node:
    if node.op_type == "Greater":
        a_name = node.input[0]
        b_name = node.input[1]
        out_name = node.output[0]
        print(f"out={out_name!r}")
        print(f"  A: {a_name!r}  [{source_info(a_name)}]")
        deep_trace(a_name, "    ", max_depth=4)
        print(f"  B: {b_name!r}  [{source_info(b_name)}]")
        bv = eval_const(b_name)
        if bv is not None:
            print(f"    value={bv.tolist()} shape={list(bv.shape)}")
        print(f"  User of {out_name!r}:")
        for n2 in m.graph.node:
            if out_name in n2.input:
                print(f"    {n2.op_type}({list(n2.input)}) → {list(n2.output)}")
