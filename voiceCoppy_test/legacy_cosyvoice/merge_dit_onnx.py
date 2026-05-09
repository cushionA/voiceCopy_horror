#!/usr/bin/env python3
"""
merge_dit_onnx.py — DiT ONNX external-data を1ファイルに統合
voice_horror Phase 3 fix

Sentis の ONNXModelConverter は external-data 形式（.onnx + .data 分離）を
サポートしていないため OnnxImportException が発生する。
本スクリプトで重みを .onnx に埋め込んだ単一ファイルを生成する。

Usage（CosyVoice3 conda env OR onnx だけ入った任意の env）:
    pip install onnx        # onnx のみ必要、torch 不要
    cd voiceCoppy_test
    python merge_dit_onnx.py

Output:
    voice_Horror_Game/Assets/SentisSpike/Models/
        flow.decoder.estimator.merged.fp32.onnx   ← Sentis でインポート可能
"""

import os
import sys
from pathlib import Path

# ─── パス設定 ───────────────────────────────────────────────
REPO_ROOT  = Path(__file__).resolve().parent.parent
SRC_ONNX   = REPO_ROOT / "voiceCoppy_test" / "onnx_export" / "flow.decoder.estimator.fp32.onnx"
DST_ONNX   = REPO_ROOT / "voice_Horror_Game" / "Assets" / "SentisSpike" / "Models" / "flow.decoder.estimator.merged.fp32.onnx"

def main():
    try:
        import onnx
    except ImportError:
        print("[ERROR] onnx が見つかりません。  pip install onnx  を実行してください。")
        sys.exit(1)

    if not SRC_ONNX.exists():
        print(f"[ERROR] 入力ファイルが見つかりません: {SRC_ONNX}")
        print("       onnx_export/ に flow.decoder.estimator.fp32.onnx と .data が必要です。")
        sys.exit(1)

    data_file = SRC_ONNX.parent / (SRC_ONNX.name + ".data")
    if not data_file.exists():
        print(f"[WARN] .data ファイルが見つかりません: {data_file}")
        print("       external-data なし形式の可能性があります。そのままコピーを試みます。")

    print(f"[1/2] Loading: {SRC_ONNX}")
    print("      (1.3GB の読み込みに数十秒かかる場合があります...)")

    # onnx.load は同ディレクトリの .data ファイルを自動的に読む
    model = onnx.load(str(SRC_ONNX))
    print(f"      opset={model.opset_import[0].version}, nodes={len(model.graph.node)}")

    # ─── stale value_info を除去 ────────────────────────────────
    # dynamo exporter が残す val_0 等の dangling 参照で
    # Sentis の "key 'val_0' was not present in the dictionary" 例外が出るので、
    # 実際の node 出力 / input / initializer に存在しない value_info を削除する。
    print("[1.5/2] Stripping stale value_info entries...")
    valid_names = set()
    for n in model.graph.node:
        valid_names.update(n.output)
    for i in model.graph.input:
        valid_names.add(i.name)
    for ini in model.graph.initializer:
        valid_names.add(ini.name)

    before = len(model.graph.value_info)
    cleaned = [vi for vi in model.graph.value_info if vi.name in valid_names]
    removed = before - len(cleaned)
    del model.graph.value_info[:]
    model.graph.value_info.extend(cleaned)
    print(f"      removed {removed} stale value_info entries (kept {len(cleaned)})")

    DST_ONNX.parent.mkdir(parents=True, exist_ok=True)

    print(f"[2/2] Saving (single-file, no external data): {DST_ONNX}")
    print("      (書き込みにも数十秒かかる場合があります...)")
    # save_as_external_data=False で全重みを1ファイルに埋め込む
    onnx.save(model, str(DST_ONNX), save_as_external_data=False)

    size_mb = DST_ONNX.stat().st_size / (1024 ** 2)
    print(f"[OK]  Done! {size_mb:.0f} MB")
    print()
    print("次のステップ:")
    print("  1. Unity で Assets > Refresh (Ctrl+R)")
    print("  2. Assets/SentisSpike/Models/ に flow.decoder.estimator.merged.fp32.onnx が")
    print("     ModelAsset として表示されることを確認")
    print("  3. Inspector の Dit Model フィールドにドラッグ")


if __name__ == "__main__":
    main()
