#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../../.." && pwd)
: "${LAZUTILS_SOURCE:?Set LAZUTILS_SOURCE}"
out=${PORT_TEST_DIR:-"$root/.android-port-build/linux-jni-map"}
mkdir -p "$out"
paths=()
while IFS= read -r -d '' dir; do paths+=("-Fu$dir" "-Fi$dir"); done < <(find "$root/src" -type d -print0)
"${FPC_HOST:-fpc}" -B -Sc -dANDROID -Mdelphi -Cg "-Fi$root" "-Fu$LAZUTILS_SOURCE" "${paths[@]}" "-FU$out" "-FE$out" "$root/android-port/host/pascal/kamprobe.lpr"
python3 "$root/android-port/host/tests/linux-jni-map.py" "$out/libkamprobe.so" "$@"
