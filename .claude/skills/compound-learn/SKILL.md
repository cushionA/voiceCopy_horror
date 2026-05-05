---
name: compound-learn
description: Manually review and promote auto-extracted compound entry drafts. Reads docs/compound/_drafts/, lets the user curate findings, and writes promoted entries to docs/compound/{date}_{slug}.md. Wave 5 Phase 24.
user-invocable: true
argument-hint: [optional draft filename]
---

# Compound Learn: $ARGUMENTS

`tools/compound-extract.py` が Stop hook で抽出した draft を確認し、再利用可能な学びを
`docs/compound/` に昇格させる skill。Wave 5 Phase 24 で導入。

## Layer

このスキルは Two-layer 構成（[詳細](../_two-layer-design.md)）。

- **base.md** — 抽出 → 確認 → 昇格 → archive のワークフロー本体。`@base.md`
- **本ファイル (SKILL.md)** — SisterGame 固有の overlay (artifact パス / rule 連携 / 命名規約)

## いつ呼ぶか

- Stop hook が `docs/compound/_drafts/` に新規 draft を置いた直後 (人間レビュー)
- 月次 review (毎月 25 日) で `tools/consolidate-memory-extension.py` の結果を確認する時
- 大きな学びを記録したい時 (auto-extract を待たず手動で書く)

## 入力アーティファクト

| 場所 | 役割 |
|------|------|
| `docs/compound/_drafts/{date}_{slug}.md` | auto-extract された候補。frontmatter + raw extract を含む |
| `docs/compound/_template.md` | 昇格時の最終フォーマット (frontmatter スキーマ) |
| `docs/compound/*.md` | 既存エントリ (重複検査の対象) |

## 出力アーティファクト

| 場所 | 役割 |
|------|------|
| `docs/compound/{YYYY-MM-DD}_{slug}.md` | 昇格後のエントリ (frontmatter 完備) |
| `docs/compound/_drafts/` から削除 | 昇格後は draft を消す (archive ではなく削除) |

## SisterGame 固有の昇格判定

base.md の手順に加え、以下の SisterGame ローカル判定:

1. **rules 化候補か** — `.claude/rules/compound-promotion.md` の経路 1 基準
   - 同抽象パターンが 3 件以上 → `.claude/rules/<新>.md` を別 PR で作成
2. **Architect 化候補か** — 経路 2 基準
   - アーキテクチャ・状態機械・データ構造に関する → `Architect/` 既存章への追記 or 新章
3. **future-task 化候補か** — 経路 3 基準
   - 実装タスクの示唆 → `docs/FUTURE_TASKS.md` に🟡または🟢タグでエントリ追加

判定後、昇格しないものは `docs/compound/` 単独エントリとして保存。

## frontmatter 必須フィールド (SisterGame 規約)

```yaml
---
topic: <1 行要約>
date: YYYY-MM-DD
outcome: <パターン名 or 結論>
related_pr: <PR 番号 or リンク or "-">
files_affected:
  - path/to/file1
tags: [tag1, tag2]
---
```

`auto-extract` タグが auto-draft 時に自動付与されているので、レビュー後に削除する。

## 実行例

### 自動 draft の確認
```bash
ls docs/compound/_drafts/
cat docs/compound/_drafts/2026-04-25_sessionXXX.md
```

### 昇格 (人間が確認後)
1. draft の Pattern セクションを書き直す (auto-extract は raw な抜粋のみ)
2. outcome を 1 行で表現
3. `docs/compound/{date}_{slug}.md` として保存
4. `docs/compound/_drafts/<原ファイル>` を `rm` で削除
5. `git add` + `git commit -m "compound: <topic>"`

### 重複・stale チェック
```bash
python tools/consolidate-memory-extension.py
# 必要なら --apply で archive 実施
python tools/consolidate-memory-extension.py --apply
```

## 関連

- `tools/compound-extract.py` (auto draft 生成)
- `tools/consolidate-memory-extension.py` (archive / 重複検出)
- `.claude/rules/compound-promotion.md` (昇格判定基準)
- `docs/compound/_template.md` (frontmatter テンプレート)
- WAVE_PLAN.md L921-930 (Phase 24 P24)
- ~/.claude/skills/dream/SKILL.md (memory consolidation との棲み分け)
