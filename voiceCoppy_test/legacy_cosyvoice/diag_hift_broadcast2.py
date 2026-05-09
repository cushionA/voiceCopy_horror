#!/usr/bin/env python3
"""
diag_hift_broadcast2.py  -  Simulate Sentis PartialTensor.Broadcast to find
the exact node causing "ValueError: broadcast dims must be equal or 1".

Sentis DynamicTensorDim.Broadcast(a, b) fires when:
  - a != 1, b != 1, a != b   AND   both are concrete ints

Strategy:
  1. Propagate TENSOR SHAPES (not values) through the graph
  2. For every binary-broadcast op, call our broadcast simulation
  3. Also simulate Sentis partial VALUE tracking for INT-typed tensors:
     if both INT inputs are fully known, check their value-shapes too

Run from repo root (or any dir):
    python voiceCoppy_test/diag_hift_broadcast2.py
"""
import sys
from pathlib import Path
from collections import defaultdict, deque
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL = REPO_ROOT / "voice_Horror_Game" / "Assets" / "SentisSpike" / "Models" / "hift.fixed.fp32.onnx"

try:
    import onnx
    from onnx import numpy_helper
except ImportError:
    print("pip install onnx")
    sys.exit(1)

print(f"Loading {MODEL.name} ...")
m = onnx.load(str(MODEL))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
INT_DTYPES = {2, 3, 4, 5, 6, 7, 9, 12, 13}   # all integer element types

def get_attrs(node):
    d = {}
    for a in node.attribute:
        if   a.type == onnx.AttributeProto.INT:    d[a.name] = int(a.i)
        elif a.type == onnx.AttributeProto.INTS:   d[a.name] = list(a.ints)
        elif a.type == onnx.AttributeProto.FLOAT:  d[a.name] = float(a.f)
        elif a.type == onnx.AttributeProto.TENSOR:
            try: d[a.name] = numpy_helper.to_array(a.t)
            except: pass
    return d

# ---------------------------------------------------------------------------
# Build maps
# ---------------------------------------------------------------------------
producer_map = {}
for node in m.graph.node:
    for o in node.output:
        if o: producer_map[o] = node

# initializers
init_by_name = {}
init_dtype   = {}
for init in m.graph.initializer:
    try:
        arr = numpy_helper.to_array(init)
        init_by_name[init.name] = arr
        init_dtype[init.name]   = init.data_type
    except: pass

# shape_map: name -> list[int|None]  (None = dynamic/unknown dim)
# dtype_map: name -> onnx elem_type int (1=float, 7=int64, etc.)
shape_map = {}
dtype_map  = {}

for name, arr in init_by_name.items():
    shape_map[name] = list(arr.shape)
    dtype_map[name] = init_dtype.get(name, 1)

for inp in m.graph.input:
    if inp.name in shape_map: continue
    if not inp.type.HasField("tensor_type"): continue
    tt = inp.type.tensor_type
    dtype_map[inp.name] = tt.elem_type
    if tt.HasField("shape"):
        dims = []
        for d in tt.shape.dim:
            dims.append(int(d.dim_value) if d.HasField("dim_value") else None)
        shape_map[inp.name] = dims

# ---------------------------------------------------------------------------
# Partial constant evaluator  (gives numpy array or None)
# ---------------------------------------------------------------------------
_cache = {}

