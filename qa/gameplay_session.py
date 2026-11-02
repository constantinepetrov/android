#!/usr/bin/env python3
"""Bounded, command-driven observations on the existing disposable KaM device.

Only the fixed GitHub command file is polled. Commands are a strict allowlist;
there is no remote shell, arbitrary URL or credential output. Completion means
the requested observation session ended, never that the build is playable.
"""
import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request

from android_cloud_qa import DATA, PACKAGE, GateError, Runner, utc_now
from validate_selftest import fatal_lines

REPOSITORY = "constantinepetrov/android"
COMMAND_PATH = "qa/gameplay-command.json"
COMMAND_URL = ("https://api.github.com/repos/" + REPOSITORY + "/contents/" + COMMAND_PATH
               + "?ref=codex%2Fkam-cloud-qa")
MAX_RESPONSE = 64 * 1024
SAVES = DATA + "/Saves"
SAFE_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
KEYS = {"KEYCODE_" + key for key in ("ENTER", "ESCAPE", "BACK", "SPACE", "P", "DEL", "MOVE_END", "MOVE_HOME",
        "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT", *("F" + str(i) for i in range(1, 13)))}


class SessionError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def need(value, code):
    if not value:
        raise SessionError(code)


def integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "duplicate_json_key")
            result[key] = value
        return result
    def bad_constant(value):
        raise SessionError("invalid_json_constant")
    return json.loads(data, object_pairs_hook=pairs, parse_constant=bad_constant)


def validate_command(value, identity, next_step):
    fields = {"schema_version", "request_id", "github_run_id", "github_run_attempt", "step", "action", "wait_seconds", "label"}
    need(isinstance(value, dict) and set(value) == fields, "command_fields")
    need(type(value["schema_version"]) is int and value["schema_version"] == 1, "command_schema")
    for key in ("request_id", "github_run_id", "github_run_attempt"):
        need(isinstance(value[key], str), "command_identity_type")
    if any(value[key] != identity[key] for key in identity):
        return None
    need(integer(value["step"], 1, 30), "command_step")
    if value["step"] != next_step:
        return None
    wait = value["wait_seconds"]
    need(type(wait) in (int, float) and math.isfinite(wait) and 0 <= wait <= 90, "command_wait")
    need(isinstance(value["label"], str) and SAFE_LABEL.fullmatch(value["label"]), "command_label")
    action = value["action"]
    need(isinstance(action, dict) and isinstance(action.get("type"), str), "command_action")
    kind = action["type"]
    if kind == "tap":
        need(set(action) == {"type", "x", "y"}, "tap_fields")
        need(integer(action["x"], 0, 1279) and integer(action["y"], 0, 719), "tap_coordinates")
    elif kind == "swipe":
        need(set(action) == {"type", "x1", "y1", "x2", "y2", "duration_ms"}, "swipe_fields")
        need(all(integer(action[key], 0, 1279) for key in ("x1", "x2")) and
             all(integer(action[key], 0, 719) for key in ("y1", "y2")) and
             integer(action["duration_ms"], 50, 2000), "swipe_bounds")
    elif kind == "key":
        need(set(action) in ({"type", "key"}, {"type", "key", "repeat"}) and action["key"] in KEYS,
             "key_allowlist")
        need(integer(action.get("repeat", 1), 1, 64), "key_repeat")
    elif kind == "text":
        need(set(action) in ({"type", "text"}, {"type", "text", "replace"}), "text_fields")
        need(isinstance(action["text"], str) and re.fullmatch(r"[A-Za-z0-9]{1,32}", action["text"]), "text_allowlist")
        need(type(action.get("replace", False)) is bool, "text_replace")
    else:
        need(kind in {"wait", "finish"} and set(action) == {"type"}, "action_allowlist")
    return value


