#!/usr/bin/env bash
# Optional real OpenAL smoke test. Requires libopenal.so in the loader path.
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
out=${PORT_TEST_DIR:-"$root/.android-port-build/openal-session"}
mkdir -p "$out"
# FPC ships a different unit also named OpenAL. Compile the game's binding first.
"${FPC_HOST:-fpc}" -Mdelphi "-FU$out" "$root/src/ext/openal.pas"
"${FPC_HOST:-fpc}" -Mdelphi -gh -gl "-Fi$root" "-Fu$root/src/media" "-Fu$root/src/ext" "-Fu$out" "-FU$out" "-FE$out" "$root/android-port/tests/openal_session_probe.pas"
ALSOFT_DRIVERS=null "$out/openal_session_probe"
