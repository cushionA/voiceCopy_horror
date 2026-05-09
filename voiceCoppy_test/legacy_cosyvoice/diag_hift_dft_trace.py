#!/usr/bin/env python3
"""
diag_hift_dft_trace.py — Trace transpose_8 (DFT input) and _fft_c2r (DFT output chain).
Determine the exact shape conflict and plan the fix.
"""
from pathlib import Path
import onnx
from onnx import numpy_helper, AttributeProto
import numpy as np

MODEL = (Path(__file__).resolve().parent.parent /
         "voice_Horror_Game" / "Assets" / "SentisSpike" / "Models" /
         "hift.fixed.fp32.onnx")

print(f"Loading {MODEL}...")
m = onnx.load(str(MODEL))

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

cache = {}

def get_attrs(node):
    attrs = {}
    for a in node.attribute:
        if a.type == AttributeProto.INT:
            attrs[a.name] = int(a.i)
        elif a.type == AttributeProto.INTS:
            attrs[a.name] = list(a.ints)
        elif a.type == AttributeProto.FLOAT:
            attrs[a.name] = float(a.f)
        elif a.type == AttributeProto.TENSOR:
            try:
                attrs[a.name] = numpy_helper.to_array(a.t)
            except Exception:
                pass
    return attrs

def eval_const(name, depth=0):
    if depth > 80:
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
            d   = eval_const(inp[0], depth+1) if len(inp) > 0 else None
            idx = eval_const(inp[1], depth+1) if len(inp) > 1 else None
            if d is not None and idx is not None:
                result = np.take(d, idx, axis=attrs.get("axis", 0))
        elif op == "Unsqueeze":
            x = eval_const(inp[0], depth+1) if len(inp) > 0 else None
            if x is not None:
                axes_v = eval_const(inp[1], depth+1) if len(inp) > 1 else None
                if axes_v is None:
                    aa = attrs.get("axes")
                    if aa:
                        axes_v = np.array(aa, dtype=np.int64)
                if axes_v is not None:
                    tmp = x
                    for a in sorted(int(ax) for ax in np.atleast_1d(axes_v)):
                        tmp = np.expand_dims(tmp, axis=a)
                    result = tmp
        elif op == "Squeeze":
            x = eval_const(inp[0], depth+1) if len(inp) > 0 else None
            if x is not None:
                axes_v = eval_const(inp[1], depth+1) if len(inp) > 1 else None
                if axes_v is None:
                    aa = attrs.get("axes")
                    if aa:
                        axes_v = np.array(aa, dtype=np.int64)
                if axes_v is not None:
                    result = np.squeeze(x, axis=tuple(int(a) % max(1, x.ndim) for a in np.atleast_1d(axes_v)))
                else:
                    result = np.squeeze(x)
        elif op == "Reshape":
            x = eval_const(inp[0], depth+1) if len(inp) > 0 else None
            s = eval_const(inp[1], depth+1) if len(inp) > 1 else None
            if x is not None and s is not None:
                result = x.reshape(s.astype(int))
        elif op == "Concat":
            parts = [eval_const(i, depth+1) for i in inp if i]
            if all(p is not None for p in parts):
                result = np.concatenate([np.atleast_1d(p) for p in parts], axis=attrs.get("axis", 0))
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
                dtype_map = {1: np.float32, 6: np.int32, 7: np.int64, 10: np.float16, 11: np.float64}
                if to in dtype_map:
                    result = x.astype(dtype_map[to])
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
                for ax, st, en, sp in zip(np.atleast_1d(axes), np.atleast_1d(start),
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
            return f"init shape={list(arr.shape)} val={arr.flatten()[:4].tolist()}"
        return "init (unreadable)"
    if name in input_shape_map:
        return f"graph.input dims={input_shape_map[name]}"
    if name in producer_map:
        return f"← {producer_map[name].op_type}"
    return "not found"

# ── 1. Evaluate Slice inputs for DFT chain ────────────────────────────────────
print("\n" + "="*70)
print("=== DFT Slice/Squeeze chain ===")
for node in m.graph.node:
    if node.op_type == "DFT":
        dft_out = node.output[0]
        print(f"DFT output: {dft_out!r}")
        print(f"DFT attributes: onesided={get_attrs(node).get('onesided')}, "
              f"inverse={get_attrs(node).get('inverse')}, "
              f"axis={get_attrs(node).get('axis')}")

        # Find Slice that uses DFT output
        for node2 in m.graph.node:
            if dft_out in node2.input and node2.op_type == "Slice":
                print(f"\nSlice node: {list(node2.input)} → {list(node2.output)}")
                inps = list(node2.input)
                for i, iname in enumerate(inps):
                    if not iname:
                        print(f"  input[{i}]: (empty)")
                        continue
                    v = eval_const(iname)
                    if v is not None:
                        print(f"  input[{i}] {iname!r} = {v.tolist()}  ({source_info(iname)})")
                    else:
                        print(f"  input[{i}] {iname!r} DYNAMIC  ({source_info(iname)})")

                slice_out = node2.output[0]
                # Find Squeeze that uses Slice output
                for node3 in m.graph.node:
                    if slice_out in node3.input and node3.op_type == "Squeeze":
                        print(f"\nSqueeze node: {list(node3.input)} → {list(node3.output)}")
                        for i, iname in enumerate(node3.input):
                            if iname:
                                v = eval_const(iname)
                                if v is not None:
                                    print(f"  input[{i}] {iname!r} = {v.tolist()}")
                                else:
                                    print(f"  input[{i}] {iname!r} DYNAMIC ({source_info(iname)})")

                        fft_c2r = node3.output[0]
                        print(f"\n_fft_c2r = {fft_c2r!r}")

                        # Find Mul
                        for node4 in m.graph.node:
                            if fft_c2r in node4.input and node4.op_type == "Mul":
                                print(f"Mul: {list(node4.input)} → {list(node4.output)}")
                                for i, iname in enumerate(node4.input):
                                    if iname:
                                        v = eval_const(iname)
                                        if v is not None:
                                            print(f"  input[{i}] {iname!r} = {v.tolist()}  shape={list(v.shape)}")
                                        else:
                                            print(f"  input[{i}] {iname!r} DYNAMIC ({source_info(iname)})")

# ── 2. Trace transpose_8 backwards ────────────────────────────────────────────
print("\n" + "="*70)
print("=== Tracing transpose_8 backwards ===")

def deep_trace_back(name, prefix="", depth=0, max_depth=10, seen=None):
    if seen is None:
        seen = set()
    if name in seen or depth > max_depth:
        return
    seen.add(name)

    v = eval_const(name)
    if v is not None:
        print(f"{prefix}{name!r} = CONST {v.tolist()} shape={list(v.shape)}")
        return

    if name in input_shape_map:
        print(f"{prefix}{name!r} = GRAPH.INPUT {input_shape_map[name]}")
        return

    if name in producer_map:
        node = producer_map[name]
        attrs = get_attrs(node)
        print(f"{prefix}{name!r} ← {node.op_type}(inp={list(node.input)}) attrs={attrs}")
        for sub in node.input:
            if sub:
                deep_trace_back(sub, prefix + "  ", depth + 1, max_depth, seen)
    else:
        print(f"{prefix}{name!r}: not found")

deep_trace_back("transpose_8", max_depth=8)

# ── 3. Check what Sentis ONNX importer maps DFT to ───────────────────────────
print("\n" + "="*70)
print("=== Verifying DFT node attributes in protobuf ===")
for node in m.graph.node:
    if node.op_type == "DFT":
        print(f"node name: {node.name!r}")
        print(f"opset_import (model-level):")
        for op in m.opset_import:
            print(f"  domain={op.domain!r}  version={op.version}")
        print(f"attribute protobuf dump:")
        for a in node.attribute:
            print(f"  name={a.name!r} type={a.type} i={a.i} f={a.f}")

# ── 4. Compute the exact shape conflict ───────────────────────────────────────
print("\n" + "="*70)
print("=== Shape conflict analysis ===")
print("""
ROOT CAUSE:
  DFT node: inverse=1, onesided=1, dft_length=16, axis=2

  Sentis DFT.InferPartial uses:
    outputXformSignalLength = onesided ? (N/2+1) : N = 9

  This is WRONG for inverse DFT. Correct output_length for
  inverse+onesided should be N=16 (the full time-domain signal).

  Consequence:
    DFT output val_886 → Sentis thinks [A, B, 9, 2]
                        → Actual runtime: [A, B, 16, 2]
    After Slice+Squeeze → _fft_c2r: Sentis thinks [A, B, 9]
                                   → Actual runtime: [A, B, 16]
    Mul with view_3=[1, 1, 16]:
      dim[-1]: 9 vs 16 → BOTH concrete, not equal, neither=1
      → DynamicTensorDim.Broadcast() → "ValueError: broadcast dims must be equal or 1"
""")

# ── 5. Check view_3 shape ─────────────────────────────────────────────────────
print("=== view_3 value ===")
v = eval_const("view_3")
if v is not None:
    print(f"view_3 = {v.tolist()}  shape={list(v.shape)}")
else:
    print(f"view_3 DYNAMIC ({source_info('view_3')})")

# Check view_4 producer
print("\n=== mul_2316 downstream (view_4, val_915) ===")
v915 = eval_const("val_915")
if v915 is not None:
    print(f"val_915 (Reshape shape for view_4) = {v915.tolist()}  shape={list(v915.shape)}")
else:
    print(f"val_915 DYNAMIC ({source_info('val_915')})")

# ── 6. Check if ConstantOfShape is connected to DFT input chain ──────────────
print("\n" + "="*70)
print("=== ConstantOfShape → DFT connection check ===")
cos_outs = []
for node in m.graph.node:
    if node.op_type == "ConstantOfShape":
        for o in node.output:
            if o:
                cos_outs.append(o)
                print(f"ConstantOfShape → {o!r}")
                # trace forward
                for node2 in m.graph.node:
                    if o in node2.input:
                        print(f"  used by: {node2.op_type}({list(node2.input)}) → {list(node2.output)}")

# ── 7. FIX PROPOSAL ───────────────────────────────────────────────────────────
print("\n" + "="*70)
print("""=== FIX PROPOSAL ===

Option A (Recommended): Change DFT onesided=1 → onesided=0
  AND expand the input from 9 to 16 complex bins using Hermitian extension.

  Steps:
  1. Find transpose_8 (DFT input)
  2. Insert a Hermitian extension node (Concat with conjugate of bins 7..1)
  3. Change DFT.onesided = 0

  Result:
  - DFT.InferPartial: output_length = dft_length = 16 ✓
  - DFT.Execute: uses full 16-bin complex spectrum ✓

Option B (Quick hack): Change DFT onesided=1 → onesided=0 without expanding input
  - InferPartial fix: output_length = 16 ✓
  - Execute: will process 9 complex bins as "full" 16-bin IDFT... may produce wrong audio
  - NOT recommended unless testing shows it doesn't matter

Option C: Insert Reshape node AFTER _fft_c2r to fix shape propagation
  - Reshape _fft_c2r from [..., 9] to [..., 16]
  - BUT: DFT actually outputs 16 at runtime, so we'd be reshaping wrong shapes
  - This could work IF the Slice+Squeeze chain doesn't strip the 16-sample dim

Let's examine which option is cleanest by checking transpose_8 rank/shape...
""")
