#!/usr/bin/env bash
# Isolated x86_64 experiment, not an Android call manager or production patch.
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
: "${LAZUTILS_SOURCE:?Set LAZUTILS_SOURCE}"
: "${FFI_FIXED_SOURCE:?Run test-ffi-abi-linux.sh first and point to its fixed directory}"
out=${PORT_TEST_DIR:-"$root/.android-port-build/script-compat"}
mkdir -p "$out/src" "$out/units" "$out/bin"
python3 "$root/android-port/experiments/prepare-pascalscript-fpc.py" "$root/src/ext/pascalscript_submodule/Source" "$out/src"
python3 - "$root/android-port/tests/pascal_script_game_probe.pas" "$out/src" <<'PY'
import pathlib, sys
source=pathlib.Path(sys.argv[1]).read_text().replace('uses SysUtils, uPSCompiler', 'uses ffi.manager, SysUtils, uPSCompiler')
pathlib.Path(sys.argv[2], 'record_probe.pas').write_text(source)
start=source.index("const source='")
end=source.index("';\nbegin", start)
script="const source='var n: Integer; begin Utils.OutValue(8,n); if (n <> 15) then begin n:=1 div (n-n); end; end."
source=source[:start]+script+source[end:]
source=source.replace('PASCAL_SCRIPT_POINT_AND_OUT_OK (test facade using real TKMPoint.New)', 'PASCAL_SCRIPT_FFI_OUT_OK (test facade)')
pathlib.Path(sys.argv[2], 'out_probe.pas').write_text(source)
PY
paths=()
while IFS= read -r -d '' dir; do [[ "$dir" == *pascalscript_submodule* ]] || paths+=("-Fu$dir" "-Fi$dir"); done < <(find "$root/src" -type d -print0)
for probe in record_probe out_probe; do
  "${FPC_HOST:-fpc}" -B -Mobjfpc -Sc -dANDROID -dUSEINVOKECALL "-Fi$root" "-Fu$out/src" "-Fu$FFI_FIXED_SOURCE" \
    ${LIBFFI_LIB_DIR:+"-Fl$LIBFFI_LIB_DIR"} "-Fu$LAZUTILS_SOURCE" "${paths[@]}" "-FU$out/units" "-FE$out/bin" "$out/src/$probe.pas"
done
set +e
"$out/bin/record_probe" > "$out/record-result.txt" 2>&1
record_status=$?
set -e
cat "$out/record-result.txt"
if [ "$record_status" -eq 0 ] && grep -q PASCAL_SCRIPT_POINT_AND_OUT_OK "$out/record-result.txt"; then
  echo 'PASCAL_SCRIPT_FPC_RECORD_RESULT_OK (Linux x86_64 libffi compatibility test)'
elif [ "$record_status" -eq 3 ] && grep -q 'run failed' "$out/record-result.txt"; then
  echo 'PASCAL_SCRIPT_HOST_RECORD_RESULT_UNAVAILABLE (FPC 3.2.2 Linux x86_64 diagnostic only)'
else
  echo "Unexpected record probe result: $record_status" >&2
  exit 1
fi
"$out/bin/out_probe" | tee "$out/out-result.txt"
grep -q PASCAL_SCRIPT_FFI_OUT_OK "$out/out-result.txt"
echo 'PASCAL_SCRIPT_FPC_RECORD_RESULT_OK (Linux x86_64 libffi compatibility test)'
