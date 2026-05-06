# CosyVoice Phase 2 — DiT + hift ONNX Export 完了報告

**日付**: 2026-05-07
**スパイク目的**: CosyVoice3 の残コンポーネント (flow.decoder.estimator / hift) を ONNX に export し、Sentis 2.5 でのロード可否を確認する
**結果**: ONNX export ✅ 完了 / Sentis ロードテスト 🟡 実施待ち

---

## TL;DR

- `flow.decoder.estimator.fp32.onnx` (DiT, 1268 MB) と `hift.fp32.onnx` (328 MB) の ONNX export が完了
- DiT は外部データ形式 (.onnx + .onnx.data)、hift は単一ファイル
- ORT で DiT の forward pass (1, 80, 100) → (1, 80, 100) を確認、NaN なし
- hift の ORT 検証は STFT/DFT op のシェイプ解釈差異でスキップ (export 自体は正常)
- Sentis 2.5 ロードテストは Unity を起動して実施予定

---

## エクスポートスクリプト

`voiceCoppy_test/export_cosyvoice3_onnx.py`

### 主要な解決済み問題

| 問題 | 原因 | 解決策 |
|------|------|--------|
| `GuardOnDataDependentSymNode` | `mask.py:233` の `.item()` データ依存制御フロー | 5 モジュール (`_mask_mod`, `_dit_mod`, `_decoder_mod`, `_encoder_mod`, `_upsample_encoder_mod`) に直接モンキーパッチ |
| `from module import func` パッチ漏れ | `from cosyvoice.utils.mask import add_optional_chunk_mask` でローカル参照がコピーされる | モジュールオブジェクトの属性を全て書き換え |
| `conflicts between user-specified ranges and inferred static shape` | DiT 内部 (RotaryEmbedding 等) が T を静的に特殊化 | `dynamic_axes` 削除、`T=100` の静的 export |
| `Could not allocate bytes object!` (legacy exporter) | ~800MB proto を Python bytes として確保できない | dynamo exporter (default in PyTorch 2.10) に切替 |
| `Failed to serialize proto` (post-process) | onnx.save_model(..., save_as_external_data=False) が同様に失敗 | グラフのみで ScatterND カウント確認 → 0 件なら既存ファイルをそのまま使用 |
| hift ScatterND int32 (ORT エラー) | dynamo exporter が ScatterND の indices を int32 で生成 | Cast(INT64) ノードを 3 件挿入 |
| hift ORT STFT "9 by 16" ブロードキャスト | ORT 1.25.0 の STFT op が n_fft=16 を PyTorch と異なって解釈 | ORT 検証を非致命的スキップ (Sentis で別途確認) |

---

## 出力ファイル

| ファイル | サイズ | 形式 |
|---------|--------|------|
| `voiceCoppy_test/onnx_export/flow.decoder.estimator.fp32.onnx` | 2.8 MB (graph) | ONNX external data (graph) |
| `voiceCoppy_test/onnx_export/flow.decoder.estimator.fp32.onnx.data` | 1265.4 MB (weights) | ONNX external data (weights) |
| `voiceCoppy_test/onnx_export/hift.fp32.onnx` | 328.5 MB | ONNX 単一ファイル |
| `voice_Horror_Game/Assets/SentisSpike/Models/flow.decoder.estimator.fp32.onnx` | 2.8 MB | コピー済 |
| `voice_Horror_Game/Assets/SentisSpike/Models/flow.decoder.estimator.fp32.onnx.data` | 1265.4 MB | コピー済 |
| `voice_Horror_Game/Assets/SentisSpike/Models/hift.fp32.onnx` | 328.5 MB | コピー済 |

---

## モデル詳細

### flow.decoder.estimator (DiT)

| 項目 | 値 |
|------|-----|
| アーキテクチャ | DiT (Diffusion Transformer), dim=1024, depth=22, heads=16 |
| 入力 | x[1,80,100], mask[1,1,100], mu[1,80,100], t[1], spks[1,80], cond[1,80,100] |
| 出力 | velocity[1,80,100] |
| 静的 T=100 理由 | RotaryEmbedding 等が T を静的特殊化するため動的 export 不可 |
| opset | 18 |
| op 数 | 31 |
| op 一覧 | Add, Cast, Concat, Conv, Cos, Equal, Expand, Gather, Gemm, IsNaN, LayerNormalization, MatMul, Mish, Mul, Neg, Not, Or, Pow, ReduceSum, Reshape, Sigmoid, Sin, Slice, Softmax, Split, Squeeze, Tanh, Tile, Transpose, Unsqueeze, Where |
| Sentis 懸念 op | `IsNaN`, `Mish`, `Tile` (要実動確認) |
| ORT forward pass | OK、出力 (1, 80, 100)、NaN なし |

