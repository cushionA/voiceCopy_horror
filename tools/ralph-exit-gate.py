#!/usr/bin/env python3
"""
ralph-exit-gate.py — Ralph ループの dual-condition exit gate (Wave 5 Phase 18)

Ralph パターン (frankbria/ralph-claude-code 参考) の終了判定。
2 つ以上の独立条件が満たされたら exit ("dual condition" の名の由来)。

判定条件:
  1. MAX_TEST_LOOPS = 3        テスト失敗の連続回数
  2. DONE_SIGNALS = 2           feature-db で全完了 + テスト全 pass
  3. TEST_PCT = 30              テストカバレッジ上昇率 (30% 以上で停止候補)

使い方:
    # ループ前に呼び、exit code で継続/停止判定
    python tools/ralph-exit-gate.py --check
    # exit 0 = 継続 / exit 1 = 終了 / exit 2 = blocker

    # 状態を更新
    python tools/ralph-exit-gate.py --signal test-failed
    python tools/ralph-exit-gate.py --signal feature-completed
    python tools/ralph-exit-gate.py --reset

状態は `.claude/ralph-state.json` に保持。
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


STATE_FILE = Path(".claude/ralph-state.json")
PIPELINE_STATE = Path("designs/pipeline-state.json")

DEFAULT_MAX_TEST_LOOPS = 3
DEFAULT_DONE_SIGNALS = 2
DEFAULT_TEST_PCT = 30


def load_state() -> dict:
    if not STATE_FILE.is_file():
        return {
            "consecutive_test_failures": 0,
            "feature_completed_count": 0,
            "test_pass_count": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "started_test_count": 0,
            "current_test_count": 0,
            "iterations": 0,
        }
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(s: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def pipeline_summary() -> dict:
    if not PIPELINE_STATE.is_file():
        return {"completed": 0, "pending": 0, "phase": "unknown"}
    p = json.loads(PIPELINE_STATE.read_text(encoding="utf-8"))
    return {
        "completed": len(p.get("completedFeatures", [])),
        "pending": len(p.get("pendingFeatures", [])),
        "phase": p.get("phase", "unknown"),
        "blocked": p.get("phase") == "blocked",
    }


def check(state: dict, max_test_loops: int, done_signals: int, test_pct: int) -> tuple[int, list[str]]:
    """
    return: (exit_code, reasons)
      exit 0 = continue
      exit 1 = stop (success or limit)
      exit 2 = blocker
    """
    reasons: list[str] = []
    triggered = 0
    pipe = pipeline_summary()

    # 条件 1: 連続テスト失敗
    if state["consecutive_test_failures"] >= max_test_loops:
        reasons.append(f"consecutive_test_failures={state['consecutive_test_failures']} >= {max_test_loops} (blocker)")
        return 2, reasons

    # 条件 2: blocked phase
    if pipe.get("blocked"):
        reasons.append(f"pipeline phase=blocked")
        return 2, reasons

    # 条件 3: 全 feature 完了 (DONE シグナル候補 1)
    if pipe["pending"] == 0 and pipe["completed"] > 0:
        triggered += 1
        reasons.append(f"all features completed ({pipe['completed']} done, 0 pending)")

    # 条件 4: テストカバレッジ上昇率
    started = max(state.get("started_test_count", 0), 1)
    delta_pct = (state.get("current_test_count", 0) - started) / started * 100
    if delta_pct >= test_pct:
        triggered += 1
        reasons.append(f"test count delta = {delta_pct:.1f}% >= {test_pct}%")

    # 条件 5: feature 完了数が高水準 (DONE シグナル候補 2)
    if state.get("feature_completed_count", 0) >= done_signals:
        triggered += 1
        reasons.append(f"feature_completed_count={state['feature_completed_count']} >= {done_signals}")

    if triggered >= 2:
        reasons.append(f"DUAL CONDITION MET: {triggered} signals triggered")
        return 1, reasons

    reasons.append(f"continue (signals triggered: {triggered}, need 2)")
    return 0, reasons


def main() -> int:
    parser = argparse.ArgumentParser(description="Ralph dual-condition exit gate (Wave 5 Phase 18)")
    parser.add_argument("--check", action="store_true", help="判定のみ (state は変更しない)")
    parser.add_argument("--signal", choices=[
        "test-failed", "test-passed", "feature-completed", "iteration"
    ], help="状態を 1 単位更新")
    parser.add_argument("--reset", action="store_true", help="state をリセット (loop 開始時)")
    parser.add_argument("--max-test-loops", type=int, default=DEFAULT_MAX_TEST_LOOPS)
    parser.add_argument("--done-signals", type=int, default=DEFAULT_DONE_SIGNALS)
    parser.add_argument("--test-pct", type=int, default=DEFAULT_TEST_PCT)
    parser.add_argument("--current-test-count", type=int, default=None,
                        help="--signal test-passed 時に現在のテスト数を指定")
    parser.add_argument("--json", action="store_true", help="state を JSON で stdout に出力")
    args = parser.parse_args()

    if args.reset:
        state = {
            "consecutive_test_failures": 0,
            "feature_completed_count": 0,
            "test_pass_count": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "started_test_count": args.current_test_count or 0,
            "current_test_count": args.current_test_count or 0,
            "iterations": 0,
        }
        save_state(state)
        print(f"[ralph-gate] state reset")
        return 0

    state = load_state()

    if args.signal:
        if args.signal == "test-failed":
            state["consecutive_test_failures"] += 1
        elif args.signal == "test-passed":
            state["consecutive_test_failures"] = 0
            state["test_pass_count"] += 1
            if args.current_test_count is not None:
                state["current_test_count"] = args.current_test_count
        elif args.signal == "feature-completed":
            state["feature_completed_count"] += 1
            state["consecutive_test_failures"] = 0
        elif args.signal == "iteration":
            state["iterations"] += 1
        save_state(state)
        print(f"[ralph-gate] signal {args.signal} recorded (state: {state['consecutive_test_failures']=}, {state['feature_completed_count']=})")

    if args.json:
        json.dump({"state": state, "pipeline": pipeline_summary()}, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 0

    if args.check:
        code, reasons = check(state, args.max_test_loops, args.done_signals, args.test_pct)
        for r in reasons:
            print(f"  - {r}")
        verdict = {0: "continue", 1: "stop", 2: "blocker"}[code]
        print(f"[ralph-gate] verdict: {verdict} (exit {code})")
        return code

    # --check も --signal も無ければ summary
    print(f"[ralph-gate] state summary:")
    print(f"  iterations            : {state.get('iterations', 0)}")
    print(f"  consecutive failures  : {state.get('consecutive_test_failures', 0)}")
    print(f"  feature completed     : {state.get('feature_completed_count', 0)}")
    print(f"  test pass count       : {state.get('test_pass_count', 0)}")
    print(f"  current_test_count    : {state.get('current_test_count', 0)} (started: {state.get('started_test_count', 0)})")
    print(f"  started_at            : {state.get('started_at', '?')}")
    pipe = pipeline_summary()
    print(f"  pipeline phase        : {pipe['phase']} (completed={pipe['completed']}, pending={pipe['pending']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
