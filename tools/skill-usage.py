#!/usr/bin/env python3
"""
skill-usage.py — Claude Code skill 使用頻度集計ツール (Wave 3 Phase 5 P5-T2)

直近 N 日の git log から skill 名（`/skill-name` 形式）の出現回数を集計し、
各 skill の最終更新日と合わせて判定する。

出力: docs/reports/analysis/YYYY-MM-DD_skill-usage.md

使い方:
    python tools/skill-usage.py --since 90d
    python tools/skill-usage.py --since 30d --format json
    python tools/skill-usage.py --since 90d --output docs/reports/analysis/2026-04-25_skill-usage.md
"""

from __future__ import annotations

import argparse
import datetime
import io
import json
import re
import subprocess
import sys
from pathlib import Path

# Windows cp932 環境でも Unicode を stdout / stderr に出せるようにする
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def list_skills(skills_dir: Path) -> list[str]:
    """SKILL.md を持つディレクトリ名を列挙"""
    if not skills_dir.is_dir():
        return []
    skills = []
    for child in sorted(skills_dir.iterdir()):
        if not child.is_dir():
            continue
        # archive と private (_) は除外
        if child.name.startswith(("_archive", "_two-layer", "_")):
            continue
        if (child / "SKILL.md").is_file():
            skills.append(child.name)
    return skills


def parse_since(value: str) -> str:
    """`90d` / `1y` / ISO 日付を git log の --since に渡せる形式に変換"""
    m = re.fullmatch(r"(\d+)([dwmy])", value)
    if m:
        num, unit = m.groups()
        unit_map = {"d": "days", "w": "weeks", "m": "months", "y": "years"}
        return f"{num} {unit_map[unit]} ago"
    # ISO 日付などはそのまま渡す（git log --since が解釈する）
    return value


def count_skill_in_git_log(skill: str, since: str) -> int:
    """git log --since=N --grep=/skill のヒット件数を返す"""
    pattern = f"/{skill}"
    cmd = [
        "git",
        "log",
        f"--since={since}",
        f"--grep={re.escape(pattern)}",
        "--oneline",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding="utf-8")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return 0
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    return len(lines)


