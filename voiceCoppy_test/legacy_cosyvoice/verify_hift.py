#!/usr/bin/env python3
"""hift.fixed.fp32.onnx の簡易検証"""
import onnx
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL = REPO_ROOT / "voice_Horror_Game" / "Assets" / "SentisSpike" / "Models" / "hift.fixed.fp32.onnx"

print(f"Loading {MODEL}...")
m = onnx.load(str(MODEL))

# rank-0 チェック
print("\n=== rank-0 残留チェック ===")
rank0_init = [i.name for i in m.graph.initializer if len(i.dims) == 0]
print(f"rank-0 initializers: {len(rank0_init)}")
for n in rank0_init[:5]:
    print(f"  {n!r}")

rank0_vi = [vi.name for vi in m.graph.value_info
            if vi.type.HasField("tensor_type") and vi.type.tensor_type.HasField("shape")
            and len(vi.type.tensor_type.shape.dim) == 0]
print(f"rank-0 value_info: {len(rank0_vi)}")
for n in rank0_vi[:5]:
    print(f"  {n!r}")

# Range ノードの入力確認
print("\n=== Range ノードの入力 ===")
for node in m.graph.node:
    if node.op_type == "Range":
        print(f"  Range outputs={list(node.output)}, inputs={list(node.input)}")

# 追加した Squeeze ノード
print("\n=== 追加 Squeeze ノード ===")
for node in m.graph.node:
    if "for_range" in node.name:
        print(f"  {node.name}: Squeeze({node.input[0]}) -> {node.output[0]}")

# onnx checker
print("\n=== onnx.checker.check_model ===")
try:
    onnx.checker.check_model(m, full_check=False)
    print("  PASS")
except Exception as e:
    print(f"  FAIL: {e}")
