#!/usr/bin/env python3
"""Strictly validate one fresh Battle Tutorial logcat capture; never run Android.

The native counter measures DoGameTick calls, not Params.Tick advancement. A
passing parser result is content-smoke evidence, not a playable-game verdict.
"""
import argparse
import json
import re
from pathlib import Path

MODE = "only:tutorials/battle tutorial"
ITEM = "Tutorials/Battle Tutorial"
TICK_CALLS = 200
BEGIN = re.compile(r"\bKAMTEST BEGIN mode=(.*?)\s*$")
DONE = re.compile(r"\bKAMTEST DONE passed=(\d+) failed=(\d+)\s*$")
FATAL = re.compile(
    r"KaMCrash.*signal|FATAL EXCEPTION|Fatal signal|Abort message:|"
    r"UnsatisfiedLinkError|NoSuchMethodError|ANR in org\.kamremake\.android|"
    r"kam_init failed|Exception in frame|Exception while closing game app|"
    r"KAMTEST message:|KAMTEST exception while stopping|KAMTEST can't save results"
)
THREADTIME = re.compile(
    r"^\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+\s+"
    r"(?P<pid>\d+)\s+\d+\s+[VDIWEF]\s+KaM\s*:\s+(?P<message>KAMTEST .*)$"
)
RECORDS = {
    "BEGIN": re.compile(r"KAMTEST BEGIN mode=(.*)"),
    "items": re.compile(r"KAMTEST items=(\d+)"),
    "START": re.compile(r"KAMTEST START\s+(\d+)/(\d+)\s+(.+)"),
    "OK": re.compile(r"KAMTEST OK\s+(\d+)/(\d+)\s+(.+) \((\d+) ticks, (\d+) ms\)"),
    "DONE": re.compile(r"KAMTEST DONE passed=(\d+) failed=(\d+)"),
}


def fatal_lines(text):
    return [{"line": i, "text": line} for i, line in enumerate(text.splitlines(), 1)
            if FATAL.search(line)]


def validate(text, expected_pid=None):
    """Require a single complete run, exact identity, real logcat framing/order.

    Freshness (force-stop + successful logcat clear) must be established by the
    runner. This pure parser cannot independently prove when a file was captured.
    """
    errors, records, pids = [], {kind: [] for kind in RECORDS}, set()
    result = {
        "status": "FAIL", "mode": MODE, "expected_item": ITEM,
        "required_tick_call_count": TICK_CALLS, "tick_call_count": None,
        "simulation_tick_advance_confirmed": False, "playable_confirmed": False,
        "freshness_confirmed_by_parser": False, "errors": errors,
    }
    for line_number, line in enumerate(text.splitlines(), 1):
        if "KAMTEST " not in line:
            continue
        framed = THREADTIME.fullmatch(line.strip())
        if not framed:
            errors.append(f"Line {line_number}: KAMTEST is not a native KaM threadtime record.")
            continue
        pids.add(int(framed.group("pid")))
        message = framed.group("message").strip()
        if message.startswith("KAMTEST progress "):
            continue
        for kind, pattern in RECORDS.items():
            match = pattern.fullmatch(message)
            if match:
                records[kind].append((line_number, match.groups()))
                break
        else:
            errors.append(f"Line {line_number}: failure, malformed, or unexpected KAMTEST record.")

    result["observed_pids"] = sorted(pids)
    if len(pids) != 1:
        errors.append("All KAMTEST records must come from exactly one native process PID.")
    if expected_pid is not None and pids != {int(expected_pid)}:
        errors.append("KAMTEST PID differs from the observed app PID.")
    for kind, values in records.items():
        if len(values) != 1:
            errors.append(f"Expected exactly one {kind} record; observed {len(values)}.")

    if all(len(values) == 1 for values in records.values()):
        order = [records[kind][0][0] for kind in ("BEGIN", "items", "START", "OK", "DONE")]
        if order != sorted(order) or len(set(order)) != len(order):
            errors.append("Require BEGIN < items < START < OK < DONE in the fresh capture.")
        if records["BEGIN"][0][1] != (MODE,):
            errors.append("BEGIN mode differs from the requested Battle Tutorial mode.")
        if records["items"][0][1] != ("1",):
            errors.append("Require exactly one discovered content item; zero items never pass.")
        if records["START"][0][1] != ("1", "1", ITEM):
            errors.append("START must identify exactly 1/1 Tutorials/Battle Tutorial.")
        ok = records["OK"][0][1]
        if ok[:3] != ("1", "1", ITEM):
            errors.append("OK must identify exactly 1/1 Tutorials/Battle Tutorial.")
        result["observed_tick_call_count"] = int(ok[3])
        if int(ok[3]) != TICK_CALLS:
            errors.append("OK must report exactly 200 update calls, including no early-end shortcut.")
        if records["DONE"][0][1] != ("1", "0"):
            errors.append("Require DONE passed=1 failed=0.")

    failures = fatal_lines(text)
    result["fatal_markers"] = failures
    if failures:
        errors.append("Fatal/error markers exist in the entire capture, including before BEGIN/after DONE.")
    if not errors:
        result.update(status="PASS", tick_call_count=TICK_CALLS, items=1, passed=1, failed=0)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logcat", type=Path)
    parser.add_argument("--expected-pid", type=int)
    args = parser.parse_args()
    try:
        text = args.logcat.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        parser.error(str(exc))
    result = validate(text, args.expected_pid)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
