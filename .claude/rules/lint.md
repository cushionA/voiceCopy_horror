---
description: PostToolUse 静的分析 hook (lint_check.py) の検査内容・誤検知抑止方法・phase 切替条件を成文化
---

# lint hook 運用ガイド (Wave 2 Phase 11 P11-T7)

PR #47 で導入された PostToolUse 静的分析 hook（`tools/lint_check.py` + `.claude/hooks/lint-check.sh` + `.claude/hooks/post-edit-dispatch.sh`）の運用ルールを定義する。

## 何が検査されるか

`Write` / `Edit` / `MultiEdit` の対象ファイルが `.cs` の場合、PostToolUse 直後に **`tools/lint_check.py`** が起動し、以下を検査する。

### 検査パターンの source of truth

- **`.claude/rules/lint-patterns.json`** — 40 パターンの regex / severity / source ヒット履歴を含む
- **`.claude/rules/lint-patterns.schema.json`** — 上記 JSON の構造定義（draft-07）

各パターンは `id` / `severity (error / warning / info)` / `regex` / `message` / `source`（規約ファイルの引用箇所）を持つ。
詳細リストは `.claude/rules/wave0-audit.md` § B（regex + source 対応表）を参照。

### 主要カテゴリ

| カテゴリ | 例 |
|---------|-----|
| 命名規則違反 | `var x = 1;` （`var` 禁止）、`private string Name;`（`_camelCase` 違反）、`const int MaxSpeed = 10;`（`k_PascalCase` 違反） |
| MonoBehaviour パフォーマンス | `Update` 内の `new List<>()`、`obj.tag == "Player"` 文字列比較、`Vector3.Distance` ホットパス使用 |
| アーキテクチャ違反 | `FindObjectOfType<T>()`、ランタイムでの `AssetDatabase`、`Resources.Load`、`Core/` 配下の `Debug.Log` |
| イベント / リソース管理 | OnEnable/OnDisable の subscribe/unsubscribe 非対称、`Addressables.LoadAssetAsync` without `Release` |
| Unity 規約 | `[SerializeField] public`、`obj.tag ==` 文字列比較、Allman ブレース違反、タブインデント |

### 入力モード

`tools/lint_check.py` は以下の起動方法をサポート:

| モード | 用途 |
|-------|------|
| `--hook-stdin` | hook から呼ばれる本番経路（`.claude/hooks/lint-check.sh` 経由）。stdin で Claude Code hook JSON を受け取り、`tool_input.file_path` / `tool_input.content` / `tool_input.new_string` を解析 |
| `--file <path>` | 開発時の手動チェック。既存ファイル全体を解析 |
| `--diff <hash>` | git ベースの差分チェック（将来拡張） |

## phase 設計（warn → error の段階昇格）

検査結果は重大度に応じて 2 phase で運用する:

| Phase | 環境変数 | 動作 | 用途 |
|-------|---------|------|------|
| **warn**（デフォルト、現行） | `LINT_PHASE=warn` または未設定 | findings を stderr に出力、PostToolUse は **常に exit 0** | 観察期間 / 学習段階。誤検知を集計し、必要なら `lint-patterns.json` を調整 |
| **error**（昇格後） | `LINT_PHASE=error` | error severity の findings 検出時に **exit 1** で `asyncRewake` をトリガー、Claude に差し戻し | 規約違反コードを実際にブロックする運用 |

**現行は warn フェーズ**（PR #47）。error 昇格は P11-T8 として 1 週間の観察期間（P11-T6）後に実施予定（`docs/FUTURE_TASKS.md` 登録済み）。

### 昇格条件

P11-T8 で `LINT_PHASE=error` をデフォルト化する条件:

1. **観察期間**（PR #47 マージから 1 週間以上経過）の hook 出力ログを `lint-observation-log.md` に集計済み
2. **誤検知件数 3 件以下**（または該当パターンを `lint-patterns.json` で調整済み）
3. **規約準拠コードで warning 0 件**（既存ファイルで 1 ファイル以上を `--file` モードでサンプル検証）

## 誤検知時の抑止方法

検査が誤検知（false positive）を出している場合、以下の優先順で対応する。

### 優先 1: regex の調整（恒久対応）

