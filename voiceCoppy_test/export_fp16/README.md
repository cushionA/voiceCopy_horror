# export_fp16/

kNN-VC ONNX (WavLM Large Layer 6 + HiFiGAN) の **重みのみ FP16 化** スクリプト群。

Phase 8 量子化比較 (`feature/phase8-fp16-quantize` ブランチ) で導入。

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
