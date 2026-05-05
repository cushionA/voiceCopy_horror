#!/usr/bin/env python3
"""
cost-aggregate.py — Claude Code transcript JSONL からセッションコストを集計 (P15-T2 拡張)

stop-cost-log.sh から呼ばれる集計バックエンド。
transcript ファイルを 1 度だけ読み、input/output/cache tokens と推定コストを集約。

使い方:
    python tools/cost-aggregate.py --transcript /path/to/session-XXXX.jsonl
    # 出力: 1 行 JSON (timestamp/branch/commit は呼び出し側で merge)

設計: docs/reports/research/2026-04-25_claude-code-cost-hook.md
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

# Windows cp932 対策
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# Claude Code 公式料金 (2026-04 時点、$/MTok)
# ref: docs/reports/research/2026-04-25_claude-code-cost-hook.md
PRICING: dict[str, tuple[float, float, float, float]] = {
    # (input, output, cache_read, cache_creation)
    "claude-opus-4-7": (15.0, 75.0, 1.50, 18.75),
    "claude-opus-4-7[1m]": (15.0, 75.0, 1.50, 18.75),
    "claude-opus-4-6": (15.0, 75.0, 1.50, 18.75),
    "claude-sonnet-4-6": (3.0, 15.0, 0.30, 3.75),
    "claude-sonnet-4-5": (3.0, 15.0, 0.30, 3.75),
    "claude-haiku-4-5": (0.80, 4.0, 0.08, 1.0),
    "claude-haiku-4-5-20251001": (0.80, 4.0, 0.08, 1.0),
}


def aggregate(transcript_path: Path) -> dict:
    """transcript JSONL を 1 度走査して合計を取る"""
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read": 0,
        "cache_creation": 0,
    }
    model_counter: dict[str, int] = {}
    assistant_turns = 0

    if not transcript_path.is_file():
        return {**totals, "model": "unknown", "estimated_cost_usd": 0.0, "assistant_turns": 0}

    try:
        for line in transcript_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # assistant turn のみ usage を持つ
            if entry.get("type") != "assistant":
                continue

            msg = entry.get("message", {})
            usage = msg.get("usage", {}) or {}

            totals["input_tokens"] += int(usage.get("input_tokens", 0))
            totals["output_tokens"] += int(usage.get("output_tokens", 0))
            # 公式フィールド名 vs 旧フィールド名の両対応
            totals["cache_read"] += int(usage.get("cache_read_input_tokens", usage.get("cache_read", 0)))
            totals["cache_creation"] += int(usage.get("cache_creation_input_tokens", usage.get("cache_creation", 0)))

            model = msg.get("model")
            if model:
                model_counter[model] = model_counter.get(model, 0) + 1
            assistant_turns += 1
    except OSError:
        pass

    # 最頻 model を採用 (セッション中で混在する場合は多数決)
    primary_model = max(model_counter, key=model_counter.get) if model_counter else "unknown"

    cost = estimate_cost(totals, primary_model)

    return {
        **totals,
        "model": primary_model,
        "estimated_cost_usd": round(cost, 4),
        "assistant_turns": assistant_turns,
        "source": "transcript",
    }


def estimate_cost(totals: dict, model: str) -> float:
    """推定コスト (USD) を返す。料金表にないモデルは 0.0"""
    p = PRICING.get(model.lower())
    if not p:
        return 0.0
    input_cost = totals["input_tokens"] * p[0]
    output_cost = totals["output_tokens"] * p[1]
    cache_read_cost = totals["cache_read"] * p[2]
    cache_creation_cost = totals["cache_creation"] * p[3]
    return (input_cost + output_cost + cache_read_cost + cache_creation_cost) / 1_000_000


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--transcript", type=Path, required=True, help="Claude Code transcript JSONL のパス")
    args = parser.parse_args()

    result = aggregate(args.transcript)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