def eval_const(name, depth=0):
    if depth > 70 or not name: return None
    if name in _cache: return _cache[name]
    if name in init_by_name:
        _cache[name] = init_by_name[name]; return _cache[name]
    if name not in producer_map:
        _cache[name] = None; return None

    node  = producer_map[name]
    op    = node.op_type
    inp   = list(node.input)
    attrs = get_attrs(node)
    res   = None
    try:
        if op == "Constant":
            v = attrs.get("value")
            if v is not None: res = v

        elif op == "Shape":
            sh = shape_map.get(inp[0] if inp else "")
            if sh and all(d is not None for d in sh):
                res = np.array(sh, dtype=np.int64)

        elif op == "Gather":
            d_v = eval_const(inp[0], depth+1) if len(inp)>0 else None
            i_v = eval_const(inp[1], depth+1) if len(inp)>1 else None
            if d_v is not None and i_v is not None:
                axis = attrs.get("axis", 0)
                res  = np.take(d_v, i_v, axis=axis)

        elif op == "Unsqueeze":
            x = eval_const(inp[0], depth+1) if inp else None
            if x is not None:
                ax = eval_const(inp[1], depth+1) if len(inp)>1 else None
                if ax is None:
                    ax_a = attrs.get("axes")
                    if ax_a is not None: ax = np.array(ax_a, dtype=np.int64)
                if ax is not None:
                    tmp = x
                    for a in sorted(int(v) for v in np.atleast_1d(ax)):
                        tmp = np.expand_dims(tmp, a)
                    res = tmp

        elif op == "Squeeze":
            x = eval_const(inp[0], depth+1) if inp else None
            if x is not None:
                ax = eval_const(inp[1], depth+1) if len(inp)>1 else None
                if ax is None:
                    ax_a = attrs.get("axes")
                    if ax_a is not None: ax = np.array(ax_a, dtype=np.int64)
                if ax is not None:
                    axes_list = tuple(int(v) % (x.ndim+1) for v in np.atleast_1d(ax))
                    res = np.squeeze(x, axis=axes_list)
                else:
                    res = np.squeeze(x)

        elif op == "Concat":
            axis  = attrs.get("axis", 0)
            parts = [eval_const(i, depth+1) for i in inp if i]
            if all(p is not None for p in parts):
                res = np.concatenate([np.atleast_1d(p) for p in parts], axis=axis)

        elif op in ("Add","Sub","Mul","Div","Pow"):
            a = eval_const(inp[0], depth+1) if len(inp)>0 else None
            b = eval_const(inp[1], depth+1) if len(inp)>1 else None
            if a is not None and b is not None:
                ops = {"Add":np.add,"Sub":np.subtract,"Mul":np.multiply,
                       "Div":np.divide,"Pow":np.power}
                res = ops[op](a, b)

        elif op == "Cast":
            x  = eval_const(inp[0], depth+1) if inp else None
            if x is not None:
                to = attrs.get("to", 1)
                lut = {1:np.float32,6:np.int32,7:np.int64,10:np.float16,11:np.float64}
                if to in lut: res = x.astype(lut[to])

        elif op == "Reshape":
            x = eval_const(inp[0], depth+1) if len(inp)>0 else None
            s = eval_const(inp[1], depth+1) if len(inp)>1 else None
            if x is not None and s is not None:
                res = x.reshape(s.astype(int))

        elif op == "Slice":
            data  = eval_const(inp[0], depth+1) if len(inp)>0 else None
            start = eval_const(inp[1], depth+1) if len(inp)>1 else None
            end_  = eval_const(inp[2], depth+1) if len(inp)>2 else None
            axes  = eval_const(inp[3], depth+1) if len(inp)>3 else None
            steps = eval_const(inp[4], depth+1) if len(inp)>4 else None
            if data is not None and start is not None and end_ is not None:
                if axes  is None: axes  = np.arange(data.ndim, dtype=np.int64)
                if steps is None: steps = np.ones(len(np.atleast_1d(axes)), dtype=np.int64)
                slc = [slice(None)] * data.ndim
                for ax,st,en,sp in zip(np.atleast_1d(axes),np.atleast_1d(start),
                                        np.atleast_1d(end_),np.atleast_1d(steps)):
                    slc[int(ax)] = slice(int(st), int(en), int(sp))
                res = data[tuple(slc)]

        elif op == "Range":
            s_v = eval_const(inp[0], depth+1) if len(inp)>0 else None
            l_v = eval_const(inp[1], depth+1) if len(inp)>1 else None
            d_v = eval_const(inp[2], depth+1) if len(inp)>2 else None
            if s_v is not None and l_v is not None and d_v is not None:
                s_f = float(np.atleast_1d(s_v)[0])
                l_f = float(np.atleast_1d(l_v)[0])
                d_f = float(np.atleast_1d(d_v)[0])
                res = np.arange(s_f, l_f, d_f)

    except Exception: pass

    _cache[name] = res
    return res

# ---------------------------------------------------------------------------
# Sentis DynamicTensorDim.Broadcast simulation
# ---------------------------------------------------------------------------
def broadcast_dim(a, b):
    """
    Returns (result, err_str).  None = dynamic/unknown.
    Mirrors Sentis exactly:
      if a==1 -> b
      if b==1 -> a
      if a==b -> a
      if both concrete -> ERROR
      else -> None (unknown)
    """
    if a == 1: return b, None
    if b == 1: return a, None
    if a == b: return a, None
    if a is not None and b is not None:
        return None, f"{a} vs {b}"
    if a is not None: return a, None
    if b is not None: return b, None
    return None, None

