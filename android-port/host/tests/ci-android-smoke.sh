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

# Assert the on-screen native result, not just a surviving Java process.
ui_ok=0
for attempt in $(seq 1 12); do
  adb shell uiautomator dump /sdcard/smoke-window.xml >> "$results/ui-check.txt" 2>&1 || true
  adb shell cat /sdcard/smoke-window.xml > "$results/smoke-window.xml" 2>/dev/null || true
  if grep -q 'Native Pascal KM_Sort: 134' "$results/smoke-window.xml"; then ui_ok=1; break; fi
  # The emulator launcher can show an ANR dialog over the app. Dismiss only that known dialog.
  if grep -q 'Pixel Launcher isn.t responding' "$results/smoke-window.xml"; then
    adb shell input keyevent KEYCODE_BACK || true
    adb shell am start -n "$package/.MainActivity" >> "$results/ui-check.txt" 2>&1 || true
  fi
  sleep 5
done
if [ "$ui_ok" -ne 1 ]; then
  echo "JNI_RESULT_MISSING: inspect window and logcat" | tee "$results/failure.txt"
  exit 1
fi
adb logcat -d -s KaMProbe:I '*:S' > "$results/probe-stages.txt"
if ! grep -q 'INSETS_OK' "$results/probe-stages.txt" || grep -q 'INSETS_FAIL' "$results/probe-stages.txt"; then
  echo "INSETS_CHECK_FAILED: inspect probe-stages.txt" | tee "$results/failure.txt"
  exit 1
fi
echo "PROCESS_ALIVE_AND_JNI_RESULT_134_AND_INSETS_OK" | tee -a "$results/runtime.txt"

# Synthetic map is generated on-device; no original assets enter CI or artifacts.
adb shell am force-stop "$package"
adb shell am start -W -n "$package/.MainActivity" --ez synthetic_test true
map_ok=0
for attempt in $(seq 1 30); do
  adb logcat -d -s KaMProbe:I '*:S' > "$results/map-stages.txt"
  if grep -q MAP_TRUNCATED_REJECTED "$results/map-stages.txt" && grep -q MAP_SELFTEST_OK "$results/map-stages.txt" && grep -q MAP_TEXTURE_UPLOADED "$results/map-stages.txt"; then map_ok=1; break; fi
  sleep 2
done
if [ "$map_ok" -ne 1 ]; then echo "MAP_RUNTIME_FAILED" | tee "$results/failure.txt"; exit 1; fi
adb shell uiautomator dump /sdcard/map-window.xml > /dev/null
adb shell cat /sdcard/map-window.xml > "$results/map-window.xml"
grep -q 'height sum: 46' "$results/map-window.xml"
adb exec-out screencap -p > "$results/map-screen.png"
echo "SYNTHETIC_MAP_PARSE_TRUNCATION_AND_GL_UPLOAD_OK" | tee -a "$results/runtime.txt"
