#!/bin/bash
# Stop hook: セッション終了時に handoff-note 作成を促す
# Phase 17 で導入。dream skill (24h 統合) と協調動作するよう設計。
#
# 動作:
#   - working tree に未コミット変更があるか or 直近 commit が現セッション中なら handoff 推奨を表示
#   - 過去 4 時間以内に handoff note が既に作成されていればスキップ
#   - dream skill の Stop hook と独立（dream は memory 統合、handoff は session スナップショット）

set -e

cd "$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0

# repo root が取れない / git 外で起動された場合は何もしない
[ -d ".git" ] || exit 0

# handoffs ディレクトリ未作成（Phase 17 未マージ環境）ならスキップ
HANDOFFS_DIR="docs/reports/handoffs"
[ -d "$HANDOFFS_DIR" ] || exit 0

# 現在ブランチ
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

# main / master では handoff 不要（基本作業ブランチではないため）
case "$CURRENT_BRANCH" in
  main|master|HEAD)
    exit 0
    ;;
esac

# 過去 4 時間以内に handoff note が既にあればスキップ
# find -mmin はクロスプラットフォーム互換問題があるので stat ベースで検出
RECENT_HANDOFF=$(find "$HANDOFFS_DIR" -maxdepth 1 -name "*.md" -not -name "README.md" -mmin -240 2>/dev/null | head -1 || true)
if [ -n "$RECENT_HANDOFF" ]; then
  exit 0
fi

# 直近 commit が 6 時間以内 or working tree に変更あり = アクティブセッション
RECENT_COMMIT_AGE=$(git log -1 --format=%ct 2>/dev/null || echo 0)
NOW=$(date +%s)
COMMIT_AGE_HOURS=$(( (NOW - RECENT_COMMIT_AGE) / 3600 ))

DIRTY=0
git diff --quiet 2>/dev/null || DIRTY=1
git diff --cached --quiet 2>/dev/null || DIRTY=1

if [ "$COMMIT_AGE_HOURS" -lt 6 ] || [ "$DIRTY" -eq 1 ]; then
  echo ""
  echo "[HOOK] セッション終了: ブランチ '$CURRENT_BRANCH' で作業中です。"
  echo "       次セッションへの引き継ぎを残すには:  /handoff-note <topic>"
  echo "       (registry: docs/reports/_registry.md / 詳細: .claude/skills/handoff-note/SKILL.md)"
fi

exit 0
