#!/usr/bin/env python3
"""
consolidate-memory-extension.py — compound エントリと _drafts の統合・archive (Wave 5 Phase 24)

dream-skill (~/.claude/skills/dream) と棲み分け:
- dream-skill は ~/.claude/projects/<hash>/memory/ の MEMORY.md を統合する (ユーザーグローバル)
- 本ツールは docs/compound/ と docs/compound/_drafts/ の管理 (プロジェクトローカル)

動作:
  1. docs/compound/_drafts/ の 30 日以上経過 draft を warning 表示 (削除はしない)
  2. docs/compound/*.md の frontmatter を走査
  3. archived: true のエントリを docs/compound/_archived/{YYYY}/ に移動
  4. 6 ヶ月超のエントリで昇格無し → archive 候補として warning
  5. 同 outcome の重複検出 (frontmatter outcome フィールドの完全一致)

使い方:
    python tools/consolidate-memory-extension.py             # report-only
    python tools/consolidate-memory-extension.py --apply     # archive 実施
    python tools/consolidate-memory-extension.py --json      # 機械可読出力

ref: WAVE_PLAN.md L929 (P24-T5)
"""

from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


COMPOUND_DIR = Path("docs/compound")
DRAFTS_DIR = COMPOUND_DIR / "_drafts"
ARCHIVED_DIR = COMPOUND_DIR / "_archived"

DRAFT_STALE_DAYS = 30
ENTRY_STALE_DAYS = 180  # 6 ヶ月


def parse_frontmatter(text: str) -> dict:
    """YAML frontmatter を辞書化 (依存ライブラリなしの簡易パーサ)"""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm = {}
    for line in parts[1].splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_-]*)\s*:\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        # bool / 数値 / 文字列を簡易判定
        if val.lower() in ("true", "false"):
            fm[key] = (val.lower() == "true")
        elif val.startswith("[") and val.endswith("]"):
            fm[key] = [v.strip().strip("\"'") for v in val[1:-1].split(",") if v.strip()]
        else:
            fm[key] = val.strip("\"'")
    return fm


def collect_entries(dir_path: Path) -> list[tuple[Path, dict]]:
    """compound エントリを (path, frontmatter) のリストで返す"""
    out: list[tuple[Path, dict]] = []
    if not dir_path.is_dir():
        return out
    for p in sorted(dir_path.glob("*.md")):
        if p.name.startswith("_"):  # _template.md などは除外
            continue
        try:
            fm = parse_frontmatter(p.read_text(encoding="utf-8"))
        except OSError:
            continue
        out.append((p, fm))
    return out


def find_stale_drafts() -> list[tuple[Path, int]]:
    """_drafts/ 配下で 30 日以上経過したファイルを検出"""
    if not DRAFTS_DIR.is_dir():
        return []
    now = datetime.now(timezone.utc).timestamp()
    out: list[tuple[Path, int]] = []
    for p in sorted(DRAFTS_DIR.glob("*.md")):
        age_days = int((now - p.stat().st_mtime) // 86400)
        if age_days >= DRAFT_STALE_DAYS:
            out.append((p, age_days))
    return out


def find_archived_entries(entries: list[tuple[Path, dict]]) -> list[Path]:
    """frontmatter で archived: true のエントリ"""
    return [p for p, fm in entries if fm.get("archived") is True]


def find_stale_unpromoted(entries: list[tuple[Path, dict]]) -> list[tuple[Path, int]]:
    """6 ヶ月超で archived 印無しのエントリ (昇格忘れの候補)"""
    out: list[tuple[Path, int]] = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=ENTRY_STALE_DAYS)
    for p, fm in entries:
        if fm.get("archived") is True:
            continue
        date_str = fm.get("date", "")
        try:
            entry_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
        if entry_date < cutoff:
            age_days = (datetime.now(timezone.utc) - entry_date).days
            out.append((p, age_days))
    return out


