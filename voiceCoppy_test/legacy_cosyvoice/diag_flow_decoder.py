#!/usr/bin/env python3
"""
diag_flow_decoder.py — flow.decoder.estimator.fp32.onnx の診断スクリプト
  1. ユニーク op タイプ一覧 (NullRef の原因: 未サポート op)
  2. ブロードキャスト衝突シミュレーション (broadcast error の原因)
  3. rank-0 initializer チェック
  4. DFT/STFT ノードの属性確認
"""
import sys
from pathlib import Path
import numpy as np

try:
    import onnx
    from onnx import numpy_helper, AttributeProto, TensorProto
except ImportError:
    print("pip install onnx")
    sys.exit(1)

MODEL_DIR = Path(__file__).resolve().parent.parent / "voiceCoppy_test" / "onnx_export"
ONNX_FILE = MODEL_DIR / "flow.decoder.estimator.fp32.onnx"

print(f"Loading {ONNX_FILE} (graph only, no external data)...")
# load_external_data=False でグラフ構造だけ読む (高速)
m = onnx.load(str(ONNX_FILE), load_external_data=False)
print(f"  nodes={len(m.graph.node)}, inputs={len(m.graph.input)}, "
      f"outputs={len(m.graph.output)}, initializers={len(m.graph.initializer)}, "
      f"value_info={len(m.graph.value_info)}")
opset_version = 11
for op in m.opset_import:
    if op.domain in ("", "ai.onnx"):
        opset_version = op.version
        break
print(f"  opset = {opset_version}")

# ── 1. ユニーク op タイプ ──────────────────────────────────────────────────
print("\n" + "="*70)
print("=== 1. Op types ===")
from collections import Counter
op_counts = Counter(n.op_type for n in m.graph.node)
# Sentis 2.5 既知対応 op (参考リスト、完全ではない)
SENTIS_KNOWN_OPS = {
    "Abs", "Acos", "Acosh", "Add", "And", "ArgMax", "ArgMin",
    "Asin", "Asinh", "Atan", "Atanh", "AveragePool",
    "BatchNormalization", "Bernoulli", "BitShift", "Cast", "CastLike",
    "Ceil", "Celu", "Clip", "Compress", "Concat", "ConcatFromSequence",
    "Constant", "ConstantOfShape", "Conv", "ConvInteger", "ConvTranspose",
    "Cos", "Cosh", "CumSum", "DepthToSpace", "DFT", "DynamicQuantizeLinear",
    "Einsum", "Elu", "Equal", "Erf", "Exp", "Expand", "EyeLike",
    "Flatten", "Floor", "GRU", "Gather", "GatherElements", "GatherND",
    "Gemm", "GlobalAveragePool", "GlobalMaxPool", "Greater", "GreaterOrEqual",
    "GroupNormalization", "HardSigmoid", "HardSwish", "Hardmax",
    "Identity", "If", "InstanceNormalization", "IsInf", "IsNaN",
    "LRN", "LSTM", "LayerNormalization", "LeakyRelu", "Less", "LessOrEqual",
    "Log", "LogSoftmax", "Loop", "MatMul", "MatMulInteger", "Max",
    "MaxPool", "MaxUnpool", "Mean", "Min", "Mish", "Mod", "Mul",
    "Multinomial", "Neg", "NonMaxSuppression", "NonZero", "Not",
    "OneHot", "Optional", "Or", "PRelu", "Pad", "Pow",
    "QLinearConv", "QLinearMatMul", "QuantizeLinear", "RNN", "Range",
    "Reciprocal", "ReduceL1", "ReduceL2", "ReduceLogSum", "ReduceLogSumExp",
    "ReduceMax", "ReduceMean", "ReduceMin", "ReduceProd", "ReduceSum",
    "ReduceSumSquare", "Relu", "Reshape", "Resize", "ReverseSequence",
    "RoiAlign", "Round", "STFT", "Scan", "ScatterElements", "ScatterND",
    "Selu", "SequenceAt", "SequenceConstruct", "SequenceEmpty",
    "SequenceErase", "SequenceInsert", "SequenceLength", "Shape",
    "Shrink", "Sigmoid", "Sign", "Sin", "Sinh", "Size", "Slice",
    "Softmax", "Softplus", "Softsign", "SpaceToDepth", "Split",
    "SplitToSequence", "Sqrt", "Squeeze", "StringNormalizer", "Sub",
    "Sum", "Tan", "Tanh", "TfIdfVectorizer", "ThresholdedRelu", "Tile",
    "TopK", "Transpose", "Trilu", "Unique", "Unsqueeze", "Where",
    "Xor",
}
print(f"{'Op':<30} {'Count':>6}  {'Sentis?':>8}")
print("-"*50)
potentially_unsupported = []
for op, cnt in op_counts.most_common():
    supported = "OK" if op in SENTIS_KNOWN_OPS else "*** UNKNOWN ***"
    print(f"{op:<30} {cnt:>6}  {supported}")
    if op not in SENTIS_KNOWN_OPS:
        potentially_unsupported.append(op)

if potentially_unsupported:
    print(f"\n*** Potentially unsupported ops (NullRef 候補): {potentially_unsupported} ***")
else:
    print("\n  All ops are in the known-supported list.")

