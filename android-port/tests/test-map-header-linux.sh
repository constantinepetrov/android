#!/usr/bin/env bash
# Compile original engine map header parser. Optional argument: lawful local .map.
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
: "${LAZUTILS_SOURCE:?Set LAZUTILS_SOURCE to Lazarus components/lazutils}"
out=${PORT_TEST_DIR:-"$root/.android-port-build/map-header-test"}
mkdir -p "$out"
paths=()
while IFS= read -r -d '' path; do paths+=("-Fu$path" "-Fi$path"); done < <(find "$root/src" -type d -print0)
"${FPC_HOST:-fpc}" -Sc -dANDROID "-Fi$root" "-Fu$LAZUTILS_SOURCE" "-Fi$LAZUTILS_SOURCE" \
  "${paths[@]}" "-FU$out" "-FE$out" "$root/android-port/tests/map_header_probe.pas"
if (($# > 0)); then "$out/map_header_probe" "$@"; fi