def broadcast_shapes(sa, sb, label=""):
    """Returns (out_shape, err_str)."""
    if sa is None or sb is None:
        return None, None
    n  = max(len(sa), len(sb))
    pa = [1]*(n-len(sa)) + list(sa)
    pb = [1]*(n-len(sb)) + list(sb)
    out = []
    for i,(a,b) in enumerate(zip(pa,pb)):
        dim, err = broadcast_dim(a, b)
        if err:
            return None, (f"dim[{i}] {err}  "
                          f"(shapes {sa} vs {sb})"
                          + (f"  [{label}]" if label else ""))
        out.append(dim)
    return out, None

# ---------------------------------------------------------------------------
# Topological sort
# ---------------------------------------------------------------------------
def topo_sort(nodes):
    prod = {}
    for i,n in enumerate(nodes):
        for o in n.output:
            if o: prod[o] = i
    indeg = [0]*len(nodes)
    adj   = defaultdict(list)
    for i,n in enumerate(nodes):
        for inp in n.input:
            if inp and inp in prod:
                j = prod[inp]
                if j != i:
                    adj[j].append(i)
                    indeg[i] += 1
    q = deque(i for i in range(len(nodes)) if indeg[i]==0)
    order = []
    while q:
        i = q.popleft(); order.append(i)
        for j in adj[i]:
            indeg[j] -= 1
            if indeg[j] == 0: q.append(j)
    if len(order) < len(nodes):
        order.extend(set(range(len(nodes))) - set(order))
    return [nodes[i] for i in order]

sorted_nodes = topo_sort(list(m.graph.node))

# ---------------------------------------------------------------------------
# Main simulation pass
# ---------------------------------------------------------------------------
errors = []

def report(msg, node, inp_a, inp_b, sa, sb, detail=""):
    entry = dict(op=node.op_type, name=node.name, out=list(node.output)[:1],
                 inp_a=inp_a, inp_b=inp_b, sa=sa, sb=sb, detail=detail)
    errors.append(entry)
    print(f"\n!!! BROADCAST ERROR !!!")
    print(f"  op={node.op_type!r}, name={node.name!r}")
    print(f"  out: {list(node.output)[:1]}")
    print(f"  inp_a={inp_a!r}  shape={sa}")
    print(f"  inp_b={inp_b!r}  shape={sb}")
    print(f"  {detail}")

BINARY_OPS = {"Add","Sub","Mul","Div","Pow","Mod","PRelu",
              "Equal","Greater","GreaterOrEqual","Less","LessOrEqual",
              "And","Or","Xor","BitShift"}

print(f"Processing {len(sorted_nodes)} nodes ...\n")

