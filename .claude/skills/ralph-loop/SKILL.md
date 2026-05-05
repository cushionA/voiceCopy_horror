---
name: ralph-loop
description: Long-running autonomous task batch using the Ralph pattern (frankbria/ralph-claude-code). Repeats /create-feature on docs/FUTURE_TASKS.md entries until dual-condition exit gate fires (test failures / done signals / coverage delta). Wave 5 Phase 18.
user-invocable: true
argument-hint: [optional task list slug]
---

# Ralph Loop: $ARGUMENTS

長時間の自律バッチ実行 skill。`/loop` 公式機能と組み合わせて
`docs/FUTURE_TASKS.md` の未消化タスクを夜間実行する。

## Layer

このスキルは Two-layer 構成（[詳細](../_two-layer-design.md)）。

- **base.md** — Ralph パターンの汎用ループロジックと dual-condition exit gate の HOW: `@base.md`
- **本ファイル (SKILL.md)** — SisterGame 固有 (FUTURE_TASKS.md / pipeline-state / Sandbox)

## いつ呼ぶか

- **夜間バッチ**: 一晩で 3-5 タスクを消化したい時
- **小タスク量産**: typo 修正 / regex 微修正 / コメント追加など機械的タスクが連続する時
- **Adversarial Review 後の対応**: review 指摘箇所を順次修正したい時

呼ばないケース:
- 1 タスクで複数ファイル横断的な変更が必要 (Ralph は逐次型、並列ではない)
- 仕様確定していない (init-agent 経由で spec を先に確定)
- セキュリティ重大度高い変更 (人間 gate 必須)

## 前提条件

| 前提 | 確認方法 |
|------|---------|
| Phase 20 Sandbox + Docker --network none 環境 | `.claude/rules/sandbox.md` (将来) |
| pipeline-state.json が phase: idle または implement | `bash scripts/init.sh` |
| docs/FUTURE_TASKS.md に🟢タグエントリが 3 件以上 | `grep "🟢" docs/FUTURE_TASKS.md` |
| feature-db に未着手タスクが登録されている | `python tools/feature-db.py list --status pending` |

## 動作

### ステップ 1: pre-flight check

```bash
# 状態確認
bash scripts/init.sh --short

# Ralph state を初期化 (loop 開始の合図)
TEST_COUNT=$(find Assets/Tests -name "*.cs" 2>/dev/null | wc -l | tr -d ' ')
python tools/ralph-exit-gate.py --reset --current-test-count "$TEST_COUNT"
```

### ステップ 2: /loop 起動 (公式機能)

`/loop` は Anthropic 公式 (slash skill リスト参照)。本 skill は /loop に投げるプロンプトを構成する:

```
/loop <interval-or-empty> /<wrapper-task>
```

例:
- `/loop 5m /consume-future-tasks` — 5 分インターバルで consume-future-tasks を起動
- `/loop /ralph-loop` — 自己ペース (本 skill は再帰的に自分を起動しない、loop 公式が制御)

### ステップ 3: 各 iteration の処理

各 loop iteration で以下:

1. ralph-exit-gate `--check` で継続/停止判定
2. continue → consume-future-tasks 1 件分実行
3. テスト実行 → ralph-exit-gate に signal 送信
4. feature 完了時 → ralph-exit-gate に signal feature-completed
5. iteration 終了 → ralph-exit-gate signal iteration

### ステップ 4: exit 時の片付け

dual-condition exit gate が stop verdict を出したら:
- pipeline-state.json の phase を idle に戻す
- claude-progress.txt に "ralph-loop session ended" を記録
- /handoff-note で session 締め (Registry-based handoff)

## 環境変数 (defaults)

| 環境変数 | default | 用途 |
|---------|--------|------|
| `RALPH_MAX_TEST_LOOPS` | 3 | 連続テスト失敗で blocker 判定 |
| `RALPH_DONE_SIGNALS` | 2 | feature 完了数の DONE シグナル閾値 |
| `RALPH_TEST_PCT` | 30 | テスト数増加率の DONE シグナル閾値 |
| `RALPH_OVERNIGHT` | 0 | 1 で夜間バッチモード (より conservative な gate) |

## 既存資産との関係

| skill / tool | 関係 |
|-------------|------|
| `/consume-future-tasks` | Ralph 1 iteration の処理本体 |
| `/loop` | Anthropic 公式、Ralph の繰り返し制御 |
| Phase 20 Sandbox (将来) | Ralph 夜間バッチの隔離実行環境 |
| `/handoff-note` | session 締め時に呼ぶ |
| Phase 24 compound-extract (PR #61) | Ralph 終了時に学びを抽出 |

## 関連

- WAVE_PLAN.md L885-895 (Phase 18 P18-T1〜T7)
- 外部: frankbria/ralph-claude-code
- `.claude/rules/ralph-overnight.md` (夜間バッチ運用ルール)
- `tools/ralph-exit-gate.py` (gate 判定)
- `~/.claude/skills/loop/SKILL.md` (公式 /loop)
