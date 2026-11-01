#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
out=${PORT_TEST_DIR:-"$root/.android-port-build/controls-input"}
mkdir -p "$out"
"${FPC_HOST:-fpc}" -dANDROID "-Fi$root" "-Fu$root/src/controls" "-FU$out" "-FE$out" "$root/android-port/tests/controls_input_probe.pas"
"$out/controls_input_probe"
