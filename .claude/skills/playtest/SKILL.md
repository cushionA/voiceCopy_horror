---
name: playtest
description: Run editor play testing workflow - build test scenes, execute auto-input tests, analyze errors, and fix issues. Use when testing feature-db features via editor play, designing auto-input sequences, or debugging runtime issues. Trigger on "playtest", "play test", "editor test", "auto input test", or when verifying game mechanics in editor.
user-invocable: true
argument-hint: [full|fix] [--feature FeatureName] [--combat-only] [--movement-only]
---

# Play Test: $ARGUMENTS

feature-dbに登録された機能をエディタ実行で検証するSkill Graphワークフロー。
エディタ操作は `/unicli` スキル経由で実行する（コマンド詳細は `/unicli` を参照）。

## このスキルの使い所

- **エディタ実行検証のオーケストレーション**スキル。単純なテスト実行ではない
- T1-T9 のテストタイプ設計・実行、シーン環境構築、バグ発見→修正ループ、レポート生成までを一気通貫
- 典型例: feature-db 機能群の一括検証、リリース前の総合テスト、バグ調査
- **Unity Test Runner を回すだけで十分**なら `/run-tests` を使う（本スキルは T1 実行時にそちらを呼ばず直接 Unity CLI/MCP を叩く）

## Skill Graph

```
START
  │
  ├─[arg == "full" or no arg]──→ GRAPH:FULL_WORKFLOW
  │   └─[複数機能指定時]────────→ batch-test.md の GRAPH:BATCH_ORCHESTRATE
  ├─[arg == "fix"]─────────────→ GRAPH:FIX_ISSUES
  └─[その他]───────────────────→ GRAPH:FULL_WORKFLOW（引数をフィルタとして使用）
```

---

## GRAPH:FULL_WORKFLOW

6ステップの完全プレイテストサイクル。

```
[0. PREFLIGHT] ─→ [1. PLAN] ─→ [2. DESIGN] ─→ [3. REVIEW] ─→ [4. EXECUTE] ─→ [5. EVALUATE]
                                     ↑              │                              │
                                     └──[不足]───────┘              [テスト不足]→ [1]に戻る
                                                                    [バグ]→ FIX → [4]に戻る
                                                                    [完了]→ REPORT → END
```

### Step 0: PREFLIGHT

接続確認・コンパイル・T6プリフライトチェック。ここを通らなければテストに進まない。

```
[0a. CONNECTION_CHECK]
  │ unicli check → 接続確認
  │ ├─[失敗]──→ ユーザーに `/unicli` セットアップを案内 → END
  │ └─[成功]──→ 続行
  │
  └──→ [0b. COMPILE_CHECK]
         │ unicli exec Compile
         │ unicli exec Console.GetLog --json
         │
         ├─[compile error]──→ [REPORT_COMPILE_ERROR] → END
         │
         └─[success]──→ [0c. SCENE_BUILD]
                          │ `/unicli`: Menu.Execute "Tools/CLIInternal/Build Test Scene"
                          │ `/unicli`: Compile  # 再コンパイル待ち
                          │
                          └──→ [0d. PREFLIGHT_CHECK (T6)]
                                 │ Read: references/test-types/t6-preflight.md
                                 │ `/unicli`: GameObject.Find --tag "Player" → レイヤー確認
                                 │ `/unicli`: GameObject.Find --tag "Enemy" → レイヤー・コンポーネント確認
                                 │ `/unicli`: Eval → GameManager/CharacterRegistry初期化確認
                                 │ `/unicli`: Prefab.GetStatus → プレハブ整合性
                                 │ Fail時 → [REPORT_PREFLIGHT_FAILURE] → END
                                 │
                                 └──→ Step 1 へ
```

### Step 1: PLAN

テスト対象機能を受け取り、必要なテストタイプを判断する。

