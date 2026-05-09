#!/usr/bin/env python3
"""
diag_hift6.py — "expecting 4, got 3" の原因を特定する
Sentis でのエラー: m_Rank=4 のテンソルに DeclareRank(3) → Conv で shapeKernel.DeclareRank(shapeX.rank=3)

調査対象:
1. graph.input に rank-4 shape で宣言されている initializer (Conv weight など)
2. graph.input の rank-4 テンソルを weight として使う Conv ノード
3. value_info に残っている rank-4 エントリ (step4 で除去漏れ)
4. 全 Conv / ConvTranspose ノードの input[1] (W) の rank を確認
"""
import onnx
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL = REPO_ROOT / "voice_Horror_Game" / "Assets" / "SentisSpike" / "Models" / "hift.fixed.fp32.onnx"

print(f"Loading {MODEL}...")
m = onnx.load(str(MODEL))

# ─── 全テンソル rank マップ（優先順: graph.input > value_info > initializer） ───
vi_map = {}  # name → (rank, source)

for init in m.graph.initializer:
    vi_map[init.name] = (len(init.dims), "initializer")

for vi in m.graph.value_info:
    if vi.type.HasField("tensor_type") and vi.type.tensor_type.HasField("shape"):
        vi_map[vi.name] = (len(vi.type.tensor_type.shape.dim), "value_info")

# graph.input は最後に上書き（Sentis はこれを使う）
graph_inputs = {}
for inp in m.graph.input:
    if inp.type.HasField("tensor_type") and inp.type.tensor_type.HasField("shape"):
        r = len(inp.type.tensor_type.shape.dim)
        dims = [d.dim_value if d.dim_value else (d.dim_param if d.dim_param else "?")
                for d in inp.type.tensor_type.shape.dim]
        graph_inputs[inp.name] = (r, dims)
        vi_map[inp.name] = (r, f"graph.input dims={dims}")

# ─── 1. graph.input で rank-4 のテンソル ───────────────────────────────────────
print("\n=== graph.input に rank-4 テンソル ===")
rank4_inputs = {n: (r, dims) for n, (r, dims) in graph_inputs.items() if r == 4}
if rank4_inputs:
    for n, (r, dims) in rank4_inputs.items():
        init_rank = None
        for init in m.graph.initializer:
            if init.name == n:
                init_rank = len(init.dims)
                break
        print(f"  {n!r}: graph.input rank=4 dims={dims}, initializer rank={init_rank}")
else:
    print("  なし")

# ─── 2. Conv / ConvTranspose の weight (input[1]) が rank-4 か ────────────────
print("\n=== Conv/ConvTranspose の weight が rank-4 (問題ケース) ===")
found_conv_rank4 = False
for node in m.graph.node:
    if node.op_type in ("Conv", "ConvTranspose"):
        if len(node.input) < 2:
            continue
        w = node.input[1]
        if w in rank4_inputs:
            print(f"  op={node.op_type}, output={list(node.output)}, weight={w!r}(rank-4)")
            found_conv_rank4 = True
if not found_conv_rank4:
    print("  なし (Conv weight で rank-4 は未検出)")

# ─── 3. value_info に残っている rank-4 エントリ ───────────────────────────────
print("\n=== value_info に残っている rank-4 テンソル (step4 除去漏れ) ===")
rank4_vi = []
for vi in m.graph.value_info:
    if vi.type.HasField("tensor_type") and vi.type.tensor_type.HasField("shape"):
        if len(vi.type.tensor_type.shape.dim) == 4:
            rank4_vi.append(vi.name)
            print(f"  {vi.name!r}: rank=4")
if not rank4_vi:
    print("  なし")

# ─── 4. graph.output に rank-4 エントリ ────────────────────────────────────────
print("\n=== graph.output に rank-4 テンソル ===")
rank4_out = []
for out in m.graph.output:
    if out.type.HasField("tensor_type") and out.type.tensor_type.HasField("shape"):
        if len(out.type.tensor_type.shape.dim) == 4:
            rank4_out.append(out.name)
            print(f"  {out.name!r}: rank=4")
if not rank4_out:
    print("  なし")

# ─── 5. initializer に rank-4 データ ──────────────────────────────────────────
print("\n=== initializer に rank-4 データ ===")
rank4_inits = []
for init in m.graph.initializer:
    if len(init.dims) == 4:
        rank4_inits.append((init.name, list(init.dims)))
        print(f"  {init.name!r}: dims={list(init.dims)}")
if not rank4_inits:
    print("  なし")

# ─── 6. graph.input と initializer のランク不一致 ─────────────────────────────
print("\n=== graph.input と initializer のランク不一致 ===")
init_by_name = {init.name: init for init in m.graph.initializer}
mismatch_count = 0
for n, (r_inp, dims_inp) in graph_inputs.items():
    if n in init_by_name:
        r_init = len(init_by_name[n].dims)
        if r_inp != r_init:
            print(f"  MISMATCH {n!r}: graph.input rank={r_inp} dims={dims_inp}, initializer rank={r_init} dims={list(init_by_name[n].dims)}")
            mismatch_count += 1
if mismatch_count == 0:
    print("  なし (全て一致)")

# ─── 7. graph.input の rank 分布 ──────────────────────────────────────────────
print("\n=== graph.input の rank 分布 ===")
from collections import Counter
rank_dist = Counter(r for r, _ in graph_inputs.values())
for r, cnt in sorted(rank_dist.items()):
    print(f"  rank-{r}: {cnt} テンソル")

# ─── 8. 最初の Conv ノードの詳細 ──────────────────────────────────────────────
print("\n=== 最初の Conv ノードの詳細 ===")
for node in m.graph.node:
    if node.op_type == "Conv":
        print(f"  outputs: {list(node.output)}")
        for i, inp in enumerate(node.input):
            if not inp:
                print(f"  input[{i}]: (empty)")
                continue
            r_init, src = vi_map.get(inp, ("?", "not found"))
            print(f"  input[{i}]={inp!r}: rank={r_init} source={src}")
        break
