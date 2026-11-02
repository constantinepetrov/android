# Isolated cloud QA for the pinned KaM Android APK

This branch runs one bounded Android check before the APK is offered for user playtesting. It does not merge or update PR #1, and it does not change the master branch.

## Trigger and environment

Only a push to `codex/kam-cloud-qa` that changes `qa/run-request.json` requests a run. There is no pull-request, scheduled, or matrix trigger. A separate `workflow_dispatch` entry point on master is not required. Normal edits to the scripts or documentation do not trigger another run.

The request's `mode` selects `full` (the default) or `readiness-only`. The latter explicitly skips input fetch and all game checks; a green readiness-only run is never evidence that KaM launched. The initial scope job validates this field before starting either path.

The workflow uses the standard GitHub-hosted Ubuntu 24.04 runner and KVM. It explicitly requires `-accel on`; a software-only TCG fallback is not accepted. Android API 35 Google APIs x86_64 is used, and the runner checks that ARM64 is advertised and a native bridge is configured before transferring the APK.

This is Android runtime with ARM64 translation, not a physical ARM64 compatibility or performance result.

The game-check job is bounded to 75 minutes, including up to 14 minutes for preparation, 32 minutes for emulator setup/checks, and 3 minutes for uploading evidence. These are failure ceilings, not an estimate of normal duration. Every dependency action is pinned to a full commit SHA. Checkout credentials are not retained.

### Network recovery and independent device probe

Real Ubuntu runs [41333826307](https://github.com/constantinepetrov/android/actions/runs/41333826307) and [41334600832](https://github.com/constantinepetrov/android/actions/runs/41334600832) failed before Android setup. The second run resolved `www.kamremake.com` to `51.77.64.109`, but three bounded IPv4 connection attempts to port 443 timed out, each after about 20 seconds, with zero downloaded bytes. This is an input-network failure, not a KaM failure.

The `input_source: official` route uses a standard `macos-15` job to download the same pinned official installer through another runner network. Its result must pass the same fixed size and SHA checks. A short-lived artifact transfers that one file to the Ubuntu game-check job, which checks it again before extraction. No game payload is added to Git or a release.

The installer artifact has one-day expiry as a fallback. A separate cleanup job normally deletes it after the consumer finishes, even if the game check fails. Only that cleanup job has `actions: write`; before deletion it verifies the exact artifact ID, expected name and current workflow run ID. Other jobs retain only `contents: read`. Temporary artifact storage is subject to the account's existing allowances; public standard compute does not imply unlimited storage.

For `mode: readiness-only`, `qa/probe_android.py` boots no game and requires no APK. It reuses the readiness gates and captures a genuine Airtest PNG. Its strongest result, `ANDROID_READINESS_PROBE_PASS`, confirms sampled Android readiness and screenshot capture only. Advertised ARM64 translation remains unproven until real ARM64 game code runs. The probe has its own 35-minute job; installer fetch has a 30-minute job and cleanup a 3-minute job.

Run [41335488254](https://github.com/constantinepetrov/android/actions/runs/41335488254) reached that real probe PASS: three stable samples, working storage, API 35 ARM64/native-bridge advertisement, and an Airtest screenshot. Its emulator action still reported failure because the earlier plain version query selected the GUI binary, which required missing `libpulse.so.0`. The diagnostic command now uses `-no-window -no-audio -version`, matching the headless runtime. No error suppression or blanket `continue-on-error` was added. The macOS input job independently reproduced three connection timeouts; no installer-transfer artifact was created.

## Exact artifact identity

### Official alternate download route (2026-11-02)

The authors' [download page](https://www.kamremake.com/download/) publishes an
[alternative download](https://release.knightsprovince.com/index.php/s/9xdF69oCWmJXW59)
for the full r16397 installer. Input preparation now uses that alternate host,
as a separate route from the primary host. The subsequent macOS run also timed out on this alternate; the direct relay below is now the requested route.
The alternate names `KaM Remake Beta r16397.exe` and advertises 711,493,971 bytes.
Neither the filename nor a successful HTTP response is sufficient: the existing
installer size/SHA-256 and complete reconstructed APK size/SHA-256 checks remain
mandatory and unchanged. No additional game bytes are committed to Git.

A `mode: full` request runs the existing install/first-launch/Battle Tutorial
checks only after verified input preparation. This route change alone is not evidence
that the game has launched; the linked Actions result and captured runtime evidence
must establish that separately.

### Direct encrypted APK input (2026-11-02)

Run [41398840259](https://github.com/constantinepetrov/android/actions/runs/41398840259)
also timed out connecting to the official alternate host. The `input_source:
relay` route therefore transfers the already saved exact APK without depending
on either download server. It uses the official, pinned `@actions/artifact`
6.3.1 backend and Azure upload client; no Actions or GitHub token leaves the job.

The job issues one temporary blob upload capability, encrypts it and a random
payload key for the operator's RSA public key, and uploads that encrypted
handshake. The private RSA key is kept outside Git. The operator encrypts the
hash-verified APK with AES-256-GCM, uploads a ZIP containing only ciphertext,
and commits a non-secret receipt tied to the exact request, run and attempt.
The same job finalizes the artifact, downloads it with strict ZIP digest checks,
authenticates/decrypts it, and requires the original complete APK size and SHA-256
before any Android commands. The relay has a bounded receipt wait.

Only source, the public transport key, request and receipt enter Git. Payload
keys, decrypted capabilities, signing keys, plaintext APK and game data do not.
The cleanup job validates the current run and exact names before deleting the
temporary encrypted payload and handshake artifacts. One-day retention is a
fallback. Runtime evidence retains the existing seven-day policy.

For `mode: full`, the game job performs its own existing Android readiness gates.
The separate readiness-only job runs only for `mode: readiness-only`.

### First real KaM runtime result

Run [41399865980](https://github.com/constantinepetrov/android/actions/runs/41399865980)
completed the encrypted transfer and exact APK verification, Android readiness,
APK installation (including the installed-file hash), and fresh bundled-data copy.
Its native log reached `Game Load Done in 3892`; Airtest captured the actual main
menu behind Android's first-use fullscreen hint. The engine identifies itself as
`r16398 [UNSECURE]`; the package label/data bundle remain r16397, and the APK is
still the exact previously pinned file, not a new build.

This run remains `BLOCKED`: the first logcat read returned 255 with 8,192 truncated
stdout bytes; the immediately following identical capture succeeded with 1,569,987
bytes and no fatal markers. Battle Tutorial was not run. The tester now retries an
incomplete capture at most three times within the original total deadline, retains
every attempt, and accepts only a successful complete capture. Fatal markers in
partial attempts still fail the check; logs are never cleared during a retry.

Before game installation, the disposable test device is configured and screenshot-
verified at 1280x720 landscape, 160 dpi, with Android's fullscreen hint marked as
acknowledged. This affects the emulator only. The APK and its data are unchanged.

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

The workflow captures its diagnostics before the emulator action shuts down the device. It uploads JSON status/commands, logs and PNG screenshots with seven-day retention. The APK, official installer, extracted game data and AVD are excluded from these evidence archives. The separate temporary installer-transfer artifact described above is deleted after its consumer finishes.

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

