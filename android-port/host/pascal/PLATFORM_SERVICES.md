The Android text clipboard scope is a concrete JNI adapter for GameTextClipboard,
which uses Android ClipboardManager. It is valid for one focused Activity UI-thread
native input call and restores the previous thread-local provider on destruction.
Callers on other threads or without a provider get an explicit error. The host
instrumentation test exercises UTF-16 (including NUL and a surrogate pair) through
this bridge and restores the original Android ClipData. It does not implement IME.
It must pass in the opt-in Android runtime workflow before claiming OS integration.

KM_BassAndroid is a narrow dynamic C ABI binding for the BASS 2.4 calls used by
KM_Music. Constants and call shapes are cross-checked against the repository's
existing src/ext/bass.pas binding. Android uses libbass.so, cdecl, fixed 32-bit
handles/BOOL, 64-bit offsets, and UTF-8 file paths without BASS_UNICODE. Desktop
continues using its original Bass unit. Version and required symbols are checked
before use; absence rejects initialization and does not report completed playback.

No proprietary BASS binary is bundled, downloaded from a third-party mirror, or
redistributed here. The actual vendor Android ARM64 library/export table and audio
playback have not been tested in this slice. Obtain it from Un4seen under applicable
terms and resolve distribution/license requirements before packaging a music-enabled
APK. Compile-only success is not proof of audio, timing or briefing callbacks.
