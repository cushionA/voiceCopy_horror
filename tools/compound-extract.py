#!/usr/bin/env python3
"""
compound-extract.py — session transcript から compound entry 候補を抽出 (Wave 5 Phase 24)

Stop hook (`stop-compound-extract.sh`) または手動 (`/compound-learn`) から呼ばれる。
session jsonl を読み、以下 3 パターンを検出して `docs/compound/_drafts/` に下書きを生成する:

  1. failure-correction  — tool error → 同種 tool 再実行 → 成功
  2. user-correction     — user メッセージに修正指示パターンが含まれる
  3. success-pattern     — 同種タスクが連続成功 (PR マージ・テスト全 pass 等)

設計原則:
- 副作用は draft の Write だけ。本ファイル `docs/compound/` には書かない (人間レビュー必須)
- 閾値以下 (assistant_turns < THRESHOLD) なら skip (動作なし、exit 0)
- 検出は heuristic ベース (LLM 呼出なし、軽量)

使い方:
    python tools/compound-extract.py --transcript /path/to/session-XXXX.jsonl
    python tools/compound-extract.py --transcript /path/to/session-XXXX.jsonl --threshold 5
    python tools/compound-extract.py --dry-run --transcript ...

出力:
- `docs/compound/_drafts/{YYYY-MM-DD}_{session-prefix}.md` (人間が `/compound-learn` で確認)

ref: WAVE_PLAN.md L921-930 (P24-T1〜T6)
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Windows cp932 対策
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


DEFAULT_THRESHOLD = 8  # assistant turn 数。これ未満なら学びが薄いので skip
DRAFTS_DIR = Path("docs/compound/_drafts")


# user message の修正指示パターン (日本語 + 英語)
USER_CORRECTION_PATTERNS = [
    r"いや[、、,。]",
    r"違う[、、,。 ]",
    r"そうじゃ",
    r"やめて",
    r"\bstop\b",
    r"\bdon't\b",
    r"\bnot that\b",
    r"逆\b",
    r"間違",
    r"修正して",
    r"\bredo\b",
    r"やり直",
    r"取り消",
    r"revert",
]

# 「正解」シグナル (これがあれば直前の手法は成功扱い)
SUCCESS_SIGNALS = [
    r"完了\b",
    r"OK[、。!]",
    r"完璧",
    r"良いね",
    r"いいね",
    r"ありがとう",
    r"\b(perfect|great|exactly|correct|nice work)\b",
    r"テスト全 ?pass",
    r"all tests? pass",
    r"PR (created|マージ|merged)",
]


def load_transcript(path: Path) -> list[dict]:
    """jsonl を list[dict] に展開"""
    if not path.is_file():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            out.append(json.loads(s))
        except json.JSONDecodeError:
            continue
    return out


def extract_text(entry: dict) -> str:
    """user/assistant entry から text content を抽出"""
    msg = entry.get("message", {})
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for c in content:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "text":
                parts.append(str(c.get("text", "")))
            elif c.get("type") == "tool_result":
                tr = c.get("content", "")
                if isinstance(tr, str):
                    parts.append(tr)
                elif isinstance(tr, list):
                    for sub in tr:
                        if isinstance(sub, dict) and sub.get("type") == "text":
                            parts.append(str(sub.get("text", "")))
        return "\n".join(parts)
    return ""


def detect_user_corrections(entries: list[dict]) -> list[dict]:
    """user メッセージから修正指示パターンを検出"""
    findings: list[dict] = []
    for i, e in enumerate(entries):
        if e.get("type") != "user":
            continue
        text = extract_text(e)
        if not text:
            continue
        for pat in USER_CORRECTION_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                findings.append({
                    "index": i,
                    "pattern": pat,
                    "snippet": text[:240].replace("\n", " "),
                })
                break  # 1 メッセージにつき 1 件
    return findings


def detect_failure_corrections(entries: list[dict]) -> list[dict]:
    """tool_result の is_error=True → 同種 tool 再実行 → success のパターン"""
    findings: list[dict] = []
    last_error_tool: str | None = None
    last_error_idx: int | None = None

    for i, e in enumerate(entries):
        msg = e.get("message", {})
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for c in content:
            if not isinstance(c, dict):
                continue
            # tool_use (assistant)
            if c.get("type") == "tool_use":
                tname = c.get("name", "")
                # 直前 error と同じ tool で再実行 → recovery
                if last_error_tool and tname == last_error_tool and last_error_idx is not None:
                    findings.append({
                        "error_index": last_error_idx,
                        "recovery_index": i,
                        "tool": tname,
                    })
                    last_error_tool = None
                    last_error_idx = None
            # tool_result error
            elif c.get("type") == "tool_result" and c.get("is_error"):
                last_error_tool = c.get("tool_use_id", "?")  # 厳密には tool_name 取得困難
                last_error_idx = i
    return findings


def detect_success_signals(entries: list[dict]) -> list[dict]:
    """user message の success signal を抽出 (今回も活きた成功パターン候補)"""
    findings: list[dict] = []
    for i, e in enumerate(entries):
        if e.get("type") != "user":
            continue
        text = extract_text(e)
        if not text:
            continue
        for pat in SUCCESS_SIGNALS:
            if re.search(pat, text, re.IGNORECASE):
                findings.append({
                    "index": i,
                    "pattern": pat,
                    "snippet": text[:240].replace("\n", " "),
                })
                break
    return findings


def count_assistant_turns(entries: list[dict]) -> int:
    return sum(1 for e in entries if e.get("type") == "assistant")


def slugify(text: str, maxlen: int = 40) -> str:
    s = re.sub(r"[^A-Za-z0-9-]", "-", text)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:maxlen] or "session"


def build_draft(
    *,
    session_id: str,
    transcript_path: Path,
    user_corrections: list[dict],
    failure_corrections: list[dict],
    success_signals: list[dict],
    assistant_turns: int,
) -> str:
    """Markdown draft を組み立てる (docs/compound/_template.md 形式に準拠)"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fm_lines = [
        "---",
        f"topic: (auto-extracted) session {session_id[:8]} learnings",
        f"date: {today}",
        "outcome: (要レビュー、人間が要約)",
        "related_pr: -",
        "files_affected: []",
        f"tags: [auto-extract, session-{session_id[:8]}]",
        "---",
        "",
        "## Context",
        "",
        f"compound-extract.py が session transcript ({transcript_path.name}) から自動抽出した候補。",
        f"assistant_turns={assistant_turns}, user_corrections={len(user_corrections)}, "
        f"failure_corrections={len(failure_corrections)}, success_signals={len(success_signals)}.",
        "",
        "**人間レビュー必須**: 以下の素材を読み、再利用可能な学びだけ Pattern セクションに昇格させること。",
        "",
        "## Pattern",
        "",
        "(レビューで埋める)",
        "",
        "## Examples (raw extract)",
        "",
    ]
    if user_corrections:
        fm_lines.append("### User corrections")
        fm_lines.append("")
        for f in user_corrections[:10]:
            fm_lines.append(f"- pattern `{f['pattern']}`  idx={f['index']}")
            fm_lines.append(f"  > {f['snippet']}")
        fm_lines.append("")
    if failure_corrections:
        fm_lines.append("### Failure → recovery")
        fm_lines.append("")
        for f in failure_corrections[:10]:
            fm_lines.append(
                f"- tool=`{f['tool']}` error@{f['error_index']} → recovery@{f['recovery_index']}"
            )
        fm_lines.append("")
    if success_signals:
        fm_lines.append("### Success signals")
        fm_lines.append("")
        for f in success_signals[:10]:
            fm_lines.append(f"- pattern `{f['pattern']}`  idx={f['index']}")
            fm_lines.append(f"  > {f['snippet']}")
        fm_lines.append("")
    fm_lines.extend([
        "## Anti-patterns",
        "",
        "(レビューで埋める。同 session で踏んだ罠があれば)",
        "",
        "## Related",
        "",
        f"- transcript: `{transcript_path}`",
        "- WAVE_PLAN.md L921-930 (Phase 24 P24)",
        "- `.claude/rules/compound-promotion.md` (昇格判定基準)",
    ])
    return "\n".join(fm_lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="compound entry 候補抽出 (Wave 5 Phase 24)")
    parser.add_argument("--transcript", required=True, help="transcript jsonl path")
    parser.add_argument("--session-id", default="", help="session id (省略時 transcript filename から推定)")
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                        help=f"assistant turn 数の最小閾値 (default={DEFAULT_THRESHOLD})")
    parser.add_argument("--dry-run", action="store_true", help="draft を書き出さず stdout に emit")
    parser.add_argument("--out-dir", default=str(DRAFTS_DIR), help="draft 出力先")
    args = parser.parse_args()

    tpath = Path(args.transcript)
    if not tpath.is_file():
        print(f"[compound-extract] transcript not found: {tpath}", file=sys.stderr)
        return 0  # hook 連携で fail させない

    entries = load_transcript(tpath)
    turns = count_assistant_turns(entries)

    if turns < args.threshold:
        print(f"[compound-extract] skip: assistant_turns={turns} < threshold={args.threshold}", file=sys.stderr)
        return 0

    user_corr = detect_user_corrections(entries)
    fail_corr = detect_failure_corrections(entries)
    success = detect_success_signals(entries)

    # 何も検出できなければ skip
    if not (user_corr or fail_corr or success):
        print(f"[compound-extract] skip: no patterns detected (turns={turns})", file=sys.stderr)
        return 0

    session_id = args.session_id or tpath.stem
    draft = build_draft(
        session_id=session_id,
        transcript_path=tpath,
        user_corrections=user_corr,
        failure_corrections=fail_corr,
        success_signals=success,
        assistant_turns=turns,
    )

    if args.dry_run:
        sys.stdout.write(draft)
        return 0

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = out_dir / f"{today}_{slugify(session_id)}.md"
    out_path.write_text(draft, encoding="utf-8")
    print(f"[compound-extract] draft written: {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
