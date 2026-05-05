#!/bin/bash
# SessionStart hook: registry と直近 3 件の handoff note を提示
# Phase 17 で導入。

set -e

cd "$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
[ -d ".git" ] || exit 0

REGISTRY="docs/reports/_registry.md"
HANDOFFS_DIR="docs/reports/handoffs"

# Phase 17 未マージ環境ではスキップ
[ -f "$REGISTRY" ] || exit 0
[ -d "$HANDOFFS_DIR" ] || exit 0

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

# 直近 3 件の handoff note を抽出（README.md は除外）
RECENT=$(find "$HANDOFFS_DIR" -maxdepth 1 -name "*.md" -not -name "README.md" 2>/dev/null \
  | xargs -r ls -t 2>/dev/null \
  | head -3 || true)

if [ -z "$RECENT" ]; then
  # handoff entry が無い → 初期化メッセージのみ
  echo ""
  echo "[HOOK] セッション開始: docs/reports/ registry が初期化されています（Phase 17）。"
  echo "       現在ブランチ: $CURRENT_BRANCH"
  echo "       handoff note を作成するには:  /handoff-note"
  echo ""
  exit 0
fi

# handoff note の frontmatter から topic / status / branch を抽出して表示
echo ""
echo "[HOOK] セッション開始: 直近の handoff note があります"
echo "       現在ブランチ: $CURRENT_BRANCH"
echo "       詳細表示は:  /registry-check"
echo "       前回作業を再開:  /resume-handoff"
echo ""

# 最大 3 件、各 4 行のサマリ
COUNT=0
while IFS= read -r FILE; do
  [ -z "$FILE" ] && continue
  COUNT=$((COUNT + 1))
  BASENAME=$(basename "$FILE")

  # frontmatter 抽出（先頭〜2 個目の `---` まで）
  TOPIC=$(awk '/^---$/{c++; if(c==2)exit} c==1 && /^session_topic:/ {sub(/^session_topic:[[:space:]]*/,""); print; exit}' "$FILE" 2>/dev/null || echo "(no topic)")
  STATUS=$(awk '/^---$/{c++; if(c==2)exit} c==1 && /^status:/ {sub(/^status:[[:space:]]*/,""); print; exit}' "$FILE" 2>/dev/null || echo "(no status)")
  BRANCH=$(awk '/^---$/{c++; if(c==2)exit} c==1 && /^branch:/ {sub(/^branch:[[:space:]]*/,""); print; exit}' "$FILE" 2>/dev/null || echo "(no branch)")

  echo "  [$COUNT] $BASENAME"
  echo "      topic : $TOPIC"
  echo "      status: $STATUS / branch: $BRANCH"
done <<< "$RECENT"

echo ""
exit 0
