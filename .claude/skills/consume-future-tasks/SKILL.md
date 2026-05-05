---
name: consume-future-tasks
description: docs/FUTURE_TASKS.md の未完タスクを仕分けし、batch消化可能なものを worktree で並列実装 → メインでテスト → 1バッチ1PR を発行する
user-invocable: true
argument-hint: [並列数]
---

# Consume Future Tasks: $ARGUMENTS

`docs/FUTURE_TASKS.md` の未完タスクを仕分け、batch 消化可能なものを並列で実装・PR化する。

## ステップ0: 引数解析 + 事前チェック

### 引数
- `$ARGUMENTS` に並列数 N が指定されていればそれを採用（1-5）
- 省略時はステップ4で自動決定

### 事前チェック
- 現在のブランチが `main` かつ clean であることを確認
  - NG なら: ユーザーに「main に戻って clean 状態にしますか?」と確認
- `docs/FUTURE_TASKS.md` の存在を確認
- `git fetch origin` + `git pull origin main` で最新化

## ステップ1: タスク抽出

`docs/FUTURE_TASKS.md` を読み、未完タスク (`- [ ]` で始まる行) を列挙する。

各タスクについて以下を収集:
- **タスク名** (行頭の太字部分)
- **対象ファイル** (リスト内の `対象ファイル:` または `対象:` 行から抽出)
- **説明・仕様** (ネストされた詳細)
- **優先度タグ** (🔴/🟡/🟢) — 必須。欠落は暫定 🟡 とみなす
- **仕様確定度タグ** (✓/⚠/🔶) — 2026-04-24 規約で追加。欠落は暫定 ✓ とみなす（既存エントリ互換）
- **関連PR** (本文中の `PR #NN` または `関連PR:` 行から抽出)

## ステップ2: 仕分け (修正量 × 影響度)

各タスクに 2軸でタグ付けする。推定は対象ファイルの行数・構造を見て判断。

### 修正量
| タグ | 目安 |
|------|------|
| S | ≤50行 / ファイル1-2個 |
| M | ≤200行 / ファイル3-5個 |
| L | 200行超 or ファイル6+個 |

### 影響度 (強い方を採用)
| タグ | 条件 |
|------|------|
| 低 | 単一クラス内の変更、private追加、定数外出し、テスト追加のみ |
| 中 | public シグネチャ変更あり・呼出元 2-3 箇所、同一 asmdef 内 |
| 高 | enum/struct 定義変更、SoA/GameManager/Events/CharacterInfo 等の共通ハブ、asmdef 跨ぎ、破壊的変更 |

### 振り分けマトリクス

| | 低 | 中 | 高 |
|---|---|---|---|
| S | **batch** | **batch** | 単独PR (スキップ) |
| M | **batch** | 単独PR (スキップ) | create-feature (スキップ) |
| L | 単独PR (スキップ) | create-feature (スキップ) | create-feature (スキップ) |

**スキップ対象**: このスキルでは処理しない。サマリに「要別対応」として列挙のみ。

### 仕様確定度によるスキップ（タグ駆動）

- **🔶 仕様検討中** — サイズ・影響度に関わらず**全スキップ**（仕様を決める対話が先）
- **⚠ 要相談** — batch 入りはさせず、サマリに「判断事項を含む」と明記して個別対応を促す
- **✓ 仕様確定** — 通常のマトリクス判定に従う

旧記述「仕様が未確定・『要検討』扱いのタスクはサイズに関わらず全てスキップ」は上記ルールに置換される。

## ステップ3: ファイル単位で融合

batch 対象タスク同士を以下ルールでグループ化:

1. **同一ファイルを触るタスクは同じ batch に寄せる** (衝突回避の最優先ルール)
2. 同一セクション (FUTURE_TASKS.md の見出し) のタスクは同じ batch に寄せやすい
3. 1 batch あたり **5-15タスク / 総行数 ≤500行** を上限目安

グループ化後、各 batch に名前を付ける (例: `batch-combat-config`、`batch-ui-cleanup`)。

## ステップ4: 並列数決定

