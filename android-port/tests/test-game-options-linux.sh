#!/usr/bin/env bash
# Exercises original game-option serialization on Linux with Android project guards.
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
: "${LAZUTILS_SOURCE:?Set LAZUTILS_SOURCE to Lazarus components/lazutils}"
out=${PORT_TEST_DIR:-"$root/.android-port-build/game-options-test"}
mkdir -p "$out"
paths=()
while IFS= read -r -d '' path; do paths+=("-Fu$path" "-Fi$path"); done < <(find "$root/src" -type d -print0)
"${FPC_HOST:-fpc}" -Sc -dANDROID "-Fi$root" "-Fu$LAZUTILS_SOURCE" "-Fi$LAZUTILS_SOURCE" \
  "${paths[@]}" "-FU$out" "-FE$out" "$root/android-port/tests/game_options_smoke.pas"
"$out/game_options_smoke"