def find_duplicate_outcomes(entries: list[tuple[Path, dict]]) -> dict[str, list[Path]]:
    """outcome フィールドが完全一致するエントリ群"""
    by_outcome: dict[str, list[Path]] = defaultdict(list)
    for p, fm in entries:
        outcome = (fm.get("outcome") or "").strip()
        if outcome and outcome.lower() not in ("", "tbd", "-"):
            by_outcome[outcome].append(p)
    return {k: v for k, v in by_outcome.items() if len(v) >= 2}


def archive_entry(path: Path) -> Path:
    """archived: true のエントリを _archived/{YYYY}/ に移動"""
    fm = parse_frontmatter(path.read_text(encoding="utf-8"))
    date_str = fm.get("date", "")
    year = "unknown"
    if re.match(r"^\d{4}-", date_str):
        year = date_str[:4]
    target_dir = ARCHIVED_DIR / year
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / path.name
    shutil.move(str(path), str(dest))
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description="compound エントリの統合・archive (Wave 5 Phase 24)")
    parser.add_argument("--apply", action="store_true", help="実際に archive 移動を実施")
    parser.add_argument("--json", action="store_true", help="機械可読 JSON で出力")
    args = parser.parse_args()

    entries = collect_entries(COMPOUND_DIR)
    stale_drafts = find_stale_drafts()
    archived_targets = find_archived_entries(entries)
    stale_unpromoted = find_stale_unpromoted(entries)
    duplicates = find_duplicate_outcomes(entries)

    report = {
        "summary": {
            "total_entries": len(entries),
            "stale_drafts": len(stale_drafts),
            "archive_targets": len(archived_targets),
            "stale_unpromoted": len(stale_unpromoted),
            "duplicate_outcomes": len(duplicates),
        },
        "stale_drafts": [{"path": str(p), "age_days": d} for p, d in stale_drafts],
        "archive_targets": [str(p) for p in archived_targets],
        "stale_unpromoted": [{"path": str(p), "age_days": d} for p, d in stale_unpromoted],
        "duplicate_outcomes": {k: [str(p) for p in v] for k, v in duplicates.items()},
    }

    if args.apply:
        archived = []
        for p in archived_targets:
            try:
                dest = archive_entry(p)
                archived.append({"from": str(p), "to": str(dest)})
            except Exception as e:
                archived.append({"from": str(p), "error": str(e)})
        report["archived_now"] = archived

    if args.json:
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 0

    s = report["summary"]
    print(f"compound entries (excluding _template/_drafts): {s['total_entries']}")
    print(f"  stale drafts (>={DRAFT_STALE_DAYS}d):       {s['stale_drafts']}")
    print(f"  archive targets (archived: true):          {s['archive_targets']}")
    print(f"  stale unpromoted (>={ENTRY_STALE_DAYS}d):   {s['stale_unpromoted']}")
    print(f"  duplicate outcomes:                        {s['duplicate_outcomes']}")

    if stale_drafts:
        print("\n## Stale drafts (review or delete):")
        for p, d in stale_drafts:
            print(f"  - {p}  ({d}d old)")
    if archived_targets:
        print("\n## Archive targets (use --apply to move):")
        for p in archived_targets:
            print(f"  - {p}")
    if stale_unpromoted:
        print("\n## Stale unpromoted (consider promotion or set archived: true):")
        for p, d in stale_unpromoted:
            print(f"  - {p}  ({d}d old)")
    if duplicates:
        print("\n## Duplicate outcomes:")
        for outcome, paths in duplicates.items():
            print(f"  outcome=\"{outcome}\":")
            for p in paths:
                print(f"    - {p}")

    if args.apply and report.get("archived_now"):
        print("\n## Moved:")
        for r in report["archived_now"]:
            if "error" in r:
                print(f"  ERR: {r['from']} -> {r['error']}")
            else:
                print(f"  {r['from']} -> {r['to']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
