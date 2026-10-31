#!/usr/bin/env bash
# Runtime smoke test. API 35 x86_64 Google emulator may translate ARM64 binaries.
# An install failure with NO_MATCHING_ABIS is a platform limitation, not an app crash.
set -Eeuo pipefail

apk="$1"
package="com.kamremake.androidprobe"
results="$GITHUB_WORKSPACE/android-runtime-results"
mkdir -p "$results"

collect() {
  local code="$?"
  set +e
  adb logcat -d -v threadtime > "$results/logcat.txt" 2>&1
  adb shell dumpsys activity activities > "$results/activities.txt" 2>&1
  adb shell getprop > "$results/device-properties.txt" 2>&1
  adb exec-out screencap -p > "$results/screen.png" 2>/dev/null
  adb shell uiautomator dump /sdcard/window.xml > "$results/uiautomator-output.txt" 2>&1
  adb shell cat /sdcard/window.xml > "$results/window.xml" 2>/dev/null
  echo "Smoke result exit code: $code" | tee "$results/result.txt"
}
trap collect EXIT

echo "APK: $apk"
test -f "$apk"
adb devices -l
echo "Emulator ABI list: $(adb shell getprop ro.product.cpu.abilist)"
echo "Native bridge: $(adb shell getprop ro.dalvik.vm.native.bridge)"
adb logcat -c

set +e
install_log=$(adb install -r "$apk" 2>&1)
install_code=$?
set -e
printf '%s\n' "$install_log" | tee "$results/install.txt"
if [ "$install_code" -ne 0 ]; then
  if printf '%s\n' "$install_log" | grep -q 'INSTALL_FAILED_NO_MATCHING_ABIS'; then
    echo "UNSUPPORTED_TEST_DEVICE_ABI: x86_64 emulator cannot install this ARM64-only APK; test on a real ARM64 device or Firebase Test Lab." | tee "$results/failure.txt"
  else
    echo "INSTALL_FAILED: inspect install.txt and logcat.txt" | tee "$results/failure.txt"
  fi
  exit 1
fi

adb shell am force-stop "$package" || true
adb shell am start -W -n "$package/.MainActivity" 2>&1 | tee "$results/start.txt"
sleep 6
pid=$(adb shell pidof "$package" 2>/dev/null | tr -d '\r' || true)
if [ -z "$pid" ]; then
  echo "APP_CRASHED_OR_EXITED: inspect logcat.txt" | tee "$results/failure.txt"
  exit 1
fi

echo "Running app pid: $pid" | tee "$results/runtime.txt"
adb shell input swipe 300 400 550 550 600
sleep 2
pid=$(adb shell pidof "$package" 2>/dev/null | tr -d '\r' || true)
if [ -z "$pid" ]; then
  echo "APP_CRASHED_AFTER_INPUT: inspect logcat.txt" | tee "$results/failure.txt"
  exit 1
fi

# The visible native result requires successful loadLibrary + JNI + Activity creation.
# UIAutomator inspection is attempted in the cleanup handler, preserving artifacts.
echo "PROCESS_ALIVE_AFTER_LAUNCH_AND_DRAG" | tee -a "$results/runtime.txt"
