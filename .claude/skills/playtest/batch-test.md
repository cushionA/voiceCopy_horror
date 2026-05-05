# バッチテストオーケストレーション

複数機能を一括テストする際のワークフロー。
FULL_WORKFLOWの6ステップ構造をベースに、複数機能をグルーピングして効率化する。

## 前提
- 各テスト種別の詳細: `references/test-types/t*.md`
- 機能→テストタイプのマッピング: `references/feature-test-matrix.md`
- レビュー専門家: `references/test-review-checklist.md`
- エディタ操作: `/unicli` スキル経由

## Skill Graph

```
START
  │ 入力: features[] (テスト対象機能リスト)
  │
  └──→ GRAPH:BATCH_ORCHESTRATE
```

---

## GRAPH:BATCH_ORCHESTRATE

FULL_WORKFLOWの6ステップを複数機能向けに最適化。

```
[Step 0: PREFLIGHT] ─→ [Step 1: PLAN] ─→ [Step 2: DESIGN] ─→ [Step 3: REVIEW]
                                                                    │
                                                    [不足]→ Step 2 に戻る
                                                    [十分]↓
                              [Step 4: EXECUTE] ─→ [Step 5: EVALUATE]
                                                    │
                                    [テスト不足]→ Step 1 に戻る
                                    [バグ]→ FIX → Step 4 に戻る
                                    [完了]→ REPORT → END
```

---

### Step 0: PREFLIGHT（1回、全機能共通）

```
[0a. CONNECTION_CHECK]
  │ unicli check → 接続確認
  │ ├─[失敗]──→ ユーザーに `/unicli` セットアップを案内 → END
  │ └─[成功]──→ 続行
  │
  └──→ [0b. COMPILE + SCENE_BUILD]
         │ `/unicli`: Compile → Console.GetLog
         │ `/unicli`: Menu.Execute "Tools/CLIInternal/Build Test Scene"
         │ `/unicli`: Compile
         │
         └──→ [0c. T6 PREFLIGHT]
                │ Read: references/test-types/t6-preflight.md
                │ 全機能の依存コンポーネント・レイヤー・シーン構成を一括チェック
                │ ├─[Fail]──→ REPORT_PREFLIGHT → END
                │ └─[Pass]──→ Step 1 へ
```

### Step 1: PLAN（全機能分を一括）

```
[1a. LOAD_FEATURES]
  │ python tools/feature-db.py list → 全機能取得
  │ features[] に該当する機能をフィルタ
  │
  └──→ [1b. GATHER_FEATURE_CONTEXT]
         │ 各機能の実装詳細を収集:
         │   python tools/feature-db.py get "機能名"
         │   Read: 実装ファイル → public API、状態変数、依存コンポーネント
         │   Read: 既存テストファイル → カバー済みケース
         │
         └──→ [1c. MAP_TO_MATRIX + GROUP]
                │ Read: references/feature-test-matrix.md
                │ 各機能のカテゴリ判定 + 必要テストタイプ列挙
                │
                │ テスト種別ごとにグルーピング:
                │   group_T1 = [◎/○の機能リスト]
                │   group_T2 = [◎/○の機能リスト]
                │   group_T3 = [◎/○の機能リスト]
                │   ... (T4-T9も同様)
                │
                └──→ Step 2 へ
```

### Step 2: DESIGN（機能×テストタイプごと）

```
[2a. DESIGN_PER_TYPE]
  │ 各グループについて:
  │   Read: references/test-types/t{N}.md
  │   専門家の知識 + 各機能の実装詳細 → テスト設計を生成
  │
  └──→ [2b. DESIGN_SCENE_REQUIREMENTS]
         │ Read: references/test-environment-profiles.md
         │ テスト設計からシーン環境計画を統合:
         │   - 全機能のPlayModeテストを1セッションでカバーする環境切替計画
         │   - プロファイル切替順序の最適化
         │
         └──→ Step 3 へ
```

### Step 3: REVIEW（全機能のテスト設計を一括レビュー）

```
[3a. REVIEW_SUFFICIENCY]
  │ Read: references/test-review-checklist.md
  │ 各機能について:
  │   実装コードの「テストすべき側面」vs テスト設計の網羅性を照合
  │
  │ ├─[不足あり]──→ 不足箇所を指摘 → Step 2 に戻る（不足箇所のみ再設計）
  │ └─[十分]──────→ Step 4 へ
  │
  │ ★ レビューループ上限: 2回
```

