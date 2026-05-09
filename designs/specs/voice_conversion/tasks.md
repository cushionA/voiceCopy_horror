# tasks: voice_conversion (kNN-VC + WavLM)

**Phase**: 7 (init-agent draft)
**Source**: `spec.md` の Behavior + `design.md` のクラス分割
**Status**: draft (要 init-agent レビュー → 人間 tasks-gate 承認)

## Test Cases (TDD 単位)

各 task は Red → Green → Refactor で実装。EditMode テスト中心、Sentis Worker
を持つ部分のみ PlayMode。

### Group A: WavLMFeatureExtractor

#### Task A-1: 16kHz mono float[] からの特徴抽出
- **テスト**:
  - 5秒の sin 波 (16kHz mono) を投入 → output Tensor が `(1, 約 249, 1024)` shape
  - NaN / Inf が含まれない
  - 値域が訓練分布内 ([-25, 50] 程度)
- **対応 spec**: VC-001, VC-003, SR-003

#### Task A-2: AudioClip リサンプル経由抽出
- **テスト**:
  - 44.1kHz stereo の AudioClip を投入 → 内部で 16kHz mono に変換、特徴抽出
  - shape が同等
- **対応 spec**: VC-001

#### Task A-3: warmup の効果計測
- **テスト**:
  - cold start 1 回目 forward 時間を計測 → 通常より遅いことを確認
  - warmup 後 2-3 回目 forward が < 50ms であることを確認
- **対応 spec**: VC-005, SR-002

#### Task A-4: Dispose の正常動作
- **テスト**:
  - Dispose 後の ExtractFeatures 呼出が ObjectDisposedException を投げる
  - GPU メモリリークがない (前後の VRAM 計測)
- **対応 spec**: SR-004

### Group B: MatchingSetPool

#### Task B-1: 空プールの初期化
- **テスト**:
  - new MatchingSetPool("test") の FrameCount=0, ToTensor() shape=(0, 1024)
- **対応 spec**: MS-001

#### Task B-2: append 動作
- **テスト**:
  - random 特徴 [50, 1024] を append → FrameCount=50
  - 連続 append → 累積される
- **対応 spec**: MS-002, MS-005

#### Task B-3: WeightedPoolBuilder (重みつき kNN 用合成プール構築)
- **テスト**:
  - pool A (frame 100) と pool B (frame 100) を α=0.7 で Build
  - 合成 features shape = (200, 1024)、weights shape = (200,)
  - weights[0..99] (= A 部分) = 0.7、weights[100..199] (= B 部分) = 0.3
  - α=1.0 で B 部分の weight = 0、α=0.0 で A 部分の weight = 0
  - α=0.5 で全 weight = 0.5
- **対応 spec**: MS-003 (重みつき kNN 方式)

#### Task B-4: npy 永続化 (save/load round-trip)
- **テスト**:
  - random プール (features [N, 1024] + weights [N]) 作成
  - SaveTo() で `pool.npy` (features) + `pool_weights.npy` (weights) の 2 ファイル生成
  - LoadFrom() で復元 → 元プールと数値一致 (rtol < 1e-6)
  - npy ファイルが Python の `numpy.load()` で正常に読める (整合性確認用、CI 外)
- **対応 spec**: MS-004 (npy フォーマット)

#### Task B-5: カバレッジ計算 + 段階目標警告
- **テスト**:
  - 5 分相当 (15000 frames) で Coverage5MinRatio = 1.0
  - 1.5 分 (4500 frames) で Coverage5MinRatio = 0.3
  - target プール作成後、frame 数が以下の段階目標に達していなければ warning ログ:
    - スパイク: 1500 (30秒)
    - MVP: 9000 (3分)
    - 本番: 30000 (10分)
- **対応 spec**: MS-006 (段階的カバレッジ目標)

### Group C: KnnVcConverter

#### Task C-1: kNN マッチ単体 (重みなし)
- **テスト**:
  - query [10, 1024] vs matching set [100, 1024]、weights=null → output [10, 1024]
  - topk=4 で平均が取られていることを数値で検証 (matcher.py 出力との一致確認)
- **対応 spec**: VC-001 内部ロジック

