#!/usr/bin/env bash
# Diagnostic: compile the real client game unit, without desktop PPU files.
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
: "${FPC_ANDROID:?Set FPC_ANDROID to the AArch64 cross compiler}"
: "${FPC_ANDROID_UNITS:?Set FPC_ANDROID_UNITS to its aarch64-android units directory}"
: "${LAZUTILS_SOURCE:?Set LAZUTILS_SOURCE to Lazarus components/lazutils source}"
: "${LCL_SOURCE:?Set LCL_SOURCE to the Lazarus lcl source directory}"
out=${PORT_BUILD_DIR:-"$root/.android-port-build"}
mkdir -p "$out"
paths=()
while IFS= read -r -d '' path; do paths+=("-Fu$path" "-Fi$path"); done < <(find "$root/src" -type d -print0)
for unit in src/common/KM_Defaults.pas src/utils/KM_MapHeader.pas src/utils/KM_MapLegacyTile.pas src/game/KM_GameOptions.pas src/game/KM_Game.pas; do
  "$FPC_ANDROID" -Paarch64 -Tandroid -XPaarch64-linux-gnu- -Mdelphi -B -Cn -Fi"$root" \
    "-Fu$FPC_ANDROID_UNITS/*" "-Fu$LAZUTILS_SOURCE" "-Fi$LAZUTILS_SOURCE" "-Fu$LCL_SOURCE" "-Fi$LCL_SOURCE/include" "${paths[@]}" -FU"$out" "$root/$unit"
done
