#!/usr/bin/env python3
"""Fix touch cheats on WargusHD 3.4.91: direct JNI -> engine-thread Lua queue.

Applied AFTER apply_cheat_palette.py. Never execute cheats on Android UI thread.
The official app package is left untouched; this modifies only the separate test.
"""
from pathlib import Path
import sys

if len(sys.argv)!=2:
    raise SystemExit("usage: apply_native_cheat_bridge.py <wargushd-source-root>")
root=Path(sys.argv[1]).resolve()
def update(path,needle,with_text):
    path=Path(path)
    s=path.read_text()
    count=s.count(needle)
    if count!=1:
        raise RuntimeError(f"Expected exactly one match in {path}: {count}: {needle[:120]}")
    path.write_text(s.replace(needle,with_text,1))
    print("UPDATED",path)

header=root/"src/include/launcher_bridge.h"
source=root/"src/stratagus/launcher_bridge.cpp"
video=root/"src/video/sdl.cpp"
java=root/"android/app/src/main/java/net/wargushd/game/WargusHDActivity.java"

update(header,
    "extern int LauncherPollCommand();",
    """extern int LauncherPollCommand();

/// Owner-only Android test: a bounded cheat command queue from the Java button to the
/// engine's own thread. Codes are whitelisted in the JNI entry. The Lua VM is never
/// touched on Android's UI thread.
extern int LauncherPollCheat();
""")

update(header,
    "LauncherMsgChat = 7          /// a game with other people can be talked in (1) or no longer (0)",
    """LauncherMsgChat = 7,         /// a game with other people can be talked in (1) or no longer (0)
    LauncherMsgCheatReady = 10,  /// owner-only touch palette may be shown (value = 1)
    LauncherMsgCheatResult = 11  /// owner-only cheat execution: +/- id (negative = refused)
""")

update(source,
    "static std::atomic<int> PendingCommand{0};",
    """static std::atomic<int> PendingCommand{0};
/// Exactly one command at a time; prevents repeated clicks from queuing dozens of cheats.
static std::atomic<int> PendingCheat{0};

int LauncherPollCheat()
{
    return PendingCheat.exchange(0);
}
""")

update(source,
    '/// The host\'s player has typed a chat line (UTF-8 bytes); the engine takes it in its next frame.',
    """/// Owner-only direct cheat bridge. A button sends one of four numbered commands; the
/// engine consumes it during WaitEventsOneFrame, never here in the Android UI thread.
/// No arbitrary Lua, keyboard injection, or file-system command channel is accepted.
extern "C" JNIEXPORT jboolean JNICALL
Java_net_wargushd_game_WargusHDActivity_nativeCheatSend(JNIEnv *, jclass, jint code)
{
    if (code < 1 || code > 4) {
        return JNI_FALSE;
    }
    int empty = 0;
    return PendingCheat.compare_exchange_strong(empty, code) ? JNI_TRUE : JNI_FALSE;
}

/// The host's player has typed a chat line (UTF-8 bytes); the engine takes it in its next frame.""")
# Patch main SDL event loop on its owning game thread.
update(video,
    '#include "loadingscreen.h"',
    '#include "loadingscreen.h"\n#include "launcher_bridge.h"')

update(video,
    """\tApplyAudioFocus();

\t// Observe-only debug bridge""",
    """    ApplyAudioFocus();

#ifdef __ANDROID__
    // The first touch-prototype tried SDLInputConnection.nativeCommitText after
    // SDL_StopTextInput. That cannot work: SDL_StopTextInput disables SDL_TEXTINPUT.
    // Handle whitelisted cheats on the real engine thread instead, where the
    // existing game's Lua HandleCheats is available.
    const bool cheatReady =
        GameRunning && GameCycle > 0 && !GameObserve && !GameEstablishing
        && !IsNetworkGame() && Editor.Running == EditorNotRunning;
    static int cheatReadyLast = -1;
    const int current = cheatReady ? 1 : 0;
    if (current != cheatReadyLast) {
        cheatReadyLast = current;
        LauncherPost(LauncherMsgCheatReady, current);
    }
    const int cheatCode = LauncherPollCheat();
    if (cheatCode > 0) {
        bool completed = false;
        if (cheatReady) {
            const char *word = nullptr;
            switch (cheatCode) {
                case 1: word = "glittering prizes"; break;
                case 2: word = "make it so"; break;
                case 3: word = "on screen"; break;
                case 4: word = "it is a good day to die"; break;
                default: break;
            }
            if (word) {
                completed = HandleCheats(word);
            }
        }
        LauncherPost(LauncherMsgCheatResult, completed ? cheatCode : -cheatCode);
    }
#endif

    // Observe-only debug bridge""")

