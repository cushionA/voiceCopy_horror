#!/usr/bin/env python3
"""
diagnose_onnx.py — Sentis インポートエラーの原因特定

使い方:
    python diagnose_onnx.py <onnx-path> [search_name]

例:
    python diagnose_onnx.py ../voice_Horror_Game/Assets/SentisSpike/Models/flow.decoder.estimator.merged.fp32.onnx val_0
    python diagnose_onnx.py ../voice_Horror_Game/Assets/SentisSpike/Models/hift.fixed.fp32.onnx
"""

import sys
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("usage: diagnose_onnx.py <onnx-path> [search_name]")
        sys.exit(1)

    import onnx
    from onnx import numpy_helper

    path = Path(sys.argv[1])
    search = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"Loading: {path}")
    model = onnx.load(str(path), load_external_data=False)
    g = model.graph
    print(f"  nodes={len(g.node)}, initializers={len(g.initializer)}, "
          f"inputs={len(g.input)}, outputs={len(g.output)}, value_info={len(g.value_info)}")

    # ─── 1. 全 node の dangling 入力を検出 ───────────────────────────────
    defined = set()
    for i in g.input: defined.add(i.name)
    for ini in g.initializer: defined.add(ini.name)
    for n in g.node:
        for o in n.output:
            defined.add(o)

    print("\n[1] Dangling node inputs (= input name not produced by anything):")
    dangling_count = 0
    dangling_names = set()
    for n in g.node:
        for inp in n.input:
            if inp == "":
                continue   # ONNX optional input
            if inp not in defined:
                dangling_count += 1
                dangling_names.add(inp)
                if dangling_count <= 20:
                    print(f"  node[{n.name or n.op_type}] op={n.op_type} input={inp!r}")
    if dangling_count == 0:
        print("  none")
    else:
        print(f"  ... total {dangling_count} dangling references, "
              f"{len(dangling_names)} unique names")
        if len(dangling_names) <= 30:
            print(f"  unique names: {sorted(dangling_names)}")

    # ─── 2. rank-0 を持つ node attribute を検出 ───────────────────────────
    print("\n[2] rank-0 tensor attributes in nodes (Constant / etc.):")
    rank0_attr_count = 0
    rank0_scalar_const_count = 0   # value_int / value_float / value_string で rank-0 を生む Constant
    for n in g.node:
        is_constant = (n.op_type == "Constant")
        for a in n.attribute:
            if a.type == onnx.AttributeProto.TENSOR:   # 単一 TensorProto
                t = a.t
                if len(t.dims) == 0:
                    rank0_attr_count += 1
                    if rank0_attr_count <= 20:
                        try:
                            arr = numpy_helper.to_array(t)
                            v = arr.item()
                        except Exception:
                            v = "?"
                        print(f"  node[{n.name or n.op_type}] op={n.op_type} attr={a.name} "
                              f"TENSOR dtype={t.data_type} value={v}")
            elif a.type == onnx.AttributeProto.TENSORS:
                for t in a.tensors:
                    if len(t.dims) == 0:
                        rank0_attr_count += 1
                        if rank0_attr_count <= 20:
                            print(f"  node[{n.name or n.op_type}] op={n.op_type} attr={a.name}[] "
                                  f"dtype={t.data_type}")
            # Constant op で value_int / value_float / value_string は rank-0 出力を生む
            elif is_constant and a.name in ("value_int", "value_float", "value_string"):
                rank0_scalar_const_count += 1
                if rank0_scalar_const_count <= 20:
                    val = a.i if a.type == onnx.AttributeProto.INT \
                        else a.f if a.type == onnx.AttributeProto.FLOAT \
                        else a.s.decode("utf-8", errors="replace") if a.type == onnx.AttributeProto.STRING \
                        else "?"
                    print(f"  node[{n.name or n.op_type}] op=Constant attr={a.name} "
                          f"-> rank-0 output={list(n.output)} value={val}")
    if rank0_attr_count == 0 and rank0_scalar_const_count == 0:
        print("  none")
    else:
        print(f"  ... total {rank0_attr_count} rank-0 TENSOR attrs, "
              f"{rank0_scalar_const_count} scalar Constant ops (value_int/float/string)")

    # ─── 3. graph 内 search_name を grep ─────────────────────────────────
    if search:
        print(f"\n[3] Searching for {search!r} in graph...")
        # input/output
        for i in g.input:
            if i.name == search:
                print(f"  graph.input: {i}")
        for o in g.output:
            if o.name == search:
                print(f"  graph.output: {o}")
        # initializer
        for ini in g.initializer:
            if ini.name == search:
                print(f"  initializer: name={ini.name} dims={list(ini.dims)} dtype={ini.data_type}")
        # node output / input
        for n in g.node:
            if search in n.input:
                print(f"  node[{n.name or n.op_type}] op={n.op_type} input={list(n.input)} output={list(n.output)}")
            if search in n.output:
                print(f"  node[{n.name or n.op_type}] op={n.op_type} produces it. inputs={list(n.input)}")
        # value_info
        for vi in g.value_info:
            if vi.name == search:
                print(f"  value_info: {vi}")

    # ─── 5. value_info / input / output / initializer の rank チェック ───
    print("\n[5] rank-0 entries in value_info / graph.input / graph.output / initializer:")

    def _rank_of_vi(vi):
        if not vi.type.HasField("tensor_type"):
            return None
        tt = vi.type.tensor_type
        if not tt.HasField("shape"):
            return None
        return len(tt.shape.dim)

    rank0_vi = [vi.name for vi in g.value_info if _rank_of_vi(vi) == 0]
    rank0_in = [vi.name for vi in g.input      if _rank_of_vi(vi) == 0]
    rank0_out = [vi.name for vi in g.output    if _rank_of_vi(vi) == 0]
    rank0_init = [ini.name for ini in g.initializer if len(ini.dims) == 0]

    print(f"  value_info rank-0: {len(rank0_vi)}  (sample: {rank0_vi[:10]})")
    print(f"  graph.input rank-0: {len(rank0_in)}  ({rank0_in})")
    print(f"  graph.output rank-0: {len(rank0_out)}  ({rank0_out})")
    print(f"  initializer rank-0: {len(rank0_init)}  (sample: {rank0_init[:10]})")

    # ─── 6. file size ────────────────────────────────────────────────────
    sz = path.stat().st_size
    print(f"\n[6] File size: {sz:,} bytes ({sz / (1024**3):.2f} GB)")

    # ─── 4. subgraph (If / Loop / Scan) の内部参照 ───────────────────────
    print("\n[4] Subgraphs (If/Loop/Scan attribute graphs):")
    sub_count = 0
    for n in g.node:
        for a in n.attribute:
            if a.type == onnx.AttributeProto.GRAPH:
                sub_count += 1
                sg = a.g
                print(f"  node[{n.name or n.op_type}] op={n.op_type} attr={a.name} "
                      f"subgraph nodes={len(sg.node)}")
            elif a.type == onnx.AttributeProto.GRAPHS:
                for sg in a.graphs:
                    sub_count += 1
                    print(f"  node[{n.name or n.op_type}] op={n.op_type} attr={a.name}[] "
                          f"subgraph nodes={len(sg.node)}")
    if sub_count == 0:
        print("  none")


if __name__ == "__main__":
    main()
