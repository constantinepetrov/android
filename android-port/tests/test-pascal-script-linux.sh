#!/usr/bin/env bash
# Compile the checked-out Pascal Script and run a small class-import scenario.
# This is a Linux x86_64 classic-invoker probe, not an Android runtime test.
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
: "${LAZUTILS_SOURCE:?Set LAZUTILS_SOURCE to Lazarus components/lazutils}"
out=${PORT_TEST_DIR:-"$root/.android-port-build/pascal-script-linux"}
mkdir -p "$out/src" "$out/units" "$out/bin"
cp "$root"/src/ext/pascalscript_submodule/Source/*.pas "$root"/src/ext/pascalscript_submodule/Source/*.inc "$out/src/"
# One inline variable in the upstream compiler needs Delphi syntax newer than
# FPC 3.2.2. This diagnostic applies only to a disposable copied source tree.
python3 - "$out/src/uPSCompiler.pas" <<'PY'
import sys
p=sys.argv[1]
s=open(p).read()
a='            var bType := GetTypeNo(BlockInfo, tmp).BaseType;\n            if not IsIntType(bType) and not (bType = btEnum) then'
b='            if not IsIntType(GetTypeNo(BlockInfo, tmp).BaseType) and not (GetTypeNo(BlockInfo, tmp).BaseType = btEnum) then'
assert s.count(a)==1, 'Unexpected Pascal Script compiler source'
open(p,'w').write(s.replace(a,b))
PY
paths=()
while IFS= read -r -d '' dir; do
  [[ "$dir" == *pascalscript_submodule* ]] || paths+=("-Fu$dir" "-Fi$dir")
done < <(find "$root/src" -type d -print0)
"${FPC_HOST:-fpc}" -Sc -dANDROID "-Fi$root" "-Fu$out/src" "-Fu$LAZUTILS_SOURCE" \
  "${paths[@]}" "-FU$out/units" "-FE$out/bin" "$root/android-port/tests/pascal_script_game_probe.pas"
"$out/bin/pascal_script_game_probe"