- ユーザー指定があればそれを使用
- 未指定時:
  - batch 数 ≤ 3 → batch 数と同じ
  - batch 数 4-5 → 3
  - batch 数 6+ → 3 (残りは次回実行送り、スキルを複数回起動する想定)
- 上限 5

## ステップ5: ユーザー承認

以下をテキスト表示し、実行前に承認を取る:

```
## Batch 消化プラン

### 対象 batch (並列 N=3)
- batch-combat-config (タスク3件, 対象ファイル: DamageReceiver.cs 他)
  - [ ] Guard 系フラグ仕様整理 (S × 中)
  - [ ] Flinch 解除後 armor 復元仕様 (S × 低)
  ...
- batch-ui-cleanup (...)
- batch-save-robustness (...)

### スキップ (別対応必要)
- Addressable 導入 (L × 高) → create-feature 推奨
- 装備→SoA書き戻しパイプライン (L × 高) → create-feature 推奨
...

### リトライ候補
なし

実行しますか? (y/n)
```

ユーザーが `y` 以外を返したら中止。

## ステップ6: 並列実装 (worktree)

各 batch に対して git worktree を作成し、Agent を並列起動する。

### worktree 作成
```bash
BRANCH_NAME="feature/future-tasks-batch-$(date +%Y%m%d)-${BATCH_NAME}"
git worktree add .claude/worktrees/consume-${BATCH_NAME} -b ${BRANCH_NAME} main
```

### Agent 起動 (並列)
各 worktree に対して、Agent ツール (subagent_type: `general-purpose`) を `isolation: "worktree"` なしで直接起動。**並列数 N 個を同一メッセージで発行**する。

各 Agent への指示 (prompt) に含めるもの:
- このスキルの目的 (FUTURE_TASKS.md の消化)
- そのbatchに含まれるタスクの一覧と詳細（FUTURE_TASKS.md から抽出した内容）
- 実行すべき手順:
  1. 各タスクについて TDD: テスト追加 → 実装 → 整合性確認 (コンパイル通過まで)
  2. コンパイル確認: `python tools/unicli.py compile` 相当または Grep/Read で変更ファイルと呼び出し元の整合検証
  3. FUTURE_TASKS.md の該当タスクに `- [x]` チェック + `✅` 完了メモ追記
  4. 小さな論理単位でコミット (`feat(scope): 日本語タイトル` + `Co-Authored-By`)
  5. **worktree 上でブランチにコミットまで**。Unity テスト実行・PR 作成はしない
- **Unity CLI テスト実行の扱い**: Agent 側では実行しない。理由は Library フォルダが worktree ごとに独立しており、worktree で初回起動すると数十分のフル再インポートが走るため。テスト実行はステップ 7 で親 Claude がメイン worktree の Library を使い回して行う
- 準拠すべき規約: `.claude/rules/unity-conventions.md`、`.claude/rules/test-driven.md`、`CLAUDE.md`
- worktree パスと対象ブランチ名
- 完了時に報告: 成功タスク一覧、失敗タスク一覧 + 失敗要因

### Agent 完了待ち
全 Agent が完了するまで待つ (Agent ツールは foreground で起動)。

## ステップ7: 順次テスト + PR 作成

メインworktree (プロジェクトルート) で batch ごとに順次処理する。

### Library フォルダの前提
Unity の `Library/` はキャッシュ本体でプロジェクトディレクトリごとに独立する。worktree は**独自の `Library/` を持つ** (空の状態) ため、worktree で Unity CLI を起動するとフル再インポートが走る (10-30 分 × worktree 数 × ディスク数 GB)。

**対策**: メイン worktree の既存 `Library/` を使い回すため、以下の順でテストする:
1. 成功した実装 worktree を**削除** (`git worktree remove`) してブランチ占有を解除
2. メイン worktree で `git checkout ${BRANCH_NAME}` してブランチ切替 (Library は共有)
3. Unity CLI でテスト実行
4. 完了後に `git checkout main` で戻す

失敗 batch の worktree はこの時点では削除しない (次回再実行材料のため)。

### 各 batch の処理フロー

