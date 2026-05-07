# Qwen3-TTS ONNX 化スパイク調査結果

**日付**: 2026-05-05
**スパイク目的**: Qwen3-TTS-12Hz-1.7B-Base を Unity ランタイム（Inference Engine 想定）で動かせるか判定
**結論**: **Inference Engine ではなく ONNX Runtime 経由で実行可能。すでに動く C# 実装が公開されている。**

---

## TL;DR

1. **ONNX 化は既に第三者によって完了済み**。ElBruno (MIT) が NuGet パッケージ + 事前 export 済モデル + C# .NET 推論パイプラインを公開済
2. **Unity Inference Engine (Sentis) は不向き**。autoregressive LLM + DynamicCache + sliding window attention の組合せで op カバレッジが厳しい
3. **採用すべきは Microsoft.ML.OnnxRuntime (Unity NuGet 経由)**。CUDA / DirectML 両対応、KV-cache を IO binding で扱える
4. **配布サイズ問題は残る**: 1.7B = ~10GB、0.6B = ~5.5GB。Steam 配信前提だと圧縮 / 量子化 / 0.6B 採用 / 初回 DL 方式の検討必須

---

## 1. Qwen3-TTS アーキテクチャ確認

[QwenLM/Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) ソース精読 + [HF model card](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base) の結果、**4 段構成**:

```
Text → BPE Tokenizer
     → Talker LM (1.7B, 28 layers, GQA 16/8 heads, hidden=2048)
       → 1st codebook token per step
     → Code Predictor (5 layers, hidden=1024)
       → remaining 31 codebook tokens
     → Vocoder (Mimi-based, 16 quantizers, BigVGAN-style upsampler 1920×)
     → 24kHz waveform
```

### 技術的ブロッカー候補（理論上）

