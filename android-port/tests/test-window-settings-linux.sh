#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
: "${LAZUTILS_SOURCE:?Set LAZUTILS_SOURCE}"
out=${PORT_TEST_DIR:-"$root/.android-port-build/window-settings"}
mkdir -p "$out"
paths=()
while IFS= read -r -d '' dir; do paths+=("-Fu$dir" "-Fi$dir"); done < <(find "$root/src" -type d -print0)
"${FPC_HOST:-fpc}" -B -Sc -dANDROID -gh -gl "-Fi$root" "-Fu$LAZUTILS_SOURCE" "${paths[@]}" "-FU$out" "-FE$out" "$root/android-port/tests/window_settings_probe.pas"
"$out/window_settings_probe" "$root/android-port/tests/fixtures/window-settings"
