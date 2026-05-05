#!/usr/bin/env bash
# PostToolUse hook for Write|Edit|MultiEdit on .cs files
# stdin: Claude Code hook JSON
#
# Phase 1 (warn): exit 0 always — findings を stderr に出力するだけ（blocking なし）
# Phase 2 (error): exit 1 on error findings（別 PR PR-E で有効化予定）
#
# 環境変数:
#   LINT_PHASE=warn|error  (デフォルト: warn)

set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

PHASE="${LINT_PHASE:-warn}"

python tools/lint_check.py --hook-stdin --phase "$PHASE"
RC=$?

# warn フェーズは常に exit 0（blocking しない）
if [ "$PHASE" = "warn" ]; then
    exit 0
fi

# error フェーズ: exit code を伝播（exit 1 で asyncRewake をトリガー）
exit "$RC"
