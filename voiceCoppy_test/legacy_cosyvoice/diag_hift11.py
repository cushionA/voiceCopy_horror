#!/usr/bin/env python3
"""
diag_hift11.py — Sentis InferPartial rank propagation シミュレーター
"expecting 4, got 3" を引き起こすノードを特定する

Sentis の InferPartial が DeclareRank を呼ぶ主要 op を Python で再現し、
value_info なし状態でトポロジー順に処理して最初の rank 衝突を報告する。
"""
import sys
from pathlib import Path
from collections import defaultdict

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
rank_map: dict[str, int | None] = {}

# initializers の rank を登録
init_by_name = {}
for init in m.graph.initializer:
    r = len(init.dims)
    rank_map[init.name] = r
    init_by_name[init.name] = init

# graph.input の rank を登録
for inp in m.graph.input:
    if inp.name in rank_map:
        continue  # initializer が既に登録済みなら skip
    if inp.type.HasField("tensor_type") and inp.type.tensor_type.HasField("shape"):
        r = len(inp.type.tensor_type.shape.dim)
        rank_map[inp.name] = r

# ──────────────────────────────────────────────────────────────────────────────
# ノードのトポロジカルソート (ONNX の定義順に依存せず再計算)
# ──────────────────────────────────────────────────────────────────────────────
def topo_sort(nodes):
    """Kahn's algorithm で ONNX ノードをトポロジカルソート"""
    produced: dict[str, int] = {}  # tensor → node index
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

    from collections import deque
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
        print(f"[WARN] topo_sort: {len(nodes) - len(order)} nodes could not be sorted (cycle or disconnected)")
        # append remaining
        sorted_set = set(order)
        for i in range(len(nodes)):
            if i not in sorted_set:
                order.append(i)

    return [nodes[i] for i in order]

sorted_nodes = topo_sort(list(m.graph.node))

# ──────────────────────────────────────────────────────────────────────────────
# DeclareRank: 衝突があれば報告して返す
# ──────────────────────────────────────────────────────────────────────────────
conflict_found = False

def declare_rank(tensor_name: str, new_rank: int, context: str) -> bool:
    """
    Sentis の DeclareRank(newRank) を模倣。
    rank_map[tensor_name] が既に newRank と異なる既知値なら衝突を報告する。
    Returns True if conflict detected.
    """
    global conflict_found
    if not tensor_name:
        return False
    current = rank_map.get(tensor_name, None)
    if current is None:
        rank_map[tensor_name] = new_rank
        return False
    if current == new_rank:
        return False
    # CONFLICT
    print(f"\n!!! RANK CONFLICT DETECTED !!!")
    print(f"  tensor:   {tensor_name!r}")
    print(f"  existing: rank={current}")
    print(f"  DeclareRank({new_rank}) called by: {context}")
    conflict_found = True
    return True

def set_output_rank(tensor_name: str, rank: int | None):
    """出力テンソルの rank を設定 (上書きはしない)"""
    if not tensor_name or rank is None:
        return
    existing = rank_map.get(tensor_name, None)
    if existing is None:
        rank_map[tensor_name] = rank
    elif existing != rank:
        # 出力側の衝突
        print(f"\n!!! OUTPUT RANK CONFLICT !!!")
        print(f"  tensor:   {tensor_name!r}")
        print(f"  existing: rank={existing}")
        print(f"  trying to set rank={rank}")

def get_rank(tensor_name: str) -> int | None:
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
    return attrs

def get_init_values(name):
    """initializer の値を numpy array で返す。なければ None。"""
    if name in init_by_name:
        return numpy_helper.to_array(init_by_name[name])
    return None