```
[1a. LOAD_FEATURES]
  │ ├─[--feature指定あり]──→ 指定機能のみ取得
  │ ├─[--combat-only]──────→ 攻撃系+防御系カテゴリの機能を抽出
  │ ├─[--movement-only]────→ 移動系カテゴリの機能を抽出
  │ └─[指定なし]───────────→ python tools/feature-db.py list --status complete + in_progress
  │
  └──→ [1b. GATHER_FEATURE_CONTEXT]
         │ 各機能の実装詳細を収集:
         │   python tools/feature-db.py get "機能名" → 実装ファイル・テストファイルパス取得
         │   Read: 実装ファイル → public API、状態変数、依存コンポーネントを把握
         │   Read: 既存テストファイル → カバー済みケースを把握
         │   Read: Architect/ の関連設計文書（必要時のみ）
         │
         └──→ [1c. MAP_TO_MATRIX]
                │ Read: references/feature-test-matrix.md
                │ 各機能をマトリクスに照合:
                │   - 機能カテゴリを特定
                │   - ◎必須/○推奨/△任意テストを列挙
                │   - 既存テスト（TestRunner.List）でカバー済みのものを除外
                │
                └──→ 出力: 機能ごとの「必要テストタイプリスト」
                       → Step 2 へ
```

### Step 2: DESIGN

各テストタイプの専門家（t*.md）が、機能の要件に基づいてテストを設計する。
シーン環境の要件もここで決定する。

```
[2a. DESIGN_PER_TYPE]
  │ Step 1 で必要と判断されたテストタイプごとに:
  │   Read: references/test-types/t{N}.md （専門家の知識をロード）
  │   専門家の知識 + 機能の実装詳細 → テスト設計を生成
  │
  │ 各専門家が設計する内容:
  │   - T1: EditModeテストケース（検証項目・境界値・期待結果）
  │   - T2: AutoInputテストステップ（入力パターン・検証コールバック）
  │   - T3: スナップショット検証項目（何をEvalで取得し何と比較するか）
  │   - T4: Animator遷移パス（検証する状態遷移・パラメータ）
  │   - T5: パフォーマンス計測シナリオ（負荷条件・閾値）
  │   - T7: 動的操作シナリオ（操作→期待状態の組み合わせ）
  │   - T8: UI検証項目（要素名・期待値・同期条件）
  │   - T9: スクリーンショットタイミング（どの状態で撮るか）
  │
  └──→ [2b. DESIGN_SCENE_REQUIREMENTS]
         │ テスト設計から必要なシーン環境を決定:
         │   Read: references/test-environment-profiles.md
         │   - 各テストフェーズでどのプロファイルが必要か
         │   - キャラクター配置・有効/無効の切替計画
         │   - 地形・障害物の要件
         │   ★ プロファイルは参考。テスト内容から「何が必要か」を論理的に判断する
         │
         └──→ 出力: テストタイプ別の設計 + シーン環境計画
                → Step 3 へ
```

### Step 3: REVIEW

レビュー専門家が、機能の実装コードとテスト設計を見比べて十分性を判断する。

```
[3a. REVIEW_SUFFICIENCY]
  │ Read: references/test-review-checklist.md （レビュー専門家の知識をロード）
  │
  │ 各機能について:
  │   実装コードの「テストすべき側面」を列挙
  │     - 公開API・状態遷移・分岐条件・境界値・副作用・エラーパス
  │   テスト設計がそれらを網羅しているか照合
  │
  │ 判定:
  │   - 網羅: 続行
  │   - 不足: 具体的な不足箇所を指摘 → Step 2 に戻る（不足箇所のみ再設計）
  │
  │ ★ レビューループ上限: 2回。2回で収束しなければ現状の設計で進行し、
  │   レポートに「レビュー未収束」として記載
  │
  └──→ Step 4 へ
```

### Step 4: EXECUTE

設計に基づいてテストを実施する。

