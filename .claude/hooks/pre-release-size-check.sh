#!/usr/bin/env bash
# pre-release-size-check.sh — pre-release hook (P22-T4)
#
# リリースビルド前に APK / IPA / exe のサイズを確認し、
# 直近のビルドサイズと比較して回帰検出する。
#
# 環境変数:
#   BUILD_OUTPUT_DIR=Builds/  (デフォルト)
#   SIZE_REGRESSION_THRESHOLD_PCT=10  (前回より 10% 増加で warn)
#
# Wave 3 Phase 22 P22-T4 で導入。本 PR ではスタブ実装。

set -uo pipefail

cd "$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0

BUILD_DIR="${BUILD_OUTPUT_DIR:-Builds}"
THRESHOLD="${SIZE_REGRESSION_THRESHOLD_PCT:-10}"
HISTORY_FILE=".claude/build-size-history.tsv"

[ -d "$BUILD_DIR" ] || {
  echo "WARN: Build directory $BUILD_DIR not found"
  exit 0
}

echo "=== pre-release size check ==="

# 各種ターゲットサイズ計測
for ext in apk ipa exe; do
  for f in "$BUILD_DIR"/*.$ext; do
    [ -f "$f" ] || continue
    SIZE=$(stat -c %s "$f" 2>/dev/null || stat -f %z "$f" 2>/dev/null || echo 0)
    SIZE_MB=$(awk "BEGIN{printf \"%.2f\", $SIZE/1024/1024}")
    echo "  $f: ${SIZE_MB} MB"

    # 前回サイズ取得 + 比較
    PREV_SIZE=$(grep -E "^$f\s" "$HISTORY_FILE" 2>/dev/null | tail -1 | awk '{print $2}' || echo 0)
    if [ "$PREV_SIZE" -gt 0 ]; then
      DELTA_PCT=$(awk "BEGIN{printf \"%.1f\", ($SIZE - $PREV_SIZE) * 100 / $PREV_SIZE}")
      if awk "BEGIN{exit !($DELTA_PCT > $THRESHOLD)}"; then
        echo "  WARN: ${DELTA_PCT}% size regression (threshold: ${THRESHOLD}%)"
      fi
    fi

    # 履歴追記
    echo -e "$f\t$SIZE\t$(date -Iseconds)" >> "$HISTORY_FILE"
  done
done

echo "=== size check done ==="
exit 0
