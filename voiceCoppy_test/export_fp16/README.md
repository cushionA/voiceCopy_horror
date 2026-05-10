# export_fp16/

kNN-VC ONNX (WavLM Large Layer 6 + HiFiGAN) の **重みのみ FP16 化** スクリプト群。

Phase 8 量子化比較 (`feature/phase8-fp16-quantize` ブランチ) で導入。

## ⚠ 重要: Sentis 2.5 では速度メリットなし (2026-05-10 確認)

[Sentis 公式 docs](https://docs.unity3d.com/Packages/com.unity.ai.inference@2.6/manual/quantize-a-model.html) より:
> "At runtime, Inference Engine converts these values back to a higher-precision
>  format **before processing the operations**."
> "A lower bit count per value decreases your model's disk and memory usage
>  **without significantly affecting inference speed**."

Sentis の量子化は **重み storage 圧縮のみ**、compute は常に FP32 にアップキャストされる。
PR #8 の実測でも FP32 → FP16 で **+5% 悪化** (dequantize overhead が純損失) を確認済:
- baseline: `VcTestOutput/perf_20260510_004308/perf.csv` (615 ms batch mean)
- FP16: `VcTestOutput/perf_20260510_004401/perf.csv` (644 ms batch mean、+4.7%)

**採用判断**:
- VRAM 余裕があるなら **FP32 のまま使うべき** (RTX 2070S 8GB は十分)
- VRAM/disk 削減を取りたい場合のみ FP16 化を検討 (速度は同等 or わずかに悪化)
- native FP16 GPU compute は ONNX Runtime DirectML / TensorRT 等の別ランタイムでないと得られない (Sentis 2.x では実装予定なし)

スクリプト自体は将来 Sentis が native FP16 compute を実装したとき再評価できるよう残置。

## 目的

- 同一の C# ランタイム (`WavLMFeatureExtractor` / `HiFiGANVocoder`) で `ModelAsset` を差し替えるだけで FP16 推論できるようにする
- FP32 と FP16 の出力波形・スペクトル・レイテンシ差を `VcQuantizeCompareRunner` で計測する
- VRAM 節約 + GPU compute 高速化 (RTX 2070 Super 8GB の余裕を確保)

## 戦略 (なぜ再 export しないか)

- 既に `voice_Horror_Game/Assets/SentisSpike/Models/KnnVc/` に FP32 ONNX 配置済み
- PyTorch checkpoint からの再 export は `dynamo_export` の安定性問題 (Phase 1-3 撤退で経験) のリスクあり
- `onnxconverter_common.float16.convert_float_to_float16` で **重みのみ FP16、入出力は FP32 boundary** で変換できる
- → C# 側のテンソル受け渡しコード変更ゼロ、`ModelAsset` 差し替えだけで動く

## 使い方

```bash
# 依存関係 (ローカル venv で 1 回)
pip install onnxconverter-common

# 変換実行
cd voiceCoppy_test/export_fp16
python export_fp16.py

# 出力先
# voice_Horror_Game/Assets/SentisSpike/Models/KnnVc/fp16/wavlm_large_layer6.onnx
# voice_Horror_Game/Assets/SentisSpike/Models/KnnVc/fp16/hifigan_wavlm_layer6.onnx
```

## op_block_list の方針

| モデル | block 対象 | 理由 |
|--------|-----------|------|
| WavLM Large | `LayerNormalization` | huggingface 既知問題: 長入力で LayerNorm を FP16 にすると nan 発散しやすい。FP32 維持で安定 |
| HiFiGAN | (なし) | LayerNorm 不使用、weight norm + Conv1D のみ。FP16 化で目立つ品質劣化なし (公式 FP16 vocoder 多数事例) |

## サイズ目安 (FP32 → FP16)

- WavLM Large Layer 6: 339 MB → ~170 MB
- HiFiGAN: 64 MB → ~32 MB

## 既知の制約

- `keep_io_types=True` を設定 → 入出力 boundary に Cast (float→float16) が自動挿入される
- Sentis 2.5 GPUCompute backend で動作確認済み (本 PR の VcQuantizeCompareRunner で検証)
- LayerNormalization を block しているため、WavLM の純粋 FP16 ratio はモデル全体のうち ~85% (LayerNorm の重みは FP32 のまま)

## 関連

- 本ブランチ: `feature/phase8-fp16-quantize`
- 前段: PR #7 `feature/phase8-knnvc-gpu-optim` (kNN 完全 GPU 化 + プールキャッシュ)
- 比較ランナー: `voice_Horror_Game/Assets/SentisSpike/Scripts/KnnVc/VcQuantizeCompareRunner.cs`
