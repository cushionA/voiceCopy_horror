---
name: resume-handoff
description: Resume work from the latest handoff note in docs/reports/handoffs/. Reads the most recent in-progress note, restores context, and presents the "next steps" section to the user.
user-invocable: true
argument-hint: [optional date or slug to resume specific handoff]
---

# Resume Handoff: $ARGUMENTS

前回セッション末尾で生成された handoff note を読み込み、作業を再開する。
**Phase 17 で導入された registry-based handoff の対 skill**（`/handoff-note` のペア）。

## いつ呼ぶか

- セッション開始時、前回の作業を続ける時
- `/registry-check` で「直近 3 件」を見て特定 handoff に飛びたい時
- 引数なしなら**最新の in-progress / paused 状態**の handoff を自動選択

## 動作

### ステップ 1: 対象 handoff の特定

引数なしの場合:
```bash
ls -t docs/reports/handoffs/*.md 2>/dev/null | head -5
```
で最新 5 件を取得し、frontmatter の `status` を確認:
- `in-progress` または `paused` を最新側から探す
- 全部 `resolved` なら、最新を提示して「再開しますか？」と確認

引数ありの場合:
- `$ARGUMENTS` が日付（`2026-04-25` 形式）なら `docs/reports/handoffs/2026-04-25_*.md` をマッチ
- slug 文字列なら `docs/reports/handoffs/*_<slug>.md` をマッチ
- 複数ヒットしたらユーザーに選ばせる

### ステップ 2: handoff note 読み込み + 検証

選択した note を Read で読み込み、以下を**実環境と照合**:

```bash
# branch 確認
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
HANDOFF_BRANCH=<note の frontmatter から>

# 一致確認
if [ "$CURRENT_BRANCH" != "$HANDOFF_BRANCH" ]; then
  echo "WARN: 現在 $CURRENT_BRANCH ですが handoff は $HANDOFF_BRANCH 用です"
fi

# last_commit 確認
git log --oneline -1 | grep <handoff の last_commit>
```

不一致があれば**ユーザーに警告し、ブランチ切り替えを提案**する（自動切替しない）。

### ステップ 2.5: stale 検証

note の `date` が**3 日以上古い**場合:
- ユーザーに「この handoff は <N 日前> のものです。状況が変わっている可能性あり」と通知
- 該当ブランチの最新 commit と handoff の last_commit を diff し、追加変更があれば提示

### ステップ 3: 状態復元の提示

note の内容をユーザーに提示する形式:

```markdown
## 前回の handoff からの再開

**topic**: <session_topic>
**branch**: <branch>
**status**: <status>
**最終 commit**: <last_commit> (<commit message>)

### 完了済み
- ...

### 進行中
- ...

### 次にやること（handoff より）
1. ...
2. ...

### 注意点
- ...

これで再開しますか？ それとも先に何か確認しますか？
```

### ステップ 4: TodoWrite 復元（推奨）

「次にやること」セクションを TodoWrite の todos に変換して、現在のセッションの todo list として登録する（ユーザー確認後）。

### ステップ 5: 関連ファイルの先読み

note の「関連ファイル」セクションのうち、編集予定の主要ファイル 1-3 個を Read で読み込んで context に乗せる（行数限定）。

## ルール

- **destructive 操作を絶対にしない**（git reset、branch -D 等）
- **handoff note は読み取り専用**として扱う（実行環境と乖離があれば警告のみ）
- **stale 検証を必ず行う**（3 日以上古い note は明示的に通知）
- 引数なしで該当 note が見つからない場合は `/registry-check` の利用を促す

## 関連 skill

- `/handoff-note` — セッション末尾で handoff note を生成
- `/registry-check` — registry 一覧から特定 handoff を選ぶ
