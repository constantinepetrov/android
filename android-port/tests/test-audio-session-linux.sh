#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
out=${PORT_TEST_DIR:-"$root/.android-port-build/audio-session"}
mkdir -p "$out"
"${FPC_HOST:-fpc}" -Mdelphi -dANDROID -gh -gl "-Fi$root" "-Fu$root/src/media" "-FU$out" "-FE$out" "$root/android-port/tests/audio_session_probe.pas"
"$out/audio_session_probe"
