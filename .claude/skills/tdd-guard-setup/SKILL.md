---
name: tdd-guard-setup
description: Set up the TDD-Guard PreToolUse hook (nizos/tdd-guard) for SisterGame. Runs the guided installation, configures the hook in .claude/settings.json, and adds the spike-mode timeout safety. Use ONCE after Wave 3 Phase 6 is approved.
user-invocable: true
argument-hint: <install | status | spike-clear>
---

# TDD-Guard Setup: $ARGUMENTS

`nizos/tdd-guard` の PreToolUse hook を SisterGame に統合する setup ガイド。
**Wave 3 Phase 13 P13-T5 で新設**。Phase 6 (TDD-Guard 本格導入) と連携する。

## 何をする skill か

| サブコマンド | 動作 |
|--------------|------|
| `install` | tdd-guard を clone し、PreToolUse hook 登録手順を案内（**ユーザー承認必須**） |
| `status` | 現在の hook 状態を表示（`.claude/.tdd-spike-mode` フラグの有無、最終更新時刻） |
| `spike-clear` | spike モードフラグを削除（緊急時に外した hook を再有効化する） |

## install サブコマンド

### ステップ 1: 前提条件確認

```bash
# git / Node.js / 必要に応じて pnpm が入っていることを確認
node --version
git --version
```

### ステップ 2: ユーザー確認

**破壊的変更**である旨をユーザーに明示:
- PreToolUse hook で `Write` / `Edit` / `MultiEdit` / `TodoWrite` が傍受される
- 失敗テストなしで実装ファイルを書こうとするとブロックされる
- 緊急時のロールバック手段: `.claude/.tdd-spike-mode` フラグ作成

ユーザー承認 (yes 明示) なしには続行しない。

### ステップ 3: tdd-guard 配置

```bash
# 例: tools/ 配下にサブモジュールとして clone
git submodule add https://github.com/nizos/tdd-guard tools/tdd-guard
```

### ステップ 4: settings.json 更新

```jsonc
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit|TodoWrite",
        "hooks": [
          { "type": "command", "command": "bash .claude/hooks/tdd-guard.sh" }
        ]
      }
    ]
  }
}
```

### ステップ 5: `.claude/hooks/tdd-guard.sh` 配置

スクリプト内容:
- `.claude/.tdd-spike-mode` フラグが存在し、24h 以内なら spike モード（チェックスキップ）
- 24h 超過なら自動失効
- spike モードでない場合、tdd-guard 本体を呼び出し

詳細は `docs/FUTURE_TASKS.md` の「TDD-Guard Spike モードの解除忘れ対策」エントリ参照。

### ステップ 6: `.gitignore` に追記

```
.claude/.tdd-spike-mode
```

誤コミット防止。

## status サブコマンド

```bash
echo "=== TDD-Guard Status ==="
if [ -f .claude/.tdd-spike-mode ]; then
  MTIME=$(stat -c %Y .claude/.tdd-spike-mode 2>/dev/null || stat -f %m .claude/.tdd-spike-mode 2>/dev/null)
  AGE_H=$(( ($(date +%s) - MTIME) / 3600 ))
  echo "Spike mode: ACTIVE (${AGE_H}h ago)"
  if [ $AGE_H -ge 24 ]; then
    echo "  → expired (>24h), TDD-Guard が自動再有効化されています"
  fi
else
  echo "Spike mode: inactive (TDD-Guard active)"
fi
echo "Hook script: $(test -x .claude/hooks/tdd-guard.sh && echo present || echo MISSING)"
echo "Settings hook: $(grep -c tdd-guard .claude/settings.json) entries"
```

## spike-clear サブコマンド

```bash
rm -f .claude/.tdd-spike-mode
echo "Spike mode cleared. TDD-Guard re-enabled."
```

## 関連

- `.claude/agents/tdd-test-writer/AGENT.md` (Red phase)
- `.claude/agents/tdd-implementer/AGENT.md` (Green phase)
- `.claude/agents/tdd-refactorer/AGENT.md` (Refactor phase)
- `.claude/skills/create-feature/SKILL.md` (3 段分割ワークフロー、本 PR で改修)
- `docs/FUTURE_TASKS.md` の「TDD-Guard Spike モードの解除忘れ対策」エントリ
- WAVE_PLAN.md L749-760 (Phase 6) / L766-773 (Phase 13)
- 参考: [nizos/tdd-guard](https://github.com/nizos/tdd-guard)
