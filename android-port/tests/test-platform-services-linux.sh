#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
out=${PORT_TEST_DIR:-"$root/.android-port-build/platform-services"}
mkdir -p "$out"
"${FPC_HOST:-fpc}" -dANDROID -Mdelphi "-Fi$root" "-Fu$root/src/utils" "-Fu$root/src/game" "-Fu$root/src/media" "-FU$out" "-FE$out" "$root/android-port/tests/platform_services_probe.pas"
"$out/platform_services_probe"