### Step 4: EXECUTE（テスト種別ごとに効率的に実行）

```
[Phase A: T1 LOGIC — EditMode, 1回]
  │ `/unicli`: TestRunner.RunEditMode
  │ 結果を機能ごとに分類して記録
  │
  └──→ [Phase B: PLAYMODE_SESSION — 1セッション]
         │
         │ [B-1. CONFIGURE — EditMode]
         │   AutoInputTester設定（Menu.Execute）
         │   `/unicli`: Scene.Open（テストシーン）
         │
         │ [B-2. PROFILER_START] (T5対象がある場合)
         │   `/unicli`: Profiler.StartRecording
         │
         │ [B-3. ENTER_PLAY]
         │   `/unicli`: PlayMode.Enter ← ★ここでのみEnter
         │
         │ [B-4. ENVIRONMENT-AWARE TEST PHASES] (PlayMode中)
         │   Step 2 で設計したシーン環境計画に従い:
         │
         │   [B-4-1. PROFILE:SAFE_INPUT → T2 AutoInput]
         │     敵/ボス/仲間を無効化・退避
         │     ポーリング: 10秒間隔、最大180秒
         │     完了判定: 「全」+「周完了」パターン
         │
         │   [B-4-2. PROFILE:COMBAT_PVE → T3/T7]
         │     敵を再有効化、攻撃距離に配置
         │     各機能のT3スナップショット検証 + T7動的操作
         │
         │   [B-4-3. 追加プロファイル切替]
         │     COMPANION_AI / PROJECTILE / BOSS 等を必要に応じて
         │     T4 Animator / T8 UI / T9 Screenshot も該当時に実行
         │
         │ [B-5. PROFILER_STOP] (T5対象がある場合)
         │   `/unicli`: Profiler.StopRecording + AnalyzeFrames + FindSpikes
         │
         │ [B-6. RUN_PLAYMODE_TESTS]
         │   `/unicli`: TestRunner.RunPlayMode（存在する場合）
         │
         │ [B-7. EXIT_PLAY]
         │   `/unicli`: Screenshot.Capture（最終エビデンス）
         │   `/unicli`: PlayMode.Exit ← ★ここでのみExit
```

### Step 5: EVALUATE（結果集約 + 次アクション決定）

```
[5a. COLLECT_RESULTS]
  │ 各フェーズの結果を集約
  │
  └──→ [5b. BUILD_MATRIX]
         │ 機能 × テストタイプの結果マトリクスを構築:
         │
         │ | 機能名 | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | PM | 判定 |
         │ |--------|----|----|----|----|----|----|----|----|----|----|------|
         │ 凡例: ✅ Pass / ❌ Fail / ⚠ Warning / — Skip
         │
         └──→ [5c. DECIDE_NEXT_ACTION]
                │
                ├─[全Pass]──→ [5d. REPORT + FEATURE_DB_UPDATE] → END
                │
                ├─[バグ発見]──→ GRAPH:FIX_ISSUES（SKILL.md参照）
                │                └─[修正完了]→ Step 4 に戻る
                │                └─[修正失敗]→ [5d. REPORT] → END
                │
                └─[テスト不足]──→ Step 1 に戻る

[5d. REPORT + FEATURE_DB_UPDATE]
  │ SKILL.md の「レポートテンプレート」に従い出力（Mode: "Batch"）
  │
  │ 判定ルール（feature-test-matrix.md参照）:
  │   ◎テスト全Pass → complete
  │   ◎テストにFail → in_progress
  │   ○テストのみFail → complete (警告付き)
  │
  │ python tools/feature-db.py update "機能名" --status <status> --test-passed N --test-failed M
  └──→ END
```

---

## 使い方

### 全機能テスト
```
/playtest full
```
→ feature-dbの全complete/in_progress機能をバッチテスト

### 特定機能群のテスト
```
/playtest full --feature Movement --feature Combat --feature HPSystem
```
→ 指定機能のみバッチテスト

### カテゴリ指定
```
/playtest full --combat-only
```
→ 攻撃系+防御系カテゴリの機能をバッチテスト

## 注意事項
- PlayMode セッションは**1回**に統合する（Enter/Exitの回数を最小化）
- T6 Preflight がFailしたら**即座に中断**（他テスト実行しない）
- Fix試行が3回失敗したらユーザーにエスカレーション
- 根本原因が複数システムにまたがる場合、修正を試みず分析結果のみ報告
- レビューループは最大2回。超過時は現状の設計で進行
