# Sentis 2.5 + CosyVoice VC コンポーネント 動作検証 (Phase 1)

**日付**: 2026-05-06
**スパイク目的**: Unity Inference Engine (Sentis 2.5) で CosyVoice VC 用 ONNX が動作するか検証
**結果**: ✅ **完全成功**。Sentis 路線採用判定。

---

## TL;DR

- 両 ONNX モデルが Sentis 2.5 で **op エラーなく動作**
- **970MB の speech_tokenizer_v3.onnx が 232ms でロード**(超高速)
- **forward pass < 1秒**で voice_horror 用途に実用的
- Unity 6000.3.9f1 + GPUCompute backend + RTX 2070 Super で問題なし
- voice_horror は **Sentis 完全採用、Path A (ONNX 化 + Unity 直接実行) で進行**

---

## 検証構成

### 環境

| 項目 | 値 |
|------|-----|
| Unity | 6000.3.9f1 |
| Inference Engine (Sentis) | 2.5.0 (`com.unity.ai.inference`) |
| namespace | `Unity.InferenceEngine` (旧 `Unity.Sentis`) |
| GPU | NVIDIA RTX 2070 Super 8GB |
| Backend | GPUCompute |
| OS | Windows 11 |

### 検証コード配置

```
voice_Horror_Game/
├── Assets/SentisSpike/
│   ├── README.md
│   ├── Scripts/
│   │   ├── SentisLoadTest.cs              ← Runtime MonoBehaviour
│   │   └── Editor/
│   │       └── SentisSpikeSetup.cs        ← Editor MenuItem (シーン自動構築)
│   ├── Models/
│   │   ├── campplus.onnx                  (28MB, gitignored)
│   │   └── speech_tokenizer_v3.onnx       (970MB, gitignored)
│   └── SentisTest.unity                   ← 自動生成シーン
└── Packages/manifest.json
    ├── com.unity.ai.inference: 2.5.0      ← Sentis 本体
    └── com.yucchiy.unicli-server: v1.2.2  ← UniCli 経由制御
```

### UniCli による完全自動化

ファイル配置 → AssetDatabase.Refresh → Compile → シーン構築 → ModelAsset アサイン → Play モード起動 → 結果取得 まで **全て CLI 経由** で実行(ユーザー手動操作は Unity ウィンドウフォーカス1回のみ)。

```bash
unicli exec Console.Clear
unicli exec Menu.Execute --menuItemPath "Assets/Refresh"
unicli exec Compile
unicli exec Menu.Execute --menuItemPath "Tools/Sentis Spike/Setup Test Scene"
unicli exec Scene.Open --path "Assets/SentisSpike/SentisTest.unity"
unicli exec PlayMode.Enter
unicli exec Console.GetLog --json
```

---

## 結果詳細

### campplus.onnx (Speaker Encoder, 28MB)

| ステップ | 時間 | 状態 |
|---------|------|------|
| ModelLoader.Load | 47ms | ✅ |
| Worker create (GPUCompute) | 56ms | ✅ |
| Forward pass `[1, 100, 80]` → `[1, 192]` | **570ms** | ✅ |
| Output 値 | `[1.0038, 0.8996, 0.3254, 1.4457, -1.1398]` | ✅ NaN/Inf 無し |

入力 shape は `(d0, d1, 80)` (動的)、出力は **192次元 speaker embedding** が確定。

### speech_tokenizer_v3.onnx (Speech Tokenizer, 970MB)

| ステップ | 時間 | 状態 |
|---------|------|------|
| ModelLoader.Load (970MB) | **232ms** | ✅ 超高速 |
| Worker create (GPUCompute) | 13ms | ✅ |
| Forward pass `feats[1,128,200]` + `feats_length[200]` → `[1, 50]` | **852ms** | ✅ |
| Output token IDs | `[4874, 3028, 3386, 3145, 4568, 2381, 2540, 3062, 3107, 2417]` | ✅ |

入力 `feats` は dynamic `(1, 128, d0)`、`feats_length` は `(1)` int。出力は VQ token IDs (range 0-4895、codebook size 4896 想定)。

### 当初懸念事項の解消

| 懸念 | 結果 |
|------|------|
| Conformer の `RelativePositionAttention` op 不対応 | 該当 op 不使用、Standard Self-Attention で構成 (事前 ONNX inspection 通り) |
| 970MB がテンソルサイズ制約に抵触 | 232ms で問題なくロード |
| `int64` (feats_length) の dtype 互換性 | Sentis 内部で正常処理 |
| GPUCompute で精度問題 (NaN/Inf) | 出力値正常範囲 |
| Conformer 系 attention の op 実装バグ | バグなし、再現性あり |

---

## Sentis vs ONNX Runtime 判定

| 観点 | Sentis 2.5 (実測) | ONNX Runtime (推定) |
|------|------------------|-------------------|
| 970MB ロード時間 | **232ms** | 1-3秒 |
| forward pass 速度 | 570-852ms | 同等 (CUDA EP 使用時 やや速) |
| op カバレッジ | **問題なし** | 問題なし |
| GPU ベンダ非依存 | ✅ Compute Shader | DirectML 経由で部分対応 |
| ネイティブ DLL 不要 | ✅ | 必要 (~100MB) |
| Unity 統合 | ✅ ネイティブ | NuGetForUnity 経由 |
| 量子化対応 | 限定的 | 全種対応 |

