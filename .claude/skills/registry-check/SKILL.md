---
name: registry-check
description: Display docs/reports/_registry.md index and the 3 most recent handoff notes. Used at session start to surface persisted context.
user-invocable: true
argument-hint: [optional category to filter, e.g. "handoffs", "bugs"]
---

# Registry Check: $ARGUMENTS

`docs/reports/_registry.md` の索引一覧と直近 3 件の handoff note を表示する。
**Phase 17 で導入された registry-based handoff の入口 skill**。SessionStart hook から自動起動される。

## いつ呼ぶか

- セッション開始時（自動 — SessionStart hook）
- 過去の作業内容を確認したい時（手動）
- 特定カテゴリのレポート一覧を見たい時（`/registry-check bugs` 等）

## 動作

### ステップ 1: registry 存在確認

```bash
test -f docs/reports/_registry.md || {
  echo "registry 未初期化です。Phase 17 が未マージかもしれません。"
  exit 0
}
```

### ステップ 2: registry 概要表示

引数なしの場合、registry ファイル先頭から「## 索引（最新順）」までを Read で表示:

- 「目的」「運用ルール」「アクセス手段」セクション
- カテゴリ一覧表

### ステップ 3: 直近 3 件の handoff を抽出して表示

```bash
ls -t docs/reports/handoffs/*.md 2>/dev/null | grep -v README.md | head -3
```

各ファイルの frontmatter（date / session_topic / status / branch）と「現在地」セクションの最初の 3 行を表示する形式:

```markdown
## 直近 3 件の handoff

### 2026-04-25 — Wave 2 Phase 17 implementation [in-progress]
**branch**: feature/wave2-phase17-handoff
**現在地**: docs/reports/ 構造作成完了、3 skill 新設中...

### 2026-04-23 — ProjectileController hit count expansion [resolved]
**branch**: feature/future-tasks-batch-20260424-projectile-hit-counts
**現在地**: PR #43 マージ済み、二段管理実装完了

### 2026-04-22 — ...
```

### ステップ 4: カテゴリ別表示（引数指定時）

`$ARGUMENTS` が指定されたら、`docs/reports/<category>/` の中身を ls で取得して表示:

```bash
CATEGORY=$ARGUMENTS  # 例: bugs, handoffs, arch
test -d docs/reports/$CATEGORY || {
  echo "カテゴリ $CATEGORY は存在しません。"
  echo "利用可能: analysis arch bugs experiments handoffs migrations postmortems research reviews specs surveys"
  exit 0
}
ls -t docs/reports/$CATEGORY/*.md 2>/dev/null | grep -v README.md | head -10
```

### ステップ 5: アクション提案

最後にユーザーへ次のアクションを提示:

```markdown
## 次のアクション

- 前回の作業を再開する場合: `/resume-handoff`
- 特定の handoff を指定して再開: `/resume-handoff <slug>`
- カテゴリ詳細を見る: `/registry-check <category>`
- 新しい handoff note を作成する場合: `/handoff-note <topic>`
```

## ルール

- **読み取り専用**。registry や handoff ファイルを編集しない
- 表示は**簡潔に**（フルテキストではなく要約）。詳細は handoff ファイルを開かせる
- SessionStart hook から呼ばれた場合は、表示後に**ユーザーの次の入力を待つ**（自動で `/resume-handoff` などに進まない）

## 関連 skill

- `/handoff-note` — handoff note の生成
- `/resume-handoff` — handoff からの作業再開
