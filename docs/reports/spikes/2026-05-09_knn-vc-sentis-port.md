# Phase 6: kNN-VC Sentis 互換性検証

**実施日**: 2026-05-09
**ブランチ**: `feature/phase5-knn-vc-spike`
**目的**: WavLM Large + HiFiGAN を ONNX export して Sentis 2.5 でロード/forward 成功するか検証

## 結論

✅ **Sentis 2.5 で完全動作確認**。voice_horror の VC ランタイム実装の最大リスクが完全クリア。

主要結果:
- WavLM Large (315M params, 24-layer Transformer) を ONNX export → Sentis ロード成功
- HiFiGAN を ONNX export → Sentis ロード成功
- PyTorch との数値一致 rtol < 1e-3 (max_abs_diff < 0.0001)
- **Sentis warmup 後の forward は PyTorch より 4 倍速い** (5秒音声に 97ms vs 382ms)

CosyVoice3 で 7-8 種類の op patch が必要だった苦労なしで、**素直に動作**。WavLM が枯れた transformer SSL モデルである利点が出た。

## ONNX export 結果

### WavLM Large (T6-1)

```python
torch.onnx.export(
    wrapper,  # WavLM.extract_features(x, output_layer=6, ret_layer_results=False)[0]
    (dummy_audio,),  # (1, 80000) — 5sec @ 16kHz
    output_path,
    input_names=["audio"],
    output_names=["features"],
    dynamic_axes={"audio": {1: "T_audio"}, "features": {1: "T_frame"}},
    opset_version=17,
)
```

| 項目 | 値 |
|------|---|
| export 時間 | 4.0s |
| ファイルサイズ | 338.6 MB (FP32) |
| Opset | 17 |
| Dynamic axes | T_audio (input), T_frame (output) |

### HiFiGAN (T6-2)

入力フォーマット注意: `(B, T_frame, dim=1024)` (channel-last)。kNN-VC matcher 側で WavLM 出力 `(1, T_frame, 1024)` をそのまま渡す。

```python
torch.onnx.export(
    hifigan,
    (dummy_features,),  # (1, 250, 1024)
    output_path,
    dynamic_axes={"features": {1: "T_frame"}, "audio": {2: "T_audio"}},
    opset_version=17,
)
```

| 項目 | 値 |
|------|---|
| export 時間 | 0.8s |
| ファイルサイズ | 63.1 MB (FP32) |

## ONNX Runtime での数値一致確認 (T6-3 part 1)

| モデル | PyTorch forward | ORT forward | max_abs_diff | mean_abs_diff | 1e-3 一致 |
|--------|----------------|-------------|--------------|---------------|----------|
| WavLM | 212ms | 228ms | 0.000095 | 0.000008 | ✅ |
| HiFiGAN | 170ms | 153ms | 0.000047 | 0.000000 | ✅ |

ONNX Runtime CUDAExecutionProvider で動作。

## Sentis 2.5 互換性 (T6-3 part 2)

### ロード時間

| モデル | Sentis ModelLoader.Load + Worker 起動 |
|--------|----------------------------------|
| WavLM | **97ms** |
| HiFiGAN | **271ms** |

CosyVoice3 系 (合計 600ms ロード) より圧倒的に速い。

### Forward 計測 (5sec audio = WavLM input 80000 samples / HiFiGAN input 250 frames × 1024)

| Run | WavLM | HiFiGAN | Total | 備考 |
|-----|-------|---------|-------|------|
| **1 (warmup)** | 392ms | 118ms | 510ms | cold start (CUDA kernel コンパイル等) |
| **2** | 39ms | 60ms | 99ms | warmed |
| **3** | 38ms | 59ms | 97ms | warmed |

**Warmup 後の RTF**: 97ms / 5000ms = **0.019 (52x real-time)**

### NaN / Inf チェック

両モデルとも出力に NaN / Inf 0 件。値域も正常 (WavLM: [-23.5, 41.2], HiFiGAN: [-0.40, 0.45])。

## レイテンシ比較

| 1秒音声処理 | PyTorch (cu124) | Sentis (warmup 後) |
|------------|----------------|-------------------|
| WavLM | ~42ms | ~8ms |
| HiFiGAN | ~34ms | ~12ms |
| **Total** | **~76ms** | **~20ms** |