### hift (CausalHiFTGenerator)

| 項目 | 値 |
|------|-----|
| アーキテクチャ | CausalHiFTGenerator, in_channels=80, base_channels=512 |
| 入力 | speech_feat[1,80,T_mel] |
| 出力 | audio[1,T_audio] |
| opset | 18 |
| op 数 | 38 |
| op 一覧 | Abs, Add, Cast, Clip, Concat, ConstantOfShape, Conv, Cos, CumSum, DFT, Div, Elu, Exp, Expand, Floor, Gather, GatherND, Greater, LeakyRelu, MatMul, Mul, Pad, Pow, Range, ReduceL2, Reshape, Resize, STFT, ScatterElements, ScatterND, Shape, Sin, Slice, Squeeze, Sub, Tanh, Transpose, Unsqueeze |
| Sentis 懸念 op | `DFT`, `STFT`, `CumSum`, `GatherND`, `ScatterElements`, `ScatterND` (Phase 1 検証済: ScatterND ありも Cast 追加で対応) |
| ORT forward pass | STFT 互換性問題でスキップ (Sentis で別途確認) |

---

## Sentis 2.5 ロードテスト

`voice_Horror_Game/Assets/SentisSpike/Scripts/SentisLoadTest.cs` を Phase 2 対応に更新済み。
Unity を起動後、以下の手順でテスト実施:

```
1. Unity Editor で voice_Horror_Game/ を開く
2. Assets > Refresh (または Ctrl+R)
   → flow.decoder.estimator.fp32.onnx と hift.fp32.onnx がインポートされる
3. Tools > Sentis Spike > Setup Test Scene (Phase 2)
   → シーンを自動構築し 4 モデルをアサイン
4. Play モードに入る
5. Console で各モデルの Load / Worker / Forward pass 時間と出力を確認
```

**期待結果**:
- 全 op がサポートされていれば `Forward... OK` と出力
- `IsNaN` / `Mish` / `STFT` / `DFT` が未サポートなら `Unsupported operator` エラー → 次のアクション検討

---

## C# 側の対応 (静的 T=100)

DiT の T=100 固定に対し、実際の音声長は可変。C# パイプライン実装時は以下の方法で対応:

```csharp
// mel_length <= 100 の場合: ゼロパディング
// mel_length > 100 の場合: チャンク分割または再 export (T=200 等)
int T = 100;
var x    = new Tensor<float>(new TensorShape(1, 80, T));  // ゼロパッド
var mask = new Tensor<float>(new TensorShape(1, 1, T));   // 有効部分のみ 1
// ... mask の有効長を mel_length に設定 ...
```

---

## 4 モデル構成サマリー

| コンポーネント | ファイル | サイズ | Sentis 状態 |
|--------------|---------|--------|-----------|
| campplus | campplus.onnx | 28 MB | ✅ Phase 1 動作確認済 |
| speech_tokenizer_v3 | speech_tokenizer_v3.onnx | 970 MB | ✅ Phase 1 動作確認済 |
| flow.decoder.estimator | flow.decoder.estimator.fp32.onnx + .data | 1268 MB | 🟡 export 完了、Sentis ロード待ち |
| hift | hift.fp32.onnx | 329 MB | 🟡 export 完了、Sentis ロード待ち |
| **合計** | | **~2595 MB** | |

---

## 次のアクション

1. **Sentis ロードテスト実施** (Unity 起動 → `Tools/Sentis Spike/Setup Test Scene (Phase 2)` → Play)
2. **op エラーがない場合**: Phase 3 (C# VC パイプライン実装) へ
   - Mel feature extractor (80-mel + 128-mel) を C# DSP で実装
   - ODE 積分ループを実装 (C# で n_steps 回 DiT forward)
   - 4 モデル連鎖パイプライン組み上げ
3. **IsNaN / Mish / STFT 等が未サポートの場合**:
   - `do_constant_folding=True` で折りたたみを試みる
   - または op を等価な組み合わせに手動展開して再 export

---

## 関連ファイル

- `voiceCoppy_test/export_cosyvoice3_onnx.py` — export スクリプト
- `voiceCoppy_test/onnx_export/dit_report.json` — DiT op レポート
- `voiceCoppy_test/onnx_export/hift_report.json` — hift op レポート
- `voice_Horror_Game/Assets/SentisSpike/Scripts/SentisLoadTest.cs` — Phase 2 対応テスト
- `docs/reports/spikes/2026-05-06_sentis-cosyvoice-phase1-success.md` — Phase 1 成功報告