# ──────────────────────────────────────────────────────────────────────────────
# トポロジカル順でノードを処理
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
            conflict = declare_rank(x, perm_len, label)
            if conflict:
                break
            # output rank
            set_output_rank(out[0] if out else "", perm_len)
        else:
            # no perm → reverse
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
                    conflict = declare_rank(i, max_rank, label)
                    if conflict:
                        break
            if conflict_found:
                break
            set_output_rank(out[0] if out else "", max_rank)

    # ── Tile ───────────────────────────────────────────────────────────────
    elif op == "Tile":
        x = inp[0] if len(inp) > 0 else ""
        repeats_name = inp[1] if len(inp) > 1 else ""
        repeats_data = get_init_values(repeats_name) if repeats_name else None
        if repeats_data is not None:
            rep_len = len(repeats_data)
            conflict = declare_rank(x, rep_len, label)
            if conflict:
                break
            set_output_rank(out[0] if out else "", rep_len)
        else:
            # repeats not constant: output rank = input rank
            r = get_rank(x)
            set_output_rank(out[0] if out else "", r)

    # ── Resize ─────────────────────────────────────────────────────────────
    elif op == "Resize":
        x = inp[0] if len(inp) > 0 else ""
        scales_name = inp[2] if len(inp) > 2 else ""
        sizes_name = inp[3] if len(inp) > 3 else ""
        axes_name = inp[4] if len(inp) > 4 else ""  # opset 18
        # Check if axes input is empty (meaning no axes = all dims)
        axes_data = get_init_values(axes_name) if axes_name else None
        if axes_data is None and not axes_name:
            # no axes: use scales or sizes length
            sz_name = sizes_name if sizes_name else scales_name
            sz_data = get_init_values(sz_name) if sz_name else None
            if sz_data is not None:
                sz_len = len(sz_data)
                conflict = declare_rank(x, sz_len, label)
                if conflict:
                    break
                set_output_rank(out[0] if out else "", sz_len)
            else:
                r = get_rank(x)
                set_output_rank(out[0] if out else "", r)
        else:
            # axes specified: output rank = input rank
            r = get_rank(x)
            set_output_rank(out[0] if out else "", r)

    # ── Pad ────────────────────────────────────────────────────────────────
    elif op == "Pad":
        x = inp[0] if len(inp) > 0 else ""
        pads_name = inp[1] if len(inp) > 1 else ""
        axes_name = inp[3] if len(inp) > 3 else ""  # opset 18 axes
        axes_data = get_init_values(axes_name) if axes_name else None
        if axes_data is None and not axes_name:
            # no axes
            pads_data = get_init_values(pads_name) if pads_name else None
            if pads_data is not None:
                expected_rank = len(pads_data) // 2
                conflict = declare_rank(x, expected_rank, label)
                if conflict:
                    break
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
        elif r_in is not None:
            # dynamic axes: output rank unknown
            pass

    # ── Unsqueeze ──────────────────────────────────────────────────────────
    elif op == "Unsqueeze":
        x = inp[0] if len(inp) > 0 else ""
        axes_name = inp[1] if len(inp) > 1 else ""
        axes_data = get_init_values(axes_name) if axes_name else None
        r_in = get_rank(x)
        if axes_data is not None and r_in is not None:
            set_output_rank(out[0] if out else "", r_in + len(axes_data))
        elif attrs.get("axes"):
            axes_attr = attrs.get("axes", [])
            if r_in is not None:
                set_output_rank(out[0] if out else "", r_in + len(axes_attr))

    # ── Gather ─────────────────────────────────────────────────────────────
    elif op == "Gather":
        x = inp[0] if len(inp) > 0 else ""
        idx = inp[1] if len(inp) > 1 else ""
        r_x = get_rank(x)
        r_idx = get_rank(idx)
        if r_x is not None and r_idx is not None:
            set_output_rank(out[0] if out else "", r_x - 1 + r_idx)
        elif r_x is not None:
            # idx rank unknown
            pass

    # ── GatherND ───────────────────────────────────────────────────────────
    elif op == "GatherND":
        x = inp[0] if len(inp) > 0 else ""
        idx = inp[1] if len(inp) > 1 else ""
        r_x = get_rank(x)
        r_idx = get_rank(idx)
        batch_dims = attrs.get("batch_dims", 0)
        if r_x is not None and r_idx is not None:
            # output rank = r_x + r_idx - r_idx[-1] - 1 (simplified)
            # Just propagate as DynamicRank for now
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

    # ── Conv / ConvTranspose ────────────────────────────────────────────────
    elif op in ("Conv", "ConvTranspose"):
        x = inp[0] if len(inp) > 0 else ""
        r = get_rank(x)
        if r is not None:
            set_output_rank(out[0] if out else "", r)

    # ── 一般: output rank = first input rank (保守的) ────────────────────
    else:
        if inp and out:
            r = get_rank(inp[0])
            if r is not None:
                set_output_rank(out[0], r)
            # multiple outputs: same rank
            for o in out[1:]:
                if o:
                    set_output_rank(o, r)

    if conflict_found:
        break

if not conflict_found:
    print("\n[OK] No rank conflicts detected in simulation.")
    print(f"Final known ranks: {sum(1 for v in rank_map.values() if v is not None)}")

    # 最終的に rank が判明しているテンソルの分布を表示
    from collections import Counter
    dist = Counter(v for v in rank_map.values() if v is not None)
    print("Rank distribution:")
    for r, cnt in sorted(dist.items()):
        print(f"  rank-{r}: {cnt}")
else:
    print("\n^^^ この衝突が 'expecting 4, got 3' の原因です ^^^")
    # どのノードが rank-4 を設定したか逆引き
    print("\n--- Tracing who set the conflicting tensor's rank ---")
    # Already printed above; just dump nearby nodes for context
