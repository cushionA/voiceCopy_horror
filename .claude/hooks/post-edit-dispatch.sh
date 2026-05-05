#!/usr/bin/env bash
# PostToolUse dispatcher
# stdin を 1 度だけ読んで複数 hook に渡す。
# jq が PATH にない Windows 環境を考慮し、Python で JSON パース。
#
# 統合している hook:
#   1. lint-check (CS ファイルのみ)
#   2. test-tip (CS 実装ファイル編集時に /run-tests を促す)
#   3. phase-boundary-commit (designs/pipeline-state.json 更新時の checkpoint tag)

set -uo pipefail

STDIN=$(cat)
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

# ファイルパスを JSON から抽出（Python で）
FILE_PATH=$(printf '%s' "$STDIN" | python -c \
    'import sys, json; d=json.load(sys.stdin); print(d.get("tool_input",{}).get("file_path",""))' \
    2>/dev/null || echo "")

# 1. lint check（.cs ファイルのみ）
if [[ "$FILE_PATH" == *.cs ]]; then
    printf '%s' "$STDIN" | bash .claude/hooks/lint-check.sh || true
fi

# 2. test-tip: 実装系 C# ファイル編集時に /run-tests を促す
# （テストファイル自体は除外）
if [ -n "$FILE_PATH" ] && \
   [[ "$FILE_PATH" == *.cs ]] && \
   ! echo "$FILE_PATH" | grep -qiE "test"; then
    echo "[HOOK] C# implementation file modified: $FILE_PATH — consider running /run-tests"
fi

# 3. phase-boundary-commit: pipeline-state.json 更新時の checkpoint tag (Wave 5 Phase 7)
if [[ "$FILE_PATH" == *pipeline-state.json ]]; then
    printf '%s' "$STDIN" | bash .claude/hooks/phase-boundary-commit.sh || true
fi

exit 0
