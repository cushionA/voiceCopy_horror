---
name: adversarial-review
description: Run a 2-model adversarial code review (Optimizer + Skeptic) with cross-model consensus. Use after implementing a non-trivial change, before merging a PR, or when wanting a sanity check that catches what a single reviewer misses. Wave 4 Phase 12 P12-T4.
user-invocable: true
argument-hint: <pr-number | "branch" for current branch | <file-path>>
---

# Adversarial Review: $ARGUMENTS

**Optimizer (Sonnet) + Skeptic (Opus)** の 2 並列レビュー。Anthropic 内部で substantive 率を 16% → 54% に上げた手法を SisterGame に最適化。

## いつ呼ぶか

- 大きめの PR をマージする前（推奨: ≥10 ファイル変更 or ≥200 行 diff）
- 自分のレビューで見落としがないか確認したい時
- TDD 3 分割モードで実装した機能の最終チェック

## 動作

### ステップ 1: 対象 diff の取得

引数解釈:
- `<pr-number>` → `gh pr diff <num>` で PR の diff
- `branch` → `git diff main..HEAD` で現ブランチの差分
- `<file-path>` → 該当ファイル全体

### ステップ 2: スコア閾値判定（実行コスト最適化）

まず軽量 heuristics で diff の重要度を見積もる:

```bash
# 変更ファイル数 / 変更行数 / Architect/ や Core/ への変更を見る
git diff --stat
git diff --name-only | grep -E "(Architect|Core|GameManager|HpArmor)" | wc -l
```

**スコア判定**:
| スコア | 範囲 | アクション |
|-------|------|-----------|
| ≤0 | 末端ドキュメントのみ等 | レポートなし、skip |
| 1〜4 | 中規模・末端コード | **Sonnet (Optimizer) のみ**起動 |
| ≥5 | コア / 大規模変更 | **Sonnet + Opus 並列起動**（dual-model consensus） |

### ステップ 3: 並列起動

#### スコア 1〜4: Optimizer のみ

```
/agent reviewer-optimizer <diff>
```

出力をそのままユーザーに提示。

#### スコア ≥5: Optimizer + Skeptic 並列

両 agent を並列で別 context で起動:

```
/agent reviewer-optimizer <diff>
/agent reviewer-skeptic <diff>
```

完了後、両者の出力を**統合**してユーザーに提示。

### ステップ 4: Cross-model consensus

両 agent が指摘した issue を以下に分類:

1. **両者一致 (HIGH SIGNAL)** — 必ず修正候補に挙げる
2. **片方のみ (MEDIUM)** — 信頼度を表示、ユーザー判断
3. **矛盾** — 両論併記 + どちらが正しいか追加確認推奨

### ステップ 5: HIGH SIGNAL のみ出力

```markdown
## Adversarial Review Result

**スコア**: 7 / dual-model

### 必修正 (両者一致)
- file:line — issue / fix
- ...

### 検討推奨 (片方のみ高信頼)
- [Optimizer] file:line — refactoring opportunity
- [Skeptic] file:line — edge case scenario

### 矛盾 (要追加確認)
- file:line — Optimizer says X, Skeptic says Y. 確認方法: ...
```

### ステップ 6: 保存（オプション）

レポートを `docs/reports/reviews/<date>_pr<N>_adversarial.md` に保存し、`docs/reports/_registry.md` の reviews/ セクション最上部に 1 行追加。

## 関連 skill / agent

- `.claude/agents/reviewer-optimizer/AGENT.md` (Sonnet)
- `.claude/agents/reviewer-skeptic/AGENT.md` (Opus、フォールバック Sonnet)
- `/review-parallel` — 4 並列版（公式 plugins/code-review パターン、より大型 PR 用）
- `/security-review-local` — security 特化、prompt injection 検査

## 関連

- WAVE_PLAN.md L794-806 (Phase 12 タスク定義) / L1088-1092 (Session 0 読み物)
- 参考: ng-adversarial-review、Anthropic plugins/code-review
- 参考: Anthropic 内部で substantive 率 16% → 54% の実績
