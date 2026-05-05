#!/usr/bin/env python3
"""
SisterGame Unity C# 静的分析ツール。
source of truth: .claude/rules/lint-patterns.json

Usage:
    python tools/lint_check.py --hook-stdin --phase warn|error
    python tools/lint_check.py --file <path>
    python tools/lint_check.py --diff <base>..<head>

Exit codes:
    0 - ok / warning only / phase=warn は常に 0
    1 - error pattern 検出（phase=error 時のみ）
    2 - 実行エラー（patterns 読み込み失敗等）
    3 - 対象外ファイル（.cs 以外）でスキップ
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Windows UTF-8 対策
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent
PATTERNS_FILE = REPO_ROOT / ".claude" / "rules" / "lint-patterns.json"

# 言語 → 拡張子マッピング
LANG_EXT_MAP: dict[str, list[str]] = {
    "cs": [".cs"],
    "md": [".md"],
    "json": [".json"],
    "commit-msg": [],  # 特殊: ファイル拡張子で判定しない
}


@dataclass
class Finding:
    pattern_id: str
    severity: str
    file: str
    line: int
    matched: str
    message: str
    hint: str = ""
    source: str = ""

    def to_dict(self) -> dict:
        d: dict = {
            "pattern_id": self.pattern_id,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "matched": self.matched,
            "message": self.message,
        }
        if self.hint:
            d["hint"] = self.hint
        if self.source:
            d["source"] = self.source
        return d


def load_patterns() -> list[dict]:
    """lint-patterns.json を読み込む。"""
    if not PATTERNS_FILE.exists():
        print(
            f"ERROR: patterns file not found: {PATTERNS_FILE}",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        data = json.loads(PATTERNS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERROR: failed to parse patterns JSON: {e}", file=sys.stderr)
        sys.exit(2)
    return data.get("patterns", [])


def validate_patterns_schema(patterns: list[dict]) -> None:
    """
    jsonschema 非依存の最低限スキーマ検証。
    必須フィールド: id, severity, pattern, message
    id 形式: ^[A-Z]+-[A-Z]+-\\d{3}$
    severity: error | warning | info
    """
    id_re = re.compile(r"^[A-Z]+-[A-Z]+-\d{3}$")
    valid_severities = {"error", "warning", "info"}
    errors: list[str] = []
    for i, pat in enumerate(patterns):
        for req in ("id", "severity", "pattern", "message"):
            if req not in pat:
                errors.append(f"patterns[{i}]: missing required field '{req}'")
        pid = pat.get("id", "")
        if pid and not id_re.match(pid):
            errors.append(f"patterns[{i}] id={pid!r}: does not match ^[A-Z]+-[A-Z]+-\\d{{3}}$")
        sev = pat.get("severity", "")
        if sev and sev not in valid_severities:
            errors.append(f"patterns[{i}] id={pid!r}: invalid severity {sev!r}")
    if errors:
        for e in errors:
            print(f"SCHEMA ERROR: {e}", file=sys.stderr)
        sys.exit(2)


def normalize_repo_relative(file_path: str) -> str:
    """
    Windows / POSIX absolute path をリポジトリルート相対の posix 形式に正規化する。

    - `C:\\Users\\...\\SisterGame\\Assets\\MyAsset\\Foo.cs` → `Assets/MyAsset/Foo.cs`
    - `C:/Users/.../SisterGame/Assets/MyAsset/Foo.cs` → `Assets/MyAsset/Foo.cs`
    - `Assets/MyAsset/Foo.cs`（既に相対）→ そのまま
    - repo root 外の absolute path → backslash → slash 統一のみ

    PostToolUse hook 経由で Claude Code が渡す `tool_input.file_path` は
    通常 absolute path のため、scope/exclude glob (`Assets/MyAsset/**/*.cs`) と
    マッチさせる前にリポジトリルート相対へ落とす必要がある。
    """
    if not file_path:
        return file_path
    fp = file_path.replace("\\", "/")
    repo_str = str(REPO_ROOT).replace("\\", "/")
    fp_lower = fp.lower()
    repo_lower = repo_str.lower()
    if fp_lower.startswith(repo_lower + "/"):
        return fp[len(repo_str) + 1:]
    if fp_lower == repo_lower:
        return ""
    return fp


def path_matches_globs(file_path: str, globs: list[str]) -> bool:
    """
    fnmatch でパス glob 判定。いずれかにマッチすれば True。
    PurePath.match() は Python 3.12 未満で ** をサポートしないため fnmatch を使用。
    パスセパレータを / に正規化してから比較する。
    """
    if not globs:
        return True  # 空 = 制限なし（全体に適用）
    # Windows のバックスラッシュを / に統一
    normalized = file_path.replace("\\", "/")
    for glob in globs:
        norm_glob = glob.replace("\\", "/")
        if fnmatch.fnmatch(normalized, norm_glob):
            return True
    return False


def get_lang_for_file(file_path: str) -> str:
    """ファイルパスから language 文字列を返す。"""
    ext = Path(file_path).suffix.lower()
    for lang, exts in LANG_EXT_MAP.items():
        if ext in exts:
            return lang
    return ""


def is_lint_ignore_line(line: str, pattern_id: str) -> bool:
    """
    行末コメントに // lint:ignore-line:<ID> または // lint:ignore:<ID> がある場合 skip。
    """
    return (
        f"// lint:ignore-line:{pattern_id}" in line
        or f"// lint:ignore:{pattern_id}" in line
    )


def scan_text(
    text: str,
    file_path: str,
    patterns: list[dict],
    start_line: int = 1,
) -> list[Finding]:
    """
    text 内で patterns を検索し Finding リストを返す。
    start_line: 行番号オフセット（差分検査用）
    """
    findings: list[Finding] = []
    file_lang = get_lang_for_file(file_path)
    lines = text.splitlines()

    for pat in patterns:
        # language フィルタ
        pat_langs: list[str] = pat.get("language", [])
        if pat_langs and file_lang not in pat_langs:
            continue

        # scope フィルタ
        scope: list[str] = pat.get("scope", [])
        if scope and not path_matches_globs(file_path, scope):
            continue

        # exclude フィルタ
        exclude: list[str] = pat.get("exclude", [])
        if exclude and path_matches_globs(file_path, exclude):
            continue

        flags = re.MULTILINE
        if pat.get("multiline", False):
            flags |= re.DOTALL

        try:
            regex = re.compile(pat["pattern"], flags)
        except re.error as e:
            print(
                f"WARN: invalid regex in pattern {pat.get('id', '?')}: {e}",
                file=sys.stderr,
            )
            continue

        if pat.get("multiline", False):
            # マルチライン: 全体テキストに対してマッチ、行番号は match.start() から計算
            for m in regex.finditer(text):
                # マッチ開始位置の行番号を計算
                lineno = text[: m.start()].count("\n") + start_line
                matched_line = lines[lineno - start_line] if (lineno - start_line) < len(lines) else ""
                pid = pat["id"]
                if is_lint_ignore_line(matched_line, pid):
                    continue
                findings.append(
                    Finding(
                        pattern_id=pid,
                        severity=pat["severity"],
                        file=file_path,
                        line=lineno,
                        matched=m.group(0)[:120],
                        message=pat["message"],
                        hint=pat.get("hint", ""),
                        source=pat.get("source", ""),
                    )
                )
        else:
            # 行単位マッチ
            for lineno, line in enumerate(lines, start=start_line):
                pid = pat["id"]
                if is_lint_ignore_line(line, pid):
                    continue
                for m in regex.finditer(line):
                    findings.append(
                        Finding(
                            pattern_id=pid,
                            severity=pat["severity"],
                            file=file_path,
                            line=lineno,
                            matched=m.group(0)[:120],
                            message=pat["message"],
                            hint=pat.get("hint", ""),
                            source=pat.get("source", ""),
                        )
                    )

    return findings


def build_result(findings: list[Finding], phase: str) -> dict:
    """Finding リストから出力 dict を構築。"""
    summary = {"error": 0, "warning": 0, "info": 0}
    for f in findings:
        if f.severity in summary:
            summary[f.severity] += 1

    if summary["error"] > 0:
        status = "error"
    elif summary["warning"] > 0:
        status = "warning"
    else:
        status = "ok"

    return {
        "status": status,
        "findings": [f.to_dict() for f in findings],
        "summary": summary,
    }


def handle_hook_stdin(phase: str, patterns: list[dict]) -> int:
    """
    PostToolUse hook モード。
    stdin から Claude Code hook JSON を受け取り検査する。
    """
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return 0
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: failed to parse hook stdin JSON: {e}", file=sys.stderr)
        return 2

    tool_name: str = data.get("tool_name", "")
    tool_input: dict = data.get("tool_input", {})
    raw_file_path: str = tool_input.get("file_path", "")
    # Windows absolute path / POSIX absolute path → repo root 相対へ
    file_path: str = normalize_repo_relative(raw_file_path)

    # .cs ファイル以外はスキップ
    if not file_path.endswith(".cs"):
        return 3

    # ツール種別ごとに検査対象テキストを決定
    texts_to_scan: list[tuple[str, int]] = []  # (text, start_line)

    if tool_name == "Write":
        content: str = tool_input.get("content", "")
        texts_to_scan.append((content, 1))

    elif tool_name == "Edit":
        new_string: str = tool_input.get("new_string", "")
        texts_to_scan.append((new_string, 1))

    elif tool_name == "MultiEdit":
        edits = tool_input.get("edits", [])
        for edit in edits:
            ns: str = edit.get("new_string", "")
            if ns:
                texts_to_scan.append((ns, 1))

    all_findings: list[Finding] = []
    for text, start_line in texts_to_scan:
        all_findings.extend(scan_text(text, file_path, patterns, start_line=start_line))

    result = build_result(all_findings, phase)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if all_findings:
        print(
            f"\n[LINT] {file_path}: {result['summary']['error']} errors, "
            f"{result['summary']['warning']} warnings, "
            f"{result['summary']['info']} infos",
            file=sys.stderr,
        )
        for f in all_findings:
            sev_label = f.severity.upper()
            hint_str = f"  hint: {f.hint}" if f.hint else ""
            print(
                f"  [{sev_label}] {f.pattern_id} line {f.line}: {f.message}\n"
                f"    matched: {f.matched!r}{hint_str}",
                file=sys.stderr,
            )

    if phase == "error" and result["status"] == "error":
        return 1
    return 0


def handle_file(file_path_str: str, phase: str, patterns: list[dict]) -> int:
    """単一ファイル検査モード。"""
    file_path = Path(file_path_str)
    if not file_path.exists():
        print(f"ERROR: file not found: {file_path}", file=sys.stderr)
        return 2

    ext = file_path.suffix.lower()
    if ext not in (".cs", ".md", ".json"):
        return 3  # 対象外

    text = file_path.read_text(encoding="utf-8", errors="replace")
    # scope/exclude 判定用に absolute path を repo root 相対へ正規化
    scan_path = normalize_repo_relative(str(file_path.resolve()))
    findings = scan_text(text, scan_path, patterns)
    result = build_result(findings, phase)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if phase == "error" and result["status"] == "error":
        return 1
    return 0


def handle_diff(diff_spec: str, phase: str, patterns: list[dict]) -> int:
    """
    git diff <base>..<head> の追加行を検査するモード。
    PR レビュー用。
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--unified=0", diff_spec, "--", "*.cs"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        diff_output = result.stdout
    except Exception as e:
        print(f"ERROR: git diff failed: {e}", file=sys.stderr)
        return 2

    # diff を解析して追加行を抽出
    all_findings: list[Finding] = []
    current_file: Optional[str] = None
    current_new_line: int = 0
    added_lines: list[str] = []
    added_start: int = 0

    for line in diff_output.splitlines():
        if line.startswith("+++ b/"):
            if current_file and added_lines:
                text = "\n".join(added_lines)
                all_findings.extend(
                    scan_text(text, current_file, patterns, start_line=added_start)
                )
            current_file = line[6:]
            added_lines = []
            added_start = 0

        elif line.startswith("@@ "):
            # @@ -old_start,old_count +new_start,new_count @@
            if current_file and added_lines:
                text = "\n".join(added_lines)
                all_findings.extend(
                    scan_text(text, current_file, patterns, start_line=added_start)
                )
                added_lines = []

            m = re.search(r"\+(\d+)", line)
            if m:
                current_new_line = int(m.group(1))
                added_start = current_new_line
            else:
                current_new_line = 1
                added_start = 1

        elif line.startswith("+") and not line.startswith("+++"):
            added_lines.append(line[1:])
            current_new_line += 1

    # 残りを処理
    if current_file and added_lines:
        text = "\n".join(added_lines)
        all_findings.extend(
            scan_text(text, current_file, patterns, start_line=added_start)
        )

    res = build_result(all_findings, phase)
    print(json.dumps(res, ensure_ascii=False, indent=2))

    if phase == "error" and res["status"] == "error":
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="SisterGame Unity C# 静的分析ツール")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--hook-stdin",
        action="store_true",
        help="PostToolUse hook モード（stdin から Claude Code hook JSON を受信）",
    )
    mode.add_argument("--file", type=str, help="単一ファイル検査")
    mode.add_argument("--diff", type=str, help="git diff 検査（例: main..HEAD）")
    parser.add_argument(
        "--phase",
        choices=["warn", "error"],
        default="warn",
        help="warn=常に exit 0 / error=error 検出で exit 1",
    )
    args = parser.parse_args()

    patterns = load_patterns()
    validate_patterns_schema(patterns)

    if args.hook_stdin:
        return handle_hook_stdin(args.phase, patterns)
    elif args.file:
        return handle_file(args.file, args.phase, patterns)
    else:
        return handle_diff(args.diff, args.phase, patterns)


if __name__ == "__main__":
    sys.exit(main())