| 要素 | ONNX 障害度 | 実際の解決策 |
|------|-----------|-------------|
| `transformers.cache_utils.DynamicCache` | 🔴 高 | eager attention + 手動 KV-cache 渡し |
| `use_kernel_forward_from_hub("RMSNorm")` | 🟡 中 | 標準 RMSNorm に置換 |
| Sliding window + full attention 混在 (`layer_types`) | 🟡 中 | 静的グラフで両方含めて分岐 |
| M-RoPE (3軸 RoPE) | 🟢 低 | torch.onnx で問題なし |
| Mimi codec (vocoder) | 🟢 低 | [Transformers.js での ONNX 実績あり](https://huggingface.co/kyutai/mimi) |
| Speaker Encoder (Res2Net + ECAPA-TDNN) | 🟢 低 | 純 CNN、export 容易 |
| 32 codebook 多段予測ループ | 🟡 中 | 推論ループは外側 (C#) で実装 |

→ 結論: **個別障害はあるが解決済み**。実証は次節。

---

## 2. 既存 ONNX 実装の発見

### 2.1 [elbruno/ElBruno.QwenTTS](https://github.com/elbruno/ElBruno.QwenTTS) (MIT, v1.0.1, 2026-05-02)

**完成度**: Production-ready
- NuGet 公開: `ElBruno.QwenTTS` / `ElBruno.QwenTTS.VoiceCloning`
- 28 リリース、CI/CD 稼働、Issue 0
- Blazor Web UI / CLI / NuGet ライブラリ 3形態

**事前 export 済モデル** (HF):
- [`elbruno/Qwen3-TTS-12Hz-0.6B-Base-ONNX`](https://huggingface.co/elbruno/Qwen3-TTS-12Hz-0.6B-Base-ONNX) — voice cloning 対応
- [`elbruno/Qwen3-TTS-12Hz-1.7B-CustomVoice-ONNX`](https://huggingface.co/elbruno/Qwen3-TTS-12Hz-1.7B-CustomVoice-ONNX) — instruct + 9プリセット音声
- [`elbruno/Qwen3-TTS-12Hz-0.6B-CustomVoice-ONNX`](https://huggingface.co/elbruno/Qwen3-TTS-12Hz-0.6B-CustomVoice-ONNX) — 9プリセット軽量

**ONNX export パイプライン** (`python/` ディレクトリ):
- `export_lm.py` (Talker LM)
- `export_speech_tokenizer.py` (Vocoder)
- `export_speaker_encoder.py` (voice cloning embedding)
- `export_vocoder.py` / `export_embeddings.py`
- `compat_patches.py`, `patch_models_for_dml.py` (DirectML 互換パッチ)

**C# 推論コード**:
```csharp
using ElBruno.QwenTTS.Pipeline;

using var pipeline = await TtsPipeline.CreateAsync("models",
    variant: QwenModelVariant.Qwen17B);
await pipeline.SynthesizeAsync(
    "今夜は冷えるね",
    speaker: "ono_anna",     // 日本語プリセット
    output: "girl.wav",
    language: "japanese",
    instruct: "speak softly with worry");

// Voice cloning
var cloner = await VoiceClonePipeline.CreateAsync();
await cloner.SynthesizeAsync("セリフ", "ref_3sec.wav", "out.wav", "japanese");
```

**GPU 加速**:
- CUDA: `Microsoft.ML.OnnxRuntime.Gpu` で NVIDIA GPU
- DirectML: `Microsoft.ML.OnnxRuntime.DirectML` で AMD/Intel/NVIDIA GPU（**Steam 配信での GPU 多様性に対応**）
- ハイブリッド: LM は GPU、Vocoder は CPU で VRAM 削減可能

### 2.2 他の選択肢

| 実装 | 言語 | 状態 |
|------|------|------|
| [SuzukiDaishi/Qwen3-TTS-ONNX-Rust](https://github.com/SuzukiDaishi/Qwen3-TTS-ONNX-Rust) | Rust | export スクリプト同梱 |
| [TrevorS/qwen3-tts-rs](https://github.com/TrevorS/qwen3-tts-rs) | Rust | 推論実装 |

→ Unity (C#) 統合視点では **ElBruno が圧倒的に最適**

---

## 3. Unity への組込み判定

### 3.1 Inference Engine (Sentis) は不向き

| 観点 | Sentis | ONNX Runtime |
|------|--------|--------------|
| op カバレッジ | 主に CV / 簡易モデル | フル LLM サポート |
| KV-cache 対応 | 動的 cache 弱い | IO Binding で完全制御 |
| autoregressive 生成 | 手動実装必須 | `RunWithBinding` で効率的 |
| GPU バックエンド | Compute Shader | CUDA / DirectML / TensorRT |
| 量子化 | INT8 限定的 | INT8/INT4/FP16/BF16 全対応 |
| Production 実績 | Unity 内のデモ程度 | 多数の商用利用 |
| **Qwen3-TTS 既存実装** | **なし** | **ElBruno NuGet 公開済** |

### 3.2 推奨アーキテクチャ

```
[Unity Game (voice_Horror_Game/)]
    ↓ Assembly Reference
[ElBruno.QwenTTS NuGet (via NuGetForUnity)]
    ↓ 内部呼出
[Microsoft.ML.OnnxRuntime + Microsoft.ML.OnnxRuntime.DirectML]
    ↓ ネイティブ DLL (onnxruntime.dll, DirectML.dll)
[GPU: CUDA / DirectML / CPU fallback]
```

**Unity 統合手順（仮）**:
1. NuGetForUnity を Unity プロジェクトに導入
2. `ElBruno.QwenTTS` + `Microsoft.ML.OnnxRuntime.DirectML` をインストール
3. `.NET Standard 2.1` 互換性を確認（Unity 2021+ なら OK）
4. ネイティブ DLL を `Assets/Plugins/x86_64/` に配置
5. C# で `TtsPipeline.CreateAsync()` 呼出

### 3.3 残るリスク

| リスク | 対策 |
|--------|------|
| **モデルサイズ 5.5-10GB** | 0.6B 採用 / INT8 量子化検証 / 初回 DL 方式 / Steam 配信前にユーザー判断 |
| **VRAM 占有 3-4GB** | 同 GPU 上で URP 描画と競合。LM=GPU + Vocoder=CPU ハイブリッド検証必要 |
| **生成遅延** | 「少女の電話」は数秒の遅延許容なら問題なし。リアルタイム用途は別途検証 |
| **NuGetForUnity 互換性** | Unity 6 + .NET Standard 2.1 環境でテスト必要 |
| **日本語品質** | ElBruno の README は日本語サポート明記、実音検証必要 |

---

## 4. 次のアクション提案

### Plan A: Unity 統合 PoC（推奨、所要 1 週間）

**目的**: 「voice_Horror_Game/ から ElBruno.QwenTTS で日本語音声を生成して再生」までを動かす

1. **Day 1**: ElBruno.QwenTTS を独立した .NET 8 コンソールアプリで動作確認
   - 0.6B モデル DL → 「今夜は冷えるね」を `ono_anna` voice で生成
   - 生成時間 / VRAM 占有を測定
   - 日本語の発音品質を耳で評価
2. **Day 2-3**: NuGetForUnity 経由で Unity に組込
   - 空の Unity プロジェクトで再生確認
   - `.meta` / DLL 配置 / .NET Standard 2.1 互換性問題の解決
3. **Day 4-5**: voice_Horror_Game に統合 + AudioSource 連携
   - UHFPS DialogueSystem との接続点設計
   - 初回起動時の DL UX（10GB 落とすので進捗バー必須）
4. **Day 6**: Voice cloning 検証
   - `voiceCoppy_test/my_sampleVoice.wav` でクローン → 既存 ComfyUI 結果と比較
5. **Day 7**: 報告書 + Phase 2 の本格実装計画

### Plan B: 量子化検証を先行（配布サイズが懸念な場合）

ElBruno.QwenTTS 自体に INT8 量子化版があるか確認 → なければ自前で `optimum.onnxruntime` で量子化試行

### Plan C: 0.6B で品質判定を先行

10GB の 1.7B vs 5.5GB の 0.6B で品質差を耳で判定。許容できれば 0.6B 採用で配布問題が大幅軽減

---

## 5. 元の予定からの変更点

当初プランの「Day 1-2 で ONNX export 可否確認」は **コードベース調査だけで判定確定**したため省略可能。代わりに **Plan A（Unity 統合 PoC）に直接移行**を推奨。

| 当初 Day | 当初予定 | 実際の判定 |
|---------|---------|-----------|
| Day 1-2 | ONNX 変換可否 | ✅ ElBruno が export 済、自前作業不要 |
| Day 3-4 | Inference Engine ロード確認 | ❌ Sentis は不向き、ONNX Runtime に変更 |
| Day 5 | C# 推論ループ実装 | ✅ ElBruno NuGet で完成済 |

**節約されたエンジニアリング工数**: 約 5-7 日

---

## 6. 関連リンク

- [QwenLM/Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) — 公式実装
- [Qwen/Qwen3-TTS-12Hz-1.7B-Base](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base) — 公式モデル (Apache 2.0)
- [elbruno/ElBruno.QwenTTS](https://github.com/elbruno/ElBruno.QwenTTS) — C# .NET 実装 (MIT)
- [ElBruno's ARCHITECTURE.md](https://github.com/elbruno/ElBruno.QwenTTS/blob/main/python/ARCHITECTURE.md) — 詳細パイプライン解説
- [kyutai/mimi](https://huggingface.co/kyutai/mimi) — Mimi codec（vocoder のベース）
- [Microsoft.ML.OnnxRuntime](https://www.nuget.org/packages/Microsoft.ML.OnnxRuntime/) — Unity で使う ONNX Runtime
- [NuGetForUnity](https://github.com/GlitchEnzo/NuGetForUnity) — Unity に NuGet を導入
