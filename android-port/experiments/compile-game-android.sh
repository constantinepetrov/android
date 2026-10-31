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
overlay=()
if [ -n "${PS_OVERLAY:-}" ]; then overlay=("-Fu$PS_OVERLAY" "-Fi$PS_OVERLAY"); fi
failed=0
for unit in src/common/KM_Defaults.pas src/utils/KM_MapHeader.pas src/utils/KM_MapLegacyTile.pas src/game/KM_GameOptions.pas src/terrain/KM_TerrainTypes.pas src/game/KM_FogOfWar.pas src/hands/KM_HandTypes.pas src/hands/KM_HandEntity.pas src/res/KM_ResUnits.pas src/scripting/KM_ScriptExceptionState.pas src/scripting/KM_ScriptingUtils.pas src/game/KM_Game.pas; do
  echo "ANDROID_UNIT_START $unit"
  # The upstream secure-auth unit is absent from this repository. This diagnostic compile
  # uses the project's documented unsecure-auth option only to continue unit analysis.
  if "$FPC_ANDROID" -Paarch64 -Tandroid -XPaarch64-linux-gnu- -Mdelphi -dDBG_SKIP_SECURE_AUTH -B -Cn -Fi"$root" \
    "-Fu$FPC_ANDROID_UNITS/*" "${overlay[@]}" "-Fu$LAZUTILS_SOURCE" "-Fi$LAZUTILS_SOURCE" "-Fu$root/android-port/pascal" "-Fi$root/android-port/pascal" "-Fu$LCL_SOURCE" "-Fi$LCL_SOURCE/include" "${paths[@]}" -FU"$out" "$root/$unit"; then
    echo "ANDROID_UNIT_OK $unit"
  else
    echo "ANDROID_UNIT_FAILED $unit"
    failed=1
  fi
done
exit "$failed"
