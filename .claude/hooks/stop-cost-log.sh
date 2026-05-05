#!/usr/bin/env bash
# stop-cost-log.sh — Stop hook (P15-T2 + transcript 解析拡張、2026-04-25)
#
# セッション終了時に Claude Code transcript を解析し
# .claude/cost-log.jsonl に追記する。
#
# 入力 (stdin): Claude Code Stop hook の JSON
#   { "session_id": "...", "transcript_path": "/path/to/transcript.jsonl", ... }
#
# 動作優先度:
#   1. stdin の JSON から transcript_path 取得 → tools/cost-aggregate.py で集計
#   2. transcript 取得失敗 → 環境変数 (CLAUDE_INPUT_TOKENS 等) フォールバック
#
# 公式 Issue: https://github.com/anthropics/claude-code/issues/52089
# (Stop hook stdin への usage 直接渡しが将来実装されたら集計部分を簡素化可能)

set -uo pipefail

cd "$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
[ -d ".git" ] || exit 0

LOG_FILE=".claude/cost-log.jsonl"
mkdir -p "$(dirname "$LOG_FILE")"

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# stdin から JSON 取得
HOOK_JSON=$(cat /dev/stdin 2>/dev/null || echo "")

TRANSCRIPT_PATH=""
SESSION_ID=""
if [ -n "$HOOK_JSON" ]; then
  TRANSCRIPT_PATH=$(echo "$HOOK_JSON" | python -c "import sys, json; d=json.loads(sys.stdin.read()); print(d.get('transcript_path', ''))" 2>/dev/null || echo "")
  SESSION_ID=$(echo "$HOOK_JSON" | python -c "import sys, json; d=json.loads(sys.stdin.read()); print(d.get('session_id', ''))" 2>/dev/null || echo "")
fi
[ -z "$SESSION_ID" ] && SESSION_ID="${CLAUDE_SESSION_ID:-unknown}"

# transcript 集計が可能なら実行
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ] && [ -f "tools/cost-aggregate.py" ]; then
  AGG_JSON=$(python tools/cost-aggregate.py --transcript "$TRANSCRIPT_PATH" 2>/dev/null || echo "")
  if [ -n "$AGG_JSON" ]; then
    python - "$AGG_JSON" "$TIMESTAMP" "$SESSION_ID" "$BRANCH" "$COMMIT" <<'PYEOF' >> "$LOG_FILE"
import json, sys
agg = json.loads(sys.argv[1])
agg["timestamp"] = sys.argv[2]
agg["session_id"] = sys.argv[3]
agg["branch"] = sys.argv[4]
agg["commit"] = sys.argv[5]
print(json.dumps(agg, ensure_ascii=False))
PYEOF
    exit 0
  fi
fi

# フォールバック: 環境変数経由
INPUT_TOKENS="${CLAUDE_INPUT_TOKENS:-0}"
OUTPUT_TOKENS="${CLAUDE_OUTPUT_TOKENS:-0}"
CACHE_READ="${CLAUDE_CACHE_READ:-0}"
CACHE_CREATION="${CLAUDE_CACHE_CREATION:-0}"
COST_USD="${CLAUDE_COST_USD:-0}"
MODEL="${CLAUDE_MODEL:-unknown}"

cat <<JSON >> "$LOG_FILE"
{"timestamp":"$TIMESTAMP","session_id":"$SESSION_ID","branch":"$BRANCH","commit":"$COMMIT","input_tokens":$INPUT_TOKENS,"output_tokens":$OUTPUT_TOKENS,"cache_read":$CACHE_READ,"cache_creation":$CACHE_CREATION,"estimated_cost_usd":$COST_USD,"model":"$MODEL","source":"env-fallback"}
JSON

exit 0
