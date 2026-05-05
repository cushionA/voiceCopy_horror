"""
Playtest report analyzer using Claude Agent SDK.

Usage:
    python tools/analyze-playtest.py <report_json_path> [--stage-data <stage_data_path>]

Reads a PlaytestReport JSON, analyzes it with Claude, and updates:
  - designs/stage-design-notes.md (adjustment rules)
  - designs/gimmick-registry.json (successful patterns)
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

try:
    from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage
except ImportError:
    print("Error: claude-agent-sdk not installed.")
    print("Install with: pip install claude-agent-sdk")
    sys.exit(1)


SYSTEM_PROMPT = """\
You are a game stage difficulty analyst for a 2D side-scrolling action game.

You will be given a PlaytestReport JSON from an ML-Agents automated playtest.
Your job is to:

1. **Analyze the report** — identify bottlenecks, difficulty issues, and patterns.
2. **Update stage-design-notes.md** — append a new entry with:
   - Date and stage ID
   - Analysis summary (success rate, death hotspots, enemy difficulty, item collection)
   - Specific bottlenecks found
   - Recommended adjustments
   - Generalized rules for future stages
3. **Update gimmick-registry.json** — if successful gimmick patterns are found, add them.

## Analysis Guidelines

### Death Heatmap
- Cells with high death counts = bottleneck areas
- Convert grid coordinates back to approximate chunk/tile positions
- Look for clusters vs scattered deaths

### Enemy Stats
- Kill rate < 30% with 3+ encounters = enemy is too hard
- Kill rate > 90% = enemy is too easy
- Damaged player count relative to encounters = threat level

### Difficulty Assessment
- Compare Assessment.Rating with DesignedDifficulty
- Score < 40 with designed difficulty "normal" = needs to be easier
- Score > 80 with designed difficulty "hard" = needs to be harder

### Item Collection
- Collection rate < 20% = item is too hidden or inaccessible
- Collection rate = 100% = item placement is too obvious

## Output Format for stage-design-notes.md
```
## [YYYY-MM-DD] {stage_id} — MLプレイテスト分析

### 結果サマリー
- 成功率: X%
- 平均死亡数: X
- 平均進行率: X%
- 難易度評価: {rating} (スコア: X/100)

### ボトルネック
- [具体的な問題箇所と原因]

### 推奨調整
- [具体的な改善案]

### 一般化ルール
- [他ステージにも適用可能なルール]
```

Always write in Japanese. Be specific and actionable.
"""


async def analyze_report(report_path: str, stage_data_path: str | None = None):
    report_path = str(Path(report_path).resolve())

    prompt_parts = [
        f"Read the playtest report at: {report_path}",
        "Read the current designs/stage-design-notes.md",
        "Read the current designs/gimmick-registry.json",
    ]

    if stage_data_path:
        stage_data_path = str(Path(stage_data_path).resolve())
        prompt_parts.append(
            f"Also read the stage data at: {stage_data_path} for context"
        )

    prompt_parts.extend([
        "",
        "Analyze the playtest report and update both files accordingly.",
        "Append your analysis to stage-design-notes.md (don't overwrite existing content).",
        "Add any successful gimmick patterns to gimmick-registry.json.",
    ])

    prompt = "\n".join(prompt_parts)

    project_root = str(Path(__file__).resolve().parent.parent)

    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            cwd=project_root,
            model="claude-sonnet-4-6",
            allowed_tools=["Read", "Edit", "Write", "Glob", "Grep"],
            permission_mode="acceptEdits",
            system_prompt=SYSTEM_PROMPT,
            max_turns=20,
        ),
    ):
        if isinstance(message, ResultMessage):
            print("\n=== Analysis Complete ===")
            print(message.result)


def main():
    parser = argparse.ArgumentParser(description="Analyze playtest report with Claude Agent SDK")
    parser.add_argument("report", help="Path to PlaytestReport JSON file")
    parser.add_argument("--stage-data", help="Path to stage data file for context")
    args = parser.parse_args()

    if not Path(args.report).exists():
        print(f"Error: Report file not found: {args.report}")
        sys.exit(1)

    asyncio.run(analyze_report(args.report, args.stage_data))


if __name__ == "__main__":
    main()
