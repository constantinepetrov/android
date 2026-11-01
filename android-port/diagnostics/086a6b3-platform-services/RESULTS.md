# Native services slice: economical CI, clipboard, music — 2026-11-01

## Published source and compile identity

Implementation commit: d0b6cb93227999b9a3f6bb914fc22968e2d6d9eb.
Actual final compile checkout: 086a6b3f98032a7addae166f0f2cfd47491b72b8.
Tree: 52d8b37ddefd47a377ea0fb7cd90c1106c3252a5. Checkout clean during and after the compile/test run.
The later reviewed CI-scope adjustment and this evidence do not change game/native source files.

This is standalone CLOUD Linux FPC 3.2.2 Android AArch64 compile-only evidence, NOT a GitHub Actions run or Android runtime.
The already prepared toolchain was reused: FPC source 0d122c49534b480be9284c21bd60b53d99904346;
Lazarus 9d15c73c91a1545be50bee02b27bd3b43f9d90e8; Pascal Script submodule ce8590dd7b9cf48fd0e446731989603e09e239b8.
The checked-in overlay generator ran again on that submodule outside the checkout. Full flags, SHA/tree,
generator SHA256, commands, unit traces and toolchain provenance are in [logs.tar.gz](logs.tar.gz).
The standalone compiler wrapper retains explicit -Sc; diagnostics preserve the existing DBG_SKIP_SECURE_AUTH
compile option for the absent upstream auth unit. No NO_MUSIC define was used.

## CI economy

- Main automatic compilation uses PR events only; push duplication removed.
- Source paths retain src/**, KaM_Remake.inc, relevant Pascal/test/build paths; diagnostics/docs excluded.
- A lightweight source-scope job compares the event-before SHA for synchronize updates. A docs-only
  update does not launch heavy compilation, even when the cumulative PR diff contains code.
  Missing comparison data retains compilation, never silently suppresses it.
- Cancellation is scoped to the compilation job with a workflow/PR-specific group. A docs-only update
  cannot cancel the preceding code compilation; the cheap scope job itself is not cancellation-grouped.
- Host/FFI emulation runs only on the explicit android-runtime label for a finished slice.
- Native ARM64 provisioning is opt-in via android-native-arm64-diagnostic or a future available dispatch
  input, default false. Other historic diagnostic workflows are no longer push-triggered.
- Manual dispatch is not promised while workflow files are absent on master. Actions remains paused
  by GitHub's fork-usage restriction; no re-enable attempts, PR reopenings or empty commits were made.
- Toolchain cache keys identify FPC source revision/target/runner version. PS overlay is generated,
  not cached as an unversioned runtime patch.
- Baseline repeats only KM_Game, not the complete target list or an emulator.
- trace[@] now reaches FPC. Expanded commands and checkout SHA/tree/target are logged.
- actionlint 1.7.7 passes. Scope tests pass for docs-only=false, code=true,
  missing comparison=true and explicit dispatch=true.

## Implemented boundaries

Audio session query: KM_Sound's direct Android dependency on KM_Game for ReadyToStop was replaced by
a session-owned query, bound/unbound by the original TKMGame lifetime. No-session, active, stopping
and stale-owner unbinding are tested. Desktop retains its original gGame check. Other sound/spectator
dependencies remain and are visible in the compiler trace.

Music: Android selects KM_BassAndroid instead of the Windows Bass unit. This dynamically loads the
real libbass.so and verifies BASS 2.4 plus all required exports before use. C calling convention,
32-bit BOOL/handles, 64-bit file offsets and Single parameters are explicit. File paths are UTF-8;
the desktop binding/path is preserved. Playback state, IsEnded, IsOtherEnded and fade decisions still
use actual backend results. Missing library/version/symbol rejects initialization; it does not
pretend that a briefing or track has completed.

No proprietary BASS binary is bundled. API names/constants were checked against the pinned existing
bass.pas (19 used identifiers), and scalar ABI widths are tested. The vendor Android ARM64 ELF,
export table, actual audio output and timing have NOT been validated. Distribution/license checks
remain required before packaging an audio-enabled APK. Compile success is not playback proof.

Clipboard: ControlsEdit excludes its desktop imports on Android and uses a Unicode text contract.
The desktop adapter calls the original Clipbrd.AsText. Android has a concrete ClipboardManager Java
host and JNI scope with UTF-16 strings. Providers are thread-local; missing provider, wrong focus/
thread, unavailable/non-text contents and JNI failure are errors rather than fake empty data.
Only a genuinely absent primary clip returns empty text. Paste snapshots clipboard text BEFORE
deleting selection; ReadOnly/BlockInput/selection/Backspace/Delete logic otherwise remains original.
IME is not implemented by this slice.

The host JNI probe and opt-in instrumentation exercise Unicode + NUL + surrogate pair and restore
the previous ClipData. They are COMPILED, but have not run on Android while Actions is disabled.
The actual full control key/selection behavior likewise has not been runtime-tested because its
dependency graph still fails to compile. No Android clipboard runtime success is claimed.

## Fresh compiler results (all compile-only, -Cn)

Successful Android AArch64 targets:
- KM_BassAndroid, KM_Music
- KM_GameAudioState, KM_TextClipboard
- KM_AndroidTextClipboard
- kamprobe.lpr (compile-only; no new linked .so/APK/runtime claim)

Controlled PS-overlay failures:
- KM_ControlsBase: lcltype.pp(51,3) Fatal: Can't find unit WSReferences used by LCLType.
  Trace: KM_ControlsBase → KM_Sound → KM_HandsCollection → KM_Game → KM_InterfaceGamePlay
  → KM_ControlsDrop → KM_ControlsList → LCLIntf → LCLType → WSReferences.
- KM_ControlsEdit: same first error; prefix KM_ControlsEdit → KM_Controls → KM_ControlsBase,
  then the same path. Its former direct LCL import is gone; a different control unit remains.
- KM_Game: KM_Sound.pas(197,5) Error: Illegal expression;
  line 198 then reports ')' expected but VAR found. This is the original anonymous
  TThread.CreateAnonymousThread(procedure ... var ...) initialization unsupported by FPC 3.2.2.
  It was not replaced by an empty initialization or fabricated success.

Unpatched baseline KM_Game: first InvokeCall.inc(116,5), wrong argument count for Invoke;
ends with 32 errors. It remains separate from the verified overlay.
The previous Bass → Windows error is no longer the first blocker; Android KM_Music now compiles.
Neither the full TKMGame unit nor PlayNextTick runs yet.

## Tests and verification

All exit 0 on actual checkout 086a6b3:
- CONTROLSBASE_INPUT_TYPES_OK
- REAL_MESSAGES_OK: legacy message bytes, Unicode/read flags, roundtrip, corrupt/truncated input
- FOG_STATE_UPDATE_OK and FOG_FLOW_OK
- PLATFORM_SERVICES_OK: real callback data, Unicode/NUL/surrogate preservation, thread isolation,
  explicit provider errors, audio state changes and ABI widths
- BASS_MISSING_LIBRARY_REJECTED: actual loader failure, no synthetic playback result
- Existing Pascal Script point/out Linux regression
- All host and instrumentation Java sources compile against Android API 35 / JDK 17
- JNI function-table indices match that JDK's jni.h
- actionlint for all workflows, plus source-scope decision checks

These are Linux runtime/Java compile/AArch64 compile checks. Existing Android host/FFI regressions
are retained and label-gated, but were not rerun on an emulator in this slice. Native ARM64 runtime
is unverified. See PLATFORM_SERVICES.md and the full logs for the bounded next steps.
