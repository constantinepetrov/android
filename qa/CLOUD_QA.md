# Isolated cloud QA for the pinned KaM Android APK

This branch runs one bounded Android check before the APK is offered for user playtesting. It does not merge or update PR #1, and it does not change the master branch.

## Trigger and environment

Only a push to `codex/kam-cloud-qa` that changes `qa/run-request.json` requests a run. There is no pull-request, scheduled, or matrix trigger. A separate `workflow_dispatch` entry point on master is not required. Normal edits to the scripts or documentation do not trigger another run.

The workflow uses the standard GitHub-hosted Ubuntu 24.04 runner and KVM. It explicitly requires `-accel on`; a software-only TCG fallback is not accepted. Android API 35 Google APIs x86_64 is used, and the runner checks that ARM64 is advertised and a native bridge is configured before transferring the APK.

This is Android runtime with ARM64 translation, not a physical ARM64 compatibility or performance result.

The entire job is bounded to 65 minutes, including up to 14 minutes for preparation, 32 minutes for emulator setup/checks, and 3 minutes for uploading evidence. These are failure ceilings, not an estimate of normal duration. Every dependency action is pinned to a full commit SHA. The job has only `contents: read` permissions; checkout credentials are not retained.

## Exact artifact identity

- Package: `org.kamremake.android`
- Version: `1.0-r16397`
- APK size: 856,629,249 bytes
- APK SHA-256: `c7df4b880984b9a475b57ee00b41fa5ba6140f4c21e5f688a9188ab1622169c4`
- Source snapshot: donor `e81c3b765a13d730140c26159eab4506499d44e6` plus the recorded Linux build, bundled data and PascalScript changes, corresponding to local main-repository commit `c9214fd1451ac264d9bfc1b851b7b9360ab9eb52`.

This tests the existing donor-based APK. It does not claim that all earlier local changes in the separate porting series are merged into this APK.

The repository carries approximately 30 MB of compressed non-game-payload bytes, divided into 58 independently hashed parts, plus a reconstruction recipe. Game payloads are downloaded by the runner from the official installer and are not committed here. Private signing keys are not required or included.

The official installer is hash-checked and extracted with `innoextract`, never executed. Reconstruction checks all 8,885 unique asset payloads and the complete signed APK. The installed device file is checked again. A different APK cannot silently pass as this build.

See [reconstruction details](reconstruction/README.md), [corresponding source](reconstruction/source-provenance.json), [file roundtrip evidence](reconstruction/local-validation.json), and [negative reconstruction checks](reconstruction/negative-validation.json).

## Result stages

1. Host input preparation: exact APK restored.
2. Android readiness: boot, Package Manager, unlocked user, stable system_server and successful storage write/read/delete.
3. APK install: local, transferred and installed APK SHA-256 agree.
4. First launch: only KaM app data is cleared; a fresh copy-completion marker and fresh native-engine log are required.
5. Visual evidence: Airtest obtains a PNG, with a separately labelled raw-ADB fallback if needed.
6. Native content smoke: exactly one Battle Tutorial item and 200 calls of the update path are required by the strict log parser.

The strongest automatic result is `AUTOMATED_CONTENT_SMOKE_PASS`. It deliberately retains:

```json
{
  "menu_review": "PENDING",
  "controls_review": "NOT_RUN",
  "playable_confirmed": false,
  "simulation_tick_advance_confirmed": false
}
```

The donor's “200 ticks” text counts calls to `DoGameTick`. It does not measure the exact change in `Params.Tick`. Screenshots must be visually reviewed before declaring the menu correct. Touch controls, building, save/load and audible sound need separate gameplay scenarios. The emulator is started without an audio output device, so this run cannot confirm audible playback.

A fatal marker from another Android process can conservatively fail the check. The process and surrounding log lines must be inspected before attributing that failure to KaM.

## Evidence and local validation

The workflow captures its diagnostics before the emulator action shuts down the device. It uploads JSON status/commands, logs and PNG screenshots with seven-day retention. The APK, official installer, extracted game data and AVD are excluded.

Local validation is distinct from cloud execution:

- Airtest 1.4.3 and pinned dependencies were installed and checked on the host.
- The strict parser has negative fixtures for incomplete, duplicated, stale/ambiguous and wrong-item runs. Synthetic fixtures are only parser checks.
- The reconstruction produced a new file with the exact APK SHA, followed by an independent file hash.
- `actionlint 1.7.12`, YAML/shell syntax and Python CLI/syntax checks passed.
- [Host results](host-check/results.json) and [workflow validation](host-check/workflow-validation.json) record the checked code hashes and commands.

Actual cloud status must be read from the GitHub run associated with the published QA commit and its artifacts; these local checks are not an Android PASS.

## Primary infrastructure references

- https://github.com/ReactiveCircus/android-emulator-runner
- https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- https://docs.github.com/en/billing/concepts/product-billing/github-actions
- https://airtest.readthedocs.io/en/latest/README_MORE.html
- https://constexpr.org/innoextract/innoextract.1

Standard GitHub-hosted compute in public repositories is free according to the cited GitHub documentation; artifact storage has separate allowances. This workflow requests no paid device farm or larger runner.

