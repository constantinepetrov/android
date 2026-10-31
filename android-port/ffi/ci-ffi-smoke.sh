#!/usr/bin/env bash
set -Eeuo pipefail
apk=$1
results="$GITHUB_WORKSPACE/android-ffi-results"
mkdir -p "$results"
collect() {
  code=$?; set +e
  adb logcat -d -v threadtime > "$results/logcat.txt" 2>&1
  adb exec-out screencap -p > "$results/screen.png" 2>/dev/null
  adb shell getprop > "$results/properties.txt" 2>&1
  adb shell ls -l /data/tombstones > "$results/tombstones.txt" 2>&1
  grep -E 'KaMProbe|Fatal signal|FATAL EXCEPTION|libffi' "$results/logcat.txt" | tail -100 || true
  echo "exit=$code" > "$results/result.txt"
}
trap collect EXIT
adb shell getprop ro.product.cpu.abilist | tee "$results/abi.txt"
adb shell getprop ro.dalvik.vm.native.bridge | tee "$results/native-bridge.txt"
adb install -r "$apk" | tee "$results/install.txt"
adb logcat -c
adb shell am start -W -n com.kamremake.androidprobe/.MainActivity --ez ffi_test true | tee "$results/start.txt"
found=0
for attempt in $(seq 1 45); do
  adb logcat -d -s KaMProbe:I '*:S' > "$results/stages.txt"
  if grep -q 'FFI_ABI_OK self integer single out TKMPoint' "$results/stages.txt" && grep -q 'FFI_SCRIPT_OK facade' "$results/stages.txt"; then found=1; break; fi
  if grep -q 'FFI_ABI_FAILED\|FFI_SCRIPT_FAILED\|Native load or JNI failure' "$results/stages.txt"; then break; fi
  sleep 2
done
[ "$found" = 1 ] || { echo 'ARM64_FFI_PROBE_FAILED' | tee "$results/failure.txt"; exit 1; }
adb shell uiautomator dump /sdcard/ffi-window.xml > "$results/ui-dump.txt" 2>&1 || true
adb shell cat /sdcard/ffi-window.xml > "$results/window.xml" 2>/dev/null || true
echo 'UI hierarchy is diagnostic here; native Pascal and libffi log assertions are the smoke-test gate.'
echo 'ARM64_FFI_SCALAR_FLOAT_OUT_RECORD_OK (x86_64 emulator ARM translation)' | tee -a "$results/result.txt"
