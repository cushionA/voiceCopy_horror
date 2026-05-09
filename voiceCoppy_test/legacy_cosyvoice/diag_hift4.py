#!/usr/bin/env python3
"""
rank-0 スカラーチェーン: sym_size_int_187 とその子孫が何のノードの入力として使われているか追跡
"""
import onnx
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "voiceCoppy_test" / "onnx_export" / "hift.fp32.onnx"

print(f"Loading {SRC}...")
m = onnx.load(str(SRC))

# rank-0 value_info
rank0_computed = {
    'sym_size_int_187', 'mul_2342', 'sym_float', 'mul_87', 'trunc',
    'sub_36', 'mul_2343', 'add_2223', 'add_2199', 'val_895', 'mul_2320', 'sub_689'
}

# 各スカラーテンソルを消費するノードを探す
consumers = {name: [] for name in rank0_computed}
for node in m.graph.node:
    for inp in node.input:
        if inp in rank0_computed:
            consumers[inp].append(node)

print("\n=== スカラーの消費先ノード ===")
for name in sorted(rank0_computed):
    nodes = consumers[name]
    print(f"\n  {name!r} → {len(nodes)} 消費者:")
    for node in nodes:
        attrs = {}
        for a in node.attribute:
            if a.type == onnx.AttributeProto.INT:
                attrs[a.name] = a.i
            elif a.type == onnx.AttributeProto.INTS:
                attrs[a.name] = list(a.ints)
        print(f"    op={node.op_type}, outputs={list(node.output)}, attrs={attrs}")

# val_0 の情報
print("\n=== val_0 (Squeeze の入力) の情報 ===")
for inp in m.graph.input:
    if inp.name == 'val_0':
        if inp.type.HasField("tensor_type"):
            tt = inp.type.tensor_type
            if tt.HasField("shape"):
                dims = [d.dim_value if d.dim_value != 0 else (d.dim_param if d.dim_param else '?') for d in tt.shape.dim]
                print(f"  graph input: rank={len(dims)}, dims={dims}")
            else:
                print("  graph input: no shape")
        break
else:
    # value_info で探す
    for vi in m.graph.value_info:
        if vi.name == 'val_0':
            if vi.type.HasField("tensor_type") and vi.type.tensor_type.HasField("shape"):
                dims = [d.dim_value for d in vi.type.tensor_type.shape.dim]
                print(f"  value_info: rank={len(dims)}, dims={dims}")
            break
    else:
        print("  not found in input or value_info")

print("\n=== グラフ入力一覧 ===")
for inp in m.graph.input:
    if inp.type.HasField("tensor_type"):
        tt = inp.type.tensor_type
        if tt.HasField("shape"):
            dims = [d.dim_value if d.dim_value != 0 else (d.dim_param if d.dim_param else '?') for d in tt.shape.dim]
            print(f"  {inp.name!r}: rank={len(dims)}, dims={dims}, dtype={tt.elem_type}")
