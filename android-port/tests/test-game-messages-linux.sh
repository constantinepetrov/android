#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
: "${LAZUTILS_SOURCE:?Set LAZUTILS_SOURCE}"
out=${PORT_TEST_DIR:-"$root/.android-port-build/messages"}
mkdir -p "$out"
paths=()
while IFS= read -r -d '' p; do paths+=("-Fu$p" "-Fi$p"); done < <(find "$root/src" -type d -print0)
"${FPC_HOST:-fpc}" -Sc -dANDROID "-Fi$root" "-Fu$LAZUTILS_SOURCE" "-Fi$LAZUTILS_SOURCE" "${paths[@]}" "-FU$out" "-FE$out" "$root/android-port/tests/game_messages_smoke.pas"
"$out/game_messages_smoke"
