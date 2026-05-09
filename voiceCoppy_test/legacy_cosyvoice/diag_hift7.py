#!/usr/bin/env python3
"""
diag_hift7.py — rank-4 value_info テンソルの下流トレース
"expecting 4, got 3" の具体的ノードを特定する

root cause 候補:
  Conv.InferPartial が shapeKernel.DeclareRank(shapeX.rank=3) を呼ぶとき
  kernel(W) が rank-4 として既知だと → "expecting 4, got 3"

"""
import onnx
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL = REPO_ROOT / "voice_Horror_Game" / "Assets" / "SentisSpike" / "Models" / "hift.fixed.fp32.onnx"

print(f"Loading {MODEL}...")
m = onnx.load(str(MODEL))

RANK4_VI = {'stft', 'val_884', 'val_885', 'complex_1', 'transpose_8', 'val_886', 'val_889'}

# ─── 1. rank-4 テンソルを直接消費するノード ───────────────────────────────────
print("\n=== rank-4 value_info テンソルを消費するノード ===")
for node in m.graph.node:
    for inp in node.input:
        if inp in RANK4_VI:
            print(f"  op={node.op_type}, inp={inp!r}, outputs={list(node.output)}, name={node.name!r}")

# ─── 2. vi_map 構築（全テンソルの rank） ─────────────────────────────────────
vi_map = {}
for init in m.graph.initializer:
    vi_map[init.name] = len(init.dims)
for vi in m.graph.value_info:
    if vi.type.HasField("tensor_type") and vi.type.tensor_type.HasField("shape"):
        vi_map[vi.name] = len(vi.type.tensor_type.shape.dim)
for inp in m.graph.input:
    if inp.type.HasField("tensor_type") and inp.type.tensor_type.HasField("shape"):
        vi_map[inp.name] = len(inp.type.tensor_type.shape.dim)

# ─── 3. Conv ノードのうち weight が rank != 3 のもの ─────────────────────────
print("\n=== Conv ノードの weight rank チェック (X.rank 推定 vs W.rank) ===")
conv_issues = []
for node in m.graph.node:
    if node.op_type in ("Conv", "ConvTranspose"):
        if len(node.input) < 2:
            continue
        x_name = node.input[0]
        w_name = node.input[1]
        x_rank = vi_map.get(x_name, "?")
        w_rank = vi_map.get(w_name, "?")
        if isinstance(x_rank, int) and isinstance(w_rank, int) and x_rank != w_rank:
            print(f"  MISMATCH op={node.op_type}, X={x_name!r}(rank={x_rank}), W={w_name!r}(rank={w_rank}), out={node.output[0]!r}")
            conv_issues.append((node.op_type, x_name, x_rank, w_name, w_rank))
print(f"  合計 {len(conv_issues)} 件の rank 不一致 Conv")

# ─── 4. rank-4 テンソルを出力する全ノードをトレース（深さ2まで） ─────────────
print("\n=== rank-4 テンソル生成→消費の全チェーン ===")

# まず全ノードの出力 → rank の逆引きマップ
output_to_node = {}
for node in m.graph.node:
    for out in node.output:
        output_to_node[out] = node

# rank-4 value_info の生成元
rank4_all = set()
for vi in m.graph.value_info:
    if (vi.type.HasField("tensor_type") and vi.type.tensor_type.HasField("shape")
            and len(vi.type.tensor_type.shape.dim) == 4):
        rank4_all.add(vi.name)

print(f"value_info の rank-4 テンソル数: {len(rank4_all)}")
for name in sorted(rank4_all):
    gen = output_to_node.get(name)
    if gen:
        print(f"\n  生成: op={gen.op_type}, out={name!r}")
        # この rank-4 テンソルを消費するノード
        for node in m.graph.node:
            for i, inp in enumerate(node.input):
                if inp == name:
                    print(f"    消費: op={node.op_type}, input_index={i}, outputs={list(node.output)}, name={node.name!r}")
                    # 消費先の出力 rank
                    for out in node.output:
                        r = vi_map.get(out, "?")
                        print(f"      → 出力 {out!r}: rank={r}")

# ─── 5. Reshape ノードのうち 4→3 になるもの ─────────────────────────────────
print("\n=== Reshape: rank-4 入力 → rank-3 出力 ===")
for node in m.graph.node:
    if node.op_type == "Reshape":
        if len(node.input) < 1 or len(node.output) < 1:
            continue
        in_r = vi_map.get(node.input[0], "?")
        out_r = vi_map.get(node.output[0], "?")
        if in_r == 4 or out_r == 3:
            print(f"  Reshape: input {node.input[0]!r}(rank={in_r}) → output {node.output[0]!r}(rank={out_r})")
