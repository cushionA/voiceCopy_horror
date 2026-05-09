# legacy_cosyvoice/ — CosyVoice3 撤退時点の遺産

Phase 3.5 (2026-05-07) で **CosyVoice3 の Sentis 統合は撤退**した。
このディレクトリは、撤退時点までに書いた **debug / export / 検証スクリプト**
を将来の再開・参照のために保全したもの。

## 撤退理由 (要約)

DiT (`flow.decoder.estimator`) の `mu` 入力には CosyVoice3 内部の
**token encoder + length_regulator の隠れ状態** が必要。
生の acoustic mel を渡すと値域が訓練分布外で発散し、
出力 mel の **58% (4640/8000) が -inf** になっていた。

token encoder + length_regulator の ONNX export は数日規模で
sub-Phase 3 つ分の作業 (export / Sentis 互換 / 統合) が必要。
voice_horror の用途 (少女幽霊 1 体固定の声) には CosyVoice3 は overkill と
判断し、kNN-VC + WavLM 路線に切替えた (Phase 5)。

## ファイル一覧

### `diag_*.py` (15 個)
hift / DiT の各ステージで shape / 数値 / op を確認する診断スクリプト群。
hift の ScatterND int32→int64 cast 挿入、`shape_inference` で segfault する
Sentis 互換問題などの追跡に使用。

### `merge_dit_*.py`
DiT モデル ONNX export の merge スクリプト。`merge_dit_chunked.py` が
本番用 (`merge_dit_onnx.py` は protobuf 1.3GB で ACCESS_VIOLATION のため
chunked 版を使うこと)。

### `diagnose_onnx.py`, `verify_hift.py`
4 モデル (campplus / tokenizer / DiT / hift) の ONNX 構造解析と
Sentis 互換性事前チェック。

### `vc_engine_compare.json`, `vc_test_chatterbox.json`
ComfyUI 側 (TTS-Audio-Suite) で 3 エンジン (ChatterBox / ChatterBox 23-Lang /
CosyVoice3) を比較したワークフロー JSON。CosyVoice3 「一番似てる」判定の
根拠データ。

## 関連ドキュメント

- `docs/reports/handoffs/2026-05-07_phase3.5-noise-and-length.md` — 詳細
- `docs/reports/spikes/2026-05-07_cosyvoice-phase2-onnx-export.md` — Phase 2 成功記録
- `docs/reports/spikes/2026-05-07_cosyvoice-phase3-pipeline.md` — Phase 3 実装と限界

## 再開する場合

1. `voice_Horror_Game/Assets/SentisSpike/Scripts/VoiceConversion/` にある
   CosyVoice3 用 C# クラス (`VoiceConversionPipeline`, `FlowMatchingODE`,
   `MelExtractor`, `SpkEmbedProjection`) を起点
2. token encoder + length_regulator の ONNX export を `export_cosyvoice3_onnx.py`
   に追加実装
3. C# 側に `RunEncoder(tokens) → mu` を追加し、Pipeline を encoder 経由に修正

なお Phase 5 で導入する WavLM / HiFiGAN は CosyVoice3 と独立に動作するため
両者を併存させることも将来可能。
