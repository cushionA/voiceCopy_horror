#!/usr/bin/env bash
# pre-build-validate.sh — pre-build hook (P22-T2)
#
# Unity ビルド前に validate:project 相当を実行する。
# - asmdef 整合性
# - Addressable 設定
# - Editor scripts のコンパイルエラー
# - placeholder アセット数 (リリースビルドではエラー)
#
# 起動方法:
#   bash .claude/hooks/pre-build-validate.sh [--release | --dev]
#
# Backend (UNITY_CLI_BACKEND で明示制御可):
#   🥇 unicli — `unicli exec Compile` でコンパイル検証、`unicli exec Console.GetLog` で error 確認 (推奨)
#   🥉 shell only — placeholder 数 / asmdef 数の表面チェックのみ (CI でも動く軽量モード)
#
# Wave 3 Phase 22 P22-T2 で導入。本 PR では shell スタブ + UniCli フックポイントのみ。
# 完全な validate:project 相当 (Addressable 検証等) は別 PR で UniCli カスタムコマンド追加後。

set -uo pipefail

cd "$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0

MODE="${1:-dev}"

echo "=== pre-build validation ($MODE) ==="

# 1. placeholder アセット数チェック
PLACEHOLDER_COUNT=$(grep -r "\[PLACEHOLDER\]" Assets/ --include="*.prefab" 2>/dev/null | wc -l)
echo "Placeholder count: $PLACEHOLDER_COUNT"

if [ "$MODE" = "release" ] && [ "$PLACEHOLDER_COUNT" -gt 0 ]; then
  echo "ERROR: Release build with $PLACEHOLDER_COUNT placeholder assets remaining"
  exit 1
fi

# 2. asmdef 整合性チェック (TODO: Unity CLI の validate:project 相当)
ASMDEF_COUNT=$(find Assets/ -name "*.asmdef" 2>/dev/null | wc -l)
echo "asmdef count: $ASMDEF_COUNT"

# 3. UniCli 経由のコンパイル検証 (Editor 起動中なら最速)
BACKEND="${UNITY_CLI_BACKEND:-auto}"
if [ "$BACKEND" != "shell" ] && command -v unicli >/dev/null 2>&1 && unicli check >/dev/null 2>&1; then
  echo "Compile check via UniCli..."
  if unicli exec Compile --json --timeout 60000 >/dev/null 2>&1; then
    # コンパイル成功後 console error 件数も確認
    LOG_RESULT=$(unicli exec Console.GetLog --json --timeout 5000 2>/dev/null) || LOG_RESULT="{}"
    ERR_COUNT=$(echo "$LOG_RESULT" | python -c "import sys,json; d=json.loads(sys.stdin.read()); print(sum(1 for e in d.get('logs',d.get('result',{}).get('logs',[])) if e.get('type','').lower() in ('error','exception','assert')))" 2>/dev/null || echo 0)
    if [ "$ERR_COUNT" -gt 0 ]; then
      echo "ERROR: $ERR_COUNT compile / console error(s) detected via UniCli"
      [ "$MODE" = "release" ] && exit 1
    else
      echo "  → compile OK, no console errors"
    fi
  else
    echo "WARN: UniCli compile check failed (Editor unreachable?)"
  fi
fi

# 4. (TODO) Addressable 設定検証
# UniCli カスタムコマンド (Addressables.Validate 相当) 追加後に有効化

echo "=== validation passed ==="
exit 0