#### Task C-1b: kNN マッチ重みつき
- **テスト**:
  - query 同じ、matching set [100, 1024]、weights=[1.0...0.0] (前半は重く、後半は軽く)
  - 重い frame の方が選ばれやすいことを数値で検証
  - weight=0 の frame は決して選ばれないこと
  - α=1.0 (target weight 全 1.0、player weight 全 0.0) のケースで b プール完全無視
- **対応 spec**: MS-003 重みつき kNN

#### Task C-2: cosine_dist 数値一致 [SCOPE OUT]
- **判定**: Phase 7 review (2026-05-09) で **scope out**。
  matcher.py との数値一致は Python sandbox (`C:/Users/tatuk/Desktop/Sandbox/knn-vc-spike/`)
  で sandbox 検証フェーズに完了済 (Phase 5 spike report)。
  Unity 側の C# 実装の数値正確性は C-1 (shape) + C-1b (重みつき動作) + C-3 (identity) で
  実用上カバーできているため、matcher.py 完全一致テストは過剰投資と判断。
- **対応 spec**: 削除 (元 VC-001 数値正確性、C-1/C-1b/C-3 でカバー)

#### Task C-3: 同一プール変換 (identity test)
- **テスト**:
  - query == matching set の subset の場合、output が query にほぼ一致 (L1 < 0.1)
- **対応 spec**: VC-002

### Group D: HiFiGANVocoder

#### Task D-1: dummy 特徴 → audio
- **テスト**:
  - random 特徴 [1, 250, 1024] を vocode → audio [80000] 出力
  - NaN / Inf なし
- **対応 spec**: VC-003

#### Task D-2: peak 正規化
- **テスト**:
  - peak > 1.0 の出力 → VocodeNormalized で peak が 0.95 にスケール
  - peak <= 1.0 の出力 → 変更なし
- **対応 spec**: VC-004

#### Task D-3: 入力 shape の罠検証
- **テスト**:
  - (B, dim, T_frame) で投入したら適切なエラー (HiFiGAN は channel-last なので)
  - (B, T_frame, dim) で投入したら正常動作
- **対応 spec**: 設計時の事故防止

### Group E: SpeakerSimilarityJudge

#### Task E-1: cosine 類似度の境界値 + 値域 [0, 1] クランプ
- **テスト**:
  - 同一プール (a == b) の類似度 == 1.0
  - 直交プール (a · b == 0) の類似度 == 0.0
  - **逆方向プール** (a · b == -1) の類似度 == 0.0 (max(0, cos) クランプの確認)
  - 一方が空プールならば例外
- **対応 spec**: SS-001 ([0, 1] クランプ)

#### Task E-2: ED 判定 (3 分岐)
- **テスト**:
  - sim=0.9 → BadCaptured
  - sim=0.5 → BadVoiceChange
  - sim=0.2 → Good
  - sim=0.85, 0.7, 0.4 (境界) の挙動を inclusive/exclusive で明示
- **対応 spec**: SS-002

#### Task E-3: EdThresholdsAsset (ScriptableObject) 注入
- **テスト**:
  - 標準閾値 SO (High=0.85, Low=0.40, MidHigh=0.70) で sim=0.5 → BadVoiceChange
  - SO の閾値を変更 (High=0.4) して同じ sim=0.5 → BadCaptured に変わる
  - 本番リリース後も SO 差し替えで hot-fix 可能であることを demo
- **対応 spec**: SS-003 (ScriptableObject による hot-fix)

### Group F: VoiceConversionService (統合)

#### Task F-1: Initialize → WarmupAsync → Convert → OnDestroy 全体パス (PlayMode)
- **テスト**:
  - Initialize 後、target プール存在を assert (空プールならエラー)
  - WarmupAsync を yield return で完了待ち、cold start の影響を測る
  - 30秒の dummy AudioClip を Convert → 出力 AudioClip が同じ長さ
  - NaN / Inf なし、peak 振幅 ≤ 1.0 (peak 正規化適用済)
  - GameObject.Destroy で OnDestroy → Dispose → GPU メモリ解放確認
- **対応 spec**: VC-001 ~ VC-006, SR-001 ~ SR-004 (lifecycle 全体)

