#!/usr/bin/env python3
"""
diag_hift9.py — Sentis の動的 rank 推論を追いかける

value_info に存在しない中間テンソルが rank-4 になってから
DeclareRank(3) を受ける可能性を調べる。

対象: 'stft' を生成する Transpose ノードの詳細 + ONNX STFT ノードの有無
"""
import onnx
from onnx import numpy_helper
import numpy as np
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL_FIXED = REPO_ROOT / "voice_Horror_Game" / "Assets" / "SentisSpike" / "Models" / "hift.fixed.fp32.onnx"
MODEL_SRC   = REPO_ROOT / "voiceCoppy_test" / "onnx_export" / "hift.fp32.onnx"

print(f"Loading fixed model...")
m = onnx.load(str(MODEL_FIXED))

def get_attrs(node):
    attrs = {}
    for a in node.attribute:
        if a.type == onnx.AttributeProto.INT:
            attrs[a.name] = a.i
        elif a.type == onnx.AttributeProto.INTS:
            attrs[a.name] = list(a.ints)
        elif a.type == onnx.AttributeProto.FLOAT:
            attrs[a.name] = a.f
        elif a.type == onnx.AttributeProto.STRING:
            attrs[a.name] = a.s
    return attrs

vi_map = {}
for init in m.graph.initializer:
    vi_map[init.name] = (len(init.dims), "init")
for vi in m.graph.value_info:
    if vi.type.HasField("tensor_type") and vi.type.tensor_type.HasField("shape"):
        vi_map[vi.name] = (len(vi.type.tensor_type.shape.dim), "value_info")
for inp in m.graph.input:
    if inp.type.HasField("tensor_type") and inp.type.tensor_type.HasField("shape"):
        vi_map[inp.name] = (len(inp.type.tensor_type.shape.dim), "graph.input")

# ─── 1. 'stft' を生成するノード詳細 ─────────────────────────────────────────
print("\n=== 'stft' 生成ノード詳細 ===")
for node in m.graph.node:
    if 'stft' in node.output:
        print(f"  op={node.op_type}, name={node.name!r}")
        attrs = get_attrs(node)
        print(f"  attrs={attrs}")
        for i, inp in enumerate(node.input):
            r, src = vi_map.get(inp, ("?", "not found"))
            print(f"  input[{i}]={inp!r}: rank={r} source={src}")
        for i, out in enumerate(node.output):
            r, src = vi_map.get(out, ("?", "not found"))
            print(f"  output[{i}]={out!r}: rank={r} source={src}")
        break

# ─── 2. ONNX の op_type 一覧（STFT が含まれるか） ────────────────────────────
print("\n=== op_type 一覧（ユニーク） ===")
from collections import Counter
op_counts = Counter(node.op_type for node in m.graph.node)
for op, cnt in sorted(op_counts.items()):
    print(f"  {op}: {cnt}")

# ─── 3. 全 Transpose ノードの perm 長 と input rank を比較 ──────────────────
print("\n=== 全 Transpose ノードの詳細 ===")
for node in m.graph.node:
    if node.op_type == "Transpose":
        attrs = get_attrs(node)
        perm = attrs.get("perm", None)
        inp = node.input[0] if node.input else ""
        out = node.output[0] if node.output else ""
        inp_r, inp_src = vi_map.get(inp, ("?", "?"))
        out_r, out_src = vi_map.get(out, ("?", "?"))
        perm_len = len(perm) if perm is not None else "?"
        flag = "⚠️ " if (isinstance(inp_r, int) and isinstance(perm_len, int) and inp_r != perm_len) else "   "
        print(f"  {flag}out={out!r}(rank={out_r}/{out_src}), perm={perm}(len={perm_len}), inp={inp!r}(rank={inp_r}/{inp_src})")

# ─── 4. value_info 未登録テンソルを出力する Conv ─────────────────────────────
# Sentis の動的推論で rank-4 になりうる Conv 出力を探す
print("\n=== Conv 出力が value_info に未登録のもの ===")
for node in m.graph.node:
    if node.op_type in ("Conv", "ConvTranspose"):
        for out in node.output:
            if out not in vi_map:
                print(f"  {node.op_type} out={out!r} → NOT in vi_map")

# ─── 5. 全 Squeeze ノード（追加済みも含む）の入力 rank ─────────────────────
print("\n=== Squeeze ノード詳細（ランク確認） ===")
for node in m.graph.node:
    if node.op_type == "Squeeze":
        inp = node.input[0] if len(node.input) > 0 else ""
        inp_r, inp_src = vi_map.get(inp, ("?", "?"))
        out = node.output[0] if len(node.output) > 0 else ""
        out_r, out_src = vi_map.get(out, ("?", "?"))
        axes_inp = node.input[1] if len(node.input) > 1 else "(attr)"
        flag = "⚠️ " if inp_r == 4 else "   "
        print(f"  {flag}inp={inp!r}(rank={inp_r}), axes={axes_inp!r}, out={out!r}(rank={out_r})")

# ─── 6. 元モデル（src）の STFT 周辺 ──────────────────────────────────────────
print(f"\nLoading source model: {MODEL_SRC}")
try:
    m_src = onnx.load(str(MODEL_SRC))
    vi_src = {}
    for init in m_src.graph.initializer:
        vi_src[init.name] = len(init.dims)
    for vi in m_src.graph.value_info:
        if vi.type.HasField("tensor_type") and vi.type.tensor_type.HasField("shape"):
            vi_src[vi.name] = len(vi.type.tensor_type.shape.dim)

    print("\n=== 元モデルの 'stft' 前後 ===")
    for node in m_src.graph.node:
        if 'stft' in node.output or 'stft' in node.input:
            print(f"  op={node.op_type}, inp={list(node.input)}, out={list(node.output)}")
            attrs = get_attrs(node)
            if attrs:
                print(f"    attrs={attrs}")

    print("\n=== 元モデルの op_type 一覧（ユニーク） ===")
    op_counts_src = Counter(node.op_type for node in m_src.graph.node)
    for op, cnt in sorted(op_counts_src.items()):
        print(f"  {op}: {cnt}")
except Exception as e:
    print(f"  ERROR: {e}")
