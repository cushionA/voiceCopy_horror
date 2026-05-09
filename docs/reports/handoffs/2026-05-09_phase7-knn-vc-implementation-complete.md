---
date: 2026-05-09
session_topic: Phase 7 kNN-VC 統合実装完了 (Group A-F)、Phase 8 着手準備
status: ready-for-next-phase
branch: feature/phase5-knn-vc-spike
related_pr: null
last_commit: 1c83f74
---

## 結論先行

Phase 7 (voice_horror への kNN-VC 統合実装) が **Group A〜F 完了**。
EditMode テスト 28 件すべて pass、ランタイム 7 components が揃っている。
**voice_horror に kNN-VC を組み込む準備完成** — GameObject にアタッチして
`Initialize() → WarmupAsync() → Convert(α)` で動作する状態。

残りは:
- Group G (パフォーマンステスト、PlayMode、ユーザー手動)
- Phase 8 (演出パターン実装: BAD ED 「奪われる」、混ざっていく、ささやき変換)
- Phase 9 (声優収録脚本設計、技術と独立で並行可)

---

## 完了した実装

### kNN-VC ランタイム (`voice_Horror_Game/Assets/SentisSpike/Scripts/KnnVc/`)

| File | Group | 責務 |
|------|-------|------|
| `WavLMFeatureExtractor.cs` | A | 16kHz mono audio → WavLM Layer 6 特徴 [N, 1024] |
| `MatchingSetPool.cs` | B | 特徴蓄積、weight 管理、npy 永続化 |
| `WeightedPoolBuilder.cs` | B | 2 プール × α → 重みつき合成プール |
| `KnnVcConverter.cs` | C | 重みつき kNN マッチ (matcher.py 移植版) |
| `HiFiGANVocoder.cs` | D | features → audio + peak 正規化 |
| `SpeakerSimilarityJudge.cs` | E | コサイン類似度 [0, 1] + 3 分岐判定 |
| `EdThresholdsAsset.cs` | E | ScriptableObject hot-fix 閾値 |
| `VoiceConversionService.cs` | F | MonoBehaviour ファサード、永続化、lifecycle |
| `KnnVcSentisLoadTest.cs` | (Phase 6) | Sentis ロード spike、参考保存 |

### EditMode テスト (`voice_Horror_Game/Assets/Tests/EditMode/KnnVc/`、計 28 件 pass)

| File | テスト数 | カバー |
|------|---------|-------|
| `WavLMFeatureExtractorTests.cs` | 6 | A-1〜A-4 (元 PlayMode から移動) |
| `MatchingSetPoolTests.cs` | 11 | B-1〜B-5 + WeightedPoolBuilder |
| `KnnVcConverterTests.cs` | 5 | C-1, C-1b, C-3 |
| `HiFiGANVocoderTests.cs` | 4 | D-1, D-2, D-3 |
| `SpeakerSimilarityJudgeTests.cs` | 8 | E-1, E-2, E-3 |

### 補助ユーティリティ

- `voice_Horror_Game/Assets/SentisSpike/Scripts/VoiceConversion/NpyReader.cs` 新規 (NpyWriter と対称、MatchingSetPool 永続化用)
- `voice_horror.Sentis.asmdef` (本体側、`Unity.InferenceEngine` 参照)
- `voice_horror.Tests.EditMode.KnnVc.asmdef` (テスト側、`includePlatforms: Editor`)

---

## Phase 7 spec / design / tasks 反映状況

`designs/specs/voice_conversion/spec.md` の Behavior 22 件のうち:

| Behavior | 状態 |
|----------|------|
| VC-001 ~ VC-006 (Voice Conversion) | ✅ 実装 + テスト |
| MS-001 ~ MS-006 (Matching Set 管理) | ✅ 実装 + テスト |
| SS-001 ~ SS-004 (類似度判定) | ✅ 実装 + テスト |
| SR-001 ~ SR-004 (Sentis ランタイム) | ✅ 実装、PlayMode 統合テストはユーザー手動 |
| DB-001 ~ DB-003 (デバッグ機能) | 🔶 Phase 8 で追加 |

`Architect/10_音声変換システム.md` で公式アーキテクチャ章として位置付け済。

---

## 重要な workflow 改善 (memory に保存)

`memory/feedback_test_workflow.md`:
- **EditMode テスト優先**: PlayMode は domain reload で UniCli server が落ちるため、Sentis Worker テストでも EditMode で書く
- Phase 6 KnnVcSentisLoadTest が Eval 経由で動作した実績から、Sentis Worker は EditMode で動作可
- PlayMode 必須テスト (Service lifecycle、パフォーマンス) は書きはするが、CI からは skip し、ユーザーがまとめて手動実行

