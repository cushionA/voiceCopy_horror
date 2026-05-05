---
name: cost-report
description: Generate cost reports from .claude/cost-log.jsonl with monthly summaries, model/branch breakdowns, and threshold alerts. Use when checking Claude Code session costs, identifying expensive branches, or preparing budget reports.
user-invocable: true
argument-hint: [period: month|7d|1y|all] [--threshold <USD>]
---

# Cost Report: $ARGUMENTS

`.claude/cost-log.jsonl` に蓄積されたセッションコストを集計してレポート化する。
**Wave 4 Phase 15 P15-T3 で新設**。Stop hook (`stop-cost-log.sh`) と連動。

## 動作

### ステップ 1: 期間指定の解釈

引数からカウント期間を決定:
- `month` (デフォルト) — 当月 1 日〜現在
- `7d` / `30d` / `1y` 等 — 相対期間
- `all` — 全期間
- ISO 日付 (`2026-04-01`) — 指定日以降

### ステップ 2: 集計実行

```bash
python tools/cost-report.py --period $ARGUMENTS
```

### ステップ 3: 出力解釈とアクション提案

レポート内容に応じてユーザーに以下を提案:

**コストが高い場合**:
- 「`<branch名>` のセッションが ${X} を占めています。長期ブランチが残っていませんか？」
- 「`claude-opus-4-7` の使用率が ${Y}% です。`/design-systems` 以外で Opus を使っていますか？ Sonnet で十分なケースは Advisor Strategy に従って切り替え可能」

**特定モデル / ブランチが集中している場合**:
- 「日次グラフを見ると ${date} に急増があります。何が起きていましたか？」
- 「キャッシュ読込が少ないです。同じ `Read` を繰り返していないか確認してください」

### ステップ 4: 月次レポート保存（オプション）

`--output docs/reports/analysis/YYYY-MM_cost.md` で月次レポートとして registry に追加:

```bash
python tools/cost-report.py --period month --output docs/reports/analysis/$(date +%Y-%m)_cost.md
```

`docs/reports/_registry.md` の analysis/ セクションに 1 行追加。

### ステップ 5: 閾値アラート

`--threshold` を指定すると総コストが超過したとき exit 1:

```bash
python tools/cost-report.py --period month --threshold 50.0
```

CI / cron 経由でアラート通知に使える（将来拡張）。

## 関連 skill / hook

- `.claude/hooks/stop-cost-log.sh` — セッション終了時のログ追記 (Stop hook)
- `tools/cost-report.py` — 集計本体
- `.claude/skills/handoff-note/SKILL.md` — handoff note の参考フォーマット
- `docs/SKILL_LIFECYCLE.md` — 棚卸しと並ぶ運用ルーチン

## 注意点

- **現状の制約**: Claude Code 本体の `/cost` 出力を hook の stdin から取得する仕様は未確立。本 hook は環境変数 (`CLAUDE_INPUT_TOKENS` 等) 経由で値を受ける雛形。実コスト計測には [ccusage](https://github.com/...) 等の外部ツール併用を推奨
- **ccusage 評価メモ**: `docs/reports/analysis/2026-04-25_ccusage-evaluation.md` を参照（P15-T4 で配置）

## 関連

- WAVE_PLAN.md L808-820 (Phase 15 タスク定義) / L1104-1108 (Session 0 読み物)
- 関連 PR (Wave 2/3): #50 / #51 / #52 / #53 / #54 / #55
