# Legacy/CosyVoice3/ — Phase 1-4 撤退時点スナップショット

CosyVoice3 ベース VC パイプラインの C# 実装と検証用シーンを保存している。
**Phase 5 以降は kNN-VC 路線で進める**ため、本ディレクトリのコードは
**ビルド時の参照保証なし**。Unity が AssetDatabase に登録するため
コンパイル自体は通るが、Phase 5 では呼び出し元コードが存在しない。

## 撤退理由

`docs/reports/handoffs/2026-05-09_phase3.5-pivot-to-knn-vc.md` を参照。
要点:

- DiT (`flow.decoder.estimator`) の `mu` 入力に **token encoder + length_regulator
  の隠れ状態** が必要。生 acoustic mel では値域が訓練分布外で発散し、
  出力 mel の **58% (4640/8000) が -inf** になっていた
- token encoder + length_regulator の ONNX export は数日規模の追加作業が必要
- voice_horror の用途 (少女幽霊 1 体固定の声、narrative の蓄積演出) には
  CosyVoice3 は overkill (合計 2.6GB VRAM、複雑な LLM token decoder)
- kNN-VC + WavLM (~900MB VRAM、1 モデル 2 役) のほうが narrative 適合性が高い

## ファイル構成

```
Legacy/CosyVoice3/
├── README.md                 (本ファイル)
├── Scripts/
│   ├── SentisLoadTest.cs     Phase 1-2: 4 モデル Sentis ロード確認
│   ├── VoiceConversionTest.cs Phase 3: コンポーネント単体テスト T1-T5
│   ├── Editor/
│   │   ├── SentisSpikeSetup.cs       Phase 1-2 シーン setup
│   │   ├── SentisSpikeSetupPhase3.cs Phase 3 シーン setup
│   │   ├── SentisSpikeSetupPhase4.cs Phase 4 (VC bench) シーン setup
│   │   └── VoiceConversionBenchEditor.cs Inspector 拡張
│   └── VoiceConversion/
│       ├── VoiceConversionPipeline.cs  4 モデル統合パイプライン
│       ├── FlowMatchingODE.cs          DiT ODE solver (uniform schedule、cosine 未対応)
│       ├── MelExtractor.cs             matcha-tts 準拠 mel 抽出 (Phase 3.5 で書き換え途中、未完)
│       ├── SpkEmbedProjection.cs       campplus 192-dim → DiT 80-dim 線形投影
│       ├── SpeakerMorphController.cs   spk_emb 補間で「声が混ざっていく」演出 (CosyVoice3 用)
│       └── VoiceConversionBench.cs     オフラインベンチ (hift-only モード対応)
└── Scenes/
    ├── SentisTest.unity        Phase 1-3 検証シーン
    └── SentisVCBench.unity     Phase 4 VC ベンチシーン
```

## 関連リソース (Legacy 外、参照保存)

- ONNX 重み: `voice_Horror_Game/Assets/SentisSpike/Models/` (~2.5GB, gitignored)
- Python export / debug: `voiceCoppy_test/legacy_cosyvoice/` (15+ スクリプト、独立 README 付)
- 撤退時点の handoff: `docs/reports/handoffs/2026-05-09_phase3.5-pivot-to-knn-vc.md`
- Phase 1-3 spike report: `docs/reports/spikes/2026-05-0{6,7}_*.md`

## 復活手順 (将来 CosyVoice3 に戻る場合)

### 前提

kNN-VC ルートが品質不足で頓挫し、token encoder export を覚悟して再開する場合。
voice_horror の VRAM 予算 (2.6GB を確保できるか) と工数予算 (4-5日 sub-Phase 3 つ分)
を再検討の上で。

### 手順

1. **Python 側で encoder ONNX export 追加実装**
   - `voiceCoppy_test/legacy_cosyvoice/` から関連スクリプトをコピー
   - `flow.encoder` (FSMN/Transformer) と `length_regulator` (token-mel 対応) を export
   - 既存 `merge_dit_chunked.py` のパターンを参考にチャンク merge

2. **Sentis 互換性確認**
   - 新 ONNX (encoder, length_regulator) を Sentis 2.5 でロード
   - PyTorch 出力との数値一致 (rtol < 1e-3)

3. **C# 側に encoder ステージ追加**
   - 本 Legacy ディレクトリのコードを `voice_Horror_Game/Assets/SentisSpike/Scripts/`
     に戻す (git mv の逆)
   - `VoiceConversionPipeline` に `RunEncoder(tokens) → mu` ステージを追加
   - `mu = source mel` を `mu = encoder(speech_tokenizer出力) → encoder_proj` に置換
   - `FlowMatchingODE` の t_scheduler を **cosine** (`1 - cos(t·π/2)`) に修正
   - CFG (`inference_cfg_rate=0.7`) を export 時 baked-in したか再確認

4. **MelExtractor 残課題**
   - Hann window: symmetric → **periodic** に変更
   - n_fft=1920 zero padding to 2048 → **real 1920 FFT** で実装
   - Slaney mel filterbank の数値を matcha-tts と要素一致確認

5. **聴感品質確認**
   - Phase 4 bench (`SentisVCBench.unity`) で source/target ペア変換テスト
   - DiT 出力 mel に -inf が混入しないこと
   - hift 出力音声がノイズでなく言語認識可能なこと

### 残作業見積もり

| 段階 | 工数 |
|------|------|
| encoder + length_regulator export | 2-3日 |
| Sentis 互換性検証 | 1-2日 |
| C# 統合 + MelExtractor 修正 | 1日 |
| 品質確認 + 微調整 | 半日 |
| **合計** | **4-5日** |

VRAM が問題でなければ kNN-VC との併存も可能 (BAD ED 用に CosyVoice3、
インゲーム用に kNN-VC、など分離運用)。

## 注意

本ディレクトリのコードを **Phase 5 以降の kNN-VC 実装と混在させない**こと。
Phase 5 で `Scripts/KnnVc/` 等の新ディレクトリを切り、namespace も分離する
ことで意図せぬ参照を防ぐ。
