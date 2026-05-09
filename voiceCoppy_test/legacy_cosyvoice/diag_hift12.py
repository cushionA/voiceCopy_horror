#!/usr/bin/env python3
"""
diag_hift12.py — Sentis InferPartial rank propagation シミュレーター v2
v11 の修正版:
  - ConstantOfShape を正しく扱う (output rank = len of shape values)
  - Shape → 常に rank-1 出力
  - Range → 常に rank-1 出力
  - ScatterElements → DeclareRank(data.rank) on indices & updates
  - ScatterND → DeclareRank(formula) on data
  - Expand, Broadcast, Cast 等を追加
  - 最初の衝突で止まらず全衝突を列挙する
"""
import sys
from pathlib import Path
from collections import defaultdict, deque

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL = REPO_ROOT / "voice_Horror_Game" / "Assets" / "SentisSpike" / "Models" / "hift.fixed.fp32.onnx"

try:
    import onnx
    from onnx import numpy_helper
    import numpy as np
except ImportError:
    print("pip install onnx  が必要です")
    sys.exit(1)

print(f"Loading {MODEL}...")
m = onnx.load(str(MODEL))

# ──────────────────────────────────────────────────────────────────────────────
# rank_map: tensor_name → int (rank) or None (unknown/DynamicRank)
# ──────────────────────────────────────────────────────────────────────────────
rank_map: dict = {}
conflicts = []   # 全衝突を収集

init_by_name = {}
for init in m.graph.initializer:
    r = len(init.dims)
    rank_map[init.name] = r
    init_by_name[init.name] = init

for inp in m.graph.input:
    if inp.name in rank_map:
        continue
    if inp.type.HasField("tensor_type") and inp.type.tensor_type.HasField("shape"):
        r = len(inp.type.tensor_type.shape.dim)
        rank_map[inp.name] = r

# ──────────────────────────────────────────────────────────────────────────────
# トポロジカルソート
# ──────────────────────────────────────────────────────────────────────────────
def topo_sort(nodes):
    produced: dict = {}
    for i, node in enumerate(nodes):
        for out in node.output:
            if out:
                produced[out] = i

    in_degree = [0] * len(nodes)
    adj = defaultdict(list)
    for i, node in enumerate(nodes):
        for inp in node.input:
            if inp and inp in produced:
                j = produced[inp]
                if j != i:
                    adj[j].append(i)
                    in_degree[i] += 1

    queue = deque(i for i in range(len(nodes)) if in_degree[i] == 0)
    order = []
    while queue:
        i = queue.popleft()
        order.append(i)
        for j in adj[i]:
            in_degree[j] -= 1
            if in_degree[j] == 0:
                queue.append(j)

    if len(order) != len(nodes):
        sorted_set = set(order)
        for i in range(len(nodes)):
            if i not in sorted_set:
                order.append(i)

    return [nodes[i] for i in order]

sorted_nodes = topo_sort(list(m.graph.node))

# ──────────────────────────────────────────────────────────────────────────────
# ヘルパー
# ──────────────────────────────────────────────────────────────────────────────
def declare_rank(tensor_name: str, new_rank: int, context: str) -> bool:
    """衝突があれば conflicts リストに追記して True を返す。止まらない。"""
    if not tensor_name:
        return False
    current = rank_map.get(tensor_name, None)
    if current is None:
        rank_map[tensor_name] = new_rank
        return False
    if current == new_rank:
        return False
    msg = (f"CONFLICT: tensor={tensor_name!r} existing={current} "
           f"DeclareRank({new_rank}) by {context}")
    conflicts.append(msg)
    print(f"\n!!! RANK CONFLICT !!!")
    print(f"  tensor:   {tensor_name!r}")
    print(f"  existing: rank={current}")
    print(f"  DeclareRank({new_rank}) called by: {context}")
    return True