これにより Phase 7 のテスト 34 件中 28 件を EditMode で実行できた (PlayMode 残 6 件は Group F の lifecycle 検証 + Group G パフォーマンス、ユーザー手動範疇)。

---

## ブランチ状態

```
feature/phase5-knn-vc-spike (HEAD = 1c83f74)
├─ Phase 5 spike (kNN-VC ローカル動作 + 品質確認)
├─ Phase 6 spike (Sentis 互換性 PASSED)
├─ Phase 7 spec / design / tasks (review 反映済)
├─ Architect/10_音声変換システム.md
├─ Group A〜F 実装 + 28 EditMode tests pass
└─ ONNX (~400MB、gitignored) は Sandbox から手動コピー
   (`Assets/SentisSpike/Models/KnnVc/{wavlm,hifigan}_*.onnx`)
```

PR #4 (Phase 4 撤退整理) は別途 review 待ち、main へマージ可能状態。

---

## 次セッションの選択肢

### 🅰 Phase 8 着手 (演出パターン実装)

具体タスク:
- BAD ED「カラダを奪われる」: PlayerPool 全体を target 声で再生する演出 scene
- 「混ざっていく」漸進演出: α 比率の時間変動 (narrative event 連動)
- ささやき変換: whisper-only matching set サブプール、ホラー要所で切替
- リアルタイムエコー演出 (ジャンプスケア時即時返答)
- 声色変えた攻略時の電話切れ判定 (similarity 中域検出)

### 🅱 Phase 9 着手 (声優収録脚本設計、技術と独立で並行可)

`designs/specs/voice_recording/recording-script.md` (新規):
- ATR503 文 + JSUT corpus を素材に音素バランス確認
- ホラー特有発話追加 (ささやき、叫び、すすり泣き、含み笑い)
- 韻律バリエーション設計 (同一文の平叙/疑問/命令/感嘆 複数テイク)
- 収録仕様書 (マイク設定、24kHz 以上、編集規格)
- プレイヤー側収録仕掛け (チュートリアルマイクテスト)

### 🅲 PR #4 review + main マージ → Phase 5/6/7 PR 作成

Phase 4 撤退整理を main に取り込んでから、現在のブランチを clean に整理して
Phase 5/6/7 を別 PR として出す。

### 🅳 ユーザー手動 PlayMode テスト実行 (Group F, G)

実機で `VoiceConversionService` の lifecycle 統合 + パフォーマンス計測 (RTF、VRAM)。
sandbox の cross_test 結果と Unity ランタイムの実測比較。

特に確認したい項目:
- **WarmupAsync の体感**: `_extractor.Warmup()` が main thread で 392ms 同期実行する。
  `yield return null` は forward 後にしか入らないため、loading 画面が一瞬フリーズする。
  許容できなければ `Awaitable.BackgroundThreadAsync()` で別スレッド化検討
  (ただし Sentis Worker の thread-safety は要確認、現状未保証)
- **KnnVcConverter のレイテンシ**: 1秒音声で **目標 5-15ms**。CPU 素朴実装 O(N1×N2×dim) のため、
  matching set 15000 frames 想定で 1-3 秒かかる可能性 → 実測で許容判断、NG なら Burst+Job
  System で SIMD 化検討

---

## 関連リソース

- 前回 handoff: `docs/reports/handoffs/2026-05-09_phase3.5-pivot-to-knn-vc.md`
- spec: `designs/specs/voice_conversion/{spec,design,tasks}.md`
- Architect 章: `Architect/10_音声変換システム.md`
- Phase 5 spike: `docs/reports/spikes/2026-05-09_knn-vc-local-spike.md`
- Phase 6 spike: `docs/reports/spikes/2026-05-09_knn-vc-sentis-port.md`
- sandbox: `C:/Users/tatuk/Desktop/Sandbox/knn-vc-spike/`
- ONNX: `voice_Horror_Game/Assets/SentisSpike/Models/KnnVc/` (gitignored)
- 公式 kNN-VC: https://github.com/bshall/knn-vc

## 注意点

- ONNX (~400MB) は gitignored、新規環境は sandbox の export スクリプトを再実行して用意
- TestSounds (~14MB) は git 追跡、`my_sampleVoice.wav` は本番リリース時に要削除
- Group F (Service lifecycle) と Group G (パフォーマンス) は PlayMode、ユーザー手動実行
- Phase 4 ブランチ (`feature/phase4-game-integration`) の PR #4 は別途 review/merge 待ち
- Phase 5/6/7 ブランチを後で main から rebase する余地あり (Phase 4 マージ後)
