# Inference Engine (Sentis 2.5) Spike

CosyVoice VC コンポーネントを Unity Inference Engine 2.5 で動作検証する。

## 配置物

```
Assets/SentisSpike/
├── README.md                           本ファイル
├── Scripts/
│   └── SentisLoadTest.cs               検証スクリプト (Unity.InferenceEngine namespace)
└── Models/
    ├── campplus.onnx                   28MB  (gitignore 対象)
    └── speech_tokenizer_v3.onnx        970MB (gitignore 対象)
```

## 前提

- Unity 6000.3.9f1 (確認済)
- com.unity.ai.inference 2.5.0 (確認済、Packages/manifest.json で導入済)
- ONNX 2 ファイル配置済 (本ディレクトリの Models/ 配下)

## 実行手順

### Step 1: Unity Editor を起動

```
C:\Users\tatuk\Desktop\GameDev\voice_horror\voice_Horror_Game
```

を開く。初回起動時に Assets/SentisSpike/ 配下のファイルが自動 import され、.meta ファイルが生成される (970MB の ONNX import に 1-3 分)。

### Step 2: シーンに検証コンポーネントを追加

1. 既存シーン or 新規シーン (`Assets/Scenes/SentisTest.unity` 等) を開く
2. Hierarchy で 右クリック → `Create Empty` → `SentisTestRunner` と命名
3. Inspector で `Add Component` → `SentisLoadTest`
4. Inspector で:
   - `Campplus Model`: `Assets/SentisSpike/Models/campplus.onnx` をドラッグ
   - `Tokenizer Model`: `Assets/SentisSpike/Models/speech_tokenizer_v3.onnx` をドラッグ
   - `Backend`: `GPUCompute` (デフォルト)
   - `Run On Start`: ✅

### Step 3: Play モード実行

`Play` ボタン → Console を確認。

成功時の出力:
```
=== Inference Engine (Sentis 2.5) Load Test ===
Backend: GPUCompute

[campplus.onnx]
  Loading model... OK (123ms)
  Input: input shape=(batch_size, sequence_length, 80) dtype=Float
  Output: output
  Worker create... OK (45ms)
  Input shape: [1, 100, 80] (random float)
  Forward pass... OK (50ms)
  Output shape: [1, 192]
  Output sample: [0.123, -0.456, 0.789, 0.012, -0.345]

[speech_tokenizer_v3.onnx]
  Loading model... OK (3421ms)
  ...
  Forward pass... OK (892ms)
  Output shape: [1, 50]
  Output sample: [123, 456, 789, ...]

=== Summary ===
  campplus.onnx        : OK
  speech_tokenizer_v3  : OK
[OK] Inference Engine 路線採用判定: 両モデルロード成功 → Phase 2 (flow + hift export) へ進行可
```

## 失敗時の対処

| エラー | 対処 |
|--------|------|
| `Unsupported operator <name>` | Inference Engine の op カバレッジ範囲外。事前 inspection では検出されなかったが、内部実装の差異の可能性。ONNX Runtime にピボット |
| `OutOfMemoryException` | 970MB が VRAM 限界。Backend を `CPU` に変更してリトライ |
| forward pass で NaN/Inf | Backend を `CPU` に変更して同じ入力で比較。CPU で NaN なら op 実装バグ、ONNX Runtime にピボット |
| 30 秒以上応答なし | モデルロード or import が長時間化。Console ログ確認、必要なら Editor を再起動 |
| `ModelAsset` が assign できない | .meta ファイル未生成。Project ビューで ONNX を右クリック → `Reimport` |

## 判定基準

| 結果 | 次のアクション |
|------|--------------|
| 両モデル動作 + forward < 2秒 | 🟢 **Inference Engine 路線採用** → Phase 2 (flow + hift export) |
| 両モデル動作 + forward 2-10秒 | 🟡 速度ベンチを ONNX Runtime と比較 |
| 片方動作・片方失敗 | 🟡 失敗側を調査、必要なら ONNX Runtime |
| 両方失敗 | 🔴 ONNX Runtime にピボット (`asus4/onnxruntime-unity`) |

## 関連ファイル

- `../../voiceCoppy_test/sentis_spike/ONNX_INSPECTION.md` — ONNX op 詳細
- `../../voiceCoppy_test/sentis_spike/README.md` — オリジナル検証手順 (空プロジェクト想定)
- `../../voiceCoppy_test/vc_engine_compare.json` — ComfyUI 3 エンジン比較 workflow

## メモ

- Inference Engine 2.5 は **Sentis の改名版**。namespace は `Unity.InferenceEngine` (旧 `Unity.Sentis`)。
- パッケージ名: `com.unity.ai.inference` (旧 `com.unity.sentis`)
- API は Sentis 2.x からほぼ互換 (ModelLoader.Load / Worker / Schedule / PeekOutput)。
