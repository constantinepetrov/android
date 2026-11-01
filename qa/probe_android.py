#!/usr/bin/env python3
"""Probe an existing Android device without an APK or launching KaM.

Reuses android_cloud_qa.Runner for bounded ADB readiness, command evidence and
PNG validation. Success confirms sampled Android readiness and an Airtest
PNG only. ARM64 translation, APK installation and playable KaM remain untested.
The only intentional guest write is the readiness helper's unique temporary
/sdcard file, which it writes, reads and deletes. Logcat is not cleared.
"""
import argparse
import json
from pathlib import Path
import sys

from android_cloud_qa import GateError, Runner, positive_int, utc_now


PROBE_PASS = "ANDROID_READINESS_PROBE_PASS"

# Direct AdbCap is intentional: Android.screen_proxy.auto_setup may install
# Yosemite.apk when it falls back to JAVACAP, before its backend can be checked.
# This isolated child has no ScreenProxy, app installation, or capture fallback.
CAPTURE_CODE = """
import json
import sys
from airtest import aircv
from airtest.core.android.adb import ADB
from airtest.core.android.cap_methods.adbcap import AdbCap

adb = ADB(serialno=sys.argv[2], adb_path=sys.argv[1])
capture = AdbCap(adb)
pixels = capture.snapshot(ensure_orientation=False)
if pixels is None:
    raise RuntimeError('Airtest AdbCap did not decode a screenshot')
aircv.imwrite(sys.argv[3], pixels, quality=99)
print(json.dumps({'backend': 'airtest-adbcap', 'capture_class': type(capture).__name__,
                  'output': sys.argv[3]}), flush=True)
"""


class Probe(Runner):
    def __init__(self, args):
        # Runner's constructor records these fields but does not inspect an APK
        # or contact Android. Its APK/app methods are never called by this CLI.
        runner_args = argparse.Namespace(
            **vars(args), apk=None, expected_sha256=None,
            install_timeout=0, data_timeout=0, engine_timeout=0, selftest_timeout=0)
        super().__init__(runner_args)
        self.current_stage = "cloud_readiness"
        for name in ("package", "apk", "expected_apk_sha256", "tick_call_count"):
            self.state.pop(name, None)
        self.state.update(
            scope="Android readiness and Airtest screenshot only; no APK or game execution",
            apk_supplied=False, apk_installation_attempted=False,
            app_data_cleared=False, game_launched=False,
            menu_review="NOT_RUN", screenshot_content_review="PENDING",
            controls_review="NOT_RUN", playable_confirmed=False,
            simulation_tick_advance_confirmed=False,
            runtime_translation_confirmed=False,
            stages={name: {"status": "NOT_RUN"} for name in
                    ("cloud_readiness", "visual_evidence")},
            timeouts_seconds={"readiness": args.readiness_timeout,
                              "final_logcat": 20, "airtest_snapshot": 40,
                              "adb_snapshot_fallback": 20},
            not_verified=["ARM64 binary execution or native-bridge translation",
                          "APK installation", "game data installation",
                          "KaM startup or menu", "screenshot content correctness",
                          "touch controls", "simulation tick advancement",
                          "save/load", "audible sound", "playability"],
        )
        self.save()

    def execute(self):
        self.readiness()
        self.state["abi_preflight"]["scope"] = (
            "Capability advertisement only; no APK or ARM64 code executed by this probe")
        self.begin("visual_evidence")

    def screenshot(self, label):
        path = self.out / (label + ".png")
        code, _, _ = self.command(label + "-airtest", [
            sys.executable, "-B", "-c", CAPTURE_CODE,
            self.adb, self.serial, str(path)], 40)
        if code == 0:
            try:
                result = dict(self.png_info(path), available=True, backend="airtest-adbcap")
                self.state["airtest_snapshot_confirmed"] = True
                return result
            except Exception as exc:
                airtest_error = f"PNG validation: {type(exc).__name__}: {exc}"
        else:
            airtest_error = f"Airtest child exit code {code}; see command evidence"
        path.unlink(missing_ok=True)
        code, raw, _ = self.adb_command(
            label + "-adb-fallback", ["exec-out", "screencap", "-p"], 20)
        if code == 0:
            path.write_bytes(raw)
            try:
                return dict(self.png_info(path), available=True, backend="adb-screencap-fallback",
                            airtest_error=airtest_error)
            except Exception as exc:
                fallback_error = f"{type(exc).__name__}: {exc}"
        else:
            fallback_error = f"ADB screencap exit code {code}"
        path.unlink(missing_ok=True)
        return {"available": False, "airtest_error": airtest_error, "fallback_error": fallback_error}

    def final_evidence(self):
        # Runner.final_evidence also pulls KaM's private game logs and uses the
        # content-smoke PASS contract. Only its generic helpers belong here.
        if not self.device_selected:
            self.state["final_evidence"] = {
                "status": "UNAVAILABLE", "reason": "No selected ADB device"}
            return
        code, _ = self.logcat("probe-logcat", 20)
        evidence = {
            "logcat_complete": code == 0,
            "logcat_scope": "Uncleared Android buffer; may contain earlier events",
            "screenshot": self.screenshot("probe-screen"),
            "engine_logs_requested": False,
        }
        self.state["final_evidence"] = evidence
        self.save()
        # On a readiness failure retain diagnostic captures, without promoting
        # that failure to PASS just because a screenshot was obtained.
        if self.state["status"] != "RUNNING":
            return
        if code:
            raise GateError("probe_final_logcat_incomplete")
        shot = evidence["screenshot"]
        if not shot.get("available") or shot.get("backend") != "airtest-adbcap":
            raise GateError("probe_airtest_png_not_confirmed; fallback is diagnostic only")
        self.complete(
            backend=shot["backend"], screenshot=shot,
            scope="Validated Airtest PNG, not visual confirmation of screen contents")
        self.state["status"] = PROBE_PASS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True,
                        help="New evidence directory; must not exist")
    parser.add_argument("--adb", default="adb", help="ADB executable; default: adb from PATH")
    parser.add_argument("--serial", help="Explicit ADB serial; otherwise exactly one device is required")
    parser.add_argument("--readiness-timeout", type=positive_int, default=120)
    args = parser.parse_args()
    args.output = args.output.resolve()
    if args.output.exists():
        parser.error("--output already exists; use a fresh directory to prevent mixed evidence")
    args.output.mkdir(parents=True, exist_ok=False)
    probe = Probe(args)
    try:
        probe.execute()
    except KeyboardInterrupt:
        probe.record_failure(GateError("interrupted", "INTERRUPTED"))
    except Exception as exc:
        probe.record_failure(exc)
    finally:
        probe.state["readiness_finished_utc"] = utc_now()
        probe.save()
        try:
            probe.final_evidence()
        except Exception as exc:
            probe.state["final_evidence_error"] = f"{type(exc).__name__}: {exc}"
            if probe.state["status"] == "RUNNING":
                probe.record_failure(exc)
        probe.state["finished_utc"] = utc_now()
        probe.save()
        print(json.dumps(probe.state, ensure_ascii=False, indent=2), flush=True)
    return 0 if probe.state["status"] == PROBE_PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
