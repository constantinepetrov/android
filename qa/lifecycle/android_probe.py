#!/usr/bin/env python3
"""Reproduce Android's background-pause regression using real in-game save TickCount.

Runs ONLY on a disposable emulator with the known exact APK. It never touches
user-device data. Saves are parsed as headers, never uploaded.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gameplay_session import parse_save_header

PACKAGE = "org.kamremake.android"
ACTIVITY = PACKAGE + "/.KaMActivity"
SAVES = "/sdcard/Android/data/" + PACKAGE + "/files/Saves"


def adb(serial, *argv, timeout=35, binary=False):
    result = subprocess.run(["adb", "-s", serial, *argv], capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError("ADB failed: " + " ".join(argv) + " stderr=" +
                           result.stderr.decode(errors="replace")[-350:])
    return result.stdout if binary else result.stdout.decode(errors="replace")


def sleep(seconds):
    time.sleep(seconds)


def event(serial, key):
    adb(serial, "shell", "input", "keyevent", key)


def tap(serial, x, y):
    adb(serial, "shell", "input", "tap", str(x), str(y))


def frame(serial, out, name):
    content = adb(serial, "exec-out", "screencap", "-p", binary=True)
    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("Invalid Android screenshot")
    (out / (name + ".png")).write_bytes(content)


def save(serial, out, name):
    event(serial, "KEYCODE_F4")
    sleep(1.5)
    tap(serial, 99, 309)      # Save Game in the ordinary menu
    sleep(1.5)
    event(serial, "KEYCODE_MOVE_END")
    for _ in range(12):
        event(serial, "KEYCODE_DEL")
    adb(serial, "shell", "input", "text", name)
    sleep(0.6)
    event(serial, "KEYCODE_BACK")
    sleep(1)
    tap(serial, 99, 549)      # Save
    sleep(3)
    remote = SAVES + "/" + name + "/" + name + ".sav"
    data = adb(serial, "exec-out", "head -c 4096 " + remote, binary=True, timeout=15)
    details = parse_save_header(data)
    (out / (name + ".json")).write_text(json.dumps(details, indent=2) + "\n")
    print(json.dumps({"save": name, "tick": details["realTickCount"]}), flush=True)
    return details["realTickCount"]


def launch(serial):
    adb(serial, "shell", "am", "start", "-n", ACTIVITY)
    sleep(6)
    pid = adb(serial, "shell", "pidof", PACKAGE).strip()
    if not pid:
        raise RuntimeError("Native activity exited on launch")
    return pid


def run(args):
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    state = {"schema_version": 1, "status": "RUNNING", "expected": args.expected,
             "apk_sha256": args.apk_sha256, "steps": []}
    def checkpoint(name, fn):
        try:
            value = fn()
            state["steps"].append({"name": name, "status": "PASS", "value": value})
            (out / "result.json").write_text(json.dumps(state, indent=2) + "\n")
            return value
        except Exception as exc:
            state["steps"].append({"name": name, "status": "FAIL", "error": str(exc)[:800]})
            state["status"] = "BLOCKED"
            (out / "result.json").write_text(json.dumps(state, indent=2) + "\n")
            raise

    try:
        pid = checkpoint("launch", lambda: launch(args.serial))
        frame(args.serial, out, "main")
        checkpoint("open-tutorial", lambda: (
            tap(args.serial, 640, 331), sleep(2),
            tap(args.serial, 640, 371), sleep(10), frame(args.serial, out, "tutorial"), True)[-1])
        a0 = checkpoint("pre-0", lambda: save(args.serial, out, "lca0"))
        sleep(14)
        a1 = checkpoint("pre-1", lambda: save(args.serial, out, "lca1"))
        if a1 - a0 < 50:
            raise RuntimeError("Simulation not advancing before background; cannot test resume")

        checkpoint("background-home", lambda: (
            event(args.serial, "KEYCODE_HOME"), sleep(5), True)[-1])
        resumed_pid = checkpoint("resume-same-process", lambda: launch(args.serial))
        if pid != resumed_pid:
            raise RuntimeError("Android killed game during background; result is not a resume test")
        frame(args.serial, out, "resumed")
        sleep(14)
        b0 = checkpoint("post-home", lambda: save(args.serial, out, "lcb0"))
        delta = b0 - a1
        state["tick_deltas"] = {"before_background": a1 - a0, "after_background": delta}
        frame(args.serial, out, "after-post-save")

        if args.expected == "baseline-stuck":
            if delta > 30:
                raise RuntimeError("No background freeze reproduced: ticks advanced " + str(delta))
            # A manual unpause should restore progression on the old build.
            event(args.serial, "KEYCODE_P")
            sleep(14)
            c0 = checkpoint("post-manual-unpause", lambda: save(args.serial, out, "lcc0"))
            state["tick_deltas"]["after_manual_unpause"] = c0 - b0
            if c0 - b0 < 50:
                raise RuntimeError("P did not restart ticks, pause hypothesis unconfirmed")
        else:
            if delta < 50:
                raise RuntimeError("Patched build still frozen after background: delta=" + str(delta))
            # Manual pause must survive background/foreground transitions.
            event(args.serial, "KEYCODE_P")
            m0 = checkpoint("pre-manual-pause", lambda: save(args.serial, out, "lcm0"))
            event(args.serial, "KEYCODE_HOME")
            sleep(3)
            _ = launch(args.serial)
            sleep(12)
            m1 = checkpoint("manual-pause-after-resume", lambda: save(args.serial, out, "lcm1"))
            state["tick_deltas"]["manual_pause_after_resume"] = m1 - m0
            if m1 - m0 > 30:
                raise RuntimeError("Manual pause was incorrectly removed by background")
            event(args.serial, "KEYCODE_P")
            sleep(12)
            m2 = checkpoint("manual-then-unpause", lambda: save(args.serial, out, "lcm2"))
            state["tick_deltas"]["manual_then_unpause"] = m2 - m1
            if m2 - m1 < 45:
                raise RuntimeError("Manual unpause did not restart simulation")

        state["status"] = ("REPRODUCED_BASELINE_PAUSE_BUG" if args.expected == "baseline-stuck"
                           else "PATCHED_LIFECYCLE_PASS")
        print(json.dumps({"status": state["status"], **state["tick_deltas"]}), flush=True)
    except Exception as exc:
        if state["status"] == "RUNNING":
            state["status"] = "FAIL"
            state["error"] = type(exc).__name__ + ": " + str(exc)[:800]
        print("Lifecycle probe failed: " + str(exc), file=sys.stderr)
        raise
    finally:
        try:
            logs = adb(args.serial, "shell", "logcat", "-d", "-s", "KaM:*", "KaMHost:*")
            (out / "kaM-logcat.txt").write_text(logs[-250000:], encoding="utf-8")
        except Exception:
            pass
        (out / "result.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--serial", default="emulator-5554")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--expected", choices=["baseline-stuck", "fixed"], required=True)
    p.add_argument("--apk-sha256", default="c7df4b880984b9a475b57ee00b41fa5ba6140f4c21e5f688a9188ab1622169c4")
    run(p.parse_args())
