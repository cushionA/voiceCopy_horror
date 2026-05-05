#!/usr/bin/env bash
# Wave 5 Phase 7 — phase-boundary commit hook
#
# 用途:
#   pipeline-state.json の phase 遷移 / completedFeatures 更新を検出して
#   軽量 git tag を打つ。Effective Harnesses の "checkpoint" を機械的に作る。
#
# 起動経路:
#   PostToolUse(Write|Edit|MultiEdit) で post-edit-dispatch.sh から呼ばれる想定。
#   独立起動 (`bash .claude/hooks/phase-boundary-commit.sh`) でも動く。
#   stdin の Claude Code hook JSON を受け取るが、ファイルが designs/pipeline-state.json
#   でなければ即 exit 0 する設計 (副作用なし)。
#
# 動作:
#   1. stdin から file_path を取得し pipeline-state.json でなければ skip
#   2. 直近 commit 後の completedFeatures 増分を検出
#   3. 増分があれば tag wave5-checkpoint-{ts}-{feature} を annotated tag として作成
#      (commit はしない。あくまで checkpoint)
#
# 環境変数:
#   PHASE_HOOK_VERBOSE=1  詳細ログを stderr に出力
#   PHASE_HOOK_DRYRUN=1   tag を実際には打たない (CI / テスト用)

set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "")"
[ -z "$REPO_ROOT" ] && exit 0
cd "$REPO_ROOT"

VERBOSE="${PHASE_HOOK_VERBOSE:-0}"
DRYRUN="${PHASE_HOOK_DRYRUN:-0}"

log() {
    [ "$VERBOSE" = "1" ] && echo "[phase-boundary] $*" >&2
}

STDIN=$(cat 2>/dev/null || echo "")

# stdin が無い (手動起動) 場合は file_path を pipeline-state に固定して進める
if [ -z "$STDIN" ]; then
    FILE_PATH="designs/pipeline-state.json"
    log "no stdin, assuming manual invocation on $FILE_PATH"
else
    FILE_PATH=$(printf '%s' "$STDIN" | python -c \
        'import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get("tool_input", {}).get("file_path", ""))
except Exception:
    print("")' \
        2>/dev/null || echo "")
fi

# pipeline-state.json 以外は無視
case "$FILE_PATH" in
    *pipeline-state.json) ;;
    *)
        log "skip: file_path=$FILE_PATH is not pipeline-state.json"
        exit 0
        ;;
esac

STATE_FILE="designs/pipeline-state.json"
[ -f "$STATE_FILE" ] || { log "skip: $STATE_FILE missing"; exit 0; }

# 現状の completedFeatures を取得
CURRENT_COMPLETED=$(python -c '
import json
try:
    d = json.load(open("designs/pipeline-state.json", encoding="utf-8"))
    print("\n".join(d.get("completedFeatures", [])))
except Exception:
    pass
' 2>/dev/null || echo "")

# 前回のスナップショット
SNAPSHOT_DIR=".git/info"
SNAPSHOT_FILE="$SNAPSHOT_DIR/wave5-completed-features.txt"
mkdir -p "$SNAPSHOT_DIR"

if [ ! -f "$SNAPSHOT_FILE" ]; then
    # 初回: 現状を記録するだけ
    printf '%s\n' "$CURRENT_COMPLETED" > "$SNAPSHOT_FILE"
    log "snapshot initialized with $(echo "$CURRENT_COMPLETED" | grep -c . 2>/dev/null || echo 0) features"
    exit 0
fi

PREV_COMPLETED=$(cat "$SNAPSHOT_FILE" 2>/dev/null || echo "")

# 増分 (新規完了 feature)
NEW_FEATURES=$(comm -13 \
    <(printf '%s\n' "$PREV_COMPLETED" | sort -u) \
    <(printf '%s\n' "$CURRENT_COMPLETED" | sort -u) \
    2>/dev/null | grep -v '^$' || true)

if [ -z "$NEW_FEATURES" ]; then
    log "no new completed features"
    exit 0
fi

# 各新規 feature に対して checkpoint tag
TS=$(date -u +%Y%m%dT%H%M%SZ)
HEAD_HASH=$(git rev-parse HEAD 2>/dev/null || echo "")
[ -z "$HEAD_HASH" ] && exit 0

while IFS= read -r FEATURE; do
    [ -z "$FEATURE" ] && continue
    # tag 名はサニタイズ (英数字・ハイフンのみ)
    SLUG=$(echo "$FEATURE" | tr ' /' '--' | tr -cd 'A-Za-z0-9._-' | head -c 50)
    TAG="wave5-checkpoint-${TS}-${SLUG}"

    if [ "$DRYRUN" = "1" ]; then
        echo "[phase-boundary] DRYRUN tag $TAG -> $HEAD_HASH"
        continue
    fi

    # 既存 tag は skip
    if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null 2>&1; then
        log "tag $TAG already exists"
        continue
    fi

    git tag -a "$TAG" -m "Phase 7 checkpoint: feature \"$FEATURE\" completed" "$HEAD_HASH" 2>/dev/null \
        && echo "[phase-boundary] tagged $TAG @ $HEAD_HASH" \
        || log "tag $TAG creation failed (likely permission or conflict)"
done <<< "$NEW_FEATURES"

# スナップショットを更新
printf '%s\n' "$CURRENT_COMPLETED" > "$SNAPSHOT_FILE"

exit 0
