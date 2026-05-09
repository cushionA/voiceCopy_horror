#!/usr/bin/env python3
"""
export_fp16.py — kNN-VC ONNX (WavLM + HiFiGAN) を FP16 weight に変換する。

戦略:
    既存 FP32 ONNX を再 export せず、onnxconverter_common.float16
    で「**重みのみ FP16、入出力は FP32 のまま**」に変換する (keep_io_types=True)。
    これにより C# 側 (WavLMFeatureExtractor / HiFiGANVocoder) のコード変更不要で
    ModelAsset の差し替えだけで FP16 推論が走る。

Sentis 2.5 互換性メモ:
    - Sentis は ONNX の FP16 weight を内部で扱える (GPUCompute backend で実速度向上)
    - 入出力 boundary に float→float16 / float16→float Cast が自動挿入される
    - shape inference 不要 (元 FP32 ONNX で確定済み)

依存:
    pip install onnx onnxconverter_common numpy

使い方:
    cd voiceCoppy_test/export_fp16
    python export_fp16.py
    # → ../../voice_Horror_Game/Assets/SentisSpike/Models/KnnVc/fp16/{wavlm_large_layer6.onnx, hifigan_wavlm_layer6.onnx}
"""
from __future__ import annotations

import sys
import time
from pathlib import Path


def ensure_dependency() -> None:
    """onnxconverter_common が未インストールなら明示エラー (auto pip は副作用大)。"""
    try:
        import onnxconverter_common  # noqa: F401
    except ImportError:
        sys.stderr.write(
            "ERROR: onnxconverter_common が見つかりません。\n"
            "  pip install onnxconverter-common\n"
            "を実行してから再度本スクリプトを実行してください。\n"
        )
        sys.exit(1)


def convert_one(src_path: Path, dst_path: Path, *, keep_io_types: bool = True,
                op_block_list: list[str] | None = None) -> dict:
    """
    1 ファイル変換。戻り値: 簡易レポート (size_before/after, elapsed, op_block_list)。

    keep_io_types=True で入出力は FP32 維持 (C# 変更不要)。
    op_block_list で FP16 化を抑止する op を指定できる (LayerNorm 等数値感度高い op を浮動精度維持)。
    """
    import onnx
    from onnxconverter_common import float16

    if not src_path.exists():
        raise FileNotFoundError(f"source ONNX not found: {src_path}")

    print(f"[fp16] loading: {src_path}")
    model = onnx.load(str(src_path), load_external_data=True)
    size_before = src_path.stat().st_size

    print(f"[fp16] converting (keep_io_types={keep_io_types}, op_block_list={op_block_list})")
    t0 = time.time()
    model_fp16 = float16.convert_float_to_float16(
        model,
        keep_io_types=keep_io_types,
        op_block_list=op_block_list or [],
        # disable_shape_infer=False  # default。ONNX の shape inference は通っている前提
    )
    elapsed = time.time() - t0

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(
        model_fp16,
        str(dst_path),
        # external data は使わず単一ファイルにする (FP16 で半分以下 → external 不要)
        save_as_external_data=False,
    )
    size_after = dst_path.stat().st_size

    return {
        "src": str(src_path),
        "dst": str(dst_path),
        "size_before_mb": size_before / 1024 / 1024,
        "size_after_mb": size_after / 1024 / 1024,
        "ratio": size_after / size_before,
        "elapsed_s": elapsed,
    }


def main() -> int:
    ensure_dependency()

    # repo root から見たパス。本ファイルは voiceCoppy_test/export_fp16/ にある想定。
    repo_root = Path(__file__).resolve().parents[2]
    models_dir = repo_root / "voice_Horror_Game" / "Assets" / "SentisSpike" / "Models" / "KnnVc"
    fp16_dir = models_dir / "fp16"

    targets = [
        # (src, dst, op_block_list)
        # WavLM: LayerNorm を FP16 にすると long input で nan 出やすい (huggingface 既知)。
        # block list で FP32 維持。Sentis でも safe。
        (
            models_dir / "wavlm_large_layer6.onnx",
            fp16_dir / "wavlm_large_layer6.onnx",
            ["LayerNormalization"],
        ),
        # HiFiGAN: LayerNorm 不使用、weight norm のみ。block list 不要。
        (
            models_dir / "hifigan_wavlm_layer6.onnx",
            fp16_dir / "hifigan_wavlm_layer6.onnx",
            None,
        ),
    ]

    reports = []
    for src, dst, blk in targets:
        try:
            r = convert_one(src, dst, keep_io_types=True, op_block_list=blk)
            reports.append(r)
            print(
                f"[fp16] DONE  {src.name}: "
                f"{r['size_before_mb']:.1f}MB -> {r['size_after_mb']:.1f}MB "
                f"(ratio={r['ratio']:.2f}) in {r['elapsed_s']:.1f}s"
            )
        except Exception as e:  # noqa: BLE001
            print(f"[fp16] FAIL  {src.name}: {type(e).__name__}: {e}")
            return 1

    print()
    print("[fp16] Summary:")
    for r in reports:
        print(
            f"  {Path(r['src']).name}: {r['size_before_mb']:.1f}MB -> "
            f"{r['size_after_mb']:.1f}MB ({r['ratio'] * 100:.0f}%)"
        )
    print()
    print("[fp16] Next:")
    print("  1) Unity で fp16/ 以下の onnx を ModelAsset としてインポート")
    print("  2) VcQuantizeCompareRunner で FP32 / FP16 双方を比較")
    return 0


if __name__ == "__main__":
    sys.exit(main())