def set_output_rank(tensor_name: str, rank):
    if not tensor_name or rank is None:
        return
    existing = rank_map.get(tensor_name, None)
    if existing is None:
        rank_map[tensor_name] = rank
    elif existing != rank:
        msg = (f"OUTPUT CONFLICT: tensor={tensor_name!r} existing={existing} "
               f"trying to set rank={rank}")
        conflicts.append(msg)
        print(f"\n!!! OUTPUT RANK CONFLICT !!!")
        print(f"  tensor:   {tensor_name!r}")
        print(f"  existing: rank={existing}")
        print(f"  trying to set rank={rank}")

def get_rank(tensor_name: str):
    return rank_map.get(tensor_name, None) if tensor_name else None

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

def get_init_values(name):
    if name in init_by_name:
        return numpy_helper.to_array(init_by_name[name])
    return None

# ──────────────────────────────────────────────────────────────────────────────
# 全ノードをトポロジカル順で処理
# ──────────────────────────────────────────────────────────────────────────────
print(f"\nProcessing {len(sorted_nodes)} nodes in topological order...")
print(f"Initial known ranks: {sum(1 for v in rank_map.values() if v is not None)}")

for node_idx, node in enumerate(sorted_nodes):
    op = node.op_type
    inp = list(node.input)
    out = list(node.output)
    attrs = get_attrs(node)
    label = f"op={op}, out={out[:1]}, name={node.name!r}"

    # ── Transpose ──────────────────────────────────────────────────────────
    if op == "Transpose":
        perm = attrs.get("perm", None)
        x = inp[0] if inp else ""
        if perm is not None:
            perm_len = len(perm)
            declare_rank(x, perm_len, label)
            set_output_rank(out[0] if out else "", perm_len)
        else:
            r = get_rank(x)
            if r is not None:
                set_output_rank(out[0] if out else "", r)

    # ── Concat ─────────────────────────────────────────────────────────────
    elif op == "Concat":
        known_ranks = [get_rank(i) for i in inp if i and get_rank(i) is not None]
        if known_ranks:
            max_rank = max(known_ranks)
            for i in inp:
                if i:
                    declare_rank(i, max_rank, label)
            set_output_rank(out[0] if out else "", max_rank)

    # ── Tile ───────────────────────────────────────────────────────────────
    elif op == "Tile":
        x = inp[0] if len(inp) > 0 else ""
        repeats_name = inp[1] if len(inp) > 1 else ""
        repeats_data = get_init_values(repeats_name) if repeats_name else None
        if repeats_data is not None:
            rep_len = len(repeats_data)
            declare_rank(x, rep_len, label)
            set_output_rank(out[0] if out else "", rep_len)
        else:
            r = get_rank(x)
            set_output_rank(out[0] if out else "", r)

    # ── Resize ─────────────────────────────────────────────────────────────
    elif op == "Resize":
        x = inp[0] if len(inp) > 0 else ""
        scales_name = inp[2] if len(inp) > 2 else ""
        sizes_name = inp[3] if len(inp) > 3 else ""
        axes_name = inp[4] if len(inp) > 4 else ""
        axes_data = get_init_values(axes_name) if axes_name else None
        if axes_data is None and not axes_name:
            sz_name = sizes_name if sizes_name else scales_name
            sz_data = get_init_values(sz_name) if sz_name else None
            if sz_data is not None:
                sz_len = len(sz_data)
                declare_rank(x, sz_len, label)
                set_output_rank(out[0] if out else "", sz_len)
            else:
                r = get_rank(x)
                set_output_rank(out[0] if out else "", r)
        else:
            r = get_rank(x)
            set_output_rank(out[0] if out else "", r)

    # ── Pad ────────────────────────────────────────────────────────────────
    elif op == "Pad":
        x = inp[0] if len(inp) > 0 else ""
        pads_name = inp[1] if len(inp) > 1 else ""
        axes_name = inp[3] if len(inp) > 3 else ""
        axes_data = get_init_values(axes_name) if axes_name else None
        if axes_data is None and not axes_name:
            pads_data = get_init_values(pads_name) if pads_name else None
            if pads_data is not None:
                expected_rank = len(pads_data) // 2
                declare_rank(x, expected_rank, label)
                set_output_rank(out[0] if out else "", expected_rank)
            else:
                r = get_rank(x)
                set_output_rank(out[0] if out else "", r)
        else:
            r = get_rank(x)
            set_output_rank(out[0] if out else "", r)

    # ── STFT ───────────────────────────────────────────────────────────────
    elif op == "STFT":
        set_output_rank(out[0] if out else "", 4)

    # ── DFT ────────────────────────────────────────────────────────────────
    elif op == "DFT":
        x = inp[0] if inp else ""
        r = get_rank(x)
        set_output_rank(out[0] if out else "", r)

    # ── Squeeze ────────────────────────────────────────────────────────────
    elif op == "Squeeze":
        x = inp[0] if len(inp) > 0 else ""
        axes_name = inp[1] if len(inp) > 1 else ""
        axes_data = get_init_values(axes_name) if axes_name else None
        r_in = get_rank(x)
        if axes_data is not None:
            n_axes = len(axes_data)
            if r_in is not None:
                set_output_rank(out[0] if out else "", r_in - n_axes)
        elif attrs.get("axes") is not None:
            n_axes = len(attrs["axes"])
            if r_in is not None:
                set_output_rank(out[0] if out else "", r_in - n_axes)
        # else: dynamic axes, output rank unknown

    # ── Unsqueeze ──────────────────────────────────────────────────────────
    elif op == "Unsqueeze":
        x = inp[0] if len(inp) > 0 else ""
        axes_name = inp[1] if len(inp) > 1 else ""
        axes_data = get_init_values(axes_name) if axes_name else None
        r_in = get_rank(x)
        if axes_data is not None and r_in is not None:
            set_output_rank(out[0] if out else "", r_in + len(axes_data))
        elif attrs.get("axes") is not None:
            n_axes = len(attrs["axes"])
            if r_in is not None:
                set_output_rank(out[0] if out else "", r_in + n_axes)

    # ── Gather ─────────────────────────────────────────────────────────────
    elif op == "Gather":
        x = inp[0] if len(inp) > 0 else ""
        idx = inp[1] if len(inp) > 1 else ""
        r_x = get_rank(x)
        r_idx = get_rank(idx)
        if r_x is not None and r_idx is not None:
            set_output_rank(out[0] if out else "", r_x - 1 + r_idx)

    # ── GatherElements ─────────────────────────────────────────────────────
    elif op == "GatherElements":
        # DeclareRank(shapeInput.rank) on indices
        x = inp[0] if len(inp) > 0 else ""
        idx = inp[1] if len(inp) > 1 else ""
        r_x = get_rank(x)
        if r_x is not None:
            declare_rank(idx, r_x, label)
        set_output_rank(out[0] if out else "", r_x)

    # ── ScatterElements ────────────────────────────────────────────────────
    elif op == "ScatterElements":
        # Sentis: DeclareRank(shapeInput.rank) on indices AND updates
        x = inp[0] if len(inp) > 0 else ""
        idx = inp[1] if len(inp) > 1 else ""
        upd = inp[2] if len(inp) > 2 else ""
        r_x = get_rank(x)
        if r_x is not None:
            declare_rank(idx, r_x, label + " [idx]")
            declare_rank(upd, r_x, label + " [upd]")
        # output rank = data rank
        set_output_rank(out[0] if out else "", r_x)

    # ── ScatterND ──────────────────────────────────────────────────────────
    elif op == "ScatterND":
        # Sentis InferPartial:
        #   if (shapeIndices.hasRank && shapeUpdates.hasRank && shapeIndices[-1].isValue)
        #       shapeInput.DeclareRank(shapeUpdates.rank - (shapeIndices.rank - shapeIndices[-1].value - 1))
        x = inp[0] if len(inp) > 0 else ""
        idx = inp[1] if len(inp) > 1 else ""
        upd = inp[2] if len(inp) > 2 else ""
        r_x = get_rank(x)
        r_idx = get_rank(idx)
        r_upd = get_rank(upd)
        # Try to get idx last-dim value from initializer
        if r_idx is not None and r_upd is not None:
            idx_data = get_init_values(idx)
            if idx_data is not None and idx_data.ndim > 0:
                # last dim = idx_data.shape[-1]
                last_dim = idx_data.shape[-1]
                declared_rank = r_upd - (r_idx - last_dim - 1)
                declare_rank(x, declared_rank, label + f" [ScatterND formula r_upd={r_upd} r_idx={r_idx} last_dim={last_dim}]")
        # output rank = data rank
        set_output_rank(out[0] if out else "", r_x)

    # ── GatherND ───────────────────────────────────────────────────────────
    elif op == "GatherND":
        # output rank = data_rank + idx_rank - idx[-1] - 1 (complex, skip declare)
        pass

    # ── Slice ──────────────────────────────────────────────────────────────
    elif op == "Slice":
        x = inp[0] if inp else ""
        r = get_rank(x)
        set_output_rank(out[0] if out else "", r)

    # ── Reshape ────────────────────────────────────────────────────────────
    elif op == "Reshape":
        shape_name = inp[1] if len(inp) > 1 else ""
        shape_data = get_init_values(shape_name) if shape_name else None
        if shape_data is not None:
            set_output_rank(out[0] if out else "", len(shape_data))
        # else: output rank unknown (dynamic shape)

    # ── ConstantOfShape ────────────────────────────────────────────────────
    elif op == "ConstantOfShape":
        # output rank = number of elements in shape input
        shape_name = inp[0] if inp else ""
        shape_data = get_init_values(shape_name) if shape_name else None
        if shape_data is not None:
            # shape_data is a 1-D array of dims, len = output rank
            set_output_rank(out[0] if out else "", len(shape_data))
        else:
            # Shape is dynamic (e.g., from Concat of Shape outputs)
            # We can't determine rank statically — leave unknown
            pass

    # ── Shape ──────────────────────────────────────────────────────────────
    elif op == "Shape":
        # Always outputs rank-1 (a 1-D tensor of dims)
        set_output_rank(out[0] if out else "", 1)

    # ── Range ──────────────────────────────────────────────────────────────
    elif op == "Range":
        # Always outputs rank-1
        set_output_rank(out[0] if out else "", 1)

    # ── Flatten ────────────────────────────────────────────────────────────
    elif op == "Flatten":
        # Always outputs rank-2
        set_output_rank(out[0] if out else "", 2)

    # ── NonZero ────────────────────────────────────────────────────────────
    elif op == "NonZero":
        # Always outputs rank-2
        set_output_rank(out[0] if out else "", 2)

    # ── Conv / ConvTranspose ────────────────────────────────────────────────
    elif op in ("Conv", "ConvTranspose"):
        x = inp[0] if len(inp) > 0 else ""
        r = get_rank(x)
        if r is not None:
            set_output_rank(out[0] if out else "", r)

    # ── Elementwise / unary (output rank = input rank) ─────────────────────
    elif op in ("Add", "Sub", "Mul", "Div", "Pow", "Max", "Min", "Abs",
                "Sqrt", "Exp", "Log", "Neg", "Relu", "Sigmoid", "Tanh",
                "LeakyRelu", "Elu", "Selu", "Gelu", "Mish",
                "Erf", "Floor", "Ceil", "Round", "Sign",
                "Not", "And", "Or", "Xor",
                "Equal", "Greater", "GreaterOrEqual", "Less", "LessOrEqual",
                "Cast", "CastLike",
                "Identity", "Dropout",
                "BatchNormalization", "LayerNormalization", "InstanceNormalization",
                "GroupNormalization",
                "Clip", "IsNaN", "IsInf",
                "CumSum",
                "Softmax", "LogSoftmax",
                "PRelu", "HardSigmoid", "HardSwish",
                "Shrink", "ThresholdedRelu",
                "Where",
               ):
        # output rank = max rank of tensor inputs
        candidate_ranks = []
        for i in inp:
            if i:
                r = get_rank(i)
                if r is not None:
                    candidate_ranks.append(r)
        if candidate_ranks:
            set_output_rank(out[0] if out else "", max(candidate_ranks))
            for o in out[1:]:
                if o:
                    set_output_rank(o, max(candidate_ranks))

    # ── Expand ─────────────────────────────────────────────────────────────
    elif op == "Expand":
        x = inp[0] if len(inp) > 0 else ""
        shape_name = inp[1] if len(inp) > 1 else ""
        r_x = get_rank(x)
        shape_data = get_init_values(shape_name) if shape_name else None
        if shape_data is not None:
            r = max(r_x or 0, len(shape_data))
            set_output_rank(out[0] if out else "", r)
        else:
            set_output_rank(out[0] if out else "", r_x)

    # ── MatMul / Gemm ───────────────────────────────────────────────────────
    elif op in ("MatMul", "Gemm"):
        x = inp[0] if len(inp) > 0 else ""
        y = inp[1] if len(inp) > 1 else ""
        r_x = get_rank(x)
        r_y = get_rank(y)
        if op == "Gemm":
            set_output_rank(out[0] if out else "", 2)
        elif r_x is not None and r_y is not None:
            set_output_rank(out[0] if out else "", max(r_x, r_y))
        elif r_x is not None:
            set_output_rank(out[0] if out else "", r_x)

    # ── Constant ────────────────────────────────────────────────────────────
    elif op == "Constant":
        for a in node.attribute:
            if a.name == "value" and a.type == onnx.AttributeProto.TENSOR:
                r = len(a.t.dims)
                set_output_rank(out[0] if out else "", r)
                break

    # ── ReduceX (reduction ops) ─────────────────────────────────────────────
    elif op in ("ReduceSum", "ReduceMean", "ReduceMax", "ReduceMin",
                "ReduceProd", "ReduceL1", "ReduceL2", "ReduceLogSum",
                "ReduceLogSumExp", "ReduceSumSquare"):
        x = inp[0] if inp else ""
        r_in = get_rank(x)
        keepdims = attrs.get("keepdims", 1)
        axes = attrs.get("axes", None)
        if r_in is not None:
            if keepdims:
                set_output_rank(out[0] if out else "", r_in)
            elif axes is not None:
                set_output_rank(out[0] if out else "", r_in - len(axes))
            # else: dynamic, skip

    # ── DepthToSpace / SpaceToDepth ─────────────────────────────────────────
    elif op in ("DepthToSpace", "SpaceToDepth"):
        # Sentis DeclareRank(4) on input
        x = inp[0] if inp else ""
        declare_rank(x, 4, label)
        set_output_rank(out[0] if out else "", 4)

    # ── Split ───────────────────────────────────────────────────────────────
    elif op == "Split":
        x = inp[0] if inp else ""
        r = get_rank(x)
        for o in out:
            if o:
                set_output_rank(o, r)

    # ── Pad (already handled above) / general fallback ──────────────────────
    else:
        if inp and out:
            r = get_rank(inp[0])
            if r is not None:
                set_output_rank(out[0], r)
            for o in out[1:]:
                if o:
                    set_output_rank(o, r)

print(f"\nDone processing {len(sorted_nodes)} nodes.")
print(f"Final known ranks: {sum(1 for v in rank_map.values() if v is not None)}")

# ── ランク分布 ──────────────────────────────────────────────────────────────
from collections import Counter
dist = Counter(v for v in rank_map.values() if v is not None)
print("Rank distribution:")
for r, cnt in sorted(dist.items()):
    print(f"  rank-{r}: {cnt}")

# ── 全衝突サマリー ──────────────────────────────────────────────────────────
print(f"\n=== CONFLICT SUMMARY ({len(conflicts)} total) ===")
for i, c in enumerate(conflicts, 1):
    print(f"  [{i}] {c}")

if not conflicts:
    print("[OK] シミュレーション上は rank 衝突なし。")
    print("     実際の Sentis エラーは InferPartial の動的分岐依存の可能性あり。")
else:
    print("\n^^^ これらが 'expecting 4, got 3' の候補です ^^^")
    # rank-4 → DeclareRank(3) のパターンを強調
    print("\n=== rank-4 → DeclareRank(3) 候補 ===")
    for c in conflicts:
        if "existing=4" in c and "DeclareRank(3)" in c:
            print(f"  *** {c}")
