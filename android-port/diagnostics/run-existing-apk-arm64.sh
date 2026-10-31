#!/usr/bin/env bash
# Run a previously built APK unchanged. All outputs are evidence, not a fix.
set -uo pipefail
out=${DIAGNOSTIC_OUT:?}
apk=${APK_PATH:?}
mkdir -p "$out"
export PATH="$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"
serial=emulator-5554
collect() {
  adb -s "$serial" logcat -b all -v threadtime -d > "$out/logcat-all.txt" 2>&1 || true
  adb -s "$serial" shell dumpsys activity exit-info com.kamremake.androidprobe > "$out/exit-info.txt" 2>&1 || true
  adb -s "$serial" shell dumpsys activity activities > "$out/activity-state.txt" 2>&1 || true
  adb -s "$serial" shell ls -l /data/tombstones > "$out/tombstones-list.txt" 2>&1 || true
  adb -s "$serial" pull /data/tombstones "$out/tombstones" > "$out/tombstones-pull.txt" 2>&1 || true
  adb -s "$serial" exec-out screencap -p > "$out/screenshot.png" 2> "$out/screenshot-error.txt" || true
  adb -s "$serial" shell uiautomator dump /sdcard/window.xml > "$out/uiautomator.txt" 2>&1 || true
  adb -s "$serial" pull /sdcard/window.xml "$out/window.xml" >> "$out/uiautomator.txt" 2>&1 || true
  adb -s "$serial" emu kill >/dev/null 2>&1 || true
}
trap collect EXIT
emulator -avd kam_arm64 -no-window -no-audio -no-snapshot -no-boot-anim -accel off -gpu swiftshader_indirect -memory 2048 > "$out/emulator.txt" 2>&1 &
echo $! > "$out/emulator.pid"
booted=0
for ((i=0;i<180;i++)); do
  if ! kill -0 "$(cat "$out/emulator.pid")" 2>/dev/null; then echo 'Emulator process exited before boot' >&2; exit 1; fi
  state=$(adb -s "$serial" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')
  if [[ "$state" == 1 ]]; then booted=1; break; fi
  sleep 5
done
if [[ "$booted" != 1 ]]; then echo 'ARM64 emulator did not boot within 15 minutes' >&2; exit 1; fi
adb -s "$serial" root > "$out/adb-root.txt" 2>&1 || true
adb -s "$serial" wait-for-device
abi=$(adb -s "$serial" shell getprop ro.product.cpu.abi | tr -d '\r')
{
  echo "abi=$abi"
  adb -s "$serial" shell getprop ro.build.version.release
  adb -s "$serial" shell getprop ro.build.version.sdk
  adb -s "$serial" shell getconf PAGE_SIZE
  adb -s "$serial" shell getprop ro.build.fingerprint
} > "$out/device.txt"
if [[ "$abi" != arm64-v8a ]]; then echo "Wrong guest ABI: $abi" >&2; exit 1; fi
adb -s "$serial" logcat -c || true
adb -s "$serial" install -r "$apk" > "$out/install.txt" 2>&1 || { cat "$out/install.txt"; exit 1; }
adb -s "$serial" shell am start -W -n com.kamremake.androidprobe/.MainActivity > "$out/start.txt" 2>&1 || true
sleep 20
adb -s "$serial" shell pidof com.kamremake.androidprobe > "$out/pid.txt" 2>&1 || true
adb -s "$serial" shell uiautomator dump /sdcard/window-check.xml > "$out/ui-check.txt" 2>&1 || true
adb -s "$serial" pull /sdcard/window-check.xml "$out/window-check.xml" >> "$out/ui-check.txt" 2>&1 || true
if ! grep -q 'Native Pascal KM_Sort: 134' "$out/window-check.xml" 2>/dev/null || [[ ! -s "$out/pid.txt" ]]; then
  echo 'Runtime check failed: process or expected JNI result missing' >&2
  exit 1
fi
echo 'ARM64 runtime smoke test passed'
