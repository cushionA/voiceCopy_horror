#!/usr/bin/env bash
# unity-console-check.sh — PostToolUse hook (P22-T1)
#
# Edit / Write / MultiEdit で .cs が変更された後、Unity Editor の
# コンソールエラーを確認する。
#
# Backend 優先順序 (UNITY_CLI_BACKEND で明示制御可):
#   🥇 1. unicli (Editor 起動中 + UniCli インストール済み)  ← Named Pipe IPC で最速・最軽量。本プロジェクト推奨
#   🥈 2. claude-mcp (MCP CLI 整備後、現状は未確立)         ← 将来用フォールバック
#   ⏸  3. (skip) — Editor が起動していない / UniCli 未インストール  ← 開発を止めない退避
#
# 環境変数:
#   UNITY_CLI_BACKEND=unicli|mcp|auto  (デフォルト: auto)
#   UNITY_HOOK_PHASE=warn|error  (デフォルト: warn — error 検出でも exit 0)
#
# Wave 3 Phase 22 P22-T1 で導入。

set -uo pipefail

cd "$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
[ -d ".git" ] || exit 0

# stdin から file_path を取得
FILE=$(cat /dev/stdin 2>/dev/null \
  | python -c "import sys, json; d=json.loads(sys.stdin.read()); print(d.get('tool_input', {}).get('file_path', ''))" \
  2>/dev/null || echo "")

# .cs 以外なら何もしない
case "$FILE" in
  *.cs) ;;
  *) exit 0 ;;
esac

PHASE="${UNITY_HOOK_PHASE:-warn}"
BACKEND="${UNITY_CLI_BACKEND:-auto}"

run_via_unicli() {
  # UniCli で console error 件数を取得
  if ! command -v unicli >/dev/null 2>&1; then
    return 1
  fi
  # status 確認 (Editor 接続できなければ skip)
  if ! unicli check >/dev/null 2>&1; then
    return 1
  fi
  # Console.GetLog --json で error / warning を取得
  RESULT=$(unicli exec Console.GetLog --json --timeout 5000 2>/dev/null) || return 1
  ERR_COUNT=$(echo "$RESULT" | python -c "import sys,json; d=json.loads(sys.stdin.read()); print(sum(1 for e in d.get('logs',d.get('result',{}).get('logs',[])) if e.get('type','').lower() in ('error','exception','assert')))" 2>/dev/null || echo 0)
  if [ "$ERR_COUNT" -gt 0 ]; then
    echo "[unity-hook] Unity console: $ERR_COUNT error(s) detected after editing $FILE" >&2
    if [ "$PHASE" = "error" ]; then
      return 2
    fi
  fi
  return 0
}

run_via_mcp() {
  # claude-mcp 経由 (将来用)
  command -v claude-mcp >/dev/null 2>&1 || return 1
  # TODO: MCP CLI 整備時に read_console を呼ぶ
  return 1
}

# Backend 選択
case "$BACKEND" in
  unicli)
    run_via_unicli || exit 0
    ;;
  mcp)
    run_via_mcp || exit 0
    ;;
  auto|*)
    if run_via_unicli; then
      :
    elif run_via_mcp; then
      :
    else
      # どの backend も使えない場合は warning なしで終了
      exit 0
    fi
    ;;
esac

EXIT_CODE=$?

# warn フェーズは常に exit 0
if [ "$PHASE" = "warn" ]; then
  exit 0
fi

exit $EXIT_CODE