`.claude/rules/lint-patterns.json` の該当パターンの `pattern` フィールドを修正。例:

```json
{
  "id": "CS-PERF-002",
  "severity": "warning",
  "pattern": "\\.tag\\s*==\\s*\"",
  "message": "CompareTag() を使用（文字列比較は遅い）"
}
```

例えばコメント行を除外したい場合は否定先読み（`(?<!//)`）を追加する。

### 優先 2: パターン除外（特定ファイル）

`.claude/rules/lint-patterns.json` の各パターンに `exclude` 配列を追加（schema が glob を受け付ける）。
※ Phase 21 改良タスクと連動（`security-patterns.json` の `exclude` 拡張と同じ仕組み）。

### 優先 3: phase=warn にロールバック（緊急退避）

万一 error 昇格後に重大な誤検知でビルドが止まる場合、環境変数で即座に warn に戻せる:

```bash
# 一時的（このシェルセッションのみ）
export LINT_PHASE=warn

# 永続的（ロールバック相当）
git revert <T8 PR の merge commit>
```

## 観察ログの記録方法

`.claude/rules/lint-observation-log.md` に以下のフォーマットで誤検知 / 真検知を集計する:

```markdown
## YYYY-MM-DD

| 時刻 | severity | pattern id | ファイル | 判定 | メモ |
|------|---------|-----------|---------|------|------|
| 14:23 | warning | CS-PERF-002 | Combat.cs:42 | 真検知 | tag 比較を CompareTag に修正 |
| 15:01 | warning | MD-EMOJI-001 | README.md | 誤検知 | regex が re.error、MD ファイル除外要 |
```

判定列:
- **真検知**: 規約違反を正しく指摘 → 規約に従ってコード修正
- **誤検知**: 規約に準拠しているのに警告 → パターン調整 or 除外設定
- **保留**: 判定難 / 仕様確認中

## phase 切替フローの早見表

```
[初期] PR #47 マージ (2026-04-25)
  ↓
[現在] LINT_PHASE=warn (デフォルト) — 観察期間
  ↓ 1 週間 + 誤検知 3 件以下
[昇格] P11-T8 で LINT_PHASE=error をデフォルト化 (PR)
  ↓
[運用] error 検出で PostToolUse exit 1 → Claude が修正を試みる
```

## トラブルシューティング

### Q. PostToolUse が遅い / 毎回 hook が走って煩わしい
A. `.claude/settings.json` の `matcher` で対象を絞り込む（現状は `Write|Edit|MultiEdit`）。
.cs 以外のファイルは `lint-check.sh` 内で early exit する設計（exit code 3）。

### Q. JSONSchema バリデーションエラー（lint-patterns.json）
A. `tools/lint_check.py` は jsonschema 外部依存なしで手動検証（id 形式 / severity / 必須フィールド）。
スキーマ違反時は `WARN: schema validation failed: ...` を stderr 出力するが処理は継続する。

### Q. `MD-EMOJI-001` の regex error が出る
A. `[\u{1F300}...]` は Python re では不正な Unicode escape。`tools/lint_check.py` は `re.error` を catch して該当パターンを WARN として skip し、他のパターン処理を継続する設計。

### Q. Hook が呼ばれていない気がする
A. `.claude/settings.json` の `PostToolUse` matcher 確認:
```bash
cat .claude/settings.json | python -m json.tool
```
`bash .claude/hooks/post-edit-dispatch.sh < /dev/null` が動くかも確認（exit 3 = .cs 以外で skip、それ以外なら成功）。

## 関連

- `.claude/rules/lint-patterns.json` — 40 パターン（source of truth）
- `.claude/rules/lint-patterns.schema.json` — JSON Schema
- `.claude/rules/lint-observation-log.md` — 観察ログ（P11-T6 で集計）
- `.claude/rules/wave0-audit.md` § B — 各パターンの規約引用
- `tools/lint_check.py` — Python 静的分析ツール
- `.claude/hooks/post-edit-dispatch.sh` — PostToolUse dispatcher
- `.claude/hooks/lint-check.sh` — lint phase wrapper
- WAVE_PLAN.md L704-715 — Phase 11 タスク定義
