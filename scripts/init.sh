#!/usr/bin/env bash
# Wave 5 Phase 7 — Effective Harnesses セッション初期化スクリプト
#
# 用途:
#   - 新規 Claude Code セッション開始時、または /rewind "code only" 復元後に
#     現在の状態 (pipeline-state.json + feature-db summary + 直近 handoff +
#     claude-progress.txt) を 1 画面に集約表示する。
#   - SessionStart hook は registry-only なので、本スクリプトは "そのセッションで
#     何をやるか" の作業文脈の復元を担う。
#
# 起動方法:
#   bash scripts/init.sh                # 全セクション表示
#   bash scripts/init.sh --short        # 圧縮表示 (claude-progress.txt のみ)
#   bash scripts/init.sh --json         # 機械可読出力 (pipeline-state.json をそのまま emit)
#
# 設計:
#   - 副作用なし (read-only)
#   - jq に依存しない (Python で JSON パース)
#   - feature-db.py が無い環境でも動く (skip warning のみ)

set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

MODE="full"
case "${1:-}" in
    --short) MODE="short" ;;
    --json)  MODE="json" ;;
    "")      MODE="full" ;;
    *)       echo "[init.sh] unknown arg: $1 (use --short, --json, or none)" >&2; exit 2 ;;
esac

# ── pipeline-state.json ─────────────────────────────────────────
STATE_FILE="designs/pipeline-state.json"

if [ "$MODE" = "json" ]; then
    if [ -f "$STATE_FILE" ]; then
        cat "$STATE_FILE"
    else
        echo '{"phase":"idle","error":"pipeline-state.json not found"}'
    fi
    exit 0
fi

if [ ! -f "$STATE_FILE" ]; then
    echo "[init.sh] WARN: $STATE_FILE not found. Skipping state summary."
else
    echo "═══ pipeline-state.json ═══"
    python - <<'PYEOF'
import json, sys
try:
    d = json.load(open("designs/pipeline-state.json", encoding="utf-8"))
except Exception as e:
    print(f"  parse error: {e}")
    sys.exit(0)

def g(k, default="-"):
    v = d.get(k, default)
    return default if v is None else v

print(f"  phase           : {g('phase', '?')}")
print(f"  currentSection  : {g('currentSection', '?')} / {g('totalSections', '?')}")
print(f"  currentBranch   : {g('currentBranch', '-')}")
done = d.get("completedFeatures", [])
pending = d.get("pendingFeatures", [])
skipped = d.get("skippedFeatures", [])
print(f"  features        : done={len(done)} pending={len(pending)} skipped={len(skipped)}")
reqs = d.get("verifiableRequirements", [])
if reqs:
    by_status = {}
    for r in reqs:
        s = r.get("status", "?")
        by_status[s] = by_status.get(s, 0) + 1
    summary = " ".join(f"{k}={v}" for k, v in sorted(by_status.items()))
    print(f"  requirements    : total={len(reqs)} {summary}")
else:
    print(f"  requirements    : (none)")
if d.get("awaitingHumanReview", False):
    print(f"  awaitingHumanReview = true (Phase 23 gate)")
print(f"  lastAction      : {g('lastAction')}")
print(f"  lastUpdated     : {g('lastUpdated')}")
PYEOF
    echo ""
fi

# ── claude-progress.txt ─────────────────────────────────────────
PROGRESS_FILE="designs/claude-progress.txt"
if [ -f "$PROGRESS_FILE" ]; then
    echo "═══ claude-progress.txt (Effective Harnesses 進捗集約) ═══"
    cat "$PROGRESS_FILE"
    echo ""
fi

# short モードはここまで
[ "$MODE" = "short" ] && exit 0

# ── feature-db summary ─────────────────────────────────────────
if [ -x "$(command -v python)" ] && [ -f "tools/feature-db.py" ]; then
    echo "═══ feature-db summary ═══"
    python tools/feature-db.py summary 2>&1 | head -30 || true
    echo ""
fi

# ── 直近 handoff note ─────────────────────────────────────────
HANDOFFS_DIR="docs/reports/handoffs"
if [ -d "$HANDOFFS_DIR" ]; then
    echo "═══ 直近 handoff (最新 1 件) ═══"
    LATEST=$(find "$HANDOFFS_DIR" -maxdepth 1 -name "*.md" -not -name "README.md" 2>/dev/null \
        | xargs -r ls -t 2>/dev/null \
        | head -1 || true)
    if [ -n "$LATEST" ]; then
        echo "  file: $LATEST"
        # frontmatter からトピックと status を抽出
        awk '/^---$/{c++; if(c==2)exit} c==1 && /^(date|session_topic|status|branch|related_pr):/' "$LATEST" \
            | sed 's/^/  /'
        echo "  詳細復元: /resume-handoff"
    else
        echo "  (no handoff entries — /handoff-note でセッション末に作成)"
    fi
    echo ""
fi

# ── git 状態 ─────────────────────────────────────────
echo "═══ git ═══"
echo "  branch  : $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
echo "  HEAD    : $(git log --oneline -1 2>/dev/null || echo unknown)"
DIRTY=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
echo "  changes : $DIRTY files modified/untracked"
echo ""

echo "[init.sh] 完了。次の作業は claude-progress.txt と handoff の指示に従ってください。"
