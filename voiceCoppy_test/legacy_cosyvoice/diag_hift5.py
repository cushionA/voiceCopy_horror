#!/usr/bin/env python3
"""
hift: rank-4 を要求するノードを特定する診断
"""
import onnx
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# 修正済みファイルで確認
MODEL = REPO_ROOT / "voice_Horror_Game" / "Assets" / "SentisSpike" / "Models" / "hift.fixed.fp32.onnx"
SRC   = REPO_ROOT / "voiceCoppy_test" / "onnx_export" / "hift.fp32.onnx"

# Sentis が rank-4 を要求するオペレーター
RANK4_OPS = {
    "DepthToSpace", "SpaceToDepth",
    "MaxPool",      # 2D pooling
    "AveragePool",  # 2D pooling
    "Conv",         # Conv2d (4D)
    "ConvTranspose",
    "BatchNormalization",
    "InstanceNormalization",
    "GroupNormalization",
}

# value_info / input / output を辞書化
def build_vi_map(m):
    vi = {}
    for v in m.graph.value_info:
        if v.type.HasField("tensor_type") and v.type.tensor_type.HasField("shape"):
            vi[v.name] = len(v.type.tensor_type.shape.dim)
    for v in m.graph.input:
        if v.type.HasField("tensor_type") and v.type.tensor_type.HasField("shape"):
            vi[v.name] = len(v.type.tensor_type.shape.dim)
    for v in m.graph.output:
        if v.type.HasField("tensor_type") and v.type.tensor_type.HasField("shape"):
            vi[v.name] = len(v.type.tensor_type.shape.dim)
    for init in m.graph.initializer:
        vi[init.name] = len(init.dims)
    return vi

print(f"=== 元モデルの rank-4 要求ノード ===")
src_m = onnx.load(str(SRC))
src_vi = build_vi_map(src_m)

for node in src_m.graph.node:
    if node.op_type in RANK4_OPS:
        inp_ranks = {}
        for inp in node.input:
            if inp and inp in src_vi:
                inp_ranks[inp] = src_vi[inp]
        print(f"  op={node.op_type}, outputs={list(node.output)}")
        for inp, r in inp_ranks.items():
            print(f"    input {inp!r}: rank={r}")

print()
print(f"=== 全 DepthToSpace ノード ===")
for node in src_m.graph.node:
    if node.op_type == "DepthToSpace":
        attrs = {a.name: a.i for a in node.attribute}
        print(f"  inputs={list(node.input)}, outputs={list(node.output)}, attrs={attrs}")
        for inp in node.input:
            r = src_vi.get(inp, "?")
            print(f"    {inp!r}: rank={r}")

print()
print(f"=== rank-3 テンソルを入力に持つ Conv / GroupNorm ノード（修正済みファイル）===")
fixed_m = onnx.load(str(MODEL))
fixed_vi = build_vi_map(fixed_m)

rank3_nodes_for_r4ops = []
for node in fixed_m.graph.node:
    if node.op_type in RANK4_OPS:
        for inp in node.input:
            if inp and fixed_vi.get(inp) == 3:
                rank3_nodes_for_r4ops.append((node.op_type, inp, list(node.output)))
                print(f"  MISMATCH op={node.op_type}, input={inp!r}(rank=3), output={node.output[0]!r}")

print(f"\nTotal rank-3→rank4 mismatches: {len(rank3_nodes_for_r4ops)}")
