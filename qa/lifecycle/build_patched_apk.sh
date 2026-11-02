#!/usr/bin/env bash
# Isolated rebuild of the exact donor + two historical patches + lifecycle fix.
set -euo pipefail
: "${GITHUB_WORKSPACE:?}"
: "${RUNNER_TEMP:?}"
: "${ANDROID_HOME:?}"
: "${KAM_OLD_APK:?}"
mkdir -p "$GITHUB_WORKSPACE/lifecycle-build-evidence" "$RUNNER_TEMP/kam-output"
LOG="$GITHUB_WORKSPACE/lifecycle-build-evidence"
DONOR="$RUNNER_TEMP/kam-donor"
TC="$RUNNER_TEMP/kam-cross-toolchain"
DATA="$RUNNER_TEMP/kam-data"
# APK already passed the complete original SHA-256 verification in a separate step.
python3 "$GITHUB_WORKSPACE/qa/lifecycle/extract_data_from_verified_apk.py" \
  --apk "$KAM_OLD_APK" --output "$DATA" > "$LOG/data-extraction.txt" 2>&1
echo '== Donor source checkout' | tee -a "$LOG/progress.txt"
git clone -q https://github.com/Vadim170/kam-remake-android.git "$DONOR"
git -C "$DONOR" checkout -q --detach e81c3b765a13d730140c26159eab4506499d44e6
git -C "$DONOR" submodule update --init --recursive > "$LOG/submodules.txt" 2>&1
git -C "$DONOR" apply --check "$GITHUB_WORKSPACE/qa/reconstruction/patches/0001-linux-build-15eeaae.patch"
git -C "$DONOR" apply "$GITHUB_WORKSPACE/qa/reconstruction/patches/0001-linux-build-15eeaae.patch"
git -C "$DONOR" apply --check "$GITHUB_WORKSPACE/qa/reconstruction/patches/0002-bundled-data-c9214fd.patch"
git -C "$DONOR" apply "$GITHUB_WORKSPACE/qa/reconstruction/patches/0002-bundled-data-c9214fd.patch"
git -C "$DONOR/src/ext/pascalscript_submodule" apply --check "$GITHUB_WORKSPACE/qa/reconstruction/patches/0003-pascalscript-working-tree.patch"
git -C "$DONOR/src/ext/pascalscript_submodule" apply "$GITHUB_WORKSPACE/qa/reconstruction/patches/0003-pascalscript-working-tree.patch"
cp "$GITHUB_WORKSPACE/qa/lifecycle/overrides/KM_MainAndroid.inc" "$DONOR/src/KM_MainAndroid.inc"
git -C "$DONOR" diff --stat > "$LOG/source-diff-stat.txt"
sha256sum "$DONOR/src/KM_MainAndroid.inc" > "$LOG/override-sha256.txt"
echo '== Install SDK components' | tee -a "$LOG/progress.txt"
yes | sdkmanager --licenses > "$LOG/sdk-licenses.txt" 2>&1 || true
sdkmanager --install 'ndk;29.0.13599879' 'cmake;3.22.1' 'platforms;android-36' 'build-tools;35.0.0' \
  > "$LOG/sdk-setup.txt" 2>&1
export KAM_TOOLCHAIN="$TC"
export KAM_DATA="$DATA"
export KAM_BUILD_TYPE=Debug
export KAM_BUNDLE_DATA=1
export ANDROID_NDK_HOME="$ANDROID_HOME/ndk/29.0.13599879"
export KAM_CMAKE_BIN="$ANDROID_HOME/cmake/3.22.1/bin"
echo '== Build FPC cross compiler and 3rd party native dependencies' | tee -a "$LOG/progress.txt"
bash "$DONOR/android/toolchain/setup_toolchain.sh" > "$LOG/toolchain.txt" 2>&1 ||
  { tail -80 "$LOG/toolchain.txt"; exit 1; }
echo '== Build patched native APK with bundled game data' | tee -a "$LOG/progress.txt"
bash "$DONOR/android/build_apk.sh" > "$LOG/gradle-and-native.txt" 2>&1 ||
  { tail -80 "$LOG/gradle-and-native.txt"; tail -70 "$DONOR/android/build/last.log" || true; exit 1; }
test -f "$DONOR/android/app/build/outputs/apk/debug/app-debug.apk"
cp "$DONOR/android/app/build/outputs/apk/debug/app-debug.apk" "$RUNNER_TEMP/kam-output/KaM_lifecycle_fix_debug.apk"
"$ANDROID_HOME/build-tools/35.0.0/apksigner" verify "$RUNNER_TEMP/kam-output/KaM_lifecycle_fix_debug.apk"
stat -c '%s bytes' "$RUNNER_TEMP/kam-output/KaM_lifecycle_fix_debug.apk" | tee "$LOG/apk-bytes.txt"
sha256sum "$RUNNER_TEMP/kam-output/KaM_lifecycle_fix_debug.apk" | tee "$LOG/apk-sha256.txt"
echo "PATCHED_APK_BUILD_COMPLETE"