```
[4a. RUN_EDIT_TESTS (T1)]
  │ unicli exec TestRunner.RunEditMode
  │ 結果を機能ごとに記録
  │
  └──→ [4b. PLAYMODE_SESSION]
         │ ※ PlayMode セッションを1回にまとめる
         │ ※ 全操作UniCli経由。ドメインリロード後サーバー自動再起動（数秒のリトライあり）
         │
         │ [4b-1. CONFIGURE — EditMode]
         │   unicli exec Scene.Open --path "Assets/Scenes/CoreTestScene.unity"
         │   AutoInputTester設定（Menu.Execute）
         │
         │ [4b-2. PROFILER_START (T5対象がある場合)]
         │   unicli exec Menu.Execute --path "Profiler/StartRecording" 等
         │
         │ [4b-3. ENTER_PLAY]
         │   unicli exec PlayMode.Enter
         │   ※ ドメインリロード発生 → サーバー自動再起動（2-4秒）
         │   ※ 再起動後: unicli exec PlayMode.Status で isPlaying=true を確認
         │
         │ [4b-4. ENVIRONMENT-AWARE TEST EXECUTION] (PlayMode中)
         │   Step 2 で設計したシーン環境計画に従い、フェーズごとに:
         │     1. 環境プロファイル適用（UniCli経由でSetActive/SetTransform）
         │     2. テスト実行（T2/T3/T4/T7/T8/T9）
         │     3. 結果記録（unicli exec Console.GetLog / ファイルtail）
         │   ※ 各テスト種別の詳細手順は該当の t*.md を参照
         │
         │ [4b-5. PROFILER_STOP (T5対象がある場合)]
         │   UniCli経由でプロファイラ停止・分析
         │
         │ [4b-6. RUN_PLAYMODE_TESTS]
         │   ⚠️ PlayModeテストはユーザーにUnity Test Runnerから手動実行を依頼する
         │   （TestRunner.RunPlayMode はCLI側が長時間接続を維持できないため非推奨）
         │
         │ [4b-7. EXIT_PLAY]
         │   unicli exec PlayMode.Exit
         │
         └──→ Step 5 へ
```

### Step 5: EVALUATE

結果を分析し、次のアクションを決定する。

```
[5a. COLLECT_RESULTS]
  │ `/unicli`: Console.GetLog
  │ Read: auto-input-test-log.txt (存在する場合)
  │ Step 4 の各テスト結果を集約
  │
  └──→ [5b. ANALYZE]
         │ → GRAPH:ANALYZE_ERRORS の手順で分析
         │
         └──→ [5c. DECIDE_NEXT_ACTION]
                │
                ├─[全Pass]──→ [5d. REPORT] → feature-db更新 → END
                │
                ├─[バグ発見]──→ GRAPH:FIX_ISSUES
                │                └─[修正完了]→ Step 4 に戻る（再テスト）
                │                └─[修正失敗]→ [5d. REPORT]（問題記載）→ END
                │
                └─[テスト不足が判明]──→ Step 1 に戻る
                   （実行中に想定外の挙動を発見し、
                    現在のテスト設計ではカバーできないケース）
```

---

## GRAPH:ANALYZE_ERRORS

エラーログを分析して問題を分類する。
**実行モード**: EditMode（PlayMode Exit 後に呼ばれる）。ランタイム状態の検証は FULL_WORKFLOW の Step 4 で PlayMode 中に取得済みの結果を使う。

```
[1. COLLECT_LOGS]
  │ `/unicli`: Console.GetLog
  │ Read: auto-input-test-log.txt (存在する場合)
  │ Step 4 の IN-PLAY CHECKS 結果を参照（T3/T4/T7/T8のデータ）
  │
  └──→ [2. INSPECT_SCENE]
         │ EditModeで取得可能な静的情報を検証:
         │ `/unicli`: GameObject.Find → キャラクターの存在・レイヤー確認
         │ `/unicli`: GameObject.GetComponents → コンポーネント構成確認
         │ `/unicli`: Eval → 静的設定値の読み取り（EditModeで有効な範囲）
         │ `/unicli`: Prefab.GetStatus → プレハブ整合性確認（必要時）
         │ ※ ランタイム状態（HP値、Animator状態等）はStep 4の結果を使う
         │
         └──→ [3. CATEGORIZE]
                │ エラーを分類:
                │
                │ A. コンパイルエラー → スクリプト修正が必要
                │ B. ランタイムエラー → 参照切れ・コンポーネント未アタッチ
                │ C. 物理/レイヤー問題 → CollisionMatrix設定ミス、レイヤー不一致
                │ D. AI行動問題 → AIInfo設定ミス、BridgeAIAction未発火
                │ E. 入力問題 → PlayerInputHandler設定ミス、バッファタイミング
                │ F. ロジックエラー → SoAデータ不整合、状態遷移バグ
                │ G. パフォーマンス問題 → スパイク、GCアロケーション
                │
                └──→ [4. ROOT_CAUSE]
                       │ 各エラーの根本原因を特定
                       │ references/known-issues.md の既知パターンと照合
                       │ 関連ソースファイルを Read で確認
                       │
                       └──→ [5. REPORT]
                              │ 構造化レポート出力
                              └──→ END
```