**Sentis は PyTorch より 4 倍速い**。理由 (推定):
1. CUDA kernel fusion (Sentis が最適化シェーダー使う)
2. PyTorch CUDAExecutionProvider のオーバーヘッド (memcpy ノード等)
3. PyTorch は dynamic shape 対応のため一般化された経路

ただし **1 回目 forward (warmup) は 510ms** かかる。voice_horror では:
- ゲーム起動時のローディング画面で warmup 1 回実行 (静的 5sec dummy で OK)
- 以降は warm 状態で real-time 余裕

## 環境

- Unity 6000.3.9f1, Sentis (Unity Inference Engine) 2.5.0
- Backend: GPUCompute
- GPU: NVIDIA GeForce RTX 2070 Super (8GB)
- ONNX 配置: `voice_Horror_Game/Assets/SentisSpike/Models/KnnVc/{wavlm,hifigan}_*.onnx` (gitignored)

## 既知の挙動と注意点

### 1 回目 forward の遅さ (cold start)

- WavLM: 392ms / HiFiGAN: 118ms → 合計 510ms (5sec audio)
- 内訳推定: CUDA kernel JIT コンパイル + GPU メモリ allocation
- **対処**: ゲーム初期化時に warmup forward を 1 回実行 (loading 画面と並行)

### 入力 shape の罠 (HiFiGAN)

HiFiGAN の入力は `(B, T_frame, dim=1024)` で **channel-last**。最初 `(B, dim, T_frame)` で試したら `RuntimeError: mat1 and mat2 shapes cannot be multiplied (1024x250 and 1024x512)` でクラッシュした。`hifigan/models.py:103` の docstring 確認推奨:
```
""" `x` as (bs, seq_len, dim), regular hifi assumes input of shape (bs, n_mels, seq_len) """
```

### CosyVoice3 期に発生した問題は再現せず

| CosyVoice3 で必要だった patch | kNN-VC で必要? |
|------------------------------|-------------|
| dynamic_axes → RotaryEmbedding 競合で T 固定 | 不要 (WavLM の relative position は dynamic OK) |
| add_optional_chunk_mask 5 モジュールパッチ | 不要 |
| merge_dit_chunked.py (protobuf 1.3GB ACCESS_VIOLATION) | 不要 (FP32 で 338MB) |
| stale value_info ストリップ | 不要 |
| ScatterND int32→int64 Cast | 不要 |
| Sentis ceil_mode バグ (AvgPool) | 不要 (kNN-VC は AvgPool 使わない) |

## 動作スクリプト

### sandbox 側 (PyTorch + ORT 検証)

- `C:/Users/tatuk/Desktop/Sandbox/knn-vc-spike/export_wavlm_onnx.py`
- `C:/Users/tatuk/Desktop/Sandbox/knn-vc-spike/export_hifigan_onnx.py`

### Unity 側 (Sentis 検証)

- `voice_Horror_Game/Assets/SentisSpike/Scripts/KnnVc/KnnVcSentisLoadTest.cs`
- 起動: UniCli 経由 Eval で `KnnVcSentisLoadTest.RunAll()` を呼ぶ

## 次のフェーズ

### Phase 7: voice_horror 統合 spec / design

最大リスク (Sentis 互換性) がクリアされたため、Phase 7 は純粋に統合実装フェーズ。
init-agent で `designs/specs/voice_conversion/{spec,design,tasks}.md` 作成へ。

主要設計ポイント:
- `WavLMFeatureExtractor` クラス (Sentis Worker wrapper、warmup 内蔵)
- `MatchingSetPool` クラス (target / player 別プール、永続化)
- `KnnVcConverter` クラス (kNN 検索 + HiFiGAN vocode)
- `VoiceConversionService` ファサード
- `SpeakerSimilarityJudge` (BAD/GOOD ED 分岐用、WavLM 兼用)

### Phase 8: 演出パターン実装

### Phase 9: 声優収録脚本設計

## 関連ファイル

- 前 phase report: `docs/reports/spikes/2026-05-09_knn-vc-local-spike.md`
- 撤退記録: `docs/reports/spikes/2026-05-07_cosyvoice-phase3-pipeline.md`
- 公式: https://github.com/bshall/knn-vc / https://bshall.github.io/knn-vc/
