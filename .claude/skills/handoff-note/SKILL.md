---
name: handoff-note
description: Generate a session handoff note for next session resumption. Captures git diff, completed/pending tasks, blockers, and key file references into docs/reports/handoffs/.
user-invocable: true
argument-hint: [optional topic slug]
---

# Handoff Note: $ARGUMENTS

セッション境界を超える知識転送のため、現在の作業状態を `docs/reports/handoffs/<date>_<slug>.md` にスナップショット保存する。
**Phase 17 で導入された registry-based handoff の中核 skill**。

## いつ呼ぶか

- セッション終了直前（`/compact` の前推奨。圧縮で消える文脈を外在化）
- 作業を中断する時（他タスクへ移る前）
- Stop hook から自動呼出（`.claude/settings.json` で設定済み）
- ユーザーが「ここまでメモしておいて」と明示した時

## 動作

### ステップ 1: 状態収集

以下を **読み取り専用で** 集める:

```bash
# git 状態
git rev-parse --abbrev-ref HEAD          # 現在ブランチ
git rev-parse HEAD                        # 現在 commit
git diff main --stat                      # main からの差分サマリ
git log --oneline main..HEAD              # 本ブランチの commit 一覧
git status --short                        # 未コミットの変更
```

```bash
# pipeline-state.json があれば
cat designs/pipeline-state.json 2>/dev/null
```

```bash
# 直近の test ログ・PR 番号
gh pr list --head $(git rev-parse --abbrev-ref HEAD) --json number,state,title
```

### ステップ 2: ファイル名決定

- 日付: 現在日付（`date +%Y-%m-%d`）
- slug: 引数 `$ARGUMENTS` を kebab-case 化、なければ「現在ブランチ名から `feature/` 等のプレフィックスを除いた部分」を使う
- 例: `docs/reports/handoffs/2026-04-25_wave2-phase17-handoff.md`

### ステップ 3: handoff note 生成

以下のテンプレートで `docs/reports/handoffs/<date>_<slug>.md` を作成:

```markdown
---
date: <YYYY-MM-DD>
session_topic: <短いタイトル>
status: in-progress | paused | needs-review | resolved
branch: <branch-name>
related_pr: <番号 or null>
last_commit: <short-hash>
---

## 現在地

- **完了タスク**:
  - <commit ハッシュ + 1 行サマリ>
- **進行中**:
  - <未完の作業内容>
- **未着手 (本ブランチ内)**:
  - <pendingFeatures から or TodoWrite から>

## 次セッションでやること

1. <具体的手順 1>
2. <具体的手順 2>
3. ...

## 注意点・ブロッカー

- <ハマり所、外部依存、判断保留事項>

## 関連ファイル

- `path/to/file.cs:123` — <短い説明>
- `path/to/another.md` — <短い説明>

## 関連リソース

- 関連 PR: #<番号>
- 関連 docs/FUTURE_TASKS.md エントリ: <該当タスク>
- 関連 WAVE_PLAN.md セクション: <Phase ID>
```

### ステップ 4: registry 更新

`docs/reports/_registry.md` の **「## 索引（最新順）」 / `### handoffs/` セクション最上部**に以下を追加:

```markdown
- [<YYYY-MM-DD> <session_topic>](handoffs/<YYYY-MM-DD>_<slug>.md) — <status> / branch: <branch-name>
```

`*エントリなし*` の行があれば削除。

### ステップ 5: コミット（オプション）

ユーザーから「コミットも」と明示されれば:

```bash
git add docs/reports/handoffs/<file> docs/reports/_registry.md
git commit -m "docs(handoff): <session_topic>"
```

明示されない場合はファイル生成だけで終了（次セッションが拾えるように working tree に残す or コミット推奨を伝える）。

## ルール

- **個人情報・secret を絶対に書かない**（API key、メアド、credential）
- **「次セッションでやること」は具体的に**: 抽象的な「続きをやる」ではなく、ファイル名・行番号・コマンド単位で書く
- **状態は事実のみ**: 推測や希望的観測は「注意点」セクションに分離
- 自動トリガー時（Stop hook）は冗長な内容を避ける（diff 全文を貼らない、要約のみ）

## 関連 skill

- `/resume-handoff` — 前回 handoff note を読み込んで作業再開
- `/registry-check` — registry 一覧と直近 3 件の handoff を表示
- dream skill — 24h ごとのメモリ統合（こちらは自動、handoff-note は毎セッション）