---

## GRAPH:FIX_ISSUES

分析結果に基づいて修正を適用する。**リトライ上限: 3回**。超過時はユーザーに報告して終了。

```
[1. READ_ANALYSIS]
  │ 直前のANALYZE_ERRORS結果を参照
  │ OR コンソールログから問題を再特定
  │ retryCount = 0
  │
  └──→ [2. PLAN_FIX]
         │ 修正計画を立案:
         │   - 影響範囲の確認
         │   - 既存テストへの影響
         │   - 最小限の変更で修正可能か
         │
         └──→ [3. APPLY_FIX]
                │ コード修正を適用
                │ retryCount++
                │
                ├─[retryCount > 3]──→ [ESCALATE]
                │                      │ 修正試行3回超過。変更をrevert提案し、
                │                      │ 問題の詳細をユーザーに報告して判断を仰ぐ
                │                      └──→ END
                │
                └──→ [4. VERIFY]
                       │ `/unicli`: Compile
                       │
                       ├─[compile error]──→ [3. APPLY_FIX] (修正を調整)
                       │
                       └─[success]──→ [5. TEST]
                                       │ `/unicli`: TestRunner.RunEditMode
                                       │ `/unicli`: GameObject.Find + GetComponents で修正対象を直接検証
                                       │ `/unicli`: Eval で状態値を確認（必要時）
                                       │
                                       ├─[test failure]──→ [3. APPLY_FIX] (修正を調整)
                                       │
                                       └─[all pass]──→ [6. RECORD_ISSUE]
                                                        │ references/known-issues.md に追記:
                                                        │   - 症状、根本原因、修正内容、確認方法
                                                        │   - 該当する調査パターンがなければ追加
                                                        │
                                                        └──→ [7. DONE]
                                                               │ 修正内容をサマリー出力
                                                               └──→ RETURN (呼び出し元に戻る)
```

---

## テスト種別と機能マッピング

9種のテストタイプ（T1-T9）と、機能カテゴリごとの適用マトリクスで構成される。

### テスト種別一覧（詳細は各 references/test-types/t*.md を参照）

| ID | テスト種別 | 実行モード | 役割 |
|----|-----------|-----------|------|
| T1 | EditModeロジック | EditMode | ロジック単体検証の専門家 |
| T2 | AutoInput動作 | PlayMode | 入力→動作フローの専門家 |
| T3 | シーン状態スナップショット | PlayMode | ランタイム状態検証の専門家 |
| T4 | Animator状態 | PlayMode | アニメーション遷移の専門家 |
| T5 | パフォーマンス回帰 | PlayMode | パフォーマンス計測の専門家 |
| T6 | プリフライト（門番） | EditMode | 実行前整合性チェックの専門家 |
| T7 | 動的シーン操作 | PlayMode | エッジケース検証の専門家 |
| T8 | UI検証 | PlayMode | UI同期・表示検証の専門家 |
| T9 | スクリーンショット | PlayMode | ビジュアルエビデンスの専門家 |

### テスト種別の使い方

各 `t*.md` は**テスト設計の専門家**として機能する:
1. Step 2 (DESIGN) で Read してロードする
2. 機能の実装詳細を入力として渡す
3. 専門家の知識に基づいてテストケースを設計する

### レビュー専門家

`references/test-review-checklist.md` に定義。
テスト設計の十分性を、機能の実装コードと照合して判断する。

### 機能-テスト組み合わせマトリクス

詳細: `references/feature-test-matrix.md`

