# Cloud Android QA runner

`android_cloud_qa.py` operates on an **already running, disposable Android test
device**. It does not start/stop an emulator, configure a cloud service, or use
an LLM API. It clears data only for `org.kamremake.android` to establish a fresh
bundled-data launch. Do not point it at a device containing user saves.

## Invocation

Run with the Python environment containing the pinned Airtest requirements:

```bash
python qa/android_cloud_qa.py \
  --apk /path/to/exact-signed.apk \
  --output /path/to/new-evidence-directory \
  --adb /path/to/android-sdk/platform-tools/adb \
  --serial emulator-5554 \
  --expected-sha256 c7df4b880984b9a475b57ee00b41fa5ba6140f4c21e5f688a9188ab1622169c4
```

`--apk` and `--output` are required. ADB defaults to `adb` from PATH. Without
`--serial`, exactly one online device must be available; multiple devices block
the run. The evidence directory must not already exist. If a workflow has
already created an artifact directory, supply a fresh child such as
`qa-artifacts/runtime`.

The default expected SHA256 is the value above. A different artifact requires
an explicit workflow-pinned `--expected-sha256`; the runner never derives its
expected value from the supplied APK. The hash is checked before contacting
Android, after pushing the APK, and against the installed package APK.

Deadlines can be overridden explicitly:

| Flag | Default seconds | Scope |
| --- | ---: | --- |
| `--readiness-timeout` | 120 | Device selection and three stable readiness probes |
| `--install-timeout` | 240 | Push, guest hash, package install and installed APK hash |
| `--data-timeout` | 300 | Activity launch through the fresh completion marker |
| `--engine-timeout` | 180 | Fresh engine log and live unchanged app PID |
| `--selftest-timeout` | 240 | Selftest launch through timely DONE observation |

Preparation and final evidence collection have separate per-command bounds.
The selftest also has a two-second post-DONE drain and a final bounded logcat
capture. A screenshot attempts Airtest for at most 40 seconds, then an explicitly
labelled ADB fallback for at most 20 seconds. Run the script before the workflow
tears down its emulator so its `finally` captures remain available.

## What each stage means

- **Cloud readiness:** boot complete, working package manager, unlocked user,
  unchanged `system_server` PID across three successful probes, and a successful
  external-storage write/read/delete probe. API 30 or newer and advertised
  ARM64 support are required. An x86 guest must also advertise a meaningful
  native bridge. These properties alone do not prove working ARM64 translation.
- **APK install:** a freshly transferred APK matches the expected SHA and size,
  `pm install` succeeds, and the installed KaM APK has the same SHA.
- **Fresh data:** after clearing only the KaM package, old markers and logs must
  be absent. A new, zero-byte `.kamdata_installed` marker must have a guest mtime
  no older than the launch epoch. This confirms completion of the copy routine,
  not individual asset hash verification.
- **Engine init:** a fresh `KaM_*.log` contains `Game Load Done in`, the process
  stays unchanged, and a complete fresh logcat has no fatal/error marker. This
  does not establish a correct visible menu.
- **Visual evidence:** save and validate a PNG for subsequent review. Airtest
  must report its actual `ADBCAP` backend; an automatic backend substitution
  fails that helper. A separate raw-ADB fallback is explicitly recorded as
  `adb-screencap-fallback`, never as successful Airtest capture.
- **Content smoke:** independently relaunch with `kam_selftest` set to
  `only:tutorials/battle tutorial`. Require exactly one native KaM process's
  BEGIN/items/START/OK/DONE sequence, exactly the expected map, exactly 200
  update calls, and `passed=1 failed=0`. Zero items, early mission termination,
  incomplete/mixed runs and fatal errors before BEGIN or after DONE fail.

The counter in the donor increments around `gGameApp.DoGameTick`, which calls
`gGame.UpdateGame`. It is not a measured `Params.Tick` delta. Consequently the
result always keeps `simulation_tick_advance_confirmed=false`.

Exit code 0 means **`AUTOMATED_CONTENT_SMOKE_PASS`**, with
`tick_call_count=200`. It never means an accepted playable build:

```json
{
  "menu_review": "PENDING",
  "controls_review": "NOT_RUN",
  "playable_confirmed": false,
  "simulation_tick_advance_confirmed": false
}
```

Building/delivery, saves, sound and manual controls remain untested. No menu taps
are guessed. A normal app exit after native DONE is expected and does not fail
the test. Early disappearance, a process change, a missed deadline or an
incomplete final log capture cannot become PASS.

## Evidence and freshness

`status.json` preserves independent stage results and limitations. `commands.json`
contains exact argv, timestamps, return codes and separate stdout/stderr files.
Readiness probes, APK identity, Android properties, first-launch engine log,
full-buffer logcat, screenshots and strict selftest validation are retained.
The final screenshot may show Android after the normal selftest exit; use
`engine-ready-screen.png` for the earlier engine/menu visual review.

The runner establishes freshness by successful force-stop/logcat clear, clearing
the KaM app's data for first launch, pre-launch absence checks, guest-clock file
timestamps and stable PID observations. `validate_selftest.py` alone can validate
log structure and PID identity but cannot prove when a supplied log was captured.
Fatal markers in the full device log are treated conservatively and require
manual attribution if they came from another process.

## Host checks only

```bash
python -B -m unittest discover -s qa -p test_validate_selftest.py -v
python -B qa/android_cloud_qa.py --help
python -B qa/validate_selftest.py --help
python -B qa/airtest_snapshot.py --help
```

`test_validate_selftest.py` contains 21 negative text fixtures plus a PID mismatch
case. A single explicitly synthetic grammar-positive control prevents an
always-failing parser from appearing correct. None of these fixtures mock a
successful Android runtime, contact ADB, or execute the game.

The recorded local checks are under `host-check/`. Their PASS concerns syntax,
CLI argument parsing and synthetic log validation only. Actual Android testing
is performed only by a separately authorised invocation of the runner.