def parse_save_header(data):
    """Decode the pinned donor's uncompressed header, not the compressed body.

    SaveGameToStream assigns GameInfo.TickCount := fParams.Tick. The revision
    string is recorded rather than guessed from the installer/menu version.
    """
    need(len(data) >= 14 and data[0] == 1 and data[1:3] == b"\x06\x00" and
         data[3:9] == b"Header" and data[9] == 0, "save_header_prefix")
    header_size = struct.unpack_from("<I", data, 10)[0]
    position, bound = 14, min(len(data), 14 + header_size)

    def read(size):
        nonlocal position
        need(position + size <= bound, "save_header_bounds")
        result = data[position:position + size]
        position += size
        return result

    def read_a():
        size = struct.unpack("<H", read(2))[0]
        return read(size).decode("ascii")

    need(read_a() == "KaM_GameInfo", "save_header_game_info")
    revision = read_a()
    read(12)  # DATCRC, MapFullCRC, MapSimpleCRC.
    title_units = struct.unpack("<H", read(2))[0]
    title = read(2 * title_units).decode("utf-16le")
    tick_offset = position
    ticks = struct.unpack("<I", read(4))[0]
    return {"revision": revision, "title": title, "realTickCount": ticks,
            "tick_count": ticks, "tick_offset": tick_offset, "header_bytes": header_size,
            "source": "save GameInfo.TickCount copied from game Params.Tick"}


class SessionRunner(Runner):
    """Reuse bounded ADB/screenshot/logcat methods, never Runner.execute()."""
    def __init__(self, output, serial, deadline):
        self.out, self.serial, self.deadline = output, serial, deadline
        self.out.mkdir(parents=True, exist_ok=False)
        self.adb = shutil.which("adb") or "adb"
        self.commands = []
        self.state = {"scope": "Interactive UI observation only", "status": "RUNNING",
                      "playable_confirmed": False, "simulation_tick_advance_confirmed": False,
                      "airtest_snapshot_confirmed": False}

    def command(self, label, command, timeout=20):
        remaining = self.deadline - time.monotonic()
        need(remaining >= 0.05, "session_deadline")
        timeout = min(timeout, remaining, 30 if label.endswith("-airtest") else timeout)
        return super().command(label, command, timeout)

    def private_header(self, remote):
        """Keep save bytes in memory; only parsed metadata is public evidence."""
        argv = [self.adb, "-s", self.serial, "exec-out", "head -c 4096 " + shlex.quote(remote)]
        remaining = self.deadline - time.monotonic()
        need(remaining >= 0.05, "session_deadline")
        started = time.monotonic()
        result = subprocess.run(argv, capture_output=True, timeout=min(10, remaining))
        self.commands.append({"name": "read-private-save-header", "argv": argv,
                              "returncode": result.returncode, "stdout_bytes": len(result.stdout),
                              "raw_stdout_retained": False, "stderr_bytes": len(result.stderr),
                              "elapsed_seconds": round(time.monotonic() - started, 3)})
        self.write_json("commands.json", self.commands)
        need(result.returncode == 0 and len(result.stdout) <= 4096, "save_header_read")
        return parse_save_header(result.stdout)


