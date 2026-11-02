#!/usr/bin/env python3
"""Reproduce Android's background-pause regression using real in-game save TickCount.

Runs ONLY on a disposable emulator with the known exact APK. It never touches
user-device data. Saves are parsed as headers, never uploaded.
"""
import argparse
import json
import hashlib
from io import BytesIO
from PIL import Image
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


# Pixel-exact UI states from the independent successful 1280x720 Airtest run
# 41441125987 (the screenshot crop contains only one KaM menu button).
# Distinguish these from a launcher ANR dialog before sending any game taps.
MAIN_MENU_SHA = "323916a04dbdb125dea1a93026fe9114693f14778278eb6f8567a28b7a941d35"
SINGLE_PLAYER_SHA = "867be1d4a0453de2bbe66ca6843630385a20ed7363f54d1bad3b564e767b36ea"


def observe_scene(serial, out, attempt):
    content = adb(serial, "exec-out", "screencap", "-p", binary=True)
    if not content.startswith(b"\\x89PNG\\r\\n\\x1a\\n"):
        raise RuntimeError("Emulator did not return a PNG")
    image = Image.open(BytesIO(content)).convert("RGB")
    if image.size != (1280, 720):
        raise RuntimeError("Expected the pinned 1280x720 Android display")
    preview = out / ("navigation-%02d.png" % attempt)
    preview.write_bytes(content)
    # A loaded Battle Tutorial map is bright grass-green over a large region.
    # The parchment menus have effectively zero strongly-green samples.
    sample = image.crop((160, 60, 1190, 650)).resize((70, 40))
    pixels = list(sample.getdata())
    green_fraction = sum(g > r * 1.18 and g > b * 1.18 and g > 90
                         for r, g, b in pixels) / len(pixels)
    if green_fraction > 0.12:
        scene = "game-map"
    else:
        menu_hash = hashlib.sha256(image.crop((470, 320, 810, 345)).tobytes()).hexdigest()
        scene = ("main-menu" if menu_hash == MAIN_MENU_SHA else
                 "single-player-menu" if menu_hash == SINGLE_PLAYER_SHA else
                 "unknown-overlay-or-transition")
    print(json.dumps({"navigation": attempt, "scene": scene,
                      "green_fraction": round(green_fraction, 4)}), flush=True)
    return scene


def navigate_tutorial(serial, out):
    """Never claim tutorial navigation passed without seeing an actual map.

    A fresh emulator can display an Android Launcher ANR on top of KaM,
    swallowing ADB taps. Wait through the overlay rather than blindly
    claiming the taps changed pages.
    """
    for attempt in range(18):
        scene = observe_scene(serial, out, attempt)
        if scene == "game-map":
            frame(serial, out, "tutorial")
            return True
        if scene == "main-menu":
            tap(serial, 640, 331)   # Single Player
            sleep(5)
        elif scene == "single-player-menu":
            tap(serial, 640, 371)   # Battle Tutorial
            sleep(12)
        else:
            sleep(4)               # system ANR or game loading
    raise RuntimeError("Unable to open Battle Tutorial from observed UI states")


def save(serial, out, name):
    """Observe each UI transition so a test failure cannot masquerade as a game regression."""
    frame(serial, out, name + "-before")
    event(serial, "KEYCODE_F4")
    sleep(2.0)
    frame(serial, out, name + "-after-f4")
    tap(serial, 99, 309)      # Save Game in the ordinary menu
    sleep(2.0)
    frame(serial, out, name + "-save-dialog")
    event(serial, "KEYCODE_MOVE_END")
    adb(serial, "shell", "input", "keyevent", *(["KEYCODE_DEL"] * 64))
    adb(serial, "shell", "input", "text", name)
    sleep(0.8)
    frame(serial, out, name + "-entered-name")
    event(serial, "KEYCODE_BACK")
    sleep(1.5)
    frame(serial, out, name + "-keyboard-dismissed")
    tap(serial, 99, 549)      # Save
    sleep(3)
    frame(serial, out, name + "-after-save")

    # Record filenames on the device, but never upload private save bodies.
    remote = SAVES + "/" + name + "/" + name + ".sav"
    for attempt in range(8):
        exists = subprocess.run(["adb", "-s", serial, "shell", "test", "-f", remote], capture_output=True).returncode == 0
        if exists:
            break
        sleep(2)
    listing = adb(serial, "shell", "find", SAVES, "-name", "*.sav")
    (out / (name + "-save-paths.txt")).write_text(listing)
    if not exists:
        raise RuntimeError("Expected game save missing: " + remote + "; available: " + repr(listing[-2000:]))
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
        checkpoint("open-tutorial", lambda: navigate_tutorial(args.serial, out))
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
            # A manually paused game deliberately blocks F4 / Save Game: never
            # try to produce a save during pause. Observe the pause overlay and
            # check the exact Android lifecycle ownership log instead.
            checkpoint("manual-pause-enter", lambda: (
                event(args.serial, "KEYCODE_P"), sleep(2),
                frame(args.serial, out, "manual-pause-before-home"), True)[-1])
            checkpoint("manual-pause-home", lambda: (
                event(args.serial, "KEYCODE_HOME"), sleep(4), True)[-1])
            manual_pid = checkpoint("manual-pause-return", lambda: launch(args.serial))
            if manual_pid != pid:
                raise RuntimeError("Android changed the PID during manually paused resume")
            sleep(9)
            frame(args.serial, out, "manual-pause-after-home")

            # The patched engine emits ownership markers to its own Logs files.
            # auto=0 on the most recent pair confirms Android never claimed
            # a manual pause as its own and therefore must not clear it.
            lifecycle_log = adb(args.serial, "shell", "sh", "-c",
                "grep -h 'Android lifecycle' " + 
                "/sdcard/Android/data/" + PACKAGE + "/files/Logs/KaM_*.log")
            markers = [line.strip() for line in lifecycle_log.splitlines()
                       if "Android lifecycle " in line]
            (out / "manual-pause-lifecycle.txt").write_text("\\n".join(markers[-20:]) + "\\n")
            last_pauses = [line for line in markers if "Android lifecycle pause:" in line]
            last_resumes = [line for line in markers if "Android lifecycle resume:" in line]
            if not last_pauses or not last_resumes:
                raise RuntimeError("Native lifecycle ownership markers not found")
            if "auto=0" not in last_pauses[-1] or "auto=0" not in last_resumes[-1]:
                raise RuntimeError("Android incorrectly took ownership of a manual pause")
            state["manual_pause"] = {
                "most_recent_pause": last_pauses[-1],
                "most_recent_resume": last_resumes[-1],
                "screenshots": ["manual-pause-before-home.png", "manual-pause-after-home.png"],
                "visual_pause_overlay_review_required": True,
            }
            checkpoint("manual-pause-ownership", lambda: state["manual_pause"])

            # Unpause explicitly before using the Save Game menu again.
            checkpoint("manual-pause-unpause", lambda: (
                event(args.serial, "KEYCODE_P"), sleep(14),
                frame(args.serial, out, "manual-pause-unpaused"), True)[-1])
            m2 = checkpoint("post-manual-unpause", lambda: save(args.serial, out, "lcm2"))
            state["tick_deltas"]["manual_then_unpause"] = m2 - b0
            if m2 - b0 < 45:
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