```bash
# 1. 実装 worktree を削除してブランチ占有を解除 (成功 batch のみ)
git worktree remove .claude/worktrees/consume-${BATCH_NAME}

# 2. main をクリーン状態に戻す (既に main なら skip)
git checkout main

# 3. batch ブランチをチェックアウト (メイン worktree の Library を使い回す)
git checkout ${BRANCH_NAME}

# 4. Unity CLI で EditMode テスト実行 (-quit なし)
"C:\Program Files\Unity\Hub\Editor\6000.3.9f1\Editor\Unity.exe" \
  -batchmode -nographics \
  -projectPath "C:\Users\tatuk\Desktop\GameDev\SisterGame" \
  -runTests -testPlatform EditMode \
  -testResults "TestResults/batch-${BATCH_NAME}.xml" \
  -logFile "TestResults/batch-${BATCH_NAME}.log"

# 5. テスト完了後、次の batch へ行く前に main に戻す
git checkout main
```

### テスト結果判定

**OK (全 Pass)**:
1. PlayMode テストの追加/変更がある場合、MCP `run_tests` で PlayMode も実行
2. PR 作成（PR 番号を変数 `PR_NUMBER` で保持）
   ```bash
   gh pr create --title "[種類](future-tasks): ${batch名} 消化 (Nタスク)" \
     --body "## 消化タスク\n- ...\n\n## Test plan\n- [ ] EditMode テスト\n- [ ] 人間レビュー"
   ```
3. **実装 worktree は削除してよい** (ステップ 9 で処理)。レビューはステップ 8 の**専用 worktree** で行う

**テスト環境が無い/Unity CLI 実行不能の場合**:
1. テスト実行は skip、PR 本文の Test plan に「人間レビュー時に Unity 側で実行」を明記
2. それ以外は OK と同じフローで PR 作成

**NG (Fail あり)**:
1. ブランチはそのまま残す (ユーザーが後で調査可能)
2. `docs/FUTURE_TASKS.md` の該当タスクは未消化のまま
3. **特筆すべき失敗要因があれば** FUTURE_TASKS.md に追記
   - 例: `<!-- 2026-04-23 consume-future-tasks: XXX が XXX に依存するため先行対応必要 -->`
4. worktree は残置 (次回再実行の材料にする)、ブランチも削除しない
5. 失敗 batch はステップ 8 のレビュー対象から除外

### ステップ7 実行中の原則
- batch 間は独立している前提なので、並列でテストはせず **逐次実行** (Library/ ロック回避)
- 先行 batch が成功しても main にマージせず、各 PR は main を base にする
  - マージはユーザー手動
- テスト失敗が連続する場合はユーザーに報告して停止判断

## ステップ8: PR 自己レビュー + 指摘対応（並列）

作成済み PR ごとに**専用のレビュー worktree** を作り、並列 Agent で自己レビュー → 指摘対応 → push まで完結させる。

**このフェーズの目的**: PR が main にマージされる前に、配線漏れ・テスト assertion の実挙動乖離・コメント整合性不良などを検出して潰しきる。実績として #39 (新フィールド伝搬漏れ)、#40 (テスト方向 assert バグ) のような Critical 指摘がここで検出できている。

### レビュー worktree 作成（並列）
ステップ 7 で作成された PR 分だけ、**新規 worktree** を切る。実装 worktree とは別に専用に切り、ブランチの head commit に対して作業する。

```bash
# PR ごとにレビュー worktree を作成 (並列で)
for PR in $PR_LIST; do
  BRANCH=$(gh pr view $PR --json headRefName --jq '.headRefName')
  git worktree add .claude/worktrees/pr-review-$PR $BRANCH
done
```

### Agent 起動 (並列 N=最大5)

各 PR に対して Agent を 1 つ起動する。**全 Agent を 1 メッセージで並列発行**。

各 Agent への指示 (prompt) に含めるもの:

