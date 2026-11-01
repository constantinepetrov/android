#!/usr/bin/env bash
# Rebuild the unmodified FPC 3.2.2 libffi manager against the installed libffi,
# then separately correct the x86_64 enum value for the current system libffi.
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
: "${FPC_SOURCE:?Set FPC_SOURCE to FPCSource release_3_2_2}"
: "${LAZUTILS_SOURCE:?Set LAZUTILS_SOURCE}"
out=${PORT_TEST_DIR:-"$root/.android-port-build/ffi-abi"}
mkdir -p "$out/original" "$out/fixed" "$out/units-original" "$out/units-fixed"
ffi=$(find "$FPC_SOURCE" -name ffi.pp -print -quit)
manager=$(find "$FPC_SOURCE" -name ffi.manager.pp -print -quit)
test -n "$ffi" && test -n "$manager"
for mode in original fixed; do
  cp "$ffi" "$out/$mode/ffi.pp"
  cp "$manager" "$out/$mode/ffi.manager.pp"
  cp "$root/android-port/tests/ffi_game_abi_probe.pas" "$out/$mode/probe.pas"
done
# libffi v8's x86_64 UNIX64 enum is 2 (not FPC 3.2.2's 1).
python3 - "$out/fixed/ffi.pp" <<'PY'
import ctypes as c, platform, sys
if platform.machine() != 'x86_64': sys.exit('This comparison expects x86_64 Linux')
f = c.CDLL('libffi.so.8')
f.ffi_prep_cif.argtypes = [c.c_void_p, c.c_uint, c.c_uint, c.c_void_p, c.c_void_p]
f.ffi_prep_cif.restype = c.c_uint
result = c.addressof((c.c_byte * 24).in_dll(f, 'ffi_type_sint32'))
def status(abi): return f.ffi_prep_cif(c.create_string_buffer(128), abi, 0, result, None)
assert status(1) != 0 and status(2) == 0, 'Unexpected installed libffi ABI'
p = sys.argv[1]
s = open(p).read()
assert s.count('    FFI_UNIX64,') == 1
open(p, 'w').write(s.replace('    FFI_UNIX64,', '    FFI_UNIX64 = 2,'))
print('System libffi: ABI 1 rejected, ABI 2 accepted')
PY
paths=()
while IFS= read -r -d '' dir; do paths+=("-Fu$dir" "-Fi$dir"); done < <(find "$root/src" -type d -print0)
for mode in original fixed; do
  "${FPC_HOST:-fpc}" -B -Mobjfpc -Sc -dANDROID "-Fi$root" "-Fu$LAZUTILS_SOURCE" \
    "-Fu$out/$mode" ${LIBFFI_LIB_DIR:+"-Fl$LIBFFI_LIB_DIR"} "${paths[@]}" "-FU$out/units-$mode" "-FE$out/$mode" "$out/$mode/probe.pas"
done
set +e
"$out/original/probe" > "$out/original-result.txt" 2>&1
status=$?
set -e
cat "$out/original-result.txt"
if [ "$status" -eq 0 ] || ! grep -q 'EInvocationError: Invoke call failed' "$out/original-result.txt"; then
  echo "Unexpected baseline result: $status" >&2; exit 1
fi
"$out/fixed/probe" | tee "$out/fixed-result.txt"
grep -q FFI_GAME_ABI_OK "$out/fixed-result.txt"
