#!/usr/bin/env bash
# Wave 5 Phase 14 — Stryker .NET runner wrapper (MVP スケルトン)
#
# Stryker .NET の起動には Unity csproj の事前生成が必要なため、本スクリプトは:
#   1. Unity Editor を batch mode で起動して csproj 固定生成 (`-executeMethod`)
#   2. dotnet stryker を起動 (config: stryker-config.json)
#   3. 結果 JSON を tools/mutation-report.py で Markdown 化
#
# 現状: 手順を documented するスケルトン。実起動は将来検証で更新。
#
# 使い方:
#   bash tools/mutation-runner.sh --feature HpArmorLogic
#   MUTATION_TESTING=1 bash tools/mutation-runner.sh           # create-feature opt-in
#
# 環境変数:
#   UNITY_PATH       Unity Editor 実行ファイル path (default: C:/Program Files/Unity/Hub/Editor/6000.3.9f1/Editor/Unity.exe)
#   STRYKER_CONFIG   stryker-config.json path (default: ./stryker-config.json)
#   MUTATION_OUTPUT  Stryker output dir (default: ./StrykerOutput)
#   DRY_RUN=1        実起動せず想定コマンドだけ表示

set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

UNITY_PATH="${UNITY_PATH:-C:/Program Files/Unity/Hub/Editor/6000.3.9f1/Editor/Unity.exe}"
STRYKER_CONFIG="${STRYKER_CONFIG:-stryker-config.json}"
MUTATION_OUTPUT="${MUTATION_OUTPUT:-StrykerOutput}"
DRY_RUN="${DRY_RUN:-1}"  # MVP は default で dry-run

FEATURE=""
while [ $# -gt 0 ]; do
    case "$1" in
        --feature) FEATURE="$2"; shift 2 ;;
        --no-dry-run) DRY_RUN=0; shift ;;
        *) echo "[mutation-runner] unknown arg: $1" >&2; exit 2 ;;
    esac
done

echo "═══ Stryker .NET runner (Wave 5 Phase 14 MVP) ═══"
echo "  unity        : $UNITY_PATH"
echo "  config       : $STRYKER_CONFIG"
echo "  output       : $MUTATION_OUTPUT"
echo "  feature      : ${FEATURE:-(all)}"
echo "  dry_run      : $DRY_RUN"
echo ""

# 前提チェック
if [ ! -f "$STRYKER_CONFIG" ]; then
    echo "[mutation-runner] ERROR: $STRYKER_CONFIG not found" >&2
    exit 1
fi

# Step 1: Unity csproj 生成 (将来実装)
echo "[mutation-runner] Step 1: Unity csproj generation"
if [ "$DRY_RUN" = "1" ]; then
    echo "  (dry-run) would invoke:"
    echo "    \"$UNITY_PATH\" -batchmode -nographics -projectPath \"$REPO_ROOT\" -executeMethod CSProjectGen.GenerateAll -quit"
else
    echo "  TODO: implement when Unity csproj fixation strategy is verified"
    echo "  Skipping for now (manual Unity Editor open recommended)" >&2
fi
echo ""

# Step 2: Stryker .NET 起動 (将来実装)
echo "[mutation-runner] Step 2: Stryker .NET execution"
if ! command -v dotnet >/dev/null 2>&1; then
    echo "  WARN: dotnet not found in PATH. Install .NET SDK 6.0+ to run Stryker"
    if [ "$DRY_RUN" != "1" ]; then
        exit 1
    fi
fi
if [ "$DRY_RUN" = "1" ]; then
    echo "  (dry-run) would invoke:"
    echo "    dotnet tool install -g dotnet-stryker  # 初回のみ"
    if [ -n "$FEATURE" ]; then
        echo "    dotnet stryker -c \"$STRYKER_CONFIG\" --mutate \"**/$FEATURE.cs\""
    else
        echo "    dotnet stryker -c \"$STRYKER_CONFIG\""
    fi
else
    echo "  TODO: real execution when Unity-Stryker integration is verified"
fi
echo ""

# Step 3: 結果を Markdown 化
echo "[mutation-runner] Step 3: Report generation"
if [ -d "$MUTATION_OUTPUT/reports" ]; then
    REPORT_JSON=$(find "$MUTATION_OUTPUT/reports" -name "mutation-report.json" 2>/dev/null | head -1)
    if [ -n "$REPORT_JSON" ] && [ -f "tools/mutation-report.py" ]; then
        python tools/mutation-report.py --input "$REPORT_JSON" --output "$MUTATION_OUTPUT/summary.md" 2>&1 | head -10
    else
        echo "  no JSON report found, skipping summary"
    fi
else
    echo "  $MUTATION_OUTPUT/reports does not exist (Stryker not run yet)"
fi

echo ""
echo "[mutation-runner] done (DRY_RUN=$DRY_RUN). See .claude/rules/mutation.md for runbook."
exit 0
