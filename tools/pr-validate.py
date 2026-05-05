#!/usr/bin/env python3
"""
PR body / comment の prompt injection 検出。

source of truth: .claude/rules/security-patterns.json

Usage:
    python tools/pr-validate.py --pr <PR_NUMBER>
    python tools/pr-validate.py --text "PR body text here"
    python tools/pr-validate.py --file path/to/text.txt

Exit codes:
    0 - 問題なし or warn のみ
    1 - block パターン検出（CI で失敗させる）
    2 - 実行エラー
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


# Windows 等で stdout が cp932 の場合の文字化け対策
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


REPO_ROOT = Path(__file__).resolve().parent.parent
PATTERNS_FILE = REPO_ROOT / ".claude" / "rules" / "security-patterns.json"


@dataclass
class Finding:
    pattern_id: str
    severity: str
    action: str
    description: str
    matched_text: str
    line_number: int | None

    def format(self) -> str:
        loc = f" (line {self.line_number})" if self.line_number else ""
        return (
            f"[{self.severity.upper()}][{self.action}] {self.pattern_id}{loc}: "
            f"{self.description}\n"
            f"  matched: {self.matched_text!r}"
        )


def load_patterns() -> dict:
    if not PATTERNS_FILE.exists():
        print(
            f"ERROR: patterns file not found: {PATTERNS_FILE}",
            file=sys.stderr,
        )
        sys.exit(2)
    return json.loads(PATTERNS_FILE.read_text(encoding="utf-8"))


def fetch_pr_body(pr_number: int) -> str:
    """gh CLI で PR body と comments を取得."""
    try:
        result = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--json", "body,comments"],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        print("ERROR: `gh` CLI not found. Install: https://cli.github.com/", file=sys.stderr)
        sys.exit(2)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: gh pr view failed: {e.stderr}", file=sys.stderr)
        sys.exit(2)

    data = json.loads(result.stdout)
    parts = [data.get("body") or ""]
    for comment in data.get("comments", []):
        parts.append(comment.get("body") or "")
    return "\n\n--- comment ---\n\n".join(parts)


def scan(
    text: str, pattern_groups: Iterable[tuple[str, list[dict]]]
) -> list[Finding]:
    findings: list[Finding] = []
    lines = text.splitlines() or [text]

    for group_name, patterns in pattern_groups:
        for pat in patterns:
            regex = re.compile(pat["pattern"])
            # 全文マッチを拾う（line 単位でも走査）
            for lineno, line in enumerate(lines, start=1):
                for m in regex.finditer(line):
                    findings.append(
                        Finding(
                            pattern_id=pat["id"],
                            severity=pat["severity"],
                            action=pat["action"],
                            description=pat["description"],
                            matched_text=m.group(0)[:120],
                            line_number=lineno,
                        )
                    )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="PR/text prompt injection validator")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--pr", type=int, help="GitHub PR number (uses gh CLI)")
    source.add_argument("--text", type=str, help="Raw text to scan")
    source.add_argument("--file", type=Path, help="File path to scan")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warn findings as errors (exit 1)",
    )
    args = parser.parse_args()

    patterns = load_patterns()

    if args.pr is not None:
        text = fetch_pr_body(args.pr)
        source_desc = f"PR #{args.pr}"
    elif args.text is not None:
        text = args.text
        source_desc = "--text argument"
    else:
        if not args.file.exists():
            print(f"ERROR: file not found: {args.file}", file=sys.stderr)
            return 2
        text = args.file.read_text(encoding="utf-8")
        source_desc = str(args.file)

    findings = scan(
        text,
        [
            ("prompt_injection", patterns.get("prompt_injection_patterns", [])),
            ("comment_and_control", patterns.get("comment_and_control_patterns", [])),
        ],
    )

    if not findings:
        print(f"[OK] No security findings in {source_desc}.")
        return 0

    print(f"[FOUND] {len(findings)} finding(s) in {source_desc}:\n")
    has_block = False
    has_warn = False
    for f in findings:
        print(f.format())
        if f.action == "block":
            has_block = True
        elif f.action == "warn":
            has_warn = True

    print()
    if has_block:
        print("=> BLOCK: at least one critical finding. PR must be reviewed manually.")
        return 1
    if has_warn and args.strict:
        print("=> STRICT: warn findings treated as errors.")
        return 1
    print("=> WARN only: review recommended but not blocking.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
