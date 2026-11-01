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
git -C "$root" rev-parse HEAD HEAD^{tree}
"$FPC_ANDROID" -Paarch64 -Tandroid -iV -iTP -iTO
failed=0
echo "KM_SCRIPTING_SOURCE_BYTES_BEGIN"
head -c 96 "$root/src/scripting/KM_Scripting.pas" | od -An -tx1c
echo "KM_SCRIPTING_SOURCE_BYTES_END"
read -r -a targets <<< "${PORT_TARGETS:-src/settings/KM_WindowTypes.pas src/settings/KM_WindowParams.pas src/settings/KM_MainSettings.pas src/common/KM_Defaults.pas src/utils/KM_MapHeader.pas src/utils/KM_MapLegacyTile.pas src/game/KM_GameOptions.pas src/terrain/KM_TerrainTypes.pas src/game/KM_FogOfWar.pas src/hands/KM_HandTypes.pas src/hands/KM_HandEntity.pas src/res/KM_ResUnits.pas src/scripting/KM_ScriptExceptionState.pas src/scripting/KM_ScriptingUtils.pas src/game/KM_GameMessages.pas src/game/KM_GamePresentationState.pas src/media/KM_BassAndroid.pas src/game/KM_GameAudioState.pas src/utils/KM_TextClipboard.pas android-port/host/pascal/KM_AndroidTextClipboard.pas src/media/KM_AudioSession.pas src/media/KM_OpenALBackend.pas src/media/KM_Sound.pas src/controls/KM_ControlsList.pas src/controls/KM_ControlsEdit.pas src/controls/KM_ControlsBase.pas src/game/KM_Game.pas}"
for unit in "${targets[@]}"; do
  echo "ANDROID_UNIT_START $unit"
  trace=()
  case "$unit" in src/controls/*.pas|src/media/KM_Sound.pas|src/game/KM_Game.pas) trace=(-vu);; esac
  # The upstream secure-auth unit is absent from this repository. This diagnostic compile
  # uses the project's documented unsecure-auth option only to continue unit analysis.
  command=("$FPC_ANDROID" -Paarch64 -Tandroid -XPaarch64-linux-gnu- -Mdelphi -dDBG_SKIP_SECURE_AUTH -B -Cn "${trace[@]}" -Fi"$root" \
    "-Fu$FPC_ANDROID_UNITS/*" "${overlay[@]}" "-Fu$LAZUTILS_SOURCE" "-Fi$LAZUTILS_SOURCE" "-Fu$root/android-port/pascal" "-Fi$root/android-port/pascal" "-Fu$LCL_SOURCE" "-Fi$LCL_SOURCE/include" "${paths[@]}" -FU"$out" "$root/$unit")
  printf 'FPC_COMMAND '
  printf '%q ' "${command[@]}"
  printf '\n'
  if "${command[@]}"; then
    echo "ANDROID_UNIT_OK $unit"
  else
    echo "ANDROID_UNIT_FAILED $unit"
    failed=1
  fi
done
exit "$failed"
