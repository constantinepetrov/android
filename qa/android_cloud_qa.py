#!/usr/bin/env python3
"""Check an existing disposable Android runner against one pinned KaM APK.

Does not boot/stop an emulator or provision a cloud device. Clears only KaM app
data on the selected test device. Success means AUTOMATED_CONTENT_SMOKE_PASS;
menu/controls/gameplay still require review. All ADB work is inside main().
"""
import argparse
import datetime
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import uuid

from validate_selftest import DONE, ITEM, MODE, fatal_lines, validate

PACKAGE = "org.kamremake.android"
DATA = "/sdcard/Android/data/" + PACKAGE + "/files"
MARKER = DATA + "/.kamdata_installed"
PINNED_SHA256 = "c7df4b880984b9a475b57ee00b41fa5ba6140f4c21e5f688a9188ab1622169c4"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
PASS = "AUTOMATED_CONTENT_SMOKE_PASS"


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class GateError(Exception):
    def __init__(self, reason, status="BLOCKED"):
        super().__init__(reason)
        self.status = status


class Runner:
    def __init__(self, args):
        self.args, self.out = args, args.output
        self.adb = shutil.which(args.adb) or args.adb
        self.serial = args.serial
        self.device_selected = False
        self.commands = []
        self.run_id = uuid.uuid4().hex
        self.current_stage = "artifact"
        self.state = {
            "schema_version": 1, "started_utc": utc_now(), "status": "RUNNING",
            "run_id": self.run_id, "package": PACKAGE, "serial": self.serial,
            "apk": str(args.apk), "expected_apk_sha256": args.expected_sha256,
            "output": str(self.out), "adb": self.adb,
            "menu_review": "PENDING", "controls_review": "NOT_RUN",
            "playable_confirmed": False, "simulation_tick_advance_confirmed": False,
            "tick_call_count": None, "airtest_snapshot_confirmed": False,
            "stages": {name: {"status": "NOT_RUN"} for name in (
                "artifact", "cloud_readiness", "apk_install", "fresh_data",
                "engine_init", "visual_evidence", "content_smoke")},
            "timeouts_seconds": {name: getattr(args, name + "_timeout") for name in
                                 ("readiness", "install", "data", "engine", "selftest")},
            "not_verified": ["visual menu correctness", "manual touch controls",
                             "building and delivery", "save/load", "audible sound",
                             "exact simulation tick advancement", "full playthrough"],
            "github": {name: os.environ.get(name) for name in (
                "GITHUB_REPOSITORY", "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")},
        }
        for package in ("airtest", "Pillow"):
            try:
                self.state.setdefault("host_packages", {})[package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                self.state.setdefault("host_packages", {})[package] = None
        self.save()

    def write_json(self, name, data):
        path = self.out / name
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

    def save(self):
        self.write_json("status.json", self.state)

    def begin(self, stage):
        self.current_stage = stage
        self.state["active_stage"] = stage
        self.state["stages"][stage].update(status="RUNNING", started_utc=utc_now())
        self.save()
        print(json.dumps({"stage": stage, "status": "RUNNING"}), flush=True)

    def complete(self, **details):
        self.state["stages"][self.current_stage].update(
            status="PASS", finished_utc=utc_now(), **details)
        self.save()

    def command(self, label, command, timeout=20):
        started = time.monotonic()
        code, stdout, stderr, timed_out = 127, b"", b"", False
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       start_new_session=True)
            try:
                stdout, stderr = process.communicate(timeout=max(0.05, timeout))
                code = process.returncode
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
                code = 124
        except OSError as exc:
            stderr = str(exc).encode()
        stem = f"{len(self.commands) + 1:04d}-{label}"
        stdout_file, stderr_file = stem + ".stdout", stem + ".stderr"
        (self.out / stdout_file).write_bytes(stdout)
        (self.out / stderr_file).write_bytes(stderr)
        record = {
            "name": label, "argv": command, "timeout_seconds": round(timeout, 3),
            "returncode": code, "timed_out": timed_out,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "stdout_file": stdout_file, "stderr_file": stderr_file,
            "finished_utc": utc_now(),
        }
        self.commands.append(record)
        self.write_json("commands.json", self.commands)
        return code, stdout, stderr

    def adb_command(self, label, arguments, timeout=20):
        if not self.serial:
            raise GateError("ADB device was not explicitly resolved")
        return self.command(label, [self.adb, "-s", self.serial, *arguments], timeout)

    @staticmethod
    def remaining(deadline, cap=20):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise GateError("stage_deadline_exceeded")
        return min(cap, remaining)

    @staticmethod
    def pause(deadline, seconds=2):
        time.sleep(max(0, min(seconds, deadline - time.monotonic())))

    def checked(self, label, arguments, timeout=20):
        code, raw, _ = self.adb_command(label, arguments, timeout)
        if code:
            raise GateError(label + "_failed")
        return raw.decode("utf-8", errors="replace")

    def logcat(self, label, timeout=20):
        code, raw, _ = self.adb_command(label, ["logcat", "-b", "all", "-d", "-v", "threadtime"], timeout)
        (self.out / (label + ".txt")).write_bytes(raw)
        return code, raw.decode("utf-8", errors="replace")

    @staticmethod
    def png_info(path):
        from PIL import Image
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError("missing or empty screenshot")
        with path.open("rb") as handle:
            if handle.read(8) != PNG_MAGIC:
                raise ValueError("screenshot has no PNG signature")
        with Image.open(path) as screenshot:
            if screenshot.format != "PNG" or min(screenshot.size) <= 0:
                raise ValueError("screenshot is not a nonempty PNG")
            dimensions = list(screenshot.size)
            screenshot.verify()
        return {"file": path.name, "bytes": path.stat().st_size,
                "sha256": sha256_file(path), "dimensions": dimensions}

    def screenshot(self, label):
        path = self.out / (label + ".png")
        helper = Path(__file__).resolve().with_name("airtest_snapshot.py")
        code, _, _ = self.command(label + "-airtest", [
            sys.executable, str(helper), "--adb", self.adb, "--serial", self.serial,
            "--output", str(path)], 40)
        airtest_error = None
        if code == 0:
            try:
                result = dict(self.png_info(path), available=True, backend="airtest-adbcap")
                self.state["airtest_snapshot_confirmed"] = True
                return result
            except Exception as exc:
                airtest_error = f"PNG validation: {type(exc).__name__}: {exc}"
        else:
            airtest_error = f"Airtest child exit code {code}; see command evidence"
        # A separate, labelled fallback preserves diagnostic evidence without
        # presenting a raw ADB capture as a successful Airtest invocation.
        path.unlink(missing_ok=True)
        code, raw, _ = self.adb_command(label + "-adb-fallback", ["exec-out", "screencap", "-p"], 20)
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

    def artifact(self):
        self.begin("artifact")
        if not self.args.apk.is_file():
            raise GateError("APK file does not exist")
        actual = sha256_file(self.args.apk)
        self.state.update(apk_sha256=actual, apk_bytes=self.args.apk.stat().st_size)
        if actual != self.args.expected_sha256:
            raise GateError("local_apk_sha256_mismatch; no Android command was run")
        self.complete(sha256=actual, bytes=self.state["apk_bytes"])

    def select_device(self, deadline):
        while time.monotonic() < deadline:
            code, raw, _ = self.command("adb-devices", [self.adb, "devices", "-l"], self.remaining(deadline, 10))
            rows = []
            for line in raw.decode(errors="replace").splitlines():
                fields = line.strip().split()
                if fields and fields[0] not in {"List", "*"} and len(fields) >= 2:
                    rows.append((fields[0], fields[1]))
            self.state["device_inventory"] = rows
            if code == 0:
                if self.args.serial:
                    if (self.args.serial, "device") in rows:
                        self.serial = self.args.serial
                        break
                else:
                    if len(rows) > 1:
                        raise GateError("ambiguous_devices; provide --serial explicitly")
                    if len(rows) == 1 and rows[0][1] == "device":
                        self.serial = rows[0][0]
                        break
            self.pause(deadline)
        else:
            raise GateError("no_single_online_device_before_readiness_deadline")
        self.state["serial"] = self.serial
        self.device_selected = True
        self.save()

    def readiness(self):
        self.begin("cloud_readiness")
        started = time.monotonic()
        deadline = started + self.args.readiness_timeout
        self.select_device(deadline)
        consecutive, last_pid, probes = 0, None, []
        probe_path = "/sdcard/.kam-cloud-qa-" + self.run_id
        probe = ("set -e; printf '%s' " + shlex.quote(self.run_id) + " > " + shlex.quote(probe_path) +
                 "; cat " + shlex.quote(probe_path) + "; rm " + shlex.quote(probe_path))
        while time.monotonic() < deadline:
            results = {}
            commands = {
                "boot_completed": ["shell", "getprop", "sys.boot_completed"],
                "package_manager": ["shell", "pm", "path", "android"],
                "user_state": ["shell", "am", "get-started-user-state", "0"],
                "system_server": ["shell", "pidof", "system_server"],
                "external_storage_write_read_delete": ["shell", probe],
            }
            for name, argv in commands.items():
                code, raw, _ = self.adb_command("readiness-" + name, argv, self.remaining(deadline, 8))
                results[name] = {"returncode": code, "value": raw.decode(errors="replace").strip()}
            good = all(value["returncode"] == 0 for value in results.values())
            good = good and results["boot_completed"]["value"] == "1"
            good = good and results["package_manager"]["value"].startswith("package:/")
            good = good and results["user_state"]["value"] == "RUNNING_UNLOCKED"
            good = good and re.fullmatch(r"\d+", results["system_server"]["value"]) is not None
            good = good and results["external_storage_write_read_delete"]["value"] == self.run_id
            pid = results["system_server"]["value"]
            consecutive = consecutive + 1 if good and pid == last_pid else (1 if good else 0)
            last_pid = pid if good else None
            probes.append({"utc": utc_now(), "checks": results, "stable_success_samples": consecutive})
            self.write_json("readiness.json", probes)
            print(json.dumps({"stage": "cloud_readiness", "stable_success_samples": consecutive,
                              "elapsed_seconds": round(time.monotonic() - started, 1)}), flush=True)
            if consecutive >= 3:
                metadata = {}
                for name in ("ro.build.version.sdk", "ro.build.fingerprint", "ro.product.cpu.abi", "ro.product.cpu.abilist",
                             "ro.dalvik.vm.native.bridge", "ro.hardware"):
                    metadata[name] = self.checked("device-property", ["shell", "getprop", name],
                                                  self.remaining(deadline, 8)).strip()
                self.state["android_metadata"] = metadata
                if not metadata["ro.build.version.sdk"].isdigit() or int(metadata["ro.build.version.sdk"]) < 30:
                    raise GateError("API_30_or_newer_required_by_this_Activity")
                abis = [abi.strip() for abi in metadata["ro.product.cpu.abilist"].split(",") if abi.strip()]
                primary_abi = metadata["ro.product.cpu.abi"]
                bridge = metadata["ro.dalvik.vm.native.bridge"]
                if "arm64-v8a" not in abis:
                    raise GateError("BLOCKED_UNSUPPORTED_ABI: guest does not advertise arm64-v8a")
                if primary_abi == "arm64-v8a":
                    abi_route = "native_arm64"
                elif primary_abi in {"x86_64", "x86"} and bridge.lower() not in {"", "0", "false", "none"}:
                    abi_route = "advertised_arm64_native_bridge"
                else:
                    raise GateError("BLOCKED_UNSUPPORTED_ABI: no native ARM64 or meaningful x86 native bridge")
                self.state["abi_preflight"] = {"route": abi_route, "primary_abi": primary_abi,
                    "arm64_advertised": True, "native_bridge": bridge,
                    "runtime_translation_confirmed": False,
                    "scope": "Capability advertisement only; real ARM64 initialization is tested later"}
                self.complete(stable_success_samples=3, system_server_pid=pid,
                              elapsed_seconds=round(time.monotonic() - started, 3))
                return
            self.pause(deadline, 3)
        raise GateError("cloud_readiness_deadline")

    def install(self):
        self.begin("apk_install")
        deadline = time.monotonic() + self.args.install_timeout
        guest = "/data/local/tmp/kam-cloud-qa-" + self.run_id + ".apk"
        self.state["guest_apk"] = guest
        self.checked("push-fresh-apk", ["push", str(self.args.apk), guest], self.remaining(deadline, self.args.install_timeout))
        size = self.checked("guest-apk-size", ["shell", "stat", "-c", "%s", guest], self.remaining(deadline, 15)).strip()
        digest = self.checked("guest-apk-sha256", ["shell", "sha256sum", guest], self.remaining(deadline, 60)).split()
        if size != str(self.state["apk_bytes"]) or not digest or digest[0] != self.args.expected_sha256:
            raise GateError("fresh_guest_apk_size_or_sha256_mismatch")
        output = self.checked("pm-install", ["shell", "pm", "install", "-r", guest],
                              self.remaining(deadline, self.args.install_timeout))
        if not re.search(r"(?m)^Success\s*$", output):
            raise GateError("pm_install_did_not_report_Success")
        paths = self.checked("installed-package", ["shell", "pm", "path", PACKAGE],
                             self.remaining(deadline, 20)).splitlines()
        if len(paths) != 1 or not paths[0].startswith("package:/"):
            raise GateError("installed_monolithic_kam_package_not_confirmed")
        installed_path = paths[0][len("package:"):]
        installed_digest = self.checked("installed-apk-sha256", ["shell", "sha256sum", installed_path],
                                        self.remaining(deadline, 60)).split()
        if not installed_digest or installed_digest[0] != self.args.expected_sha256:
            raise GateError("installed_package_does_not_match_pinned_apk")
        self.complete(installed_package_path=installed_path, guest_sha256=digest[0],
                      installed_sha256=installed_digest[0])

    @staticmethod
    def missing_path(code, stderr):
        return code == 1 and b"no such file or directory" in stderr.lower()

    def marker_info(self, timeout=15):
        code, raw, err = self.adb_command("data-marker", ["shell", "stat -c '%Y %s' " + shlex.quote(MARKER)], timeout)
        if self.missing_path(code, err):
            return None
        if code:
            raise GateError("data_marker_unreadable")
        values = raw.decode(errors="replace").strip().split()
        if len(values) != 2 or not all(value.isdigit() for value in values):
            raise GateError("invalid_data_marker_stat")
        return {"mtime": int(values[0]), "bytes": int(values[1])}

    def engine_files(self, timeout=15):
        remote = ("find " + shlex.quote(DATA + "/Logs") +
                  " -maxdepth 1 -type f -name 'KaM_*.log' -exec stat -c '%Y %n' '{}' \\;")
        code, raw, err = self.adb_command("engine-files", ["shell", remote], timeout)
        if self.missing_path(code, err):
            return []
        if code:
            raise GateError("engine_log_directory_unreadable")
        result = []
        for line in raw.decode(errors="replace").splitlines():
            fields = line.strip().split(" ", 1)
            if len(fields) != 2 or not fields[0].isdigit():
                raise GateError("invalid_engine_log_stat")
            if not fields[1].startswith(DATA + "/Logs/KaM_") or not fields[1].endswith(".log"):
                raise GateError("unexpected_engine_log_path")
            result.append((int(fields[0]), fields[1]))
        return result

    def pid(self, timeout=10, expected=None, required=True):
        code, raw, _ = self.adb_command("app-pid", ["shell", "pidof", PACKAGE], timeout)
        text = raw.decode(errors="replace").strip()
        if code or not re.fullmatch(r"\d+", text):
            if required:
                raise GateError("app_process_not_alive", "FAIL")
            return None
        value = int(text)
        if expected is not None and value != expected:
            raise GateError("app_process_changed_during_this_launch", "FAIL")
        return value

    def clean_logcat(self):
        self.checked("clear-all-logcat", ["logcat", "-b", "all", "-c"], 20)

    def first_launch(self):
        self.begin("fresh_data")
        self.checked("first-force-stop", ["shell", "am", "force-stop", PACKAGE])
        output = self.checked("clear-only-kam-data", ["shell", "pm", "clear", PACKAGE], 60)
        if output.strip() != "Success":
            raise GateError("pm_clear_only_kam_not_confirmed")
        if self.marker_info() is not None or self.engine_files():
            raise GateError("old_marker_or_engine_logs_remain_after_app_clear")
        self.state["first_launch_freshness"] = {"app_data_cleared": True,
            "marker_absent_before_launch": True, "engine_logs_absent_before_launch": True}
        self.clean_logcat()
        epoch = self.checked("first-guest-epoch", ["shell", "date", "+%s"]).strip()
        if not epoch.isdigit():
            raise GateError("guest_launch_epoch_unknown")
        launch_epoch = int(epoch)
        self.state["first_launch_freshness"].update(guest_epoch=launch_epoch, logcat_clear_succeeded=True)
        started = time.monotonic()
        deadline = started + self.args.data_timeout
        output = self.checked("first-activity-launch", ["shell", "am", "start", "-W", "-n", PACKAGE + "/.KaMActivity"],
                              self.remaining(deadline, 90))
        if not re.search(r"(?m)^Status:\s*ok\s*$", output):
            raise GateError("first_activity_launch_not_confirmed")
        first_pid = self.pid(self.remaining(deadline, 10))
        self.state["first_launch_pid"] = first_pid
        while time.monotonic() < deadline:
            self.pid(self.remaining(deadline, 10), expected=first_pid)
            marker = self.marker_info(self.remaining(deadline, 10))
            if marker is not None:
                if marker["mtime"] < launch_epoch or marker["bytes"] != 0:
                    raise GateError("completion_marker_is_not_fresh_and_empty")
                self.complete(marker=marker, elapsed_seconds=round(time.monotonic() - started, 3),
                              scope="Bundled copy completed; marker does not verify per-file hashes")
                break
            print(json.dumps({"stage": "fresh_data", "elapsed_seconds": round(time.monotonic() - started, 1)}), flush=True)
            self.pause(deadline, 3)
        else:
            raise GateError("fresh_data_deadline")

        self.begin("engine_init")
        started = time.monotonic()
        deadline = started + self.args.engine_timeout
        while time.monotonic() < deadline:
            self.pid(self.remaining(deadline, 10), expected=first_pid)
            files = self.engine_files(self.remaining(deadline, 10))
            if files:
                modified, path = max(files)
                if modified < launch_epoch:
                    raise GateError("engine_log_is_older_than_this_launch")
                text = self.checked("fresh-engine-log", ["shell", "cat " + shlex.quote(path)], self.remaining(deadline, 15))
                (self.out / "first-launch-engine.log").write_text(text, encoding="utf-8")
                if "Game Load Done in" in text:
                    code, logs = self.logcat("first-launch-logcat", self.remaining(deadline, 20))
                    if code:
                        raise GateError("first_launch_logcat_incomplete")
                    errors = fatal_lines(logs)
                    if errors:
                        self.state["first_launch_fatal_markers"] = errors
                        raise GateError("fatal_markers_in_fresh_first_launch", "FAIL")
                    self.pid(self.remaining(deadline, 10), expected=first_pid)
                    self.complete(engine_log=path, engine_log_mtime=modified, pid=first_pid,
                                  elapsed_seconds=round(time.monotonic() - started, 3),
                                  scope="Native engine initialized; menu correctness remains PENDING")
                    break
            print(json.dumps({"stage": "engine_init", "elapsed_seconds": round(time.monotonic() - started, 1)}), flush=True)
            self.pause(deadline, 3)
        else:
            raise GateError("engine_init_deadline")

        self.begin("visual_evidence")
        screen = self.screenshot("engine-ready-screen")
        self.state["engine_ready_screenshot"] = screen
        if not screen["available"]:
            raise GateError("required_engine_ready_PNG_unavailable")
        self.pid(expected=first_pid)
        # A slow snapshot can overlap a late startup crash/ANR. Preserve and
        # check this interval before the independent selftest clears logcat.
        code, logs = self.logcat("first-launch-after-screenshot-logcat", 20)
        if code:
            raise GateError("first_launch_post_screenshot_logcat_incomplete")
        errors = fatal_lines(logs)
        if errors:
            self.state["first_launch_fatal_markers"] = errors
            raise GateError("fatal_markers_during_first_launch_capture", "FAIL")
        self.complete(screenshot=screen, scope="Image captured only; visual review remains PENDING")

    def selftest(self):
        self.begin("content_smoke")
        self.checked("selftest-force-stop", ["shell", "am", "force-stop", PACKAGE])
        self.clean_logcat()
        self.state["selftest_freshness"] = {"force_stop_succeeded": True, "logcat_clear_succeeded": True}
        started = time.monotonic()
        deadline = started + self.args.selftest_timeout
        remote = "am start -W -n " + PACKAGE + "/.KaMActivity --es kam_selftest " + shlex.quote(MODE)
        output = self.checked("selftest-launch", ["shell", remote], self.remaining(deadline, 90))
        if not re.search(r"(?m)^Status:\s*ok\s*$", output):
            raise GateError("selftest_activity_launch_not_confirmed")
        observed_done, expected_pid = False, None
        logs = ""
        while time.monotonic() < deadline:
            code, logs = self.logcat("selftest-logcat", self.remaining(deadline, 15))
            if code:
                raise GateError("selftest_logcat_capture_failed")
            if any(DONE.search(line) for line in logs.splitlines()):
                observed_done = time.monotonic() <= deadline
                break
            if fatal_lines(logs):
                raise GateError("fatal_error_before_selftest_done", "FAIL")
            app_pid = self.pid(self.remaining(deadline, 10), expected=expected_pid, required=False)
            if app_pid is None:
                # Native DONE calls gHostQuit. Check once more for a normal exit
                # racing the previous capture, still inside the original deadline.
                code, logs = self.logcat("selftest-logcat", self.remaining(deadline, 15))
                observed_done = code == 0 and time.monotonic() <= deadline and any(
                    DONE.search(line) for line in logs.splitlines())
                if not observed_done:
                    raise GateError("app_exited_before_selftest_done", "FAIL")
                break
            expected_pid = app_pid
            events = [line for line in logs.splitlines() if "KAMTEST " in line]
            print(json.dumps({"stage": "content_smoke", "elapsed_seconds": round(time.monotonic() - started, 1),
                              "latest_selftest_line": events[-1] if events else None}), flush=True)
            self.pause(deadline, 2)
        self.state["selftest_done_observed_within_deadline"] = observed_done
        self.state["selftest_wait_elapsed_seconds"] = round(time.monotonic() - started, 3)
        if not observed_done:
            raise GateError("selftest_deadline_without_complete_run", "FAIL")
        time.sleep(2)  # Bounded post-DONE drain: save/StopGame errors occur after DONE.
        code, logs = self.logcat("selftest-logcat", 20)
        if code:
            raise GateError("final_selftest_logcat_incomplete")
        validation = validate(logs, expected_pid=expected_pid)
        self.write_json("selftest-validation.json", validation)
        self.state["selftest_validation"] = validation
        if validation["status"] != "PASS":
            raise GateError("strict_selftest_validation_failed", "FAIL")
        self.state["tick_call_count"] = 200
        self.complete(mode=MODE, item=ITEM, tick_call_count=200,
                      simulation_tick_advance_confirmed=False,
                      scope="One real Battle Tutorial startup/update/StopGame smoke; not a playthrough")

    def execute(self):
        self.artifact()
        self.readiness()
        self.install()
        self.first_launch()
        self.selftest()
        self.state["status"] = PASS

    def final_evidence(self):
        if not self.device_selected:
            self.state["final_evidence"] = {"status": "UNAVAILABLE", "reason": "No selected ADB device"}
            return
        evidence = {}
        code, logs = self.logcat("final-logcat", 20)
        evidence["logcat_complete"] = code == 0
        evidence["screenshot"] = self.screenshot("final-screen")
        pull_code, _, _ = self.adb_command("final-engine-logs", ["pull", DATA + "/Logs", str(self.out / "engine-logs")], 30)
        evidence["engine_logs_pull_returncode"] = pull_code
        self.state["final_evidence"] = evidence
        if self.state["status"] == PASS:
            if code:
                raise GateError("final_evidence_logcat_incomplete")
            errors = fatal_lines(logs)
            if errors:
                self.state["final_fatal_markers"] = errors
                raise GateError("fatal_error_after_content_smoke", "FAIL")
        # The workflow owns emulator shutdown. Do not kill its emulator/server.

    def record_failure(self, exc):
        status = exc.status if isinstance(exc, GateError) else "BLOCKED"
        self.state.update(status=status, reason=str(exc), failure_stage=self.current_stage)
        stage = self.state["stages"][self.current_stage]
        if stage["status"] == "RUNNING":
            stage.update(status=status, reason=str(exc), finished_utc=utc_now())
        self.save()


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Timeout must be positive")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New evidence directory; must not exist")
    parser.add_argument("--adb", default="adb", help="ADB executable; default: adb from PATH")
    parser.add_argument("--serial", help="Explicit ADB serial; otherwise exactly one device is required")
    parser.add_argument("--expected-sha256", default=PINNED_SHA256,
                        help="Expected APK SHA256, pinned to the workflow artifact")
    for name, seconds in (("readiness", 120), ("install", 240), ("data", 300), ("engine", 180), ("selftest", 240)):
        parser.add_argument("--" + name + "-timeout", type=positive_int, default=seconds)
    args = parser.parse_args()
    args.apk, args.output = args.apk.resolve(), args.output.resolve()
    args.expected_sha256 = args.expected_sha256.lower()
    if not re.fullmatch(r"[0-9a-f]{64}", args.expected_sha256):
        parser.error("--expected-sha256 must contain exactly 64 hexadecimal characters")
    if args.output.exists():
        parser.error("--output already exists; use a fresh directory to prevent mixed evidence")
    args.output.mkdir(parents=True, exist_ok=False)
    runner = Runner(args)
    try:
        runner.execute()
    except KeyboardInterrupt:
        runner.record_failure(GateError("interrupted", "INTERRUPTED"))
    except Exception as exc:
        runner.record_failure(exc)
    finally:
        runner.state["test_finished_utc"] = utc_now()
        runner.save()
        try:
            runner.final_evidence()
        except Exception as exc:
            runner.state["final_evidence_error"] = f"{type(exc).__name__}: {exc}"
            if runner.state["status"] == PASS:
                runner.record_failure(exc)
        runner.state["finished_utc"] = utc_now()
        runner.save()
        print(json.dumps(runner.state, ensure_ascii=False, indent=2), flush=True)
    return 0 if runner.state["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
