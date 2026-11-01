"""Host-only parser regressions. Synthetic text is not an Android execution.

One grammar positive control prevents an always-failing validator from passing
this suite. Negative cases cover the concrete false-success risks in the donor.
"""
import unittest
from validate_selftest import validate

PREFIX = "11-01 13:00:00.000  1234  1256 I KaM     : "
MESSAGES = [
    "KAMTEST BEGIN mode=only:tutorials/battle tutorial",
    "KAMTEST items=1",
    "KAMTEST START 1/1 Tutorials/Battle Tutorial",
    "KAMTEST OK   1/1 Tutorials/Battle Tutorial (200 ticks, 600 ms)",
    "KAMTEST DONE passed=1 failed=0",
]


def trace(messages):
    return "\n".join(PREFIX + message for message in messages) + "\n"


class StrictParserTests(unittest.TestCase):
    def test_synthetic_grammar_positive_control_has_limited_scope(self):
        result = validate(trace(MESSAGES), expected_pid=1234)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["tick_call_count"], 200)
        self.assertFalse(result["simulation_tick_advance_confirmed"])
        self.assertFalse(result["playable_confirmed"])
        self.assertFalse(result["freshness_confirmed_by_parser"])

    def test_negative_fixtures(self):
        valid = trace(MESSAGES)
        fixtures = {
            "empty": "",
            "zero_items": trace([MESSAGES[0], "KAMTEST items=0", "KAMTEST DONE passed=0 failed=0"]),
            "incomplete": trace(MESSAGES[:-1]),
            "missing_start": trace(MESSAGES[:2] + MESSAGES[3:]),
            "duplicate_run": valid + valid,
            "wrong_map": valid.replace("Tutorials/Battle Tutorial", "Maps/Wrong Map"),
            "wrong_mode": valid.replace("only:tutorials/battle tutorial", "all"),
            "early_end": valid.replace("200 ticks", "199 ticks"),
            "extra_calls": valid.replace("200 ticks", "201 ticks"),
            "wrong_index": valid.replace("START 1/1", "START 2/1"),
            "ok_before_start": trace(MESSAGES[:2] + [MESSAGES[3], MESSAGES[2], MESSAGES[4]]),
            "event_after_done": trace(MESSAGES[:3] + [MESSAGES[4], MESSAGES[3]]),
            "items_after_start": trace([MESSAGES[0], MESSAGES[2], MESSAGES[1], *MESSAGES[3:]]),
            "failure": valid + PREFIX + "KAMTEST FAIL 1/1 Tutorials/Battle Tutorial: error\n",
            "fatal_before_begin": "FATAL EXCEPTION: main\n" + valid,
            "fatal_after_done": valid + "Fatal signal 11 (SIGSEGV)\n",
            "save_error_after_done": valid + PREFIX + "KAMTEST can't save results: error\n",
            "mixed_pid": valid.replace(PREFIX + MESSAGES[3], PREFIX.replace("1234", "9999") + MESSAGES[3]),
            "wrong_tag": valid.replace("I KaM     :", "I Other   :"),
            "unframed_summary": "\n".join(MESSAGES),
            "malformed_done": valid.replace("failed=0", "failed=0 extra"),
        }
        for name, text in fixtures.items():
            with self.subTest(fixture=name):
                result = validate(text)
                self.assertEqual(result["status"], "FAIL", name)
                self.assertTrue(result["errors"], name)
                self.assertIsNone(result["tick_call_count"], name)

    def test_pid_identity_mismatch_is_not_accepted(self):
        self.assertEqual(validate(trace(MESSAGES), expected_pid=9999)["status"], "FAIL")


if __name__ == "__main__":
    unittest.main(verbosity=2)