→ voice_horror の VC 用途では **Sentis が現実的に勝者**。配布性・統合性の優位が op カバレッジ懸念を上回ることが確認できた。

---

## 残コンポーネントの ONNX 化計画 (Phase 2)

CosyVoice VC 完全パイプラインに必要だが、まだ ONNX 化されていない:

| コンポーネント | サイズ | 状態 | export 方法 |
|--------------|--------|------|-----------|
| campplus | 28MB | ✅ 公式 ONNX 同梱 | – |
| speech_tokenizer_v3 | 970MB | ✅ 公式 ONNX 同梱 | – |
| **flow.decoder.estimator** | flow.pt の一部 | 🟡 公式 export_onnx.py で部分 export 可 | `python -m cosyvoice.bin.export_onnx --model_dir <path>` |
| flow.encoder + length_predictor | flow.pt の残部 | 🔴 自前 export 必要 | torch.onnx.export で個別 export |
| **hift** (vocoder) | 83MB | 🔴 公式 ONNX 化未対応 | 自前 export 必要 |
| mel feature extractor | 軽量 | 🔴 C# DSP で代替推奨 | STFT + 80/128-mel filterbank を C# 実装 |

### Phase 2 タスク

1. (1日) 公式 export_onnx.py で `flow.decoder.estimator.fp32.onnx` 生成 → Sentis ロード確認
2. (2-3日) flow encoder + length predictor を自前 export → Sentis ロード確認
3. (1-2日) hift vocoder を自前 export → Sentis ロード確認
4. (3-4日) mel feature extractor を C# DSP で実装 (Whisper 系の参考実装多数)
5. (1週間) 4 モデル + DSP を連鎖させる C# パイプライン実装、ODE 積分ループ実装

→ Phase 2 完成で Unity 内で完全 VC が動作する状態に到達

---

## VC パイプライン全体図 (Phase 2 完成形)

```csharp
// プレイヤー声 (ref) → speaker embedding 抽出
ref_audio_pcm
  → MelExtractor (C# DSP, 80-mel)
  → campplus (Sentis)
  → speaker_embedding [1, 192]

// 少女セリフ (source) → token 抽出
source_audio_pcm
  → MelExtractor (C# DSP, 128-mel)
  → speech_tokenizer_v3 (Sentis)
  → source_tokens [1, T]

// VC: source content + ref voice → 音響特徴 → 波形
// (ODE 積分ループは C# で実装)
mel = noise [1, 80, T_audio]
for step in 0..n_steps:
    t = step / n_steps
    v = flow.decoder.estimator(mel, mask, mu, t, speaker_embedding, cond)  // Sentis
    mel = mel + v * dt

waveform = hift(mel)  // Sentis
  → AudioClip
  → AudioSource.PlayOneShot()
```

進行度に応じた morph (`speaker_embedding = α * 少女_emb + (1-α) * プレイヤー_emb`) は C# 1 行で実装可能。

---

## voice_horror への含意

Path A (Sentis 完全採用) が確定したことで:

| 項目 | 影響 |
|------|------|
| 配布サイズ | ~2.4GB (CosyVoice モデル各種、INT8 量子化で 600MB-1GB に削減可能性) |
| GPU 多様性 | Compute Shader で AMD/Intel/NVIDIA 全カバー、Steam 配信で恩恵大 |
| ネイティブ DLL | 不要、Unity Player ビルド単体で完結 |
| 推論コスト | URP 描画と同 GPU 共有、フレーム間で VC 1回程度なら問題なし |
| ライセンス | Apache 2.0 (CosyVoice) + Unity 標準 + ChatterBox 比較で MIT、商用配布可 |
| 工数見積 | Phase 2 (残コンポーネント export + パイプライン実装) で 2-3 週間 |

---

## 関連ファイル

- `voice_Horror_Game/Assets/SentisSpike/` — 検証コード一式
- `voice_Horror_Game/Assets/SentisSpike/Scripts/SentisLoadTest.cs` — Runtime テストコンポーネント
- `voice_Horror_Game/Assets/SentisSpike/Scripts/Editor/SentisSpikeSetup.cs` — Editor MenuItem 自動セットアップ
- `voiceCoppy_test/sentis_spike/ONNX_INSPECTION.md` — 事前 ONNX op 検査結果
- `voiceCoppy_test/sentis_spike/README.md` — 当初検証手順
- `docs/reports/spikes/2026-05-05_qwen3-tts-onnx-feasibility.md` — 関連スパイク (Qwen3 ONNX 調査)

---

## 次のアクション

1. **本 spike report をベースに Phase 2 のタスク分解** (flow / hift export スパイク)
2. CosyVoice 公式 `export_onnx.py` を実行して `flow.decoder.estimator.fp32.onnx` 生成試行
3. 生成された ONNX を本検証と同じ枠組み (`SentisLoadTest.cs` 拡張) でロード確認
4. Phase 2 完了後、4 モデル + DSP の C# パイプライン実装スパイク
