#!/usr/bin/env python3
"""
diag_hift10.py — ScatterElements / ScatterND / STFT input rank チェック
"""
import onnx
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL = REPO_ROOT / "voice_Horror_Game" / "Assets" / "SentisSpike" / "Models" / "hift.fixed.fp32.onnx"

print(f"Loading {MODEL}...")
m = onnx.load(str(MODEL))

vi_map = {}
for init in m.graph.initializer:
    vi_map[init.name] = (len(init.dims), "init", list(init.dims))
for vi in m.graph.value_info:
    if vi.type.HasField("tensor_type") and vi.type.tensor_type.HasField("shape"):
        dims = [d.dim_value if d.dim_value else (d.dim_param if d.dim_param else "?") for d in vi.type.tensor_type.shape.dim]
        vi_map[vi.name] = (len(vi.type.tensor_type.shape.dim), "value_info", dims)
for inp in m.graph.input:
    if inp.type.HasField("tensor_type") and inp.type.tensor_type.HasField("shape"):
        dims = [d.dim_value if d.dim_value else (d.dim_param if d.dim_param else "?") for d in inp.type.tensor_type.shape.dim]
        vi_map[inp.name] = (len(inp.type.tensor_type.shape.dim), "graph.input", dims)

def info(name):
    if name in vi_map:
        r, src, dims = vi_map[name]
        return f"rank={r} dims={dims} ({src})"
    return f"rank=? (not in vi)"

# ─── ScatterElements ─────────────────────────────────────────────────────────
print("\n=== ScatterElements nodes ===")
for node in m.graph.node:
    if node.op_type == "ScatterElements":
        d = node.input[0] if len(node.input) > 0 else ""
        idx = node.input[1] if len(node.input) > 1 else ""
        upd = node.input[2] if len(node.input) > 2 else ""
        print(f"  out={list(node.output)}")
        print(f"  data:    {d!r}: {info(d)}")
        print(f"  indices: {idx!r}: {info(idx)}")
        print(f"  updates: {upd!r}: {info(upd)}")
        attrs = {}
        for a in node.attribute:
            if a.type == onnx.AttributeProto.INT:
                attrs[a.name] = a.i
        print(f"  attrs={attrs}")

# ─── ScatterND ───────────────────────────────────────────────────────────────
print("\n=== ScatterND nodes ===")
for node in m.graph.node:
    if node.op_type == "ScatterND":
        d = node.input[0] if len(node.input) > 0 else ""
        idx = node.input[1] if len(node.input) > 1 else ""
        upd = node.input[2] if len(node.input) > 2 else ""
        print(f"  out={list(node.output)}")
        print(f"  data:    {d!r}: {info(d)}")
        print(f"  indices: {idx!r}: {info(idx)}")
        print(f"  updates: {upd!r}: {info(upd)}")

# ─── STFT node ───────────────────────────────────────────────────────────────
print("\n=== STFT node ===")
for node in m.graph.node:
    if node.op_type == "STFT":
        print(f"  name={node.name!r}, out={list(node.output)}")
        for i, inp in enumerate(node.input):
            if inp:
                print(f"  input[{i}]={inp!r}: {info(inp)}")
            else:
                print(f"  input[{i}]: (empty)")
        for i, out in enumerate(node.output):
            print(f"  output[{i}]={out!r}: {info(out)}")

# ─── val_162 tracing ─────────────────────────────────────────────────────────
print("\n=== val_162 producer ===")
for node in m.graph.node:
    if 'val_162' in node.output:
        print(f"  op={node.op_type}, out={list(node.output)}, name={node.name!r}")
        for i, inp in enumerate(node.input):
            print(f"  input[{i}]={inp!r}: {info(inp)}")
        break
else:
    print("  not found (may be graph input)")

# ─── Resize nodes ────────────────────────────────────────────────────────────
print("\n=== Resize nodes ===")
for node in m.graph.node:
    if node.op_type == "Resize":
        x = node.input[0] if len(node.input) > 0 else ""
        scales = node.input[2] if len(node.input) > 2 else ""
        sizes = node.input[3] if len(node.input) > 3 else ""
        print(f"  out={node.output[0]!r}")
        print(f"  X:      {x!r}: {info(x)}")
        if scales:
            print(f"  scales: {scales!r}: {info(scales)}")
        if sizes:
            print(f"  sizes:  {sizes!r}: {info(sizes)}")

# ─── Squeeze that converts rank-4 -> rank-3 ──────────────────────────────────
print("\n=== Squeeze that consumes rank-4 tensors ===")
for node in m.graph.node:
    if node.op_type == "Squeeze":
        inp = node.input[0] if len(node.input) > 0 else ""
        if inp in vi_map:
            r, src, dims = vi_map[inp]
            if r == 4:
                out = node.output[0] if len(node.output) > 0 else ""
                axes_inp = node.input[1] if len(node.input) > 1 else ""
                print(f"  Squeeze(rank-4 -> rank-3?)")
                print(f"  inp={inp!r}: {info(inp)}")
                print(f"  axes={axes_inp!r}: {info(axes_inp)}")
                print(f"  out={out!r}: {info(out)}")
