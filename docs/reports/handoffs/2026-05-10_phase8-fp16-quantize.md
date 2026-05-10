# 2026-05-10 Phase 8 — 量子化 + 事前トークン化スパイク検証

## 状態

- ブランチ: `feature/phase8-fp16-quantize` (main から派生)
- 親 PR: #7 `feature/phase8-knnvc-gpu-optim` (Phase A 完全 GPU 化 + プールキャッシュ) — マージ済み
- 本 PR: **#8** (https://github.com/cushionA/voiceCopy_horror/pull/8)
- 状態: ready-for-review / トピック: 2 つの最適化スパイクを検証、勝者は事前トークン化
- **中間結論**: FP16 量子化 → 速度メリットなし (Sentis 設計上の制約)、事前トークン化 → **batch mean -34%、p95 -47%** で大成功

## 結論サマリ (実測ベース)

| アプローチ | 速度 | サイズ | 採用判断 |
|-----------|------|--------|---------|
| **FP16 量子化** (onnxconverter_common) | **+5%** (悪化) | -50% (340→170MB) | ❌ Sentis 2.5 は FP16 を真にサポートせず、内部で FP32 upcast。公式 docs で「速度メリットなし」明言済 |
| **事前トークン化** (固定 source 用) | **-34% (batch mean)** | 純増 (`.npy` 同梱) | ✅ 演出時の少女セリフ変換に投入する価値、Phase 9 で本格統合 |

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

### B-5. 事前トークン化スパイク (commit `585b210`)
量子化が振るわなかった一方、**ユーザー提案の「source の事前トークン化」を試したら大当たり**。

#### 実装
- `VoiceConversionService.ExtractQueryFeatures(AudioClip)`: source を WavLM forward して
  query features [N, 1024] を返す public API
- `VoiceConversionService.Convert(Tensor<float>, alpha, out timings)` overload: 事前トークン化
  された features を入力に取り、WavLM stage を完全 skip。timings.extractMs = 0 で返る
- `VcPerfRunner.usePretokenizedSource` フラグ: ON で計測前に各 source を WavLM forward → cache
  (stats から除外)、ConvertClip は cache 経由 Convert を呼ぶ
- `OnDestroy` で cache `Tensor<float>[]` を全 Dispose
- CSV header に `# usePretokenizedSource={true|false}` を追記 (両モード CSV 区別用)

#### 計測 (`VcTestOutput/perf_20260510_135417/perf.csv`)
| 計測 | baseline (live forward) | pretokenized | delta |
|------|------------------------|--------------|-------|
| single mean (n=4) | 687.1 ms | 397.5 ms | **−42.1%** |
| single p95 | 845.4 ms | 445.0 ms | **−47.4%** |
| batch mean (n=40) | 615.1 ms | 404.5 ms | **−34.2%** |
| batch p95 | 693.8 ms | 461.4 ms | −33.5% |
| batch max | 715.1 ms | 465.2 ms | −34.9% |

→ 演出時のセリフ変換が「ボタン押下から 0.4 秒以内」に収まる体感に変わる。
   variance も pretokenized 側が素直 (WavLM cold/warm 揺らぎ消失)。

## やっていないこと (次のチケット)

### 1. Phase 9 事前トークン化の本格統合 (本 PR スパイク → 次 PR で実装)
- `voiceCoppy_test/pretokenize/pretokenize_source.py`: 少女セリフ wav 群を WavLM ONNX で
  forward して `.npy` 化 (onnxruntime ベース、GPU 利用)
- `Assets/Audio/PretokenizedFeatures/*.npy` を Addressable group `Audio_PretokenizedFeatures`
  (label: `pretokenize`, `event-*`) に登録
- 演出側 (BAD ED 等) で `Addressables.LoadAssetAsync<TextAsset>("cached-features/...")` →
  NpyReader で features ロード → `service.Convert(features, alpha, out _)`
- design.md の「事前トークン化パス」セクションに統合タスクを記載済

### 2. VcQuantizeCompare シーン作成 + 実計測 (本 PR には含めない判断)
- 量子化が Sentis 設計上速度メリットなし → 比較の優先度低下
- インフラ (`VcQuantizeCompareRunner`) は残しておく (将来 Sentis が native FP16 compute を
  実装したとき再評価できる)
- `VcQuantizeCompare.unity` シーンは未作成
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

## FP16 量子化の最終判断 (実計測後 2026-05-10 追記)

実測 (`VcTestOutput/perf_20260510_004401/perf.csv` vs `perf_20260510_004308/perf.csv`):

| 計測 | FP32 baseline | FP16 | delta |
|------|---------------|------|-------|
| single mean (n=4) | 687.1 ms | 947.3 ms | **+37.9%** (悪化) |
| batch mean (n=40) | 615.1 ms | 644.0 ms | +4.7% (悪化) |
| batch p95 | 693.8 ms | 743.4 ms | +7.2% |
| Model size | 402 MB | 201 MB | -50% |

**Sentis 2.5 公式 docs で裏取り済**:
[Quantize a Model | Inference Engine 2.6](https://docs.unity3d.com/Packages/com.unity.ai.inference@2.6/manual/quantize-a-model.html):
> "At runtime, Inference Engine converts these values back to a higher-precision format
>  before processing the operations."
> "A lower bit count per value decreases your model's disk and memory usage **without
>  significantly affecting inference speed**."

→ Sentis の量子化は重み storage 圧縮のみ、compute は常に FP32。`onnxconverter_common` で
  挿入された 84 個の Cast (boundary + LN) が dequantize overhead として +5% 計上され、
  メモリ帯域削減効果を上回って **純損失**。

**判断**:
- 量子化は voice_horror では採用せず (RTX 2070S 8GB に対し VRAM 余裕十分、size 削減動機薄)
- 公式 `ModelQuantizer.QuantizeWeights(QuantizationType.Float16, ref model)` を Editor で
  呼べば Cast 配置がより最適化される可能性は残るが、「速度改善はない」のは公式明言済 → 着手保留

## 関連

- 親 PR (Phase A): #7 (merged 2026-05-09 15:19 UTC)
- main commit: `c312111`
- 本ブランチ: `feature/phase8-fp16-quantize`
- FUTURE_TASKS.md エントリ更新: **未実施** (本 PR の Phase B 対応は B-1〜B-3 のみ、シーン構築は別タスク)
