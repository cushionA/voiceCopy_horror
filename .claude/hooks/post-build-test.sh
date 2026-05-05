#!/usr/bin/env bash
# post-build-test.sh — post-build hook (P22-T3)
#
# Unity ビルド後に PlayMode テストを実行する。
#
# Backend 優先順序 (UNITY_CLI_BACKEND で明示制御可):
#   🥇 1. unicli (Editor 起動中 + UniCli インストール済み) — ロック競合なし、最軽量。本プロジェクト推奨
#   🥉 2. Unity batch mode (CI 等、Editor 未起動環境) — フルロード必要、低速。CI 専用
#
# 環境変数:
#   UNITY_CLI_BACKEND=unicli|batch|auto  (デフォルト: auto)
#   UNITY_PATH=<Unity.exe path>  (batch mode 用)
#   PLAYMODE_RESULTS=<XML 出力先>  (デフォルト: TestResults/post-build-playmode.xml)
#
# Wave 3 Phase 22 P22-T3 で導入。

set -uo pipefail

cd "$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0

BACKEND="${UNITY_CLI_BACKEND:-auto}"
RESULTS_PATH="${PLAYMODE_RESULTS:-TestResults/post-build-playmode.xml}"

mkdir -p "$(dirname "$RESULTS_PATH")"

run_via_unicli() {
  command -v unicli >/dev/null 2>&1 || return 1
  unicli check >/dev/null 2>&1 || return 1

  echo "=== post-build PlayMode test (UniCli) ==="
  unicli exec TestRunner.RunPlayMode --json --timeout 600000 || return 1
  return 0
}

run_via_batch() {
  UNITY_PATH="${UNITY_PATH:-C:/Program Files/Unity/Hub/Editor/6000.3.9f1/Editor/Unity.exe}"
  if [ ! -x "$UNITY_PATH" ]; then
    echo "WARN: Unity not found at $UNITY_PATH" >&2
    return 1
  fi

  echo "=== post-build PlayMode test (batch mode) ==="
  "$UNITY_PATH" \
    -batchmode \
    -projectPath . \
    -runTests \
    -testPlatform PlayMode \
    -testResults "$RESULTS_PATH" \
    -logFile - \
    || return 1
  return 0
}

case "$BACKEND" in
  unicli)
    run_via_unicli || { echo "ERROR: UniCli backend failed" >&2; exit 1; }
    ;;
  batch)
    run_via_batch || { echo "ERROR: batch backend failed" >&2; exit 1; }
    ;;
  auto|*)
    if run_via_unicli; then
      :
    elif run_via_batch; then
      :
    else
      echo "ERROR: no Unity backend available" >&2
      exit 1
    fi
    ;;
esac

echo "=== PlayMode tests passed ==="
exit 0
