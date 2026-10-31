#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
out=${PORT_TEST_DIR:-"$root/.android-port-build/font-types"}
for mode in desktop android-conditional; do
  mkdir -p "$out/$mode"
  defs=(); [ "$mode" = desktop ] || defs=(-dANDROID)
  "${FPC_HOST:-fpc}" -B -Sc "${defs[@]}" "-Fi$root" "-Fu$root/src/res" "-Fu$root/src/hands" \
    "-FU$out/$mode" "-FE$out/$mode" "$root/android-port/tests/font_type_probe.pas"
  "$out/$mode/font_type_probe" > "$out/$mode/result.txt"
done
diff -u "$out/desktop/result.txt" "$out/android-conditional/result.txt"
cat "$out/desktop/result.txt"