for node in sorted_nodes:
    op   = node.op_type
    inp  = list(node.input)
    out  = list(node.output)
    attr = get_attrs(node)

    # ------------------------------------------------------------------ Constant
    if op == "Constant":
        v = attr.get("value")
        if v is not None:
            shape_map[out[0]] = list(np.atleast_1d(v).shape) if out else None
            # elem type from the tensor proto
            for a in node.attribute:
                if a.name == "value" and a.type == onnx.AttributeProto.TENSOR:
                    dtype_map[out[0]] = a.t.data_type

    # ------------------------------------------------------------------ Binary
    elif op in BINARY_OPS:
        a_n = inp[0] if len(inp)>0 else ""; sa = shape_map.get(a_n)
        b_n = inp[1] if len(inp)>1 else ""; sb = shape_map.get(b_n)
        res_shape, err = broadcast_shapes(sa, sb, f"{op}")
        if err:
            report(op, node, a_n, b_n, sa, sb, err)
        else:
            if out: shape_map[out[0]] = res_shape
        # Also check: for INT-typed ops, Sentis tracks VALUES.
        # The VALUE shape is the same as the tensor shape, but let's double-check
        # by also evaluating concrete values and seeing if they'd mismatch.
        if sa and sb:
            a_dt = dtype_map.get(a_n, 1)
            b_dt = dtype_map.get(b_n, 1)
            if a_dt in INT_DTYPES and b_dt in INT_DTYPES:
                a_val = eval_const(a_n)
                b_val = eval_const(b_n)
                if a_val is not None and b_val is not None:
                    av = np.atleast_1d(a_val); bv = np.atleast_1d(b_val)
                    _, err2 = broadcast_shapes(list(av.shape), list(bv.shape),
                                               f"INT-value {op}")
                    if err2:
                        report(f"INT-value {op}", node, a_n, b_n,
                               list(av.shape), list(bv.shape), err2)

    # ------------------------------------------------------------------ Expand
    elif op == "Expand":
        x_n = inp[0] if len(inp)>0 else ""; x_sh = shape_map.get(x_n)
        s_n = inp[1] if len(inp)>1 else ""
        target_val = eval_const(s_n)
        if target_val is not None:
            tgt_sh = [int(v) for v in np.atleast_1d(target_val)]
            # Sentis: FromPartialTensor(shape).Broadcast(input.shape)
            res_shape, err = broadcast_shapes(tgt_sh, x_sh, "Expand")
            if err:
                report("Expand", node, s_n, x_n, tgt_sh, x_sh, err)
            else:
                if out: shape_map[out[0]] = res_shape
        else:
            # dynamic target; output shape unknown but at least rank matches
            if x_sh is not None and out:
                shape_map[out[0]] = [None]*len(x_sh)

    # ------------------------------------------------------------------ Where
    elif op == "Where":
        c_n = inp[0] if len(inp)>0 else ""; c_sh = shape_map.get(c_n)
        x_n = inp[1] if len(inp)>1 else ""; x_sh = shape_map.get(x_n)
        y_n = inp[2] if len(inp)>2 else ""; y_sh = shape_map.get(y_n)
        for (sa2,na2,sb2,nb2) in [(c_sh,c_n,x_sh,x_n),(c_sh,c_n,y_sh,y_n),(x_sh,x_n,y_sh,y_n)]:
            _, err = broadcast_shapes(sa2, sb2, f"Where")
            if err: report("Where", node, na2, nb2, sa2, sb2, err)
        # propagate
        res = c_sh
        for s2 in [x_sh, y_sh]:
            if res is None: res = s2
            elif s2 is not None:
                res, _ = broadcast_shapes(res, s2)
        if out: shape_map[out[0]] = res

    # ------------------------------------------------------------------ Shape propagation stubs
    elif op in ("Relu","Sigmoid","Tanh","Softmax","LogSoftmax","Elu","LeakyRelu",
                "Mish","Gelu","Silu","Swish","Clip","Abs","Neg","Ceil","Floor",
                "Round","Sqrt","Log","Exp","Cos","Sin","Sign","Erf",
                "IsNaN","IsInf","Not","Cast","CastLike","Identity","Dropout"):
        if inp and out: shape_map.setdefault(out[0], shape_map.get(inp[0]))

    elif op == "Transpose":
        x_sh = shape_map.get(inp[0]) if inp else None
        perm = attr.get("perm")
        if x_sh and perm and out:
            shape_map[out[0]] = [x_sh[int(p)] for p in perm]
        elif x_sh and out:
            shape_map[out[0]] = list(reversed(x_sh))

    elif op == "Reshape":
        s_n = inp[1] if len(inp)>1 else ""; s_v = eval_const(s_n)
        if s_v is not None and out:
            shape_map[out[0]] = [int(v) if v != -1 else None for v in np.atleast_1d(s_v)]

    elif op == "Unsqueeze":
        x_sh = shape_map.get(inp[0]) if inp else None
        ax_n = inp[1] if len(inp)>1 else ""; ax_v = eval_const(ax_n)
        if ax_v is None:
            ax_a = attr.get("axes")
            if ax_a is not None: ax_v = np.array(ax_a, dtype=np.int64)
        if x_sh is not None and ax_v is not None and out:
            shape_map[out[0]] = [None] * (len(x_sh) + len(np.atleast_1d(ax_v)))

    elif op == "Squeeze":
        x_sh = shape_map.get(inp[0]) if inp else None
        ax_n = inp[1] if len(inp)>1 else ""; ax_v = eval_const(ax_n)
        if ax_v is None:
            ax_a = attr.get("axes")
            if ax_a is not None: ax_v = np.array(ax_a, dtype=np.int64)
        if x_sh is not None and ax_v is not None and out:
            n_out = max(0, len(x_sh) - len(np.atleast_1d(ax_v)))
            shape_map[out[0]] = [None] * n_out
        elif x_sh is not None and out:
            shape_map[out[0]] = [None] * max(0, len(x_sh) - 1)  # guess

    elif op == "Concat":
        axis  = attr.get("axis", 0)
        shs   = [shape_map.get(i) for i in inp if i]
        if shs and all(s is not None for s in shs) and out:
            base = list(shs[0])
            for s in shs[1:]:
                if len(s) == len(base):
                    if base[axis] is not None and s[axis] is not None:
                        base[axis] += s[axis]
                    else:
                        base[axis] = None
            shape_map[out[0]] = base

    elif op == "Gather":
        x_sh  = shape_map.get(inp[0] if len(inp)>0 else "")
        idx_sh = shape_map.get(inp[1] if len(inp)>1 else "")
        axis  = attr.get("axis", 0)
        if x_sh is not None and idx_sh is not None and out:
            out_sh = list(x_sh[:axis]) + list(idx_sh) + list(x_sh[axis+1:])
            shape_map[out[0]] = out_sh

    elif op == "GatherElements":
        x_sh = shape_map.get(inp[0]) if inp else None
        if x_sh is not None and out: shape_map[out[0]] = x_sh

    elif op == "GatherND":
        x_sh = shape_map.get(inp[0]) if inp else None
        if x_sh is not None and out: shape_map[out[0]] = [None]*max(1,len(x_sh))

    elif op == "Slice":
        x_sh = shape_map.get(inp[0]) if inp else None
        if x_sh is not None and out: shape_map[out[0]] = [None]*len(x_sh)

    elif op in ("Conv","ConvTranspose"):
        x_sh = shape_map.get(inp[0]) if inp else None
        if x_sh is not None and out: shape_map[out[0]] = [None]*len(x_sh)

    elif op in ("MaxPool","AveragePool"):
        x_sh = shape_map.get(inp[0]) if inp else None
        if x_sh is not None and out: shape_map[out[0]] = [None]*len(x_sh)

    elif op in ("GlobalAveragePool","GlobalMaxPool"):
        x_sh = shape_map.get(inp[0]) if inp else None
        if x_sh is not None and out:
            shape_map[out[0]] = list(x_sh[:2]) + [1]*(len(x_sh)-2)

    elif op == "Shape":
        x_sh = shape_map.get(inp[0]) if inp else None
        if x_sh is not None and out:
            shape_map[out[0]] = [len(x_sh)]
            dtype_map[out[0]] = 7  # INT64

    elif op == "Range":
        s_v = eval_const(inp[0]) if len(inp)>0 else None
        l_v = eval_const(inp[1]) if len(inp)>1 else None
        d_v = eval_const(inp[2]) if len(inp)>2 else None
        if s_v is not None and l_v is not None and d_v is not None and out:
            try:
                n = max(0, int(np.ceil((float(np.atleast_1d(l_v)[0]) -
                                        float(np.atleast_1d(s_v)[0])) /
                                       float(np.atleast_1d(d_v)[0]))))
                shape_map[out[0]] = [n]
            except: shape_map[out[0]] = [None]
        elif out: shape_map[out[0]] = [None]

    elif op == "CumSum":
        x_sh = shape_map.get(inp[0]) if inp else None
        if x_sh is not None and out: shape_map[out[0]] = list(x_sh)

    elif op == "STFT":
        if out: shape_map[out[0]] = [None, None, None, 2]

    elif op == "DFT":
        x_sh = shape_map.get(inp[0]) if inp else None
        if x_sh is not None and out: shape_map[out[0]] = list(x_sh)

    elif op in ("ScatterElements","ScatterND"):
        x_sh = shape_map.get(inp[0]) if inp else None
        if x_sh is not None and out: shape_map[out[0]] = list(x_sh)

    elif op == "Tile":
        x_sh  = shape_map.get(inp[0]) if inp else None
        rep_v = eval_const(inp[1]) if len(inp)>1 else None
        if x_sh and rep_v is not None and out:
            rep = [int(v) for v in np.atleast_1d(rep_v)]
            out_sh = [x_sh[i]*rep[i] if x_sh[i] is not None else None
                      for i in range(len(x_sh))]
            shape_map[out[0]] = out_sh
        elif x_sh and out: shape_map[out[0]] = [None]*len(x_sh)

    elif op in ("Resize","Pad"):
        x_sh = shape_map.get(inp[0]) if inp else None
        if x_sh is not None and out: shape_map[out[0]] = [None]*len(x_sh)

    elif op == "ConstantOfShape":
        sv = eval_const(inp[0]) if inp else None
        if sv is not None and out:
            shape_map[out[0]] = [int(v) for v in np.atleast_1d(sv)]

    elif op in ("Gemm",):
        a_sh = shape_map.get(inp[0]) if len(inp)>0 else None
        b_sh = shape_map.get(inp[1]) if len(inp)>1 else None
        if a_sh and b_sh and len(a_sh)>=2 and len(b_sh)>=2 and out:
            transA = attr.get("transA", 0); transB = attr.get("transB", 0)
            m_ = a_sh[1 if transA else 0]
            n_ = b_sh[0 if transB else 1]
            shape_map[out[0]] = [m_, n_]

    elif op == "MatMul":
        a_sh = shape_map.get(inp[0]) if len(inp)>0 else None
        b_sh = shape_map.get(inp[1]) if len(inp)>1 else None
        if a_sh and b_sh and out:
            shape_map[out[0]] = [None]*max(len(a_sh),len(b_sh))

    elif op in ("Flatten",):
        x_sh = shape_map.get(inp[0]) if inp else None
        axis = attr.get("axis", 1)
        if x_sh is not None and out:
            shape_map[out[0]] = [None, None]

    elif op in ("LayerNormalization","GroupNormalization","BatchNormalization",
                "InstanceNormalization"):
        x_sh = shape_map.get(inp[0]) if inp else None
        if x_sh is not None and out: shape_map[out[0]] = list(x_sh)

    elif op == "Split":
        x_sh = shape_map.get(inp[0]) if inp else None
        if x_sh is not None:
            for o in out:
                if o: shape_map[o] = [None]*len(x_sh)

    else:
        # default: propagate first input shape
        x_sh = shape_map.get(inp[0]) if inp else None
        if x_sh is not None and out and out[0]:
            shape_map.setdefault(out[0], list(x_sh))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"Total tensors with known shapes: {len(shape_map)}\n")