- PR 情報: PR 番号、タイトル、ブランチ名、概要（ステップ 7 で作成した PR 本文のサマリ）
- 作業ディレクトリ: `.claude/worktrees/pr-review-$PR` の絶対パス
- 変更内容: コミット単位の変更サマリ（Agent が diff を読む際の導入情報）
- **レビュー手順（テンプレート）**:
  1. `git diff main..HEAD` で差分を読む
  2. 周辺コードを `Read`/`Grep` で確認（呼び出し元、類似パターン、既存テストの前提）
  3. 下記**レビュー観点** に沿って分析
  4. 指摘があれば:
     - 該当ファイルを `Edit` で修正
     - 必要なら回帰テストを追加
     - `fix(review): PR #${PR} レビュー R1/R2 対応 — ${要約}` 形式で 1 コミット
     - `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>` を付与
  5. `git push origin ${BRANCH}` で修正を反映
  6. `gh pr review ${PR} --comment --body "${観点別コメント}"` で投稿
     - **自己 PR は `--approve` 不可** (GitHub API エラー `Can not approve your own pull request`)。必ず `--comment` を使う
     - Critical 未対応があれば `--request-changes`、対応済み or 軽微指摘のみなら `--comment`
- **Unity CLI テスト実行の扱い**: Agent 側では実行しない。レビュー worktree も独自の空 `Library/` を持ち、ここで CLI を起動するとフル再インポートが走るため。テスト実行は Agent 完了後に親 Claude がメイン worktree の Library を使い回して行う (ステップ 7 と同じ戦略)
- **レビュー観点** (`.claude/rules/git-workflow.md` のプルリクエストルール準拠):
  - **Code Reuse**: 重複パターン、既存ユーティリティ・既存命名スタイル未使用、類似フィールド命名の統一
  - **Code Quality**:
    - バグ・例外時のリソース漏れ
    - 命名規約 (`k_PascalCase` 定数、`_camelCase` private field 等)
    - イベント購読/解除の対称性
    - 新フィールド追加時の**配線漏れ** (Clone/Build/Serialize/Migrate 等の周辺経路)
    - テスト assertion が実装本体の実挙動と整合しているか (**テストバグ検出**)
  - **Efficiency**: ホットパスのアロケーション、キャッシュ漏れ、不要な sqrt / GetComponent
  - **TDD 観点**:
    - 境界値・不変条件検証の網羅
    - 既存テストが新変更で回帰しないか
    - 結合テストが「既存ユーティリティ経由で副作用が効いていること」まで検証しているか
- 準拠規約: `.claude/rules/git-workflow.md`、`.claude/rules/unity-conventions.md`、`.claude/rules/test-driven.md`
- 完了時の報告フォーマット:
  ```
  ## PR #${PR} レビュー + 対応 完了報告
  ### レビュー結果
  - Code Reuse: OK/指摘
  - Code Quality: OK/指摘 (Critical: R1/R2 ...)
  - Efficiency: OK
  - TDD: OK/追加テスト
  ### 修正コミット
  - {hash}: {タイトル}
  ### gh pr review 結果
  - {comment|request-changes}, {state}, 投稿日時
  ```

### Agent 完了待ち
全 Agent の完了通知を待つ。各 Agent は独立して worktree 内で完結するため並列衝突なし。

### 失敗対応
- Agent が `gh pr review` エラーに遭遇した場合（例: 自己 PR で `--approve` を試みた）、`--comment` にフォールバック
- push が reject された場合は `git fetch origin && git rebase origin/${BRANCH}` を試み、conflict 発生時はユーザーに報告

### ステップ8 実行中の原則
- レビュー worktree と実装 worktree は**別ディレクトリ**。実装 worktree は既に削除されている想定
- 各 PR は独立にレビューされる（Agent 間のファイル衝突なし）
- Critical 指摘があれば必ず修正コミットを push してから review 投稿（「Critical 指摘ありだけど対応済み」が最も安全）
- レビューで発見した新たな将来タスクは各 Agent が FUTURE_TASKS.md に追記してよい

## ステップ9: worktree 後処理

- **成功 batch の実装 worktree**: `git worktree remove .claude/worktrees/consume-${BATCH_NAME}` で削除 (ブランチは残る)
- **成功 PR のレビュー worktree**: `git worktree remove .claude/worktrees/pr-review-${PR}` で削除
- **失敗 batch の worktree**: 残置（次回再実行材料）
- `git worktree prune` で孤立エントリをクリーンアップ

