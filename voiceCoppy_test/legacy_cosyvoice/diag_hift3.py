#!/usr/bin/env python3
"""
hift: 元々 rank-0 だった value_info テンソルがどのノードに生成されているか追跡。
- 元のファイル (rank-0 のまま) を読み込む
- rank-0 value_info テンソルの生成元ノードを特定
- そのノードの op_type とアトリビュートを表示
"""
import onnx
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# 元のファイルで確認（fix 前）
SRC = REPO_ROOT / "voiceCoppy_test" / "onnx_export" / "hift.fp32.onnx"

print(f"Loading {SRC}...")
m = onnx.load(str(SRC))

# 1. rank-0 value_info の名前を収集
rank0_vi = set()
for vi in m.graph.value_info:
    if vi.type.HasField("tensor_type") and vi.type.tensor_type.HasField("shape"):
        if len(vi.type.tensor_type.shape.dim) == 0:
            rank0_vi.add(vi.name)

print(f"\nrank-0 value_info tensors: {len(rank0_vi)}")
print(", ".join(sorted(rank0_vi)))
print()

# 2. 初期化子の名前を収集（定数）
init_names = {i.name for i in m.graph.initializer}

# 3. rank-0 value_info を生成しているノードを探す
print("=== Nodes that produce rank-0 value_info tensors ===")
for node in m.graph.node:
    for out in node.output:
        if out in rank0_vi and out not in init_names:
            attrs = {a.name: a for a in node.attribute}
            attr_summary = {}
            for a in node.attribute:
                if a.type == onnx.AttributeProto.INT:
                    attr_summary[a.name] = a.i
                elif a.type == onnx.AttributeProto.INTS:
                    attr_summary[a.name] = list(a.ints)
                elif a.type == onnx.AttributeProto.FLOAT:
                    attr_summary[a.name] = a.f
            print(f"  output: {out!r}")
            print(f"    op_type: {node.op_type}")
            print(f"    inputs:  {list(node.input)}")
            print(f"    attrs:   {attr_summary}")

            # 入力テンソルのランクも確認
            vi_by_name = {vi.name: vi for vi in m.graph.value_info}
            init_by_name = {i.name: i for i in m.graph.initializer}
            for inp in node.input:
                if inp in vi_by_name:
                    vi = vi_by_name[inp]
                    if vi.type.HasField("tensor_type") and vi.type.tensor_type.HasField("shape"):
                        in_rank = len(vi.type.tensor_type.shape.dim)
                        in_dims = [d.dim_value if d.dim_value != 0 else '?' for d in vi.type.tensor_type.shape.dim]
                        print(f"    input {inp!r}: rank={in_rank}, dims={in_dims}")
                elif inp in init_by_name:
                    init = init_by_name[inp]
                    print(f"    input {inp!r}: initializer rank={len(init.dims)}, dims={list(init.dims)}")
            print()