#### Task F-2: AccumulatePlayerVoice (PlayMode)
- **テスト**:
  - 3 回 AccumulatePlayerVoice → PlayerPool.FrameCount が増加
  - 永続化されていることを確認
- **対応 spec**: MS-002, MS-005

#### Task F-3: α=0 / 0.5 / 1.0 の Convert 出力差 (PlayMode)
- **テスト**:
  - 同じ source で α 変動 → 出力 audio が異なる (L1 比較で 0 でない)
  - α=1.0 で純 target、α=0.0 で純 player
- **対応 spec**: G-2 narrative 演出

#### Task F-4: JudgeEnding 統合 (PlayMode)
- **テスト**:
  - target プール = 少女声 dummy / player プール = 同一 dummy → BadCaptured
  - target プール = 少女声 dummy / player プール = 直交 random → Good
- **対応 spec**: SS-002, G-3

### Group G: パフォーマンステスト (PlayMode)

#### Task G-1: warmup 後 RTF 確認
- **テスト**:
  - 5 秒 audio の Convert (warmup 後) が < 250ms (RTF 0.05、RTX 2070S 想定)
- **対応 spec**: VC-005

#### Task G-2: VRAM 上限
- **テスト**:
  - Initialize + 30 秒 Convert で peak VRAM < 3GB
- **対応 spec**: VC-006

#### Task G-3: 連続変換のメモリリーク (PlayMode)
- **テスト**:
  - Convert を 100 回連続実行 → VRAM が単調増加しない (リーク無し)
- **対応 spec**: SR-004

## 実装順序 (推奨)

```
A-1 → A-3 → A-4              (WavLMFeatureExtractor 基本)
   ↓
B-1 → B-2 → B-3 → B-4 → B-5  (MatchingSetPool)
   ↓
C-1 → C-2 → C-3              (KnnVcConverter)
   ↓
D-1 → D-2 → D-3              (HiFiGANVocoder)
   ↓
E-1 → E-2 → E-3              (SpeakerSimilarityJudge)
   ↓
F-1 → F-2 → F-3 → F-4        (Service 統合、PlayMode)
   ↓
G-1 → G-2 → G-3              (パフォーマンス)
```

A から順に進めて TDD ワークフローを回す。F (Service) は単体クラスが揃ってから着手。

## Coverage と verifiableRequirements

各 spec の Behavior は以下の task でカバー:

| Behavior ID | カバー task |
|-------------|------------|
| VC-001 | A-1, A-2, C-1, F-1 |
| VC-002 | C-3 |
| VC-003 | A-1, D-1 |
| VC-004 | D-2, F-1 (peak 正規化) |
| VC-005 | A-3, G-1 |
| VC-006 | G-2 |
| MS-001-002, MS-005 | B-1, B-2 |
| MS-003 (重みつき kNN) | B-3, C-1b |
| MS-004 (npy 永続化) | B-4 |
| MS-006 (段階目標) | B-5 |
| SS-001 ([0,1] クランプ) | E-1 |
| SS-002 (3 分岐) | E-2, F-4 |
| SS-003 (SO hot-fix) | E-3 |
| SS-004 (WavLM 共用) | (アーキテクチャ依存、別途レビュー) |
| SR-001 (起動プリロード) | F-1 |
| SR-002 (warmup タイミング) | A-3, F-1 |
| SR-003 (CPU フォールバック) | (環境依存、手動テスト) |
| SR-004 (Dispose) | A-4, F-1, G-3 |
| DB-001-003 | (Group H 想定、Phase 8 で追加) |

カバー漏れ:
- DB-* (デバッグ機能) は Phase 8 で実装
- SS-004 (WavLM 共用、追加モデル不要): 設計レベルの主張で、Phase 7 実装で
  ECAPA-TDNN を呼び出さないことの確認のみ
- SR-003 (CPU フォールバック): GPU 不在環境での動作は手動テスト

## 関連

- `designs/specs/voice_conversion/spec.md`
- `designs/specs/voice_conversion/design.md`
- `.claude/rules/test-driven.md` (TDD ワークフロー)
- `designs/pipeline-state.json` (verifiableRequirements 連動、Phase 19 二相運用時に自動同期)
