---
name: review-parallel
description: Run a 4-parallel code review based on Anthropic's official plugins/code-review pattern (2 Sonnet for compliance/style + 2 Opus for logic/security + independent verification). Use for very large PRs or release-critical changes. Wave 4 Phase 12 P12-T8.
user-invocable: true
argument-hint: <pr-number | "branch">
---

# Review Parallel: $ARGUMENTS

Anthropic 公式 [plugins/code-review](https://github.com/anthropics/claude-code/blob/main/plugins/code-review/commands/code-review.md) の 4 並列パターンを SisterGame に移植。
**`/adversarial-review` の上位版** — 大型 PR / リリースクリティカル変更向け。

## いつ呼ぶか

- 大型 PR (≥30 ファイル変更 or ≥800 行 diff)
- リリースクリティカル変更（main / production への直接影響）
- 公式パターンの 4 並列で網羅的にチェックしたい時

## 並列構成

| # | agent | model | 観点 |
|---|-------|-------|------|
| 1 | `reviewer-optimizer` | Sonnet | **Compliance/Style**: 規約準拠、命名、フォーマット |
| 2 | `reviewer-optimizer` (再起動) | Sonnet | **Refactoring/Reuse**: 既存ユーティリティ未使用、重複 |
| 3 | `reviewer-skeptic` | Opus | **Logic/Edge Cases**: 境界値、状態シーケンス |
| 4 | `reviewer-skeptic` (再起動) | Opus | **Security**: prompt injection、secret、CVE |

各 agent は別 context で起動。同じ agent を 2 回起動する場合は引数で観点を指定:

```
/agent reviewer-optimizer <diff> --focus compliance
/agent reviewer-optimizer <diff> --focus refactoring
/agent reviewer-skeptic <diff> --focus logic
/agent reviewer-skeptic <diff> --focus security
```

## 動作

### ステップ 1: 対象 diff 取得

`/adversarial-review` と同じ。

### ステップ 2: 4 並列起動

```bash
# 並列実行（Agent ツールの並列呼び出し）
Agent reviewer-optimizer  → focus: compliance
Agent reviewer-optimizer  → focus: refactoring
Agent reviewer-skeptic    → focus: logic
Agent reviewer-skeptic    → focus: security
```

### ステップ 3: 独立検証 subagent

別の subagent (または `/simplify`) を起動し、上記 4 件の指摘の中から **false positive** を抽出する:

```
独立検証 subagent への入力:
  - 4 件のレビュー出力
  - diff 本体
  - SisterGame の `.claude/rules/` 全文

出力:
  - 指摘ごとに「真陽性 / 偽陽性 / 保留」判定
  - 偽陽性の根拠 (該当規約は適用外、別の理由で OK 等)
```

### ステップ 4: HIGH SIGNAL のみ統合出力

```markdown
## Review Parallel Result (4 + 独立検証)

### 必修正（≥3 agent 一致 or 独立検証で真陽性確定）
- ...

### 検討推奨（2 agent 一致）
- [compliance + refactoring] file:line — 規約違反 + 既存ユーティリティ未使用
- ...

### 偽陽性として除外（独立検証）
- file:line — 規約 X はテスト用ファイルには適用されない
```

### ステップ 5: 保存

`docs/reports/reviews/<date>_pr<N>_parallel.md` に保存。

## `/adversarial-review` との使い分け

| 軸 | `/adversarial-review` | `/review-parallel` |
|----|----------------------|---------------------|
| 並列数 | 2 (Optimizer + Skeptic) | 4 + 独立検証 |
| コスト | 中 (≥5 スコアで dual) | 高 (常に 4 並列) |
| 用途 | 通常の PR | 大型 / リリースクリティカル |
| 偽陽性抑止 | cross-model consensus | 独立検証 subagent |

## ルール

- **コスト管理**: 4 並列 + 独立検証は API コスト 5x 程度。常用は避け、判断要件のあるときのみ
- **偽陽性除外を必ず行う**: 4 並列だと指摘が増えるが、独立検証で HIGH SIGNAL のみに絞る
- 起動前に `/adversarial-review` で十分かを判定推奨

## 関連

- WAVE_PLAN.md L805 (P12-T8) / L1088-1092 (Session 0 読み物)
- 参考: [Anthropic plugins/code-review](https://github.com/anthropics/claude-code/blob/main/plugins/code-review/commands/code-review.md)
- 関連 skill: `/adversarial-review` (2 並列版)
