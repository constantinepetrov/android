"""Host-only regression fixtures for bounded logcat reads.

No Android or ADB is contacted. Synthetic subprocess outputs test timeout,
evidence retention and fail-closed behavior; they are not a game runtime PASS.
"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from android_cloud_qa import GateError, Runner


class Clock:
    def __init__(self):
        self.now = 100.0

    def monotonic(self):
        return self.now

    def sleep(self, duration):
        self.now += duration


class FakeProcess:
    def __init__(self, fixture, clock, waits):
        self.returncode, self.stdout, self.stderr, self.duration = fixture
        self.clock, self.waits = clock, waits

    def communicate(self, timeout):
        self.waits.append(timeout)
        self.clock.now += self.duration
        return self.stdout, self.stderr


class LogcatCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runner = object.__new__(Runner)
        self.runner.out = Path(self.temp.name)
        self.runner.adb = "fixture-adb-not-executed"
        self.runner.serial = "fixture-device"
        self.runner.commands = []
        self.runner.state = {}
        self.clock = Clock()
        self.waits, self.argv = [], []

    def capture(self, fixtures, timeout=20):
        pending = iter(fixtures)

        def create_process(argv, **kwargs):
            self.argv.append(argv)
            return FakeProcess(next(pending), self.clock, self.waits)

        with patch("android_cloud_qa.subprocess.Popen", side_effect=create_process), \
                patch("android_cloud_qa.time.monotonic", self.clock.monotonic), \
                patch("android_cloud_qa.time.sleep", self.clock.sleep):
            return self.runner.logcat("fixture-logcat", timeout)

    def test_255_then_complete_preserves_failed_bytes_without_concatenation(self):
        partial = b"11-02 06:31:07.354 1190 1190 I partial line"
        complete = b"11-02 06:31:07.354 1190 1190 I partial line completed\n"
        result = self.capture([(255, partial, b"", 0.094),
                               (0, complete, b"- waiting for device -\n", 0.729)])
        self.assertEqual(result, (0, complete.decode()))
        self.assertEqual((self.runner.out / "fixture-logcat.txt").read_bytes(), complete)
        commands = json.loads((self.runner.out / "commands.json").read_text())
        self.assertEqual(len(commands), 2)
        self.assertEqual((self.runner.out / commands[0]["stdout_file"]).read_bytes(), partial)
        self.assertEqual((self.runner.out / commands[1]["stderr_file"]).read_bytes(), b"- waiting for device -\n")
        self.assertEqual(self.argv[0], self.argv[1])
        self.assertEqual(self.argv[0][3:], ["logcat", "-b", "all", "-d", "-v", "threadtime"])
        summary = self.runner.state["logcat_captures"][-1]
        self.assertEqual(summary["complete_attempt"], 2)
        self.assertTrue(summary["retried"])

    def test_three_failed_reads_never_return_partial_parser_input(self):
        old_alias = self.runner.out / "fixture-logcat.txt"
        old_alias.write_text("old capture must not be mistaken for this invocation")
        result = self.capture([(255, b"part-one", b"first error", 0.1),
                               (255, b"part-two", b"second error", 0.1),
                               (1, b"part-three", b"third error", 0.1)])
        self.assertEqual(result, (1, ""))
        self.assertEqual(len(self.argv), 3)
        self.assertFalse(old_alias.exists())
        for command, expected in zip(self.runner.commands, (b"first error", b"second error", b"third error")):
            self.assertEqual((self.runner.out / command["stderr_file"]).read_bytes(), expected)
        self.assertFalse(self.runner.state["logcat_captures"][-1]["complete"])

    def test_original_timeout_is_shared_and_late_success_is_rejected(self):
        # First command consumes 0.5 s, retry pause 0.25 s, so only 0.25 s
        # remains for the second read. A delayed exit=0 beyond that cannot pass.
        result = self.capture([(255, b"prefix", b"", 0.5),
                               (0, b"late full capture\n", b"", 0.3)], timeout=1)
        self.assertEqual(result, (124, ""))
        self.assertEqual(len(self.argv), 2)
        self.assertAlmostEqual(self.waits[0], 1.0)
        self.assertAlmostEqual(self.waits[1], 0.25)
        self.assertFalse((self.runner.out / "fixture-logcat.txt").exists())
        self.assertTrue(self.runner.state["logcat_captures"][-1]["deadline_exhausted"])

    def test_insufficient_remaining_budget_does_not_start_a_new_process(self):
        result = self.capture([(255, b"prefix", b"", 0.98)], timeout=1)
        self.assertEqual(result, (124, ""))
        self.assertEqual(len(self.argv), 1)
        self.assertAlmostEqual(self.clock.now, 101.0)

    def test_partial_fatal_is_not_lost_when_retry_is_clean(self):
        for channel in ("stdout", "stderr"):
            with self.subTest(channel=channel):
                fatal = b"11-02 06:31:07.354 3649 3649 F libc: Fatal signal 11 (SIGSEGV)\n"
                stdout = fatal if channel == "stdout" else b"partial log"
                stderr = fatal if channel == "stderr" else b""
                with self.assertRaises(GateError) as raised:
                    self.capture([(255, stdout, stderr, 0.1), (0, b"clean full capture\n", b"", 0.1)])
                self.assertEqual(raised.exception.status, "FAIL")
                summary = self.runner.state["logcat_captures"][-1]
                self.assertEqual(summary["status"], "REJECTED_PARTIAL_FATAL")
                self.assertEqual(summary["partial_fatal_markers"][0]["stream"], channel)
                self.assertEqual(summary["partial_fatal_markers"][0]["attempt"], 1)
                self.assertEqual((self.runner.out / "fixture-logcat.txt").read_bytes(), b"clean full capture\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
