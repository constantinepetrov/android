#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
: "${LAZARUS_SOURCE:?Set LAZARUS_SOURCE to the pinned Lazarus tree}"
: "${FPC_SOURCE:?Set FPC_SOURCE to FPC 3.2.2 source (CHM parser dependency)}"
out=${PORT_TEST_DIR:-"$root/.android-port-build/desktop-window-types"}
mkdir -p "$out"
"${FPC_HOST:-fpc}" -Sc -Mdelphi "-Fi$root" "-Fu$root/src/settings" "-Fu$root/src/forms" \
  "-Fu$LAZARUS_SOURCE/lcl" "-Fi$LAZARUS_SOURCE/lcl/include" "-Fu$LAZARUS_SOURCE/lcl/widgetset" \
  "-Fu$LAZARUS_SOURCE/lcl/interfaces/nogui" "-Fu$LAZARUS_SOURCE/components/lazutils" \
  "-Fu$LAZARUS_SOURCE/packager/registration" "-Fu$FPC_SOURCE/packages/chm/src" "-FU$out" "-FE$out" "$root/android-port/tests/desktop_window_types_probe.pas"
"$out/desktop_window_types_probe"
