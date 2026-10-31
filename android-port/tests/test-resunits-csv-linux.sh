#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
: "${LAZUTILS_SOURCE:?Set LAZUTILS_SOURCE}"
out=${PORT_TEST_DIR:-"$root/.android-port-build/resunits-csv"}
mkdir -p "$out/units" "$out/data"
paths=()
while IFS= read -r -d '' dir; do paths+=("-Fu$dir" "-Fi$dir"); done < <(find "$root/src" -type d -print0)
"${FPC_HOST:-fpc}" -B -Sc -dANDROID "-Fi$root" "-Fu$LAZUTILS_SOURCE" "${paths[@]}" \
  "-FU$out/units" "-FE$out" "$root/android-port/tests/resunits_csv_probe.pas"
"$out/resunits_csv_probe" "$out/data"