# ── 2. rank-0 initializer チェック ────────────────────────────────────────
print("\n" + "="*70)
print("=== 2. Rank-0 initializers ===")
rank0_count = 0
for init in m.graph.initializer:
    if len(init.dims) == 0:
        rank0_count += 1
        if rank0_count <= 10:
            print(f"  rank-0: {init.name!r}")
print(f"  Total rank-0 initializers: {rank0_count}")

# ── 3. DFT/STFT ノードの属性確認 ───────────────────────────────────────
print("\n" + "="*70)
print("=== 3. DFT / STFT nodes ===")
spectral_found = False
for node in m.graph.node:
    if node.op_type in ("DFT", "STFT"):
        spectral_found = True
        attrs = {}
        for a in node.attribute:
            if a.type == AttributeProto.INT:
                attrs[a.name] = int(a.i)
            elif a.type == AttributeProto.FLOAT:
                attrs[a.name] = float(a.f)
        print(f"  {node.op_type}: name={node.name!r}, attrs={attrs}")
        print(f"    inputs={list(node.input)[:4]}")
if not spectral_found:
    print("  No DFT or STFT nodes found.")

# ── 4. ブロードキャスト衝突シミュレーション ─────────────────────────────
print("\n" + "="*70)
print("=== 4. Broadcast simulation ===")

# 形状マップを構築 (initializer + graph.input + value_info)
shape_map = {}  # name -> list of dims (int or "?")

def get_dim(d):
    if d.HasField("dim_value"):
        return int(d.dim_value)
    return d.dim_param if d.dim_param else "?"

for vi in list(m.graph.input) + list(m.graph.value_info) + list(m.graph.output):
    if vi.type.HasField("tensor_type") and vi.type.tensor_type.HasField("shape"):
        shape_map[vi.name] = [get_dim(d) for d in vi.type.tensor_type.shape.dim]

for init in m.graph.initializer:
    shape_map[init.name] = list(init.dims)

def can_broadcast(s1, s2):
    """2つの形状が broadcast できるかチェック。
    具体的な整数同士で s1!=s2 かつ どちらも!=1 なら衝突。"""
    n = max(len(s1), len(s2))
    p1 = [1]*(n-len(s1)) + list(s1)
    p2 = [1]*(n-len(s2)) + list(s2)
    conflicts = []
    for i, (a, b) in enumerate(zip(p1, p2)):
        if isinstance(a, int) and isinstance(b, int) and a != b and a != 1 and b != 1:
            conflicts.append(f"dim[{i}]: {a} vs {b}")
    return conflicts

BINARY_OPS = {"Add", "Sub", "Mul", "Div", "Pow", "And", "Or", "Xor",
              "Greater", "GreaterOrEqual", "Less", "LessOrEqual", "Equal",
              "Where", "PRelu", "Expand"}

conflict_count = 0
for node in m.graph.node:
    if node.op_type not in BINARY_OPS:
        continue
    if node.op_type == "Where":
        inputs_to_check = [(node.input[1], node.input[2])]  # true/false values
    else:
        inputs_to_check = [(node.input[0], node.input[1])] if len(node.input) >= 2 else []

    for inp_a, inp_b in inputs_to_check:
        s1 = shape_map.get(inp_a)
        s2 = shape_map.get(inp_b)
        if s1 is None or s2 is None:
            continue
        conflicts = can_broadcast(s1, s2)
        if conflicts:
            conflict_count += 1
            print(f"  *** BROADCAST CONFLICT ***")
            print(f"    node: {node.op_type}  name={node.name!r}")
            print(f"    {inp_a!r}: {s1}")
            print(f"    {inp_b!r}: {s2}")
            print(f"    conflicts: {conflicts}")
            print()

if conflict_count == 0:
    print("  No concrete broadcast conflicts found (some shapes may be dynamic/unknown).")

# ── 5. value_info 数確認 (dynamic rank への影響) ──────────────────────────
print("\n" + "="*70)
print("=== 5. value_info summary ===")
print(f"  value_info count: {len(m.graph.value_info)}")

# ── 6. Sentis で NullRef を起こしやすい属性パターン ────────────────────
print("\n" + "="*70)
print("=== 6. Potentially problematic nodes (Sentis quirks) ===")
for node in m.graph.node:
    # GroupNormalization: Sentis は opset 18 で追加、古いバージョンは未対応
    if node.op_type == "GroupNormalization":
        attrs = {a.name: int(a.i) for a in node.attribute if a.type == AttributeProto.INT}
        print(f"  GroupNormalization: name={node.name!r} attrs={attrs}")
    # Attention, MultiHeadAttention: contrib op の可能性
    if node.op_type in ("Attention", "MultiHeadAttention", "RotaryEmbedding"):
        print(f"  *** Custom/contrib op: {node.op_type} name={node.name!r} ***")
    # ReduceMean with axes as input (opset 18+)
    if node.op_type in ("ReduceSum", "ReduceMean", "ReduceMax", "ReduceMin") and opset_version >= 18:
        # opset 18+ では axes が入力 (input[1])、古い Sentis は属性しか見ない可能性
        if len(node.input) > 1 and node.input[1]:
            print(f"  {node.op_type} with axes as input (opset 18+): "
                  f"name={node.name!r}, axes_input={node.input[1]!r}")

print("\nDone.")