if not errors:
    print("[OK] No broadcast errors detected by shape-level simulation.")
    print()
    print("The error may come from Sentis's PARTIAL TENSOR VALUE tracking.")
    print("Let's check all binary ops where both INT inputs have evaluable concrete values ...\n")

    # Second pass: exhaustive partial-value check
    suspects = []
    for node in sorted_nodes:
        op = node.op_type
        if op not in ("Add","Sub","Mul","Div","Pow","Mod"): continue
        inp = list(node.input)
        a_n = inp[0] if len(inp)>0 else ""; a_dt = dtype_map.get(a_n,1)
        b_n = inp[1] if len(inp)>1 else ""; b_dt = dtype_map.get(b_n,1)

        a_val = eval_const(a_n); b_val = eval_const(b_n)
        if a_val is None or b_val is None: continue

        av = np.atleast_1d(a_val); bv = np.atleast_1d(b_val)
        _, err = broadcast_shapes(list(av.shape), list(bv.shape), op)
        if err:
            suspects.append((op, node, a_n, av.shape, b_n, bv.shape, err))
            print(f"SUSPECT: op={op!r}, name={node.name!r}")
            print(f"  out={list(node.output)[:1]}")
            print(f"  a={a_n!r}  value={av}  value_shape={list(av.shape)}")
            print(f"  b={b_n!r}  value={bv}  value_shape={list(bv.shape)}")
            print(f"  {err}")

    if not suspects:
        print("[OK] No value-level broadcast conflicts found either.")
        print()
        print("Falling back to checking ALL ops whose output shape is")
        print("determined by broadcasting (incl. Expand) with partial shapes...")
        print()
        print("Current shape map for known tensors (sample):")
        # Print concrete shapes only
        concrete = {k:v for k,v in shape_map.items() if v and all(d is not None for d in v)}
        for k,v in sorted(concrete.items())[:40]:
            print(f"  {k!r}: {v}")
else:
    print(f"\n{'='*60}")
    print(f"FOUND {len(errors)} BROADCAST ERROR(S)")
    print(f"{'='*60}")
    for i,e in enumerate(errors):
        print(f"\n--- Error {i+1} ---")
        print(f"  op   = {e['op']}")
        print(f"  name = {e['name']!r}")
        print(f"  out  = {e['out']}")
        print(f"  inp_a= {e['inp_a']!r}  shape={e['sa']}")
        print(f"  inp_b= {e['inp_b']!r}  shape={e['sb']}")
        print(f"  detail: {e['detail']}")
