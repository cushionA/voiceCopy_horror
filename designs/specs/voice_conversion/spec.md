# spec: voice_conversion (kNN-VC + WavLM)

**Phase**: 7 (init-agent draft)
**Source**: Phase 5/6 spike 結果から派生
**Status**: draft (要 init-agent レビュー → 人間 spec-gate 承認)

## Overview

voice_horror のランタイム音声変換システム。kNN-VC + WavLM Large +
HiFiGAN により、プレイヤー音声と少女幽霊音声の **zero-shot voice
conversion** および **エンディング分岐用の話者類似度判定** を行う。

## Goal

- **G-1**: プレイヤーの発話を、少女幽霊の声色で再生できる (BAD ED 演出)
- **G-2**: ゲーム進行に応じて少女声 / プレイヤー声の混合比 α を動的に変えられる
        (「混ざっていく」narrative 演出)
- **G-3**: ゲーム終了時、プレイヤー全録音 vs 少女声プールの話者類似度で
        BAD/GOOD ED 分岐を行える
- **G-4**: 上記すべてを Unity ランタイムで Sentis 経由で実行 (外部 API 依存無し)

## Non-Goals

- 多言語対応 (日本語のみ前提、英語入力でも音響変換は動作するが品質保証なし)
- 0 ターゲット音声での zero-shot (matching set 構築のための target reference は必須)
- 5 分音声以上の長尺ストリーミング (ゲーム内録音は基本 30 秒以下を想定)
- TTS (text-to-speech) 機能 (本システムは VC のみ)

## Behavior (verifiableRequirements 候補)

### B-1 Voice Conversion

- **VC-001**: 16kHz mono の source audio (1〜30 秒) と matching set を入力すると、target 声色で再合成された 16kHz mono audio が出力される
- **VC-002**: source audio の発話内容 (音素列) は変換後も保たれる (音素エラー率 < 25%、cross_test サンプルで聴感確認)
- **VC-003**: 変換後 audio に NaN / Inf 値が含まれない
- **VC-004**: 変換後 audio の peak 振幅が 1.0 を超える場合、自動正規化が適用される (peak 0.95 にスケール)
- **VC-005**: 変換処理は warmup 後 1 秒音声に対し 50ms 以下で完了する (RTX 2070S 想定)
- **VC-006**: 変換中に VRAM 3GB を超えない

### B-2 Matching Set 管理

- **MS-001**: 任意の 16kHz mono audio を WavLM forward して [N, 1024] 特徴プールに変換できる
- **MS-002**: 既存プールに新規録音の特徴を **append** できる (player voice 蓄積)
- **MS-003**: 2 つのプール (target / player) を α 比率で混合し、変換用の合成プールを構築できる
- **MS-004**: プールは Unity `Application.persistentDataPath` に永続化され、ゲーム再起動後も復元される
- **MS-005**: プール 1 件の追加 (3 秒録音) は 0.5 秒以下で完了する
- **MS-006**: target プール作成時、推奨カバレッジ (5 分以上) を満たさない場合は warning ログを出す

### B-3 Speaker Similarity (BAD/GOOD 判定)

- **SS-001**: 2 つの WavLM 特徴プールに対し、コサイン類似度を [0.0, 1.0] 範囲で算出できる
  (1.0 = 同一、0.0 = 直交)
- **SS-002**: プレイヤー全録音 vs 少女声プールの類似度判定が、エンディング分岐の閾値判定に使える
  - 高類似 (default 閾値: > 0.85) → BAD ED 「カラダを奪われる」
  - 中類似 (0.40-0.70) → 「声を変えて攻略 → 電話切れ」分岐
  - 低類似 (< 0.40) → GOOD ED 「脱出成功」
- **SS-003**: 閾値は ScriptableObject 等の設定で調整可能
- **SS-004**: 類似度判定は WavLM を共用し、別途 ECAPA-TDNN 等の追加モデルを必要としない

### B-4 Sentis ランタイム

- **SR-001**: ゲーム起動時、WavLM + HiFiGAN ONNX をプリロードする
  (Loading 画面で 3 秒以下を想定、ONNX 合計 ~400MB)
- **SR-002**: 起動直後に warmup forward を 1 回実行する
  (cold start ~510ms を loading 画面に隠す)
- **SR-003**: BackendType.GPUCompute をデフォルトとし、GPU 不在時は CPU フォールバックする
- **SR-004**: ゲーム終了時、Sentis Worker を Dispose して GPU メモリを解放する

### B-5 デバッグ・運用

- **DB-001**: 任意の変換ステージ (audio, query features, matching set, output) を npy / wav に
  ダンプできる (NpyWriter / WavWriter 流用)
- **DB-002**: 各変換ジョブの計測値 (query_ms, match_ms, vocode_ms, total_ms) がログ出力される
- **DB-003**: matching set のサイズ・カバレッジ (frame 数) を Inspector / Editor から可視化できる

## Architecture (high level)

```
[マイク入力] ──→ AudioClip ──→ WavLMFeatureExtractor (Sentis Worker)
                                       │
                                       ▼
                                [N, 1024] features
                                       │
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                  ▼
            MatchingSetPool      KnnVcConverter   SpeakerSimilarityJudge
            (target / player)    (kNN match)      (cosine sim)
                    │                  │                  │
                    └──────────────────┘                  ▼
                            │                      ED 分岐 (BAD/GOOD)
                            ▼
                       converted features
                            │
                            ▼
                    HiFiGANVocoder (Sentis Worker)
                            │
                            ▼
                       output AudioClip
```

詳細クラス分割は `design.md` に記述する。

## Open Questions (init-agent → 人間 review で解決)

- **OQ-1**: target reference 5 分以上の収録は Phase 9 で実施。それまでは仮 30 秒で進めるが、品質基準をどこに置く?
- **OQ-2**: matching set の永続化フォーマット (npy / Sentis Tensor save / 独自バイナリ)
- **OQ-3**: SS-002 の閾値 0.85 / 0.40 はキャリブレーション必要。Phase 8 の演出実装時に
  実プレイヤー録音で再調整する想定で OK か
- **OQ-4**: warmup タイミング (起動時即時 vs シーン遷移時)。loading 画面の UX に依存

## 関連

- `designs/specs/voice_conversion/design.md` (本 spec から派生する設計)
- `designs/specs/voice_conversion/tasks.md` (TDD 単位の test cases)
- `docs/reports/spikes/2026-05-09_knn-vc-local-spike.md`
- `docs/reports/spikes/2026-05-09_knn-vc-sentis-port.md`
- `.claude/rules/sdd-workflow.md`
- `.claude/rules/effective-harnesses.md` (verifiableRequirements への接続)
