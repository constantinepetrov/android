#!/usr/bin/env bash
# Test the original fog update on Linux using the Android platform conditionals.
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
: "${LAZUTILS_SOURCE:?Set LAZUTILS_SOURCE}"
out=${PORT_TEST_DIR:-"$root/.android-port-build/fog-state"}
mkdir -p "$out"
paths=()
while IFS= read -r -d '' dir; do paths+=("-Fu$dir" "-Fi$dir"); done < <(find "$root/src" -type d -print0)
"${FPC_HOST:-fpc}" -B -Sc -dANDROID "-Fi$root" "-Fu$LAZUTILS_SOURCE" "${paths[@]}" \
    "-FU$out" "-FE$out" "$root/android-port/tests/fog_state_probe.pas"
"$out/fog_state_probe"
