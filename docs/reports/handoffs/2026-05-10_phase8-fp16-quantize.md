# 2026-05-10 Phase 8 — FP16 量子化比較インフラ整備

## 状態

- ブランチ: `feature/phase8-fp16-quantize` (main から派生)
- 親 PR: #7 `feature/phase8-knnvc-gpu-optim` (Phase A 完全 GPU 化 + プールキャッシュ) — マージ済み
- 本 PR: 未作成 (本 handoff の commit 後に出す)
- 状態: ready-for-next-phase / トピック: FP16 ONNX 重み変換 + 比較ランナー導入完了
- 計測: **未実施** (Editor で VcQuantizeCompare シーンを組み立てる必要あり)

## やったこと

### B-1. Python FP16 export (`voiceCoppy_test/export_fp16/`)
- `export_fp16.py`: 既存 FP32 ONNX を `onnxconverter_common.float16.convert_float_to_float16(keep_io_types=True)` で **重みのみ FP16** に変換
- `README.md`: 戦略 / 使い方 / op_block_list 方針を文書化
- 結果:
  - `wavlm_large_layer6.onnx`: 338.6MB → 169.6MB (50%、`LayerNormalization` を block list で FP32 維持)
  - `hifigan_wavlm_layer6.onnx`: 63.1MB → 31.6MB (50%、block list 不要)
- 出力先: `voice_Horror_Game/Assets/SentisSpike/Models/KnnVc/fp16/` (gitignored)
- 入出力 boundary は FP32 維持 → C# 側のテンソル受け渡しコード変更ゼロ、`ModelAsset` 差し替えだけで動く

### B-2. C# 側 API 追加
- `MatchingSetPool.Clear()`: pool 全 frame と weight を破棄。compare ランナーで同一 service を別 target で使い回す用途。内部キャッシュ配列は length 0 で再利用 (再 alloc 回避)
- `VoiceConversionService.ClearPools()`: 上記の facade
- `VoiceConversionService.ConversionTimings` 構造体: `extractMs / knnMs / vocodeMs / totalMs` の Stopwatch ベース内訳
- `VoiceConversionService.Convert(AudioClip, float, out ConversionTimings)` overload: 既存 `Convert(AudioClip, float)` は `out _` で内訳を捨てる薄い wrapper に変更 — 既存呼び出しは **無変更で動く**

### B-3. VcQuantizeCompareRunner.cs (新規)
- 2 つの `VoiceConversionService` を SerializeField で並行運用 (FP32 / FP16)
- `testClips[5]` を全組合せで src/tgt として使い回し (対角除外 → 5×4=20 ペア)
- 各ペアで:
  1. 両 service の TargetPool を tgt で再構築
  2. FP32 / FP16 双方で Convert + per-stage timings 取得
  3. メトリクス計算: time-domain RMSE, max abs diff, peak (FP32/FP16)
  4. WAV 書き出し: `fp32/{src}_to_{tgt}.wav`, `fp16/{src}_to_{tgt}.wav`, `diff/{src}_to_{tgt}_diff.wav` (= (fp32-fp16)/2 をクリップ)
- CSV: `quantize_compare.csv`
  - per-pair: src, tgt, len, extract/knn/vocode/total ms (×2), time_rmse, time_max_abs_diff, peak (×2)
  - mean 集計: 各 stage の FP32/FP16 平均と delta (ms / %)
- 出力先: `VcTestOutput/quantize_{timestamp}/` (既存 gitignore でカバー)

### 検証
- compile: 0 errors / 2 warnings (UHFPS 既存の `Physics.autoSyncTransforms` deprecation のみ)
- EditMode test: 48 / 48 PASS (KnnVc アセンブリ全テスト維持)

## やっていないこと (次のチケット)

### 1. シーン作成 + 実計測
- `VcQuantizeCompare.unity` シーンが未作成
- 必要な手順 (Editor 手作業):
  1. シーンに 2 つの `VoiceConversionService` GameObject を配置:
     - `VcService_FP32`: WavLM/HiFiGAN を `Assets/SentisSpike/Models/KnnVc/*.onnx` (FP32) でアサイン
     - `VcService_FP16`: 同 `Assets/SentisSpike/Models/KnnVc/fp16/*.onnx` でアサイン (Unity に再 import 必要)
  2. `VcQuantizeCompareRunner` を 1 つ配置、両 service と testClips[5] をアサイン
     - testClips: `my_sampleVoice.wav`, `107.wav`, `10.wav`, `86.wav`, `raizyo.mp3`
  3. Play 押下 → 自動シーケンスで 20 ペア処理 → CSV / WAV 出力
- 自動化したい場合: `tools/build_vc_perf_scene.cs` の流儀でシーン構築スクリプトを足す (将来タスク)

### 2. spectral L1 / mel-spec MAE
- 当初計画では FFT magnitude L1 を CSV に追加予定だったが、Unity 標準に FFT API がなく自前実装 or 外部依存が必要
- 今回は **time-domain RMSE + max abs diff + peak** で十分 (ユーザー指示: 「単純に音の波形がどれくらい変わったでいいよ」)
- 必要になれば後続 PR で `MathNet.Numerics` 等を導入して STFT magnitude L1 を追加

### 3. Phase A の Risk 1 follow-up
- VcPerfRunner に `ProfilerRecorder` 統合し、`VC.kNN` 単独マーカーを CSV に直接出す改善は本 PR scope 外
- VcQuantizeCompareRunner 側では **Stopwatch ベースで自前計測**しているので、量子化比較の per-stage 解析には支障なし

## 想定される判断ポイント (実計測後に確認すべきこと)

| 観点 | 期待値 | 判断基準 |
|------|--------|---------|
| total latency 改善 | FP32 → FP16 で **総時間 -10〜30%** | 改善なしなら GPUCompute backend が FP16 を活かせていない疑い (Sentis profiling で確認) |
| extract / vocode 個別改善 | extract と vocode は改善、knn は ±5% 以内 | knn は FP32 のまま (KnnVcConverter の graph は FP32 内部) なので変動なしが正常 |
| time RMSE | < 1e-2 | 0.1 を超えるなら数値発散疑い (LayerNorm 以外を block list 追加) |
| 聴感品質 | "変わってる" で OK | ユーザー方針: FP16 で品質が "良くなる" ことはない、"変わって/劣化" で正常 |

## 関連

- 親 PR (Phase A): #7 (merged 2026-05-09 15:19 UTC)
- main commit: `c312111`
- 本ブランチ: `feature/phase8-fp16-quantize`
- FUTURE_TASKS.md エントリ更新: **未実施** (本 PR の Phase B 対応は B-1〜B-3 のみ、シーン構築は別タスク)