## ステップ10: サマリ表示

最終報告:

```
## Consume Future Tasks 完了

### PR 作成 + レビュー済み (N件)
- [batch-combat-config](PR URL) — 3 タスク消化
  - レビュー: R1 コメント整合性、R2 重複登録検知テスト追加
  - 修正コミット: 1 件
- [batch-ui-cleanup](PR URL) — 5 タスク消化
  - レビュー: 指摘なし (COMMENTED で approve 相当)
  - 修正コミット: 0 件

### レビューで検出した Critical 指摘 (N件)
- PR #XX — 新フィールド配線漏れ (Clone/Build で dead data) → 修正済
- PR #YY — テスト assertion が実挙動と乖離 (CI fail 案件) → 修正済

### テスト失敗 (N件)
- batch-save-robustness — EditMode テスト 2 件失敗
  - 原因メモ: SaveDataStore.ResolveType の型解決順序変更で既存テストが影響

### スキップ (別対応)
- Addressable 導入 (L × 高)
- 装備→SoA書き戻しパイプライン (L × 高)

### 次回へ
- 失敗 batch のブランチと worktree は残置。再実行時に拾うか、create-feature で個別対応してください
```

## ルール・注意点

### 実装フェーズ (ステップ 6-7)
- **Unity CLI テスト時 `-quit` は絶対に付けない** (メモリ: Unity CLIバッチテスト注意点)
- **Library フォルダは worktree ごとに独立**。worktree で Unity CLI を起動するとフル再インポートで 10-30 分 × ディスク数 GB 消費するため、テスト実行はメイン worktree でブランチ切替 (成功 batch の worktree を先に削除してブランチ占有を解除してから) して Library を共有する
- **失敗 batch のブランチ・worktree は削除しない** — 次回再実行の材料
- **FUTURE_TASKS.md の編集は各 Agent に委ねる** — 本スキルは orchestration 専任
- **PR の base は常に main** — batch 間は独立前提
- **マージは常にユーザー手動** — スキルは作成まで
- コミットメッセージ規約: `[種類](範囲): 日本語タイトル` + `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>` (CLAUDE.md 準拠)
- 大きめ・高影響度タスクは **create-feature** を案内してスキップ

### レビューフェーズ (ステップ 8)
- **自己 PR は `--approve` 不可** — GitHub API が `Can not approve your own pull request` を返す。必ず `gh pr review <PR> --comment` を使用する
- **レビュー worktree は実装 worktree とは別に切る** (`.claude/worktrees/pr-review-<PR>`)。実装 worktree を流用しない理由: head commit の検証を最新状態で行うため、かつ実装 worktree は既に削除されている可能性あり
- **レビュー Agent は Unity CLI テスト実行しない** — レビュー worktree も独自の空 `Library/` を持つためフル再インポートコストが発生する。テスト実行は Agent 完了後に親 Claude がメイン worktree でブランチ切替して行う (修正コミット push 済みの状態で)
- **Critical 指摘は必ず修正コミットを push してから review 投稿**（対応漏れで PR がマージされる事故を避ける）
- **修正コミットのタイトル形式**: `fix(review): PR #${PR} レビュー R1/R2 対応 — ${要約}` で識別しやすくする
- **rate limit 対策**: 各 Agent は diff + 周辺コードだけ読ませる。全ファイル走査は避ける
- **レビュー観点は規約ドキュメントから引用** — `.claude/rules/git-workflow.md` に定義された Code Reuse / Code Quality / Efficiency の 3 観点 + TDD 観点
- **Critical 指摘の検出実績**: 新フィールド追加時の Clone/Build 配線漏れ、テスト assertion の実挙動乖離、コメント整合性不良 — これらはこのフェーズで潰すべき定番パターン

## 依存スキル・ツール

- `create-feature` — スキップ対象のタスクを個別消化する際に案内
- `git worktree` — 並列 Agent の隔離環境（実装用・レビュー用で別ディレクトリ）
- Unity CLI — EditMode テスト実行
- MCP `run_tests` — PlayMode テスト実行
- `gh pr create` / `gh pr view` / `gh pr review` — PR 作成・情報取得・レビュー投稿
