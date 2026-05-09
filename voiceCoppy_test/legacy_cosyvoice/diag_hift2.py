#!/usr/bin/env python3
"""hift.fixed.fp32.onnx の詳細診断 v2"""
import onnx
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL = REPO_ROOT / "voice_Horror_Game" / "Assets" / "SentisSpike" / "Models" / "hift.fixed.fp32.onnx"

m = onnx.load(str(MODEL))

# 1. Constant nodes のチェック
print("=== Constant nodes with rank-0 value ===")
const_rank0 = []
for node in m.graph.node:
    if node.op_type == "Constant":
        for attr in node.attribute:
            if attr.name == "value":
                t = attr.t
                if len(t.dims) == 0:
                    out_name = node.output[0] if node.output else "???"
                    const_rank0.append(out_name)
                    print(f"  node output: {out_name!r}, dtype={t.data_type}, dims=[]")

print(f"Total rank-0 Constant nodes: {len(const_rank0)}")
print()

# 2. value_info との衝突チェック
vi_names = {vi.name: vi for vi in m.graph.value_info}
print("=== Const rank-0 outputs that ARE in value_info ===")
conflicts = []
for name in const_rank0:
    if name in vi_names:
        vi = vi_names[name]
        if vi.type.HasField("tensor_type") and vi.type.tensor_type.HasField("shape"):
            ndim = len(vi.type.tensor_type.shape.dim)
            conflicts.append((name, ndim))
            print(f"  {name!r}: value_info rank={ndim}")
print(f"Total conflicts: {len(conflicts)}")
print()

# 3. 残っている rank-0 value_info
print("=== Remaining rank-0 value_info ===")
remaining_r0 = []
for vi in m.graph.value_info:
    if vi.type.HasField("tensor_type") and vi.type.tensor_type.HasField("shape"):
        if len(vi.type.tensor_type.shape.dim) == 0:
            remaining_r0.append(vi.name)
            print(f"  {vi.name!r}")
print(f"Total remaining rank-0 value_info: {len(remaining_r0)}")
print()

# 4. Constant nodes の出力で value_info にない rank-0
print("=== Const rank-0 outputs NOT in value_info (Sentis will infer rank-0) ===")
not_in_vi = [n for n in const_rank0 if n not in vi_names]
for name in not_in_vi:
    print(f"  {name!r}")
print(f"Total: {len(not_in_vi)}")
print()

# 5. 全 Constant nodes サマリ
all_const = [n for n in m.graph.node if n.op_type == "Constant"]
print(f"Total Constant nodes: {len(all_const)}")
