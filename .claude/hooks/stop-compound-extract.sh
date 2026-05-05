#!/usr/bin/env bash
# Wave 5 Phase 24 — Stop hook: compound entry 候補の自動抽出
#
# stdin: { "session_id": "...", "transcript_path": "/path/.jsonl", ... }
# 動作:
#   - 閾値超え session で tools/compound-extract.py を起動
#   - draft は docs/compound/_drafts/ に出力 (人間レビュー必須)
#   - 既存の stop-handoff-reminder.sh / stop-cost-log.sh と並列に動作
#
# 環境変数:
#   COMPOUND_HOOK_DISABLED=1   完全に skip (緊急退避)
#   COMPOUND_THRESHOLD=N        assistant_turns 最小閾値 (default 8)

set -uo pipefail

[ "${COMPOUND_HOOK_DISABLED:-0}" = "1" ] && exit 0

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "")"
[ -z "$REPO_ROOT" ] && exit 0
cd "$REPO_ROOT"

# tools が無ければ skip (Phase 24 未マージ環境への配慮)
[ -f "tools/compound-extract.py" ] || exit 0

HOOK_JSON=$(cat /dev/stdin 2>/dev/null || echo "")
[ -z "$HOOK_JSON" ] && exit 0

TRANSCRIPT_PATH=$(echo "$HOOK_JSON" | python -c "import sys, json
try:
    d = json.loads(sys.stdin.read())
    print(d.get('transcript_path', ''))
except Exception:
    pass" 2>/dev/null || echo "")

SESSION_ID=$(echo "$HOOK_JSON" | python -c "import sys, json
try:
    d = json.loads(sys.stdin.read())
    print(d.get('session_id', ''))
except Exception:
    pass" 2>/dev/null || echo "")

[ -z "$TRANSCRIPT_PATH" ] && exit 0
[ ! -f "$TRANSCRIPT_PATH" ] && exit 0

THRESHOLD="${COMPOUND_THRESHOLD:-8}"

python tools/compound-extract.py \
    --transcript "$TRANSCRIPT_PATH" \
    --session-id "$SESSION_ID" \
    --threshold "$THRESHOLD" 2>&1 | head -3

exit 0
