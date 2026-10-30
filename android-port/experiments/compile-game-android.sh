#!/usr/bin/env bash
# Diagnostic: compile the real client game unit, without desktop PPU files.
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
: "${FPC_ANDROID:?Set FPC_ANDROID to the AArch64 cross compiler}"
: "${FPC_ANDROID_UNITS:?Set FPC_ANDROID_UNITS to its aarch64-android units directory}"
out=${PORT_BUILD_DIR:-"$root/.android-port-build"}
mkdir -p "$out"
paths=()
while IFS= read -r -d '' path; do paths+=("-Fu$path" "-Fi$path"); done < <(find "$root/src" -type d -print0)
"$FPC_ANDROID" -Paarch64 -Tandroid -Mdelphi -B -Cn -Fi"$root" \
  "-Fu$FPC_ANDROID_UNITS/*" "${paths[@]}" -FU"$out" \
  "$root/src/game/KM_Game.pas"
