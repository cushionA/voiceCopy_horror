#!/usr/bin/env python3
"""
mutation-report.py — Stryker JSON → Markdown サマリ変換 (Wave 5 Phase 14)

Stryker .NET の出力 JSON (mutation-report.json) を読み、人間レビュー用 Markdown を生成する。
mutation-runner.sh の Step 3 で呼ばれる。

Stryker JSON spec: https://github.com/stryker-mutator/mutation-testing-elements/blob/master/packages/report-schema/

使い方:
    python tools/mutation-report.py --input StrykerOutput/reports/mutation-report.json --output report.md
    python tools/mutation-report.py --input X.json --json     # 機械可読
    python tools/mutation-report.py --input X.json --threshold-only  # exit code で閾値判定

exit code:
    0  - mutation score >= 80%
    1  - mutation score < 60%
    2  - mutation score 60-79% (yellow)
    3  - 入力エラー
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path


if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def load_report(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def aggregate(report: dict) -> dict:
    """Stryker JSON から各種メトリクスを集計"""
    stats = {
        "killed": 0,
        "survived": 0,
        "no_coverage": 0,
        "timeout": 0,
        "compile_error": 0,
        "runtime_error": 0,
        "ignored": 0,
        "total": 0,
    }
    survived_list: list[dict] = []

    files = report.get("files", {})
    for fname, fdata in files.items():
        for mut in fdata.get("mutants", []):
            status = (mut.get("status") or "").lower()
            stats["total"] += 1
            key = {
                "killed": "killed",
                "survived": "survived",
                "nocoverage": "no_coverage",
                "no_coverage": "no_coverage",
                "timeout": "timeout",
                "compileerror": "compile_error",
                "compile_error": "compile_error",
                "runtimeerror": "runtime_error",
                "runtime_error": "runtime_error",
                "ignored": "ignored",
            }.get(status)
            if key:
                stats[key] += 1
            if status == "survived":
                survived_list.append({
                    "file": fname,
                    "line": mut.get("location", {}).get("start", {}).get("line"),
                    "mutator": mut.get("mutatorName") or mut.get("mutator"),
                    "original": mut.get("original") or mut.get("replacement", {}).get("original"),
                    "replacement": mut.get("replacement") if isinstance(mut.get("replacement"), str)
                                    else mut.get("replacement", {}).get("text", ""),
                })

    # mutation score の定義: killed / (killed + survived + timeout)
    # no_coverage / compile_error は除外 (Stryker 公式)
    detected = stats["killed"] + stats["timeout"]
    valid = detected + stats["survived"]
    score = (detected / valid * 100) if valid > 0 else 0.0
    stats["mutation_score"] = round(score, 2)
    stats["valid_mutants"] = valid

    return {"stats": stats, "survived": survived_list}


def threshold_judge(score: float) -> tuple[int, str]:
    if score >= 80:
        return 0, "green"
    if score >= 60:
        return 2, "yellow"
    return 1, "red"


def render_markdown(agg: dict, source: Path) -> str:
    s = agg["stats"]
    code, level = threshold_judge(s["mutation_score"])
    lines = [
        f"# Mutation Testing Report",
        "",
        f"**Source**: `{source}`",
        f"**Mutation score**: **{s['mutation_score']}%** ({level})",
        f"**Threshold**: green ≥80% / yellow 60-79% / red <60%",
        "",
        "## Stats",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| killed         | {s['killed']} |",
        f"| survived       | {s['survived']} |",
        f"| timeout        | {s['timeout']} |",
        f"| no_coverage    | {s['no_coverage']} |",
        f"| compile_error  | {s['compile_error']} |",
        f"| runtime_error  | {s['runtime_error']} |",
        f"| ignored        | {s['ignored']} |",
        f"| **total**      | **{s['total']}** |",
        f"| valid mutants  | {s['valid_mutants']} |",
        "",
    ]

    if agg["survived"]:
        lines.extend([
            f"## Survived mutants ({len(agg['survived'])})",
            "",
            "テスト追加でこれらを killed にする。優先度高い順に列挙。",
            "",
            "| file | line | mutator | original → replacement |",
            "|------|------|---------|----------------------|",
        ])
        for m in agg["survived"][:50]:  # 50 件まで
            orig = (m.get("original") or "")[:30].replace("\n", " ").replace("|", "\\|")
            repl = (m.get("replacement") or "")[:30].replace("\n", " ").replace("|", "\\|")
            lines.append(f"| `{m['file']}` | {m['line']} | {m['mutator']} | `{orig}` → `{repl}` |")
        if len(agg["survived"]) > 50:
            lines.append("")
            lines.append(f"... and {len(agg['survived']) - 50} more")
        lines.append("")

    lines.extend([
        "## 次のアクション",
        "",
        f"- {'green: ' if level == 'green' else 'yellow/red: '}",
    ])
    if level == "green":
        lines.append("  - 本番投入可。次の feature へ進める")
    elif level == "yellow":
        lines.append("  - レビューで survived mutants を確認、テスト追加を検討")
    else:
        lines.append("  - PR ブロック対象。survived mutants 全件をテストで kill する")

    lines.extend([
        "",
        "## 関連",
        "",
        "- `.claude/rules/mutation.md` (運用規約)",
        "- `stryker-config.json` (設定)",
        "- WAVE_PLAN.md L862-871 (Phase 14)",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Stryker JSON → Markdown (Wave 5 Phase 14)")
    parser.add_argument("--input", required=True, help="mutation-report.json path")
    parser.add_argument("--output", default="-", help="output Markdown path (default: stdout)")
    parser.add_argument("--json", action="store_true", help="機械可読 JSON 出力")
    parser.add_argument("--threshold-only", action="store_true",
                        help="exit code で閾値判定のみ (0=green / 2=yellow / 1=red)")
    args = parser.parse_args()

    inp = Path(args.input)
    try:
        report = load_report(inp)
    except FileNotFoundError:
        print(f"ERROR: input not found: {inp}", file=sys.stderr)
        return 3
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON: {e}", file=sys.stderr)
        return 3

    agg = aggregate(report)
    score = agg["stats"]["mutation_score"]
    code, level = threshold_judge(score)

    if args.threshold_only:
        print(f"score={score}% level={level}")
        return code

    if args.json:
        json.dump(agg, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        md = render_markdown(agg, inp)
        if args.output == "-":
            sys.stdout.write(md)
        else:
            Path(args.output).write_text(md, encoding="utf-8")
            print(f"[mutation-report] written: {args.output} (score={score}%, level={level})", file=sys.stderr)

    return code


if __name__ == "__main__":
    raise SystemExit(main())