# Replace the incorrectly wired keyboard-injection Java UI in the separately
# packaged application. Retain the supported Android View overlay.
update(java,
    '    private static native byte[] nativeChatLines();',
    '''    private static native byte[] nativeChatLines();

    /** Deliver a numbered cheat, not keyboard text. Native game thread acknowledges it. */
    private static native boolean nativeCheatSend(int id);''')

update(java,
    '    private void ownerCheatButton(String title, final String command) {',
    '    private void ownerCheatButton(String title, final int command) {')

update(java,
    '''                // Three stages via the already-loaded SDL input bridge:
                // Enter -> type the exact cheat phrase -> Enter.
                // Every ASCII character is sent as its own TEXTINPUT event
                // because this engine reads only the first char per event.
                org.libsdl.app.WargusHDKeys.submit(command);
                ownerCheatMenu.setVisibility(View.GONE);''',
    '''                if (nativeCheatSend(command)) {
                    ownerCheatMenu.setVisibility(View.GONE);
                    android.widget.Toast.makeText(WargusHDActivity.this,
                        "Команда передана движку…", android.widget.Toast.LENGTH_SHORT).show();
                } else {
                    android.widget.Toast.makeText(WargusHDActivity.this,
                        "Другая команда ещё выполняется", android.widget.Toast.LENGTH_SHORT).show();
                }''')

update(java,
    'ownerCheatButton("💰 Добавить ресурсы (+12000 золота)", "glittering prizes");',
    'ownerCheatButton("💰 Добавить ресурсы (+12000 золота)", 1);')
update(java,
    'ownerCheatButton("⚡ Ускорить / вернуть скорость", "make it so");',
    'ownerCheatButton("⚡ Ускорить / вернуть скорость", 2);')
update(java,
    'ownerCheatButton("🗺 Открыть всю карту", "on screen");',
    'ownerCheatButton("🗺 Открыть всю карту", 3);')
update(java,
    'ownerCheatButton("🛡 Неуязвимость: переключить", "it is a good day to die");',
    'ownerCheatButton("🛡 Неуязвимость: переключить", 4);')

update(java,
    '''            } else if (what == MSG_LOADING_END) {
                ownerCheatReady = true;
                ownerCheatTab.setVisibility(View.VISIBLE);
            } else if (what == MSG_RESULT_READY || what == MSG_ENGINE_EXIT) {
                ownerCheatReady = false;
                ownerCheatTab.setVisibility(View.GONE);
                ownerCheatMenu.setVisibility(View.GONE);
            }
        }
''',
    '''            } else if (what == 10) { // LauncherMsgCheatReady, engine decides actual gameplay
                ownerCheatReady = value == 1;
                ownerCheatTab.setVisibility(ownerCheatReady ? View.VISIBLE : View.GONE);
                if (!ownerCheatReady) ownerCheatMenu.setVisibility(View.GONE);
            } else if (what == 11) { // LauncherMsgCheatResult
                android.widget.Toast.makeText(WargusHDActivity.this,
                    value > 0 ? "Чит выполнен" : "Чит отклонён (нет активной миссии)",
                    android.widget.Toast.LENGTH_SHORT).show();
            } else if (what == MSG_RESULT_READY || what == MSG_ENGINE_EXIT) {
                ownerCheatReady = false;
                ownerCheatTab.setVisibility(View.GONE);
                ownerCheatMenu.setVisibility(View.GONE);
            }
        }
''')
# Never show during first game loading/cutscene merely from MSG_LOADING_END.
helper=root/"android/app/src/main/java/org/libsdl/app/WargusHDKeys.java"
assert helper.is_file(),helper
helper.unlink()
print("REMOVED obsolete keyboard injection",helper)
print("DIRECT_JNI_BRIDGE_PATCH_COMPLETE",True)