機能カテゴリ（移動系/攻撃系/UI系 等）ごとに◎必須/○推奨/△任意のテストタイプを定義。
Step 1 (PLAN) でこのマトリクスを参照してテスト計画を立てる。

### 適用ルール
1. **◎が1つでもFail → feature-db: in_progress**
2. **○のみFail → complete可能、レポートに警告**
3. **△ → 時間が許す場合のみ**
4. **T6 Fail → 他テスト中断**（Step 0 で実施済み）

### バッチテスト（複数機能一括）

複数機能を同時テストする場合は `batch-test.md` のワークフローを使用。
テスト種別ごとにグルーピングし、PlayMode Enter/Exit を最小化する。

## レポートテンプレート（統一フォーマット）

FULL_WORKFLOW / batch-test / playtest-orchestrator agent が共通で使うフォーマット。

```
=== Play Test Report ===
Date: YYYY-MM-DD
Scene: [scene name]
Mode: [Full / Batch / Single Feature]
Features: [テスト対象機能リスト]

### Test Result Matrix
| 機能名 | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | PM | 判定 |
|--------|----|----|----|----|----|----|----|----|----|----|------|
| ...    | ✅ | ✅ | — | — | — | ✅ | — | — | — | ✅ | Pass |
凡例: ✅Pass / ❌Fail / ⚠Warning / —Skip / PM=PlayModeテスト

### Summary
- Total features: N
- Pass: N / Fail: N / Warning: N

### Issues Found
1. [機能名][Tx] 問題詳細
   - File: path/to/file.cs:line
   - Root cause: 説明
   - Fix: applied / proposed / needs-investigation

### Performance (T5, 該当時)
- Avg frame time: N ms
- Spikes: N frames > 33ms (rate%)
- Top allocators: [sample names]

### Evidence (T9)
- [screenshot paths]

### Coverage Gaps
- [機能名]: Tx テストが未作成

### Known Issues Updated
- [新規追加した known-issues.md エントリ]
```

---

## feature-db 更新ルール

GRAPH:FULL_WORKFLOW の Step 5 で、テスト結果に基づいて feature-db を更新する。

### 更新判定

1. **feature-db から対象機能を取得**: `python tools/feature-db.py list` で全機能一覧を取得
2. **テスト結果と照合**: 各テストタイプの結果を機能ごとに分類
3. **ステータス更新**:
   - 対象機能の◎テスト全Pass → `python tools/feature-db.py update "機能名" --status complete --test-passed N --test-failed 0`
   - ◎テストに失敗あり → `python tools/feature-db.py update "機能名" --status in_progress --test-passed N --test-failed M`
   - テスト対象外（テストが存在しない）→ 更新しない（レポートにギャップとして記載）

### 注意事項
- AutoInputTestの結果はPlayMode統合テストであり、個別機能のステータスに直接マッピングしにくい場合がある
- その場合はテストレポートに「手動確認推奨」として記載し、feature-dbは変更しない

## UniCli利用規約

エディタ操作はすべて `/unicli` スキル経由で実行する。コマンドの詳細・パラメータは `/unicli` を参照。

- **接続確認**: ワークフロー開始時に `unicli check` → 失敗時はユーザーに `/unicli` でのセットアップを案内
- **フォールバック**: unicli不可時は unity-mcp MCP ツール群を使用
- **Menu.Execute**: ダイアログなしメニュー項目は `Tools/CLIInternal/` 配下
- **Compile**: コード変更後は必ず実行
- **分析時は受動的ログ解析だけでなく、`Eval`/`GameObject.*`/`Profiler.*` で能動的に検証する**

## 参考資料

- `references/known-issues.md` — 過去のセッションで発見した問題と解決策
- `references/test-scene-architecture.md` — TestSceneBuilder のエリア構成と配線
- `references/auto-input-patterns.md` — AutoInputTester のテストパターン設計
- `references/test-environment-profiles.md` — テスト環境プロファイル定義
- `references/test-review-checklist.md` — レビュー専門家のチェックリスト
- `references/feature-test-matrix.md` — 機能-テスト組み合わせマトリクス
