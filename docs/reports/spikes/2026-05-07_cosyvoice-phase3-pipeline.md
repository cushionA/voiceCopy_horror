# CosyVoice Phase 3 — C# VC パイプライン実装

**日付**: 2026-05-07
**フェーズ**: Phase 3 — C# パイプライン実装 (4 モデル連鎖 + DSP + ODE + speaker morphing)

---

## TL;DR

- C# mel feature extractor (STFT + 80-mel + 128-mel + acoustic mel) 実装完了
- Flow matching ODE loop (Euler, n_steps=10) 実装完了
- VoiceConversionPipeline MonoBehaviour 実装完了 (全 4 モデル連鎖)
- SpeakerMorphController (少女↔プレイヤー声モーフィング + cosine 類似度) 実装完了
- Phase 3 テスト T1–T5 定義完了。Unity で実行して検証が必要。

---

## 実装ファイル一覧

| ファイル | 役割 |
|---------|------|
| `Assets/SentisSpike/Scripts/VoiceConversion/MelExtractor.cs` | C# DSP: STFT + mel filterbank + CMVN + resample |
| `Assets/SentisSpike/Scripts/VoiceConversion/SpkEmbedProjection.cs` | Linear 192→80 projection (JSON weight load / truncation fallback) |
| `Assets/SentisSpike/Scripts/VoiceConversion/FlowMatchingODE.cs` | Euler ODE loop for DiT (t: 0→1, n_steps=10) |
| `Assets/SentisSpike/Scripts/VoiceConversion/VoiceConversionPipeline.cs` | 全 4 モデル連鎖 MonoBehaviour + async coroutine API |
| `Assets/SentisSpike/Scripts/VoiceConversion/SpeakerMorphController.cs` | 少女↔プレイヤー embedding 補間 + 減衰 + cosine 類似度 |
| `Assets/SentisSpike/Scripts/VoiceConversionTest.cs` | Phase 3 テストランナー T1–T5 |
| `Assets/SentisSpike/Scripts/Editor/SentisSpikeSetupPhase3.cs` | "Tools/Sentis Spike/Setup VC Test Scene (Phase 3)" メニュー |
| `voiceCoppy_test/extract_spk_projection.py` | spk_embed_affine_layer 重み JSON 抽出スクリプト |

---

## 設計詳細

### Mel Extractor (DSP)

| 用途 | SR | n_fft | hop | win | n_mels |
|------|-----|-------|-----|-----|--------|
| campplus 入力 | 16 kHz | 512 | 160 | 400 | 80 |
| tokenizer 入力 | 16 kHz | 512 | 160 | 400 | 128 |
| DiT mu / hift 入力 | 22050 Hz | 1024 | 256 | 1024 | 80 |

- FFT: Cooley-Tukey radix-2 in-place (n_fft = 512 / 1024 はいずれも 2 冪)
- 窓関数: Hann window (center padding = n_fft/2 のリフレクトパディング)
- campplus 用: utterance-level CMVN (ゼロ平均・単位分散)
- 出力形式: feature mel [T, 80] / [128, T] / acoustic mel [80, T]

### Flow Matching ODE

```
x(0) = N(0, I)  shape [1, 80, 100]
dt = 1 / n_steps
for step in [0, 1, ..., n_steps-1]:
    t = step * dt          # 0 → 1-dt (CosyVoice convention: 0=noise, 1=data)
    v = DiT(x, mask, mu, t, spks, cond)
    x += dt * v
return x[0]               # [80, 100] generated mel
```

- mu (conditioning): source acoustic mel を [80, 100] にゼロパディング
- cond: mu と同一 (VC 簡略実装)
- spks: campplus 出力 [192] → SpkEmbedProjection → [80]

### 既知の簡略化 (Phase 4 で改善予定)

| 項目 | Phase 3 実装 | 本来の実装 |
|------|------------|-----------|
| mu (DITへの conditioning) | source acoustic mel (直接) | speech tokens → LLM decoder → mel |
| spks projection | truncation fallback (JSON未取得時) | extract_spk_projection.py で抽出した実重み |
| ODE 精度 | Euler (1次) | 高精度: Heun / DPM++ |
| 長い音声 (>1秒) | 100フレームで切り落とし | チャンク分割 |

### Speaker Morph Controller

- `girlGhostEmb [192]`: 事前計算済み少女幽霊 embedding (Inspector で設定)
- `playerEmb [192]`: プレイヤー声を録音するたびに `RecordPlayerVoice()` で更新
- `morphRatio`: 0 (全て少女) → 1 (全てプレイヤー)
  - 声を出すたびに `+morphSpeedPerVoice` (default 0.05/発話)
  - 時間経過で減衰: half-life = decayHalfLife 秒 (default 30s)
- `ComputeSimilarity()`: cosine 類似度 → エンドロール直前の分岐判定に使用

---

## 実行手順 (Unity での確認)

```
1. Unity Editor で voice_Horror_Game/ を開く
2. Assets > Refresh (または Ctrl+R) → VoiceConversion/*.cs をコンパイル
3. Tools > Sentis Spike > Setup VC Test Scene (Phase 3)
4. Play モードに入る
5. Console で T1–T5 テスト結果を確認
```

### 期待される Console 出力

```
════════ Phase 3 VC Pipeline Tests ════════
[T1] MelExtractor
  Feature mel80: [100, 80] in Xms
  Feature mel128: [128, 100] in Xms
  Acoustic mel: [80, 86] in Xms
  PadOrTruncate: [80, 100] (target 100)
  T1 OK
[T2] SpkEmbedProjection
  Fallback truncation OK.
  T2 OK (JSON load skipped)
[T3] FlowMatchingODE
  DiT worker created in Xms
  ODE 3 steps in Xms → 8000 floats
  T3 OK
[T4] FullPipeline
  ExtractSpeakerEmbedding: Xms → [192]
  ConvertVoice: Xms → XXXXX samples
  T4 OK
[T5] SpeakerMorphController
  Before voice: morph[0]=1.000
  After 1 voice: morphRatio=0.100
  CosineSim(same, same) = 1.000
  T5 OK
════════ Summary ════════
  T1–T5: OK
[OK] Phase 3 全テスト通過
```

---

## Phase 4 タスク (次フェーズ)

| # | タスク | 優先度 |
|---|--------|--------|
| 1 | `extract_spk_projection.py` 実行 → `spk_projection.json` 取得 → Unity に配置 | 🔴 高 |
| 2 | マイク入力 `Microphone.Start()` → リアルタイムキャプチャ + VC 変換 | 🔴 高 |
| 3 | SpeakerMorphController を UHFPS PlayerController に統合 | 🟡 中 |
| 4 | VC 変換を async coroutine 化 (ゲームフロー中断なし) | 🟡 中 |
| 5 | DiT n_steps 削減テスト (3→5 steps) — 遅延 vs 品質トレードオフ確認 | 🟢 低 |
| 6 | 声類似度スコアをゲームエンディング分岐ロジックに接続 | 🟢 低 |
| 7 | 少女幽霊の reference audio を録音 → girlGhostEmb を事前計算 | 🟢 低 |

---

## 関連ファイル

- Phase 1 レポート: `docs/reports/spikes/2026-05-06_sentis-cosyvoice-phase1-success.md`
- Phase 2 レポート: `docs/reports/spikes/2026-05-07_cosyvoice-phase2-onnx-export.md`
- ONNX export スクリプト: `voiceCoppy_test/export_cosyvoice3_onnx.py`
- spk projection 抽出: `voiceCoppy_test/extract_spk_projection.py`