class Session:
    def __init__(self, args):
        self.args, self.out = args, args.output.resolve()
        self.deadline = time.monotonic() + args.timeout
        self.identity = {"request_id": args.request_id, "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
                         "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "")}
        need(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY and os.environ.get("GH_TOKEN"), "github_context")
        need(all(re.fullmatch(r"[1-9][0-9]*", self.identity[key]) for key in ("github_run_id", "github_run_attempt")), "run_identity")
        need(not self.out.exists(), "output_already_exists")
        self.out.mkdir(parents=True)
        self.opener = urllib.request.build_opener(NoRedirect())
        self.state = {"schema_version": 1, **self.identity, "status": "RUNNING", "started_utc": utc_now(),
                      "timeout_seconds": args.timeout, "max_steps": 30, "artifacts": [],
                      "playable_confirmed": False, "simulation_tick_advance_confirmed": False,
                      "scope": "Recorded actions and observations; gameplay conclusions require review"}
        self.pid_value, self.engine_path, self.runner, self.sequence = None, None, None, 0
        self.save()

    def save(self):
        target = self.out / "session-status.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, indent=2, ensure_ascii=False) + "\n")
        temporary.replace(target)

    def new_step(self, sequence):
        self.sequence = sequence
        self.runner = SessionRunner(self.out / "steps" / f"step-{sequence:03d}", self.args.serial, self.deadline)
        return self.runner

    def start_game(self, runner):
        runner.checked("session-force-stop", ["shell", "am", "force-stop", PACKAGE])
        old = {}
        for _, filename in runner.engine_files():
            old[filename] = runner.checked("old-native-log", ["shell", "cat " + shlex.quote(filename)])
        runner.clean_logcat()  # Exactly once, before the new normal launch.
        epoch = runner.checked("launch-guest-epoch", ["shell", "date", "+%s"]).strip()
        need(epoch.isdigit(), "guest_launch_epoch")
        launch_epoch = int(epoch)
        launch = runner.checked("session-normal-launch", ["shell", "am", "start", "-W", "-n", PACKAGE + "/.KaMActivity"], 45)
        need(re.search(r"(?m)^Status:\s*ok\s*$", launch), "normal_launch")
        self.pid_value = runner.pid()
        deadline = min(self.deadline, time.monotonic() + 90)
        while time.monotonic() < deadline:
            runner.pid(expected=self.pid_value)
            for modified, filename in sorted(runner.engine_files(), reverse=True):
                if modified < launch_epoch:
                    continue
                text = runner.checked("fresh-native-log", ["shell", "cat " + shlex.quote(filename)])
                before = old.get(filename, "")
                fresh = text[len(before):] if before and text.startswith(before) else text
                if "Game Load Done in" in fresh:
                    self.engine_path = filename
                    self.state.update(pid=self.pid_value, native_log=filename,
                                      new_session_logcat_clear_confirmed=True, guest_launch_epoch=launch_epoch)
                    self.save()
                    return
            time.sleep(min(1, max(0, deadline - time.monotonic())))
        raise SessionError("normal_engine_start_deadline")

    def save_inventory(self, runner):
        exists = runner.adb_command("save-directory", ["shell", "test -d " + shlex.quote(SAVES)], 10)
        if exists[0] == 1:
            return {"files": [], "count": 0, "directory_exists": False}
        need(exists[0] == 0, "save_directory_read")
        text = runner.checked("save-files", ["shell", "find " + shlex.quote(SAVES) + " -maxdepth 2 -type f -name '*.sav'"], 10)
        paths = sorted(set(text.splitlines()))
        rows = []
        for filename in paths[:20]:
            relative = PurePosixPath(filename).relative_to(PurePosixPath(SAVES))
            need(filename.startswith(SAVES + "/") and ".." not in relative.parts and
                 filename.endswith(".sav") and not any(ord(char) < 32 for char in filename), "save_path_scope")
            before = runner.checked("save-stat-before", ["shell", "stat -c '%s %Y' " + shlex.quote(filename)], 10).strip()
            fields = before.split()
            need(len(fields) == 2 and all(field.isdigit() for field in fields), "save_stat")
            sha = runner.checked("save-sha256", ["shell", "sha256sum " + shlex.quote(filename)], 20).split()[0]
            need(re.fullmatch(r"[0-9a-f]{64}", sha), "save_sha256")
            try:
                header = runner.private_header(filename)
                header["header_parsed"] = True
            except (SessionError, UnicodeError, struct.error) as exc:
                # A concurrent autosave or older-format save is an observation
                # error for this file, never an invented tick count or proof.
                code = str(exc) if isinstance(exc, SessionError) and re.fullmatch(r"[a-z_]+", str(exc)) else type(exc).__name__
                header = {"header_parsed": False, "parse_error": code}
            after = runner.checked("save-stat-after", ["shell", "stat -c '%s %Y' " + shlex.quote(filename)], 10).strip()
            rows.append({"path": filename, "size_bytes": int(fields[0]), "mtime": int(fields[1]),
                         "sha256": sha, "stable_read": before == after, **header})
        return {"files": rows, "count": len(paths), "sampled_count": len(rows), "limit": 20}

    def observe(self, runner, command):
        runner.write_json("command.json", command)
        screenshot = runner.screenshot("screen")
        need(screenshot.get("available") and screenshot.get("dimensions") == [1280, 720], "observation_screenshot")
        pid = runner.pid(expected=self.pid_value)
        code, logs = runner.logcat("session-logcat", 20)
        need(code == 0, "observation_logcat_incomplete")
        need(not fatal_lines(logs), "observation_fatal_marker")
        files = runner.engine_files()
        if files:
            self.engine_path = max(files)[1]
        need(self.engine_path is not None, "observation_native_log_missing")
        native = runner.checked("current-native-log", ["shell", "cat " + shlex.quote(self.engine_path)], 15)
        (runner.out / "game-native.log").write_text(native)
        saves = self.save_inventory(runner)
        runner.write_json("save-inventory.json", saves)
        runner.write_json("observation.json", {"schema_version": 1, **self.identity, "step": self.sequence,
            "observed_utc": utc_now(), "pid": pid, "screenshot": screenshot,
            "native_log_path": self.engine_path, "saves": saves,
            "playable_confirmed": False, "simulation_tick_advance_confirmed": False})
        runner.state["status"] = "OBSERVATION_CAPTURED"
        runner.save()

    def upload(self, runner):
        helper = Path(__file__).resolve().parent / "input-relay/upload-evidence.cjs"
        code, stdout, _ = runner.command("upload-ui-evidence", ["node", str(helper), str(runner.out), str(self.sequence)], 120)
        need(code == 0, "evidence_upload")
        response = strict_json(stdout.decode("utf-8"))
        expected_name = "kam-ui-" + self.identity["github_run_id"] + "-" + self.identity["github_run_attempt"] + "-" + str(self.sequence)
        need(response.get("status") == "UI_EVIDENCE_UPLOADED" and response.get("artifact_name") == expected_name
             and integer(response.get("artifact_id"), 1, 2**53 - 1), "evidence_upload_response")
        runner.write_json("upload-result.json", response)
        self.state["artifacts"].append({"step": self.sequence, **response})
        self.state["next_step"] = self.sequence + 1
        self.save()
        print(json.dumps({"status": "UI_OBSERVATION_READY", "step": self.sequence,
                          "artifact_id": response["artifact_id"], "artifact_name": expected_name}), flush=True)

    def fetch_command(self, next_step):
        remaining = self.deadline - time.monotonic()
        need(remaining > 0, "session_deadline")
        request = urllib.request.Request(COMMAND_URL, headers={"Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + os.environ["GH_TOKEN"], "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "KaMCloudQA-UI/1.0", "Accept-Encoding": "identity", "Cache-Control": "no-cache"})
        try:
            with self.opener.open(request, timeout=min(10, remaining)) as response:
                need(response.status == 200 and response.headers.get("Content-Encoding", "identity") == "identity", "command_response")
                raw = response.read(MAX_RESPONSE + 1)
            need(0 < len(raw) <= MAX_RESPONSE, "command_response_size")
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
            if status in (404, 408, 429, 500, 502, 503, 504):
                return None
            raise SessionError("command_http_error") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            return None
        envelope = strict_json(raw.decode("utf-8"))
        need(envelope.get("type") == "file" and envelope.get("path") == COMMAND_PATH and
             envelope.get("encoding") == "base64" and integer(envelope.get("size"), 1, 8192), "command_envelope")
        encoded = envelope.get("content")
        need(isinstance(encoded, str) and len(encoded) <= 16384, "command_envelope_content")
        content = base64.b64decode(encoded.replace("\n", "").replace("\r", ""), validate=True)
        need(len(content) == envelope["size"], "command_content_size")
        return validate_command(strict_json(content.decode("utf-8")), self.identity, next_step)

    def act(self, runner, action):
        kind = action["type"]
        if kind == "tap":
            runner.checked("ui-tap", ["shell", "input", "tap", str(action["x"]), str(action["y"])])
        elif kind == "swipe":
            runner.checked("ui-swipe", ["shell", "input", "swipe", *[str(action[key]) for key in ("x1", "y1", "x2", "y2", "duration_ms")]])
        elif kind == "key":
            runner.checked("ui-key", ["shell", "input", "keyevent", *([action["key"]] * action.get("repeat", 1))])
        elif kind == "text":
            if action.get("replace", False):
                runner.checked("ui-text-end", ["shell", "input", "keyevent", "KEYCODE_MOVE_END"])
                runner.checked("ui-text-clear", ["shell", "input", "keyevent", *(["KEYCODE_DEL"] * 64)])
            runner.checked("ui-text", ["shell", "input", "text", action["text"]])

    def run(self):
        runner = self.new_step(0)
        self.start_game(runner)
        self.observe(runner, {"step": 0, "label": "initial", "action": {"type": "normal_launch"}})
        self.upload(runner)
        for step in range(1, 31):
            command = None
            while command is None:
                command = self.fetch_command(step)
                if command is None:
                    time.sleep(min(3, max(0, self.deadline - time.monotonic())))
            runner = self.new_step(step)
            runner.write_json("command.json", command)
            self.act(runner, command["action"])
            remaining = self.deadline - time.monotonic()
            need(command["wait_seconds"] < remaining, "session_deadline")
            time.sleep(command["wait_seconds"])
            self.observe(runner, command)
            self.upload(runner)
            if command["action"]["type"] == "finish":
                self.state.update(status="COMPLETED", completed_steps=step, finished_utc=utc_now())
                self.save()
                return
        raise SessionError("session_step_limit_without_finish")

    def failed(self, error):
        # Preserve only a controlled code or exception type, never request text,
        # headers, credentials, raw exception messages or tracebacks.
        code = str(error) if isinstance(error, SessionError) and re.fullmatch(r"[a-z_]+", str(error)) else type(error).__name__
        self.state.update(status="FAIL", reason=code, failed_step=self.sequence, finished_utc=utc_now())
        if self.runner and self.deadline - time.monotonic() > 2:
            try:
                self.runner.state["failure_screenshot"] = self.runner.screenshot("failure-screen")
                self.runner.logcat("failure-logcat", min(10, self.deadline - time.monotonic()))
            except Exception:
                self.runner.state["failure_capture_incomplete"] = True
            self.runner.state["status"] = "FAIL"
            self.runner.save()
        self.save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enabled", choices=("true", "false"), default="false")
    parser.add_argument("--serial", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    if args.enabled == "false":
        print(json.dumps({"status": "UI_SESSION_DISABLED", "gameplay_actions_run": False}))
        return 0
    if not 1 <= args.timeout <= 1200 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", args.request_id):
        parser.error("Invalid bounded timeout or request identifier")
    session = None
    old_handler = None
    try:
        session = Session(args)
        def alarm(signum, frame):
            raise SessionError("session_deadline")
        old_handler = signal.signal(signal.SIGALRM, alarm)
        signal.setitimer(signal.ITIMER_REAL, args.timeout)
        session.run()
        return 0
    except Exception as exc:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if session is not None:
            session.failed(exc)
        print(json.dumps({"status": "UI_SESSION_FAILED", "playable_confirmed": False}), flush=True)
        return 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if old_handler is not None:
            signal.signal(signal.SIGALRM, old_handler)


if __name__ == "__main__":
    raise SystemExit(main())
