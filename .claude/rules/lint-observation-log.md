---
description: lint hook (Phase 11) の誤検知 / 真検知を集計するログ。Phase 11 P11-T8 (error 昇格) の判定材料。
---

# lint observation log (Wave 2 Phase 11 P11-T6)

PR #47 で導入された `tools/lint_check.py` の出力を集計し、`LINT_PHASE=error` 昇格判定（P11-T8）の材料にする。

## 運用ルール

- **観察期間**: 2026-04-25（PR #47 マージ）〜 2026-05-02（1 週間）
- 各セッション末に hook 出力（stderr）から検出された findings を本ファイルに追記
- `判定` 列で「真検知 / 誤検知 / 保留」を分類
- **誤検知が 3 件以上**になった時点で `lint-patterns.json` の該当パターンを修正
- **誤検知 3 件以下** & **規約準拠コードで warning 0 件**を確認できたら P11-T8 (error 昇格 PR) へ進む

## 集計フォーマット

```markdown
## YYYY-MM-DD

| 時刻 | severity | pattern id | ファイル:行 | 判定 | メモ |
|------|---------|-----------|------------|------|------|
| HH:MM | error/warning/info | <id> | <path>:<line> | 真検知/誤検知/保留 | 短い説明 |
```

判定区分:
- **真検知** — 規約違反を正しく指摘した。コード側を修正
- **誤検知** — 規約に準拠しているのに警告。`lint-patterns.json` の regex 修正 or `exclude` 設定で対応
- **保留** — 判定難 or 仕様確認中

## 観察ログ

### 2026-04-25（観察開始日）

| 時刻 | severity | pattern id | ファイル:行 | 判定 | メモ |
|------|---------|-----------|------------|------|------|
| - | - | - | - | - | 観察期間開始。エントリは hook 出力に応じて随時追記 |

### 2026-04-26

*エントリなし*

### 2026-04-27

*エントリなし*

### 2026-04-28

*エントリなし*

### 2026-04-29

*エントリなし*

### 2026-04-30

*エントリなし*

### 2026-05-01

*エントリなし*

### 2026-05-02（観察期間終了 / P11-T8 判定日）

*エントリなし*

---

## 集計サマリ（P11-T8 判定用）

観察期間終了時に以下を埋めて P11-T8 (error 昇格 PR) の判定材料にする:

| 区分 | 件数 |
|------|------|
| 真検知（severity: error） | __ |
| 真検知（severity: warning） | __ |
| 真検知（severity: info） | __ |
| 誤検知 | __ |
| 保留 | __ |

### 昇格判定

- [ ] 誤検知 3 件以下
- [ ] 規約準拠コード（例: `Assets/MyAsset/Core/Combat/Projectile/ProjectileHitProcessor.cs`）で `--file` モードを実行し warning 0 件
- [ ] 該当する場合、誤検知パターンを `lint-patterns.json` で調整済み

3 つすべて満たせば P11-T8（`LINT_PHASE=error` デフォルト化）の PR を出してよい。

## 関連

- `.claude/rules/lint.md` — phase 切替条件（本ファイルの判定基準と整合）
- `.claude/rules/lint-patterns.json` — パターン source of truth（誤検知時はここを調整）
- `.claude/hooks/post-edit-dispatch.sh` / `.claude/hooks/lint-check.sh` — hook 経路
- `tools/lint_check.py` — 検査本体
- WAVE_PLAN.md L713 (P11-T6) / L715 (P11-T8)
