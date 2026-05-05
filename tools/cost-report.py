#!/usr/bin/env python3
"""
cost-report.py — Claude Code セッションコスト集計ツール (Wave 4 Phase 15 P15-T1)

`.claude/cost-log.jsonl` に追記された /cost 出力スナップショットを集計し、
月次レポート + 閾値アラートを生成する。

ログフォーマット (1 行 1 JSON):
{
  "timestamp": "2026-04-25T10:33:18Z",
  "session_id": "<id>",
  "branch": "feature/...",
  "input_tokens": 12345,
  "output_tokens": 6789,
  "cache_read": 50000,
  "cache_creation": 1000,
  "estimated_cost_usd": 0.42,
  "model": "claude-opus-4-7"
}

使い方:
    python tools/cost-report.py --period month       # 当月集計
    python tools/cost-report.py --period 7d          # 直近 7 日
    python tools/cost-report.py --period all --format json
    python tools/cost-report.py --threshold 50.0     # $50 超過で exit 1

設計: Wave 4 Phase 15 P15-T1。
P15-T2 (Stop hook で /cost 捕捉) と連動して使う。
"""

from __future__ import annotations

import argparse
import datetime
import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# Windows cp932 対策
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def parse_period(value: str) -> datetime.datetime | None:
    """`7d` / `month` / `all` / ISO 日付 を datetime に変換 (None = 全期間)"""
    if value == "all":
        return None
    if value == "month":
        now = datetime.datetime.now(datetime.timezone.utc)
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    m = re.fullmatch(r"(\d+)([dwmy])", value)
    if m:
        num, unit = int(m.group(1)), m.group(2)
        delta_map = {
            "d": datetime.timedelta(days=num),
            "w": datetime.timedelta(weeks=num),
            "m": datetime.timedelta(days=num * 30),
            "y": datetime.timedelta(days=num * 365),
        }
        return datetime.datetime.now(datetime.timezone.utc) - delta_map[unit]
    try:
        return datetime.datetime.fromisoformat(value).replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        return None


def load_log(log_path: Path, since: datetime.datetime | None) -> list[dict]:
    """JSONL を読み込み、since 以降のエントリを返す"""
    if not log_path.is_file():
        return []
    rows = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts_str = entry.get("timestamp")
        if not ts_str:
            continue
        try:
            ts = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            continue
        if since is not None and ts < since:
            continue
        entry["_ts"] = ts
        rows.append(entry)
    return rows


def aggregate(rows: list[dict]) -> dict:
    """集計"""
    total = {
        "sessions": len(rows),
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read": 0,
        "cache_creation": 0,
        "estimated_cost_usd": 0.0,
    }
    by_model: defaultdict[str, dict] = defaultdict(lambda: {
        "sessions": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_cost_usd": 0.0,
    })
    by_branch: defaultdict[str, dict] = defaultdict(lambda: {
        "sessions": 0,
        "estimated_cost_usd": 0.0,
    })
    cost_per_day: defaultdict[str, float] = defaultdict(float)

    for r in rows:
        for k in ("input_tokens", "output_tokens", "cache_read", "cache_creation"):
            total[k] += int(r.get(k, 0))
        cost = float(r.get("estimated_cost_usd", 0.0))
        total["estimated_cost_usd"] += cost

        model = r.get("model", "unknown")
        by_model[model]["sessions"] += 1
        by_model[model]["input_tokens"] += int(r.get("input_tokens", 0))
        by_model[model]["output_tokens"] += int(r.get("output_tokens", 0))
        by_model[model]["estimated_cost_usd"] += cost

        branch = r.get("branch", "unknown")
        by_branch[branch]["sessions"] += 1
        by_branch[branch]["estimated_cost_usd"] += cost

        day = r["_ts"].date().isoformat()
        cost_per_day[day] += cost

    return {
        "total": total,
        "by_model": dict(by_model),
        "by_branch": dict(by_branch),
        "cost_per_day": dict(cost_per_day),
    }


def render_markdown(agg: dict, period: str) -> str:
    today = datetime.date.today().isoformat()
    t = agg["total"]
    lines = [
        f"# Cost Report — {today}",
        "",
        f"**集計範囲**: `{period}`",
        f"**セッション数**: {t['sessions']}",
        f"**総コスト (推定)**: ${t['estimated_cost_usd']:.2f}",
        "",
        "## トークン内訳",
        "",
        f"- input: {t['input_tokens']:,}",
        f"- output: {t['output_tokens']:,}",
        f"- cache_read: {t['cache_read']:,}",
        f"- cache_creation: {t['cache_creation']:,}",
    ]
    if t["sessions"] > 0:
        avg_cost = t["estimated_cost_usd"] / t["sessions"]
        lines.append(f"- 平均コスト/セッション: ${avg_cost:.2f}")
    lines.append("")

    if agg["by_model"]:
        lines.append("## モデル別")
        lines.append("")
        lines.append("| model | sessions | input | output | cost |")
        lines.append("|-------|---------:|------:|-------:|-----:|")
        for model, m in sorted(agg["by_model"].items(), key=lambda x: -x[1]["estimated_cost_usd"]):
            lines.append(f"| `{model}` | {m['sessions']} | {m['input_tokens']:,} | {m['output_tokens']:,} | ${m['estimated_cost_usd']:.2f} |")
        lines.append("")

    if agg["by_branch"]:
        lines.append("## ブランチ別 (上位 10)")
        lines.append("")
        lines.append("| branch | sessions | cost |")
        lines.append("|--------|---------:|-----:|")
        top = sorted(agg["by_branch"].items(), key=lambda x: -x[1]["estimated_cost_usd"])[:10]
        for branch, b in top:
            lines.append(f"| `{branch}` | {b['sessions']} | ${b['estimated_cost_usd']:.2f} |")
        lines.append("")

    if agg["cost_per_day"]:
        lines.append("## 日次コスト推移")
        lines.append("")
        lines.append("| day | cost |")
        lines.append("|-----|-----:|")
        for day in sorted(agg["cost_per_day"].keys()):
            lines.append(f"| {day} | ${agg['cost_per_day'][day]:.2f} |")
        lines.append("")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--log", type=Path, default=Path(".claude/cost-log.jsonl"))
    parser.add_argument("--period", default="month", help="期間 (例: 7d / month / 1y / all / ISO 日付)")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--threshold", type=float, default=None, help="この USD 額を総コストが超えたら exit 1")
    args = parser.parse_args()

    since = parse_period(args.period)
    rows = load_log(args.log, since)
    agg = aggregate(rows)

    if args.format == "json":
        # _ts は serialize できないので除外済 (集計時に消費)
        out = json.dumps({"period": args.period, "since": since.isoformat() if since else None, **agg}, indent=2, ensure_ascii=False, default=str)
    else:
        out = render_markdown(agg, args.period)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(out, encoding="utf-8")
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(out)

    if args.threshold is not None:
        if agg["total"]["estimated_cost_usd"] > args.threshold:
            print(f"\nALERT: cost ${agg['total']['estimated_cost_usd']:.2f} exceeds threshold ${args.threshold:.2f}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
