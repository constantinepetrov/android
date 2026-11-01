# Fresh cloud ARM64 compile of current PR tree — 2026-11-01

This is a standalone cloud compile, **not a GitHub Actions run**. Actions is blocked by GitHub at the fork level.

## Source identity

- Actual checkout: `dba4bf9a7786d41a8e2a2e0974f3e7a6039b3745`.
- Tree: `c24a66e175a8e97067cdb0a523963895109d2244`, identical to `028f0b58`.
- Checkout clean before/after compilation. No tracked source changes, no force push, no master changes.
- Pascal Script submodule: `ce8590dd7b9cf48fd0e446731989603e09e239b8`.
- FPC release_3_2_2: `0d122c49534b480be9284c21bd60b53d99904346`.
- Lazarus lazarus_4_0: `9d15c73c91a1545be50bee02b27bd3b43f9d90e8`.
- Bootstrap FPC 3.2.2, source-built Android AArch64 compiler/RTL/packages; GNU binutils 2.44 extracted locally. Debian 13 cloud host, not the Actions Ubuntu runner.
- Explicit target `-Paarch64 -Tandroid`, compile-only `-Cn`. No APK/link/runtime claim.

## Actions cause and access limits

The public [workflow page](https://github.com/constantinepetrov/android/actions/workflows/android-client-probe.yml) returned HTTP 200 and this exact GitHub banner:

> Workflows are not currently being run on this fork due to the scale of GitHub Actions usage. A repository maintainer can choose to re-enable these.

A repository maintainer must re-enable workflows on this fork's Actions page. No further PR closing/reopening or empty commits were attempted. The connector rejects GET actions/workflows/401800660 and GET actions/permissions with HTTPError 400, “GitHub Fetch URL is not an allowed public GitHub repository or search endpoint.” It exposes no workflow enable/dispatch action. The cloud CLI request to api.github.com returns “Forbidden” through the network layer; that is not evidence of a GitHub REST permissions 403. Environment readiness reports no configured secrets or outbound identities. The client workflow file on master returns GitHub 404, so manual workflow_dispatch cannot be assumed available without a default-branch change; master was not changed.

## Compiler results

The checked-in Pascal Script generator was applied outside the checkout; generated runtime/compiler both compiled. Baseline uses the unchanged submodule.

| Target | Configuration | Exit | First compiler error |
| --- | --- | --- | --- |
| KM_ControlsBase | controlled PS overlay | 1 | bass.pas(19,3) Fatal: Can't find unit Windows used by Bass |
| KM_Game | controlled PS overlay | 1 | lcltype.pp(51,3) Fatal: Can't find unit WSReferences used by LCLType |
| KM_ControlsBase | unpatched PS baseline | 1 | InvokeCall.inc(116,5) Error: Wrong number of parameters specified for call to Invoke |
| KM_Game | unpatched PS baseline | 1 | InvokeCall.inc(116,5) Error: Wrong number of parameters specified for call to Invoke |

The baseline ends with 32 Invoke errors. Fresh `-vu` import traces establish these paths:

- ControlsBase → KM_Sound → KM_Game → KM_InterfaceGame → KM_InterfaceDefaults → KM_Music → Bass → Windows.
- KM_Game → KM_InterfaceGame → KM_Controls → KM_ControlsEdit → LCLIntf → LCLType → WSReferences.

The direct ControlsBase LCL imports no longer cause the first failure. Dragger → Controls is not the observed widgetset blocker: the configured search path resolves the existing Android Controls input-value compatibility unit. Edit still explicitly imports LCLIntf/LCLType and Clipbrd; its actual key handlers use VK_* constants and Clipboard.AsText for copy/cut/paste. Music explicitly enables USEBASS when NO_MUSIC is absent; its Bass binding imports Windows. Neither music nor clipboard/input was disabled to hide these failures.

## Reproduction and limitations

`run-current-tree.sh` follows the checked-in compile script in both configurations. `trace-targets.sh` invokes each target separately into isolated unit directories; the four .command files retain the full expanded commands. Existing `-dDBG_SKIP_SECURE_AUTH` diagnostic option is preserved; no NO_MUSIC define or gameplay-unit omission was introduced.

An initial standalone pass without a compiler config failed at Lazarus lazfileutils.pas(1329), on its += syntax. It is retained under initial-no-config. The configured wrapper explicitly adds `-Sc`, without editing sources; the table above is from that corrected configuration. This is an environment/configuration adjustment, not an engine fix.

The checked-in script defines `trace=(-vu)` but never passes `trace[@]` to the compiler (its command has an intervening -dDBG_SKIP_SECURE_AUTH). Thus it does not currently provide the intended verbose trace. The standalone target commands explicitly add -vu; the source tree remains unchanged.

Input-state regression: CONTROLSBASE_INPUT_TYPES_OK. Original message-state regression: REAL_MESSAGES_OK (typed dispatch, legacy byte parity, Unicode/read flag, roundtrip, malformed/truncated input). Both ran on the same checkout with host FPC 3.2.2; these are Linux runtime tests. The produced KM_GameMessages.o is independently identified as ARM aarch64 relocatable ELF. Full game units did not compile, and PlayNextTick did not run.

Full logs, expanded compiler commands, toolchain build log, provenance and test output are in [logs.tar.gz](logs.tar.gz). GitHub Actions must still be re-enabled by a maintainer before a fresh Actions-run URL/check result can be provided.