def skill_last_modified(skills_dir: Path, skill: str) -> str:
    """`.claude/skills/<skill>/SKILL.md` の最終 git commit 日を返す（YYYY-MM-DD）"""
    skill_path = skills_dir / skill / "SKILL.md"
    if not skill_path.is_file():
        return "(missing)"
    cmd = [
        "git",
        "log",
        "-1",
        "--format=%cd",
        "--date=short",
        "--",
        str(skill_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding="utf-8")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "(error)"
    return result.stdout.strip() or "(uncommitted)"


def days_since(date_str: str) -> int | None:
    """YYYY-MM-DD から今日までの日数を計算。失敗時は None"""
    try:
        d = datetime.date.fromisoformat(date_str)
    except ValueError:
        return None
    return (datetime.date.today() - d).days


def classify(commit_count: int, last_modified: str, skill: str, deprecated_keywords: list[str]) -> str:
    """SKILL_LIFECYCLE.md の判定基準に従って区分を返す"""
    # description で deprecated チェックは外側で行う想定
    age = days_since(last_modified)
    if commit_count >= 1:
        return "active"
    if age is None:
        return "unknown"
    if age >= 180:
        return "candidate-archive"
    if age >= 90:
        return "stale"
    return "active"  # 90 日未満なら直近作成 / 更新でアクティブ扱い


def is_deprecated(skills_dir: Path, skill: str) -> bool:
    """SKILL.md の deprecated 判定 (P5-T2 改善版)

    判定優先度:
    1. frontmatter `deprecated: true` キー (明示宣言、最優先)
    2. frontmatter `description:` 行に deprecated キーワード
    3. 本文の見出し (`# Deprecated` 等) 行頭に deprecated キーワード

    本文中で deprecated パターンを「説明」している skill (writing-skills が
    judgment 区分として deprecated を語る等) を誤判定しないため、
    本文の自由記述からは検出しない (旧版の単純全文検索を廃止)。
    """
    skill_path = skills_dir / skill / "SKILL.md"
    if not skill_path.is_file():
        return False
    try:
        content = skill_path.read_text(encoding="utf-8")
    except OSError:
        return False

    # frontmatter 抽出 (先頭の `---` から次の `---` まで)
    frontmatter_match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if frontmatter_match:
        frontmatter = frontmatter_match.group(1)

        # 優先度 1: 明示的な deprecated: true キー
        if re.search(r"^deprecated\s*:\s*(true|yes)\s*$", frontmatter, re.MULTILINE | re.IGNORECASE):
            return True

        # 優先度 2: description 行に deprecated キーワード
        # (description は短い 1 行説明なので、ここに含まれていれば真の宣言)
        desc_match = re.search(r"^description\s*:\s*(.+)$", frontmatter, re.MULTILINE | re.IGNORECASE)
        if desc_match:
            desc = desc_match.group(1).lower()
            if any(kw in desc for kw in ("deprecated", "obsolete", "廃止", "非推奨")):
                return True

    # 優先度 3: 本文の H1/H2 見出し行頭に deprecated キーワード
    # `# Deprecated` / `## 廃止` 等の節タイトルを検出
    for line in content.splitlines():
        if re.match(r"^#{1,3}\s+", line):
            heading = line.lower()
            if any(kw in heading for kw in ("deprecated", "obsolete", "廃止", "非推奨")):
                return True

    return False


def collect(repo_root: Path, since: str) -> list[dict]:
    """各 skill のメトリクスを集める"""
    skills_dir = repo_root / ".claude" / "skills"
    skills = list_skills(skills_dir)
    rows = []
    for skill in skills:
        commit_count = count_skill_in_git_log(skill, since)
        last_modified = skill_last_modified(skills_dir, skill)
        deprecated = is_deprecated(skills_dir, skill)
        verdict = "deprecated" if deprecated else classify(commit_count, last_modified, skill, [])
        rows.append({
            "skill": skill,
            "commit_count": commit_count,
            "last_modified": last_modified,
            "verdict": verdict,
        })
    return rows


def render_markdown(rows: list[dict], since: str) -> str:
    today = datetime.date.today().isoformat()
    lines = [
        f"# Skill 使用頻度レポート — {today}",
        "",
        f"**集計期間**: 直近 `{since}` の git log 範囲",
        f"**対象**: `.claude/skills/` 配下の SKILL.md を持つ skill",
        f"**判定基準**: `docs/SKILL_LIFECYCLE.md` § Step 2",
        "",
        "## 結果",
        "",
        "| skill | コミット出現 | 最終更新 | 判定 |",
        "|-------|-------------|---------|------|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['skill']}` | {row['commit_count']} | {row['last_modified']} | {row['verdict']} |"
        )
    lines.append("")
    # サマリ
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    lines.append("## サマリ")
    lines.append("")
    lines.append("| 判定 | 件数 |")
    lines.append("|------|------|")
    for verdict in ["active", "stale", "candidate-archive", "deprecated", "unknown"]:
        if verdict in counts:
            lines.append(f"| {verdict} | {counts[verdict]} |")
    lines.append("")
    lines.append("## 次のアクション (`docs/SKILL_LIFECYCLE.md` § Step 3 参照)")
    lines.append("")
    lines.append("- **active**: 維持")
    lines.append("- **stale**: ユーザーと合議。直近で意識的に使った記憶があれば維持、無ければ archive 候補")
    lines.append("- **candidate-archive**: archive 推奨 (`git mv .claude/skills/<name> .claude/skills/_archive/<name>`)")
    lines.append("- **deprecated**: 削除推奨 (`git rm -rf .claude/skills/<name>`)")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--since", default="90d", help="集計範囲 (例: 90d / 30d / 6m / 1y、または ISO 日付)")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--output", type=Path, default=None, help="出力先 (省略時は stdout)")
    args = parser.parse_args()

    repo_root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], encoding="utf-8").strip())
    since = parse_since(args.since)

    rows = collect(repo_root, since)

    if args.format == "json":
        out = json.dumps({"since": since, "skills": rows}, indent=2, ensure_ascii=False)
    else:
        out = render_markdown(rows, since)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(out, encoding="utf-8")
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
