#!/usr/bin/env python3
"""
diag_hift_broadcast3.py — STFT/DFT onesided 値を正しく読み取り、
broadcast エラーの根本原因を特定する。

fix: INT 属性は a.type==2 (AttributeProto.INT) で読む
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

# ── helper maps ───────────────────────────────────────────────────────────────
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

print(f"\ngraph.input shapes:")
for name, dims in input_shape_map.items():
    print(f"  {name!r}: {dims}")

# ── constant evaluator (reused) ───────────────────────────────────────────────
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
            d   = eval_const(inp[0], depth+1) if len(inp) > 0 else None
            idx = eval_const(inp[1], depth+1) if len(inp) > 1 else None
            if d is not None and idx is not None:
                axis = attrs.get("axis", 0)
                result = np.take(d, idx, axis=axis)
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
        elif op == "Squeeze":
            x = eval_const(inp[0], depth+1) if len(inp) > 0 else None
            if x is not None:
                axes_v = eval_const(inp[1], depth+1) if len(inp) > 1 else None
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
    except Exception:
        pass

    cache[name] = result
    return result


# ── 1. STFT and DFT — read all attributes correctly ──────────────────────────
print("\n" + "="*70)
print("=== STFT node ===")
for node in m.graph.node:
    if node.op_type == "STFT":
        attrs = get_attrs(node)
        print(f"  name={node.name!r}")
        print(f"  inputs: {list(node.input)}")
        print(f"  outputs: {list(node.output)}")
        print(f"  attributes (all):")
        for a in node.attribute:
            type_names = {
                AttributeProto.FLOAT: "FLOAT",
                AttributeProto.INT: "INT",
                AttributeProto.STRING: "STRING",
                AttributeProto.TENSOR: "TENSOR",
                AttributeProto.FLOATS: "FLOATS",
                AttributeProto.INTS: "INTS",
            }
            tname = type_names.get(a.type, f"type={a.type}")
            if a.type == AttributeProto.INT:
                print(f"    {a.name} = {int(a.i)}  ({tname})")
            elif a.type == AttributeProto.INTS:
                print(f"    {a.name} = {list(a.ints)}  ({tname})")
            elif a.type == AttributeProto.FLOAT:
                print(f"    {a.name} = {a.f}  ({tname})")
            elif a.type == AttributeProto.STRING:
                print(f"    {a.name} = {a.s}  ({tname})")
            else:
                print(f"    {a.name}  ({tname})")
        # evaluate inputs
        for i, inp_name in enumerate(node.input):
            if inp_name:
                v = eval_const(inp_name)
                if v is not None:
                    print(f"  input[{i}] {inp_name!r} = {v.tolist()}")
                else:
                    if inp_name in input_shape_map:
                        print(f"  input[{i}] {inp_name!r} = DYNAMIC (graph.input {input_shape_map[inp_name]})")
                    elif inp_name in producer_map:
                        print(f"  input[{i}] {inp_name!r} = DYNAMIC (← {producer_map[inp_name].op_type})")
                    else:
                        print(f"  input[{i}] {inp_name!r} = not found")

print("\n" + "="*70)
print("=== DFT node ===")
for node in m.graph.node:
    if node.op_type == "DFT":
        attrs = get_attrs(node)
        print(f"  name={node.name!r}")
        print(f"  inputs: {list(node.input)}")
        print(f"  outputs: {list(node.output)}")
        print(f"  attributes (all):")
        for a in node.attribute:
            type_names = {
                AttributeProto.FLOAT: "FLOAT",
                AttributeProto.INT: "INT",
                AttributeProto.STRING: "STRING",
                AttributeProto.TENSOR: "TENSOR",
                AttributeProto.FLOATS: "FLOATS",
                AttributeProto.INTS: "INTS",
            }
            tname = type_names.get(a.type, f"type={a.type}")
            if a.type == AttributeProto.INT:
                print(f"    {a.name} = {int(a.i)}  ({tname})")
            elif a.type == AttributeProto.INTS:
                print(f"    {a.name} = {list(a.ints)}  ({tname})")
            elif a.type == AttributeProto.FLOAT:
                print(f"    {a.name} = {a.f}  ({tname})")
            else:
                print(f"    {a.name}  (type={a.type})")
        # evaluate inputs
        for i, inp_name in enumerate(node.input):
            if inp_name:
                v = eval_const(inp_name)
                if v is not None:
                    print(f"  input[{i}] {inp_name!r} = {v.tolist()}")
                else:
                    if inp_name in input_shape_map:
                        print(f"  input[{i}] {inp_name!r} = DYNAMIC (graph.input {input_shape_map[inp_name]})")
                    elif inp_name in producer_map:
                        print(f"  input[{i}] {inp_name!r} = DYNAMIC (← {producer_map[inp_name].op_type})")

# ── 2. Simulate InferPartial for STFT and DFT ────────────────────────────────
print("\n" + "="*70)
print("=== STFT output shape simulation ===")
for node in m.graph.node:
    if node.op_type == "STFT":
        attrs = get_attrs(node)
        onesided = attrs.get("onesided", 1)  # default=1 per ONNX spec

        # Get frameLength and frameStep from inputs
        # STFT inputs: [signal, frameStep, window, frameLength]
        inps = list(node.input)
        frame_step_v = eval_const(inps[1]) if len(inps) > 1 and inps[1] else None
        window_v = eval_const(inps[2]) if len(inps) > 2 and inps[2] else None
        frame_length_v = eval_const(inps[3]) if len(inps) > 3 and inps[3] else None

        frame_step = int(frame_step_v.flat[0]) if frame_step_v is not None else None
        frame_length = int(frame_length_v.flat[0]) if frame_length_v is not None else (len(window_v) if window_v is not None else None)

        print(f"  onesided={onesided}")
        print(f"  frame_step={frame_step}")
        print(f"  frame_length={frame_length}")

        if frame_length is not None:
            freq_bins = (frame_length // 2 + 1) if onesided else frame_length
            print(f"  freq_bins = {freq_bins}  ({'onesided' if onesided else 'twosided'})")
            print(f"  output shape = [1, T_stft, {freq_bins}, 2]")

        print(f"  output tensor: {list(node.output)}")

print("\n" + "="*70)
print("=== DFT output shape simulation ===")
for node in m.graph.node:
    if node.op_type == "DFT":
        attrs = get_attrs(node)
        onesided = attrs.get("onesided", 0)  # default=0 per ONNX spec
        inverse = attrs.get("inverse", 0)
        axis = attrs.get("axis", None)  # opset 17+: attribute

        inps = list(node.input)
        dft_length_v = eval_const(inps[1]) if len(inps) > 1 and inps[1] else None
        axis_v = eval_const(inps[2]) if len(inps) > 2 and inps[2] else None  # opset 17: tensor input

        dft_length = int(dft_length_v.flat[0]) if dft_length_v is not None else None

        print(f"  onesided={onesided}")
        print(f"  inverse={inverse}")
        print(f"  axis (attr)={axis}")
        if axis_v is not None:
            print(f"  axis (input tensor)={axis_v.tolist()}")

        if dft_length is not None:
            output_len = (dft_length // 2 + 1) if onesided else dft_length
            print(f"  dft_length={dft_length}")
            print(f"  output_xform_len = {output_len}  ({'onesided' if onesided else 'twosided'})")

        print(f"  output tensor: {list(node.output)}")

# ── 3. Trace who uses STFT and DFT outputs ───────────────────────────────────
print("\n" + "="*70)
print("=== Users of STFT/DFT outputs ===")

stft_outs = set()
dft_outs = set()
for node in m.graph.node:
    if node.op_type == "STFT":
        stft_outs.update(o for o in node.output if o)
    if node.op_type == "DFT":
        dft_outs.update(o for o in node.output if o)

def trace_tensor_users(tensor_name, label, depth=0, seen=None):
    if seen is None:
        seen = set()
    if tensor_name in seen or depth > 6:
        return
    seen.add(tensor_name)
    for node in m.graph.node:
        if tensor_name in node.input:
            out = list(node.output)
            attrs = get_attrs(node)
            print(f"  {'  '*depth}{label!r} → {node.op_type}({list(node.input)}) → {out}")
            for o in out:
                if o:
                    trace_tensor_users(o, o, depth+1, seen)

for sout in sorted(stft_outs):
    print(f"\nSTFT output {sout!r}:")
    trace_tensor_users(sout, sout)

for dout in sorted(dft_outs):
    print(f"\nDFT output {dout!r}:")
    trace_tensor_users(dout, dout)

# ── 4. Full broadcast simulation over ALL binary-element nodes ────────────────
print("\n" + "="*70)
print("=== Full broadcast simulation (concrete dims only) ===")

# We need a shape_map that tracks concrete dimensions as we propagate
# Key insight: speech_feat has dims [1, 80, T_mel] where 1 and 80 are concrete

# Represent shape as list of int | None
# None = symbolic/unknown, int = concrete

class Dim:
    """A dimension that might be concrete or dynamic."""
    def __init__(self, v):
        self.v = v  # int or None
    def __repr__(self):
        return str(self.v) if self.v is not None else "?"
    def broadcast(self, other):
        if self.v == 1:
            return Dim(other.v)
        if other.v == 1:
            return Dim(self.v)
        if self.v == other.v:
            return Dim(self.v)
        if self.v is None or other.v is None:
            return Dim(None)
        # CONFLICT!
        return Dim(f"CONFLICT({self.v},{other.v})")
    def is_conflict(self):
        return isinstance(self.v, str) and "CONFLICT" in self.v

class Shape:
    def __init__(self, dims):
        """dims: list of int|None|str"""
        self.dims = [Dim(d) if not isinstance(d, Dim) else d for d in dims]
        self.rank = len(dims) if dims is not None else None
    def __repr__(self):
        if self.dims is None:
            return "DYNAMIC_RANK"
        return "[" + ", ".join(str(d) for d in self.dims) + "]"
    def broadcast(self, other):
        if self.rank is None or other.rank is None:
            return Shape(None)
        n = max(self.rank, other.rank)
        a = [Dim(1)] * (n - self.rank) + self.dims
        b = [Dim(1)] * (n - other.rank) + other.dims
        result = []
        conflicts = []
        for i, (da, db) in enumerate(zip(a, b)):
            br = da.broadcast(db)
            result.append(br)
            if br.is_conflict():
                conflicts.append(f"dim[{i}]: {da} vs {db}")
        if conflicts:
            print(f"  *** BROADCAST CONFLICT: {conflicts} ***")
        return Shape(result)

shape_map = {}

# Initialize from graph.input
for inp in m.graph.input:
    if inp.name in init_map:
        arr = init_map[inp.name]
        if arr is not None:
            shape_map[inp.name] = Shape(list(arr.shape))
        continue
    if inp.type.HasField("tensor_type") and inp.type.tensor_type.HasField("shape"):
        dims = []
        for d in inp.type.tensor_type.shape.dim:
            if d.HasField("dim_value"):
                dims.append(int(d.dim_value))
            else:
                dims.append(None)  # symbolic
        shape_map[inp.name] = Shape(dims)

# Initialize from initializers
for init in m.graph.initializer:
    arr = init_map.get(init.name)
    if arr is not None:
        shape_map[init.name] = Shape(list(arr.shape))

STFT_out_shape = None
DFT_out_shape = None

conflict_count = 0

for node in m.graph.node:
    op = node.op_type
    inps = list(node.input)
    outs = list(node.output)
    attrs = get_attrs(node)

    def get_shape(name):
        if not name:
            return None
        if name in shape_map:
            return shape_map[name]
        return None

    def set_shape(name, shape):
        if name:
            shape_map[name] = shape

    def broadcast_binary(a_name, b_name, out_name):
        global conflict_count
        sa = get_shape(a_name)
        sb = get_shape(b_name)
        if sa is None or sb is None:
            return
        result = sa.broadcast(sb)
        # Check conflicts
        for d in result.dims:
            if d.is_conflict():
                conflict_count += 1
                print(f"  CONFLICT in {op} (out={out_name!r}): {sa} ⊗ {sb} → {result}")
                print(f"    a from: {a_name!r}")
                print(f"    b from: {b_name!r}")
                break
        set_shape(out_name, result)

    if op in ("Add", "Sub", "Mul", "Div", "Pow"):
        if len(inps) >= 2 and len(outs) >= 1:
            broadcast_binary(inps[0], inps[1], outs[0])

    elif op == "STFT":
        # inputs: signal, frameStep, window, frameLength
        onesided = attrs.get("onesided", 1)
        window_v = eval_const(inps[2]) if len(inps) > 2 and inps[2] else None
        frame_length_v = eval_const(inps[3]) if len(inps) > 3 and inps[3] else None
        frame_step_v = eval_const(inps[1]) if len(inps) > 1 and inps[1] else None
        frame_length = int(frame_length_v.flat[0]) if frame_length_v is not None else (len(window_v) if window_v is not None else None)
        frame_step = int(frame_step_v.flat[0]) if frame_step_v is not None else None
        freq_bins = (frame_length // 2 + 1) if onesided and frame_length else frame_length
        sig_shape = get_shape(inps[0]) if inps else None
        if sig_shape and frame_step and freq_bins:
            # signal is [batch, signal_len, 1] or [batch, signal_len]
            # output is [batch, frames, freq_bins, 2]
            batch = sig_shape.dims[0] if sig_shape.rank >= 1 else Dim(None)
            # frames is dynamic
            s = Shape([batch, Dim(None), Dim(freq_bins), Dim(2)])
            set_shape(outs[0], s)
            STFT_out_shape = s
            print(f"  STFT output {outs[0]!r}: {s}  (onesided={onesided}, freq_bins={freq_bins})")
        else:
            set_shape(outs[0], Shape([None, None, freq_bins, 2]))
            print(f"  STFT output {outs[0]!r}: [?, ?, {freq_bins}, 2]  (onesided={onesided})")

    elif op == "DFT":
        onesided = attrs.get("onesided", 0)
        dft_length_v = eval_const(inps[1]) if len(inps) > 1 and inps[1] else None
        dft_length = int(dft_length_v.flat[0]) if dft_length_v is not None else None
        output_len = (dft_length // 2 + 1) if onesided and dft_length else dft_length
        in_shape = get_shape(inps[0]) if inps else None
        if in_shape and in_shape.rank:
            s = Shape(list(in_shape.dims))
            # axis = -2 by default in Sentis InferPartial
            axis_val = attrs.get("axis", None)
            if axis_val is not None and output_len is not None:
                ax = axis_val if axis_val >= 0 else in_shape.rank + axis_val
                s.dims[ax] = Dim(output_len)
            else:
                # default axis = -2
                if output_len is not None and in_shape.rank >= 2:
                    s.dims[-2] = Dim(output_len)
            # last dim = 2 always
            if in_shape.rank >= 1:
                s.dims[-1] = Dim(2)
            set_shape(outs[0], s)
            DFT_out_shape = s
            print(f"  DFT output {outs[0]!r}: {s}  (onesided={onesided}, output_len={output_len})")
        else:
            print(f"  DFT: input shape unknown, cannot determine output")

    elif op == "Transpose":
        perm = attrs.get("perm", None)
        in_shape = get_shape(inps[0]) if inps else None
        if in_shape and perm and in_shape.rank == len(perm):
            s = Shape([in_shape.dims[p] for p in perm])
        elif in_shape:
            s = Shape(list(reversed(in_shape.dims)))
        else:
            s = None
        if s:
            set_shape(outs[0], s)

    elif op == "Reshape":
        shape_v = eval_const(inps[1]) if len(inps) > 1 and inps[1] else None
        if shape_v is not None:
            new_shape = []
            in_shape = get_shape(inps[0]) if inps else None
            in_total = None
            if in_shape and all(d.v is not None for d in in_shape.dims):
                in_total = 1
                for d in in_shape.dims:
                    in_total *= d.v
            for sv in shape_v.astype(int).tolist():
                if sv == -1:
                    if in_total is not None:
                        known = 1
                        unknowns = [s for s in shape_v.astype(int).tolist() if s != -1]
                        for u in unknowns:
                            known *= u
                        new_shape.append(in_total // known if known != 0 else None)
                    else:
                        new_shape.append(None)
                elif sv == 0:
                    # keep input dim
                    idx = len(new_shape)
                    if in_shape and idx < in_shape.rank:
                        new_shape.append(in_shape.dims[idx].v)
                    else:
                        new_shape.append(None)
                else:
                    new_shape.append(sv)
            set_shape(outs[0], Shape(new_shape))
        else:
            # dynamic reshape
            pass

    elif op == "Concat":
        axis = attrs.get("axis", 0)
        shapes = [get_shape(i) for i in inps if i]
        if shapes and all(s is not None for s in shapes):
            first = shapes[0]
            if all(s.rank == first.rank for s in shapes):
                new_dims = []
                for ax_i in range(first.rank):
                    if ax_i == axis:
                        # sum over concat axis
                        total = 0
                        dynamic = False
                        for s in shapes:
                            if s.dims[ax_i].v is None:
                                dynamic = True
                                break
                            total += s.dims[ax_i].v
                        new_dims.append(None if dynamic else total)
                    else:
                        # should be same
                        new_dims.append(first.dims[ax_i].v)
                set_shape(outs[0], Shape(new_dims))

    elif op == "Squeeze":
        in_shape = get_shape(inps[0]) if inps else None
        axes_v = eval_const(inps[1]) if len(inps) > 1 and inps[1] else None
        if axes_v is None:
            axes_attr = attrs.get("axes")
            if axes_attr:
                axes_v = np.array(axes_attr)
        if in_shape and axes_v is not None:
            axes_list = sorted(int(a) % max(1, in_shape.rank) for a in np.atleast_1d(axes_v))
            new_dims = [d for i, d in enumerate(in_shape.dims) if i not in axes_list]
            set_shape(outs[0], Shape(new_dims))
        elif in_shape:
            set_shape(outs[0], Shape([None]*max(0, in_shape.rank - 1)))

    elif op == "Unsqueeze":
        in_shape = get_shape(inps[0]) if inps else None
        axes_v = eval_const(inps[1]) if len(inps) > 1 and inps[1] else None
        if axes_v is None:
            axes_attr = attrs.get("axes")
            if axes_attr:
                axes_v = np.array(axes_attr)
        if in_shape and axes_v is not None:
            r_out = in_shape.rank + len(np.atleast_1d(axes_v))
            new_dims = list(in_shape.dims)
            for ax in sorted(int(a) % (r_out) for a in np.atleast_1d(axes_v)):
                new_dims.insert(ax, Dim(1))
            set_shape(outs[0], Shape(new_dims[:r_out]))

    elif op in ("Relu", "Elu", "LeakyRelu", "Tanh", "Sigmoid", "Exp", "Log",
                "Abs", "Floor", "Ceil", "Round", "Sqrt", "Neg", "Mish", "Sin", "Cos"):
        in_shape = get_shape(inps[0]) if inps else None
        if in_shape:
            set_shape(outs[0], in_shape)

    elif op == "Slice":
        in_shape = get_shape(inps[0]) if inps else None
        if in_shape:
            set_shape(outs[0], Shape([None]*in_shape.rank))

    elif op in ("Conv", "ConvTranspose"):
        in_shape = get_shape(inps[0]) if inps else None
        if in_shape:
            set_shape(outs[0], Shape([None]*in_shape.rank))

    elif op == "ReduceL2":
        in_shape = get_shape(inps[0]) if inps else None
        axes_v = eval_const(inps[1]) if len(inps) > 1 and inps[1] else None
        keepdims = attrs.get("keepdims", 1)
        if in_shape and axes_v is not None:
            axes_list = [int(a) % in_shape.rank for a in np.atleast_1d(axes_v)]
            if keepdims:
                new_dims = [Dim(1) if i in axes_list else d for i, d in enumerate(in_shape.dims)]
            else:
                new_dims = [d for i, d in enumerate(in_shape.dims) if i not in axes_list]
            set_shape(outs[0], Shape(new_dims))
        elif in_shape:
            set_shape(outs[0], Shape([None]*in_shape.rank))

    elif op == "MatMul":
        sa = get_shape(inps[0]) if inps else None
        sb = get_shape(inps[1]) if len(inps) > 1 else None
        if sa and sb and sa.rank >= 2 and sb.rank >= 2:
            batch_dims = [Dim(None)] * max(sa.rank - 2, sb.rank - 2, 0)
            out_dims = batch_dims + [sa.dims[-2], sb.dims[-1]]
            set_shape(outs[0], Shape(out_dims))

    elif op == "Gather":
        in_shape = get_shape(inps[0]) if inps else None
        idx_shape = get_shape(inps[1]) if len(inps) > 1 else None
        axis = attrs.get("axis", 0)
        if in_shape and idx_shape is not None:
            # output rank = data_rank - 1 + idx_rank
            out_dims = (in_shape.dims[:axis] +
                        idx_shape.dims +
                        in_shape.dims[axis+1:])
            set_shape(outs[0], Shape(out_dims))

    elif op in ("Where",):
        # ternary broadcast
        pass

    elif op == "Range":
        set_shape(outs[0], Shape([None]))

    elif op == "ConstantOfShape":
        shape_v = eval_const(inps[0]) if inps else None
        if shape_v is not None:
            set_shape(outs[0], Shape(shape_v.astype(int).tolist()))
        else:
            set_shape(outs[0], Shape([None]))

    elif op == "Expand":
        in_shape = get_shape(inps[0]) if inps else None
        shape_v = eval_const(inps[1]) if len(inps) > 1 and inps[1] else None
        if shape_v is not None:
            target = [int(x) for x in shape_v]
            if in_shape:
                n = max(in_shape.rank, len(target))
                a_dims = [Dim(1)] * (n - in_shape.rank) + in_shape.dims
                b_dims = [Dim(x) for x in [1] * (n - len(target)) + target]
                result_dims = []
                for da, db in zip(a_dims, b_dims):
                    result_dims.append(da.broadcast(db))
                set_shape(outs[0], Shape(result_dims))

    elif op == "Resize":
        in_shape = get_shape(inps[0]) if inps else None
        sizes_v = eval_const(inps[3]) if len(inps) > 3 and inps[3] else None
        if sizes_v is not None:
            set_shape(outs[0], Shape(sizes_v.astype(int).tolist()))
        elif in_shape:
            set_shape(outs[0], Shape([None]*in_shape.rank))

    elif op in ("Shape",):
        in_shape = get_shape(inps[0]) if inps else None
        if in_shape:
            set_shape(outs[0], Shape([in_shape.rank]))
        else:
            set_shape(outs[0], Shape([None]))

    elif op == "Cast":
        in_shape = get_shape(inps[0]) if inps else None
        if in_shape:
            set_shape(outs[0], in_shape)

    elif op in ("Pad",):
        in_shape = get_shape(inps[0]) if inps else None
        if in_shape:
            set_shape(outs[0], Shape([None]*in_shape.rank))

    elif op == "Constant":
        v = eval_const(outs[0]) if outs else None
        if v is not None:
            set_shape(outs[0], Shape(list(v.shape)))

    elif op == "Identity":
        in_shape = get_shape(inps[0]) if inps else None
        if in_shape:
            set_shape(outs[0], in_shape)

    elif op in ("STFT", "DFT"):
        pass  # already handled above

    # For all ops: ensure all outputs have at least something
    # (even if None, initialize)
    for out_name in outs:
        if out_name and out_name not in shape_map:
            in_shape = get_shape(inps[0]) if inps else None
            if in_shape:
                shape_map[out_name] = in_shape


print(f"\nTotal broadcast conflicts found: {conflict_count}")
if conflict_count == 0:
    print("  No conflicts detected via simulation.")
    print("  The error may occur in an op not fully simulated, or with symbolic dims.")

# ── 5. Check for concrete-dim binary ops involving STFT/DFT derived tensors ──
print("\n" + "="*70)
print("=== Checking all concrete-dim binary ops ===")
concrete_conflicts = 0
for name, shape in shape_map.items():
    if shape and shape.dims:
        for d in shape.dims:
            if d.is_conflict():
                concrete_conflicts += 1
                print(f"  CONFLICT in tensor {name!r}: {shape}")
                break

if concrete_conflicts == 0:
    print("  No concrete-dim conflicts found in shape_map.")

# ── 6. Check specifically what shapes tensors from STFT chain have ────────────
print("\n" + "="*70)
print("=== Shape map for STFT/DFT derived tensors ===")
# Find STFT output and trace all derived tensors
def find_derived(start_names, max_hops=15):
    derived = set(start_names)
    frontier = set(start_names)
    for _ in range(max_hops):
        new_frontier = set()
        for node in m.graph.node:
            if any(i in frontier for i in node.input if i):
                for o in node.output:
                    if o and o not in derived:
                        derived.add(o)
                        new_frontier.add(o)
        frontier = new_frontier
        if not frontier:
            break
    return derived

stft_out_names = []
dft_out_names = []
for node in m.graph.node:
    if node.op_type == "STFT":
        stft_out_names.extend(o for o in node.output if o)
    if node.op_type == "DFT":
        dft_out_names.extend(o for o in node.output if o)

print(f"\nSTFT outputs: {stft_out_names}")
all_stft_derived = find_derived(stft_out_names)
print(f"STFT-derived tensors: {len(all_stft_derived)} total")

print(f"\nDFT outputs: {dft_out_names}")
all_dft_derived = find_derived(dft_out_names)
print(f"DFT-derived tensors: {len(all_dft_derived)} total")

# Find binary ops where one input is from STFT chain and has concrete dims
print("\n--- Binary ops with at least one STFT-derived concrete-dim input ---")
for node in m.graph.node:
    if node.op_type not in ("Add", "Sub", "Mul", "Div", "Pow"):
        continue
    inps = list(node.input)
    if len(inps) < 2:
        continue
    sa = shape_map.get(inps[0])
    sb = shape_map.get(inps[1])
    if sa is None or sb is None:
        continue
    # Check if either input comes from STFT chain
    if inps[0] not in all_stft_derived and inps[1] not in all_stft_derived:
        if inps[0] not in all_dft_derived and inps[1] not in all_dft_derived:
            continue
    print(f"  {node.op_type}({inps[0]!r}:{sa}, {inps[1]!r}:{sb}) → {list(node.output)}")
    # Check for conflict
    if sa.rank is not None and sb.rank is not None:
        n = max(sa.rank, sb.rank)
        a_dims = [Dim(1)] * (n - sa.rank) + sa.dims
        b_dims = [Dim(1)] * (n - sb.rank) + sb.dims
        has_conflict = False
        for i, (da, db) in enumerate(zip(a_dims, b_dims)):
            if da.v is not None and db.v is not None and da.v != 1 and db.v != 1 and da.v != db.v:
                print(f"    *** DIM CONFLICT at dim[{i}]: {da.v} vs {db.v} ***")
                has_conflict = True
        if not has_conflict:
            print(f"    shapes compatible")
