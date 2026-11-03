#!/usr/bin/env python3
"""WargusHD Cheats v3 after the v2 direct JNI patch.

Replace the 'make it so' all-player cheat with a *local player's* x20
production multiplier (build/train/research/upgrades/economy), and expose four
additional built-in Lua cheats. v3 installs with its own package ID.
"""
from pathlib import Path
import sys

if len(sys.argv)!=2: raise SystemExit("usage: apply_gameplay_v3.py /path/to/source")
root=Path(sys.argv[1]).resolve()
video=root/"src/video/sdl.cpp"
bridge=root/"src/stratagus/launcher_bridge.cpp"
java=root/"android/app/src/main/java/net/wargushd/game/WargusHDActivity.java"
gradle=root/"android/app/build.gradle"
strings=root/"android/app/src/main/res/values/strings.xml"

def once(p,old,new):
    t=p.read_text()
    n=t.count(old)
    if n!=1:
        raise RuntimeError(f"{p}: expected exactly one anchor but got {n}:\n{old[:200]}")
    p.write_text(t.replace(old,new,1))
    print("PATCH",p,"old_chars",len(old),"new_chars",len(new))

once(bridge,
'''    if (code < 1 || code > 4) {
        return JNI_FALSE;
    }''',
'''    if (code < 1 || code > 8) {
        return JNI_FALSE;
    }''')

once(video,'#include "launcher_bridge.h"',
'''#include "launcher_bridge.h"
#include "player.h"
#include "script.h"''')

old='''    const int cheatCode = LauncherPollCheat();
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
'''
new='''    // Speed is intentionally not "make it so": Wargus' Lua version
    // boosts every player (including AI). Instead change only ThisPlayer's
    // actual production/harvest coefficients, which action code reads each tick.
    // Keep exact original values for a reversible switch, not a guessed 100.
    struct LocalSpeed {
        CPlayer *owner = nullptr;
        bool enabled = false;
        int build = SPEEDUP_FACTOR;
        int train = SPEEDUP_FACTOR;
        int research = SPEEDUP_FACTOR;
        int upgrade = SPEEDUP_FACTOR;
        int harvest[MaxCosts]{};
        int deposit[MaxCosts]{};
    };
    static LocalSpeed speed;
    const int cheatCode = LauncherPollCheat();
    if (cheatCode > 0) {
        int answer = -cheatCode;
        if (cheatReady && ThisPlayer != nullptr) {
            if (cheatCode == 2) {
                CPlayer &p = *ThisPlayer;
                if (speed.owner != &p) {
                    speed.owner = &p;
                    speed.enabled = false;
                }
                if (!speed.enabled) {
                    speed.build = p.SpeedBuild;
                    speed.train = p.SpeedTrain;
                    speed.research = p.SpeedResearch;
                    speed.upgrade = p.SpeedUpgrade;
                    for (int i=0;i<MaxCosts;++i) {
                        speed.harvest[i] = p.SpeedResourcesHarvest[i];
                        speed.deposit[i] = p.SpeedResourcesReturn[i];
                    }
                    constexpr int FAST = SPEEDUP_FACTOR * 20;
                    p.SpeedBuild = FAST;
                    p.SpeedTrain = FAST;
                    p.SpeedResearch = FAST;
                    p.SpeedUpgrade = FAST;
                    for (int i=0;i<MaxCosts;++i) {
                        p.SpeedResourcesHarvest[i] = FAST;
                        p.SpeedResourcesReturn[i] = FAST;
                    }
                    speed.enabled = true;
                    // The original script marks any cheat with zero ranked score.
                    // Do the same for this direct native-only command.
                    if (Lua != nullptr) {
                        lua_pushboolean(Lua, 1);
                        lua_setglobal(Lua, "ischeater");
                    }
                    answer = (p.SpeedBuild == FAST && p.SpeedTrain == FAST) ? 102 : -2;
                } else {
                    p.SpeedBuild = speed.build;
                    p.SpeedTrain = speed.train;
                    p.SpeedResearch = speed.research;
                    p.SpeedUpgrade = speed.upgrade;
                    for (int i=0;i<MaxCosts;++i) {
                        p.SpeedResourcesHarvest[i] = speed.harvest[i];
                        p.SpeedResourcesReturn[i] = speed.deposit[i];
                    }
                    speed.enabled = false;
                    answer = (p.SpeedBuild == speed.build && p.SpeedTrain == speed.train) ? 202 : -2;
                }
            } else {
                const char *word = nullptr;
                switch (cheatCode) {
                    case 1: word = "glittering prizes"; break;
                    case 3: word = "on screen"; break;
                    case 4: word = "it is a good day to die"; break;
                    case 5: word = "fill mana"; break;
                    case 6: word = "hatchet"; break;
                    case 7: word = "fow on"; break;
                    case 8: word = "unite the clans"; break;
                    default: break;
                }
                if (word && HandleCheats(word)) {
                    answer = cheatCode;
                }
            }
        }
        LauncherPost(LauncherMsgCheatResult, answer);
    }
'''
once(video,old,new)

# Never claim this palette is ready while the GUI owns game input.
once(video,
    'GameRunning && GameCycle > 0 && !GameObserve && !GameEstablishing',
    'GameRunning && GameCycle > 0 && !GuichanOwnsInput() && !GameObserve && !GameEstablishing')

# v2 JNI returns actual completion; add a confirmation for irreversible victory.
old='''                if (nativeCheatSend(command)) {
                    ownerCheatMenu.setVisibility(View.GONE);
                    android.widget.Toast.makeText(WargusHDActivity.this,
                        "Команда передана движку…", android.widget.Toast.LENGTH_SHORT).show();
                } else {
                    android.widget.Toast.makeText(WargusHDActivity.this,
                        "Другая команда ещё выполняется", android.widget.Toast.LENGTH_SHORT).show();
                }'''
new='''                if (command == 8) {
                    new android.app.AlertDialog.Builder(WargusHDActivity.this)
                        .setTitle("Завершить миссию победой?")
                        .setMessage("Игра сразу завершит миссию. Это действие нельзя отменить.")
                        .setPositiveButton("Победа", (dialog, which) -> submitOwnerCheat(command))
                        .setNegativeButton("Отмена", null)
                        .show();
                } else {
                    submitOwnerCheat(command);
                }'''
once(java,old,new)

once(java,
    '''    private void ownerCheatButton(String title, final int command) {''',
    '''    private void submitOwnerCheat(int command) {
        if (nativeCheatSend(command)) {
            ownerCheatScroll.setVisibility(View.GONE);
        } else {
            android.widget.Toast.makeText(this,
                "Другая команда ещё выполняется", android.widget.Toast.LENGTH_SHORT).show();
        }
    }

    private void ownerCheatButton(String title, final int command) {''')

# Put 8 options inside a bounded scroll panel, not across the intro/game field.
once(java,
    '''    private LinearLayout ownerCheatMenu;
    private boolean ownerCheatReady;''',
    '''    private LinearLayout ownerCheatMenu;
    private android.widget.ScrollView ownerCheatScroll;
    private boolean ownerCheatReady;''')
once(java,
    '''        ownerCheatMenu.setVisibility(View.GONE);
        FrameLayout.LayoutParams panel = new FrameLayout.LayoutParams(
            ownerDp(280),FrameLayout.LayoutParams.WRAP_CONTENT,Gravity.TOP | Gravity.RIGHT);''',
    '''        ownerCheatMenu.setVisibility(View.VISIBLE);
        FrameLayout.LayoutParams panel = new FrameLayout.LayoutParams(
            ownerDp(300),
            Math.min(ownerDp(450), (int)(getResources().getDisplayMetrics().heightPixels * 0.76f)),
            Gravity.TOP | Gravity.RIGHT);''')
once(java,
    '''        overlayHost.addView(ownerCheatMenu,panel);
        ownerCheatButton("💰 Добавить ресурсы (+12000 золота)", 1);
        ownerCheatButton("⚡ Ускорить / вернуть скорость", 2);
        ownerCheatButton("🗺 Открыть всю карту", 3);
        ownerCheatButton("🛡 Неуязвимость: переключить", 4);''',
    '''        ownerCheatScroll = new android.widget.ScrollView(this);
        ownerCheatScroll.setFillViewport(false);
        ownerCheatScroll.setVerticalScrollBarEnabled(true);
        ownerCheatScroll.setVisibility(View.GONE);
        ownerCheatScroll.addView(ownerCheatMenu);
        overlayHost.addView(ownerCheatScroll,panel);
        ownerCheatButton("💰 Ресурсы: +12000 золота, +5000 дерева и нефти", 1);
        ownerCheatButton("⚡ Ускорение ×20 только для себя / обычная скорость", 2);
        ownerCheatButton("🗺 Открыть всю карту", 3);
        ownerCheatButton("🛡 Неуязвимость: вкл/выкл", 4);
        ownerCheatButton("🔮 Восстановить ману всем своим магам", 5);
        ownerCheatButton("🪓 Быстрая рубка дерева (для всех игроков)", 6);
        ownerCheatButton("🌫 Вернуть туман войны", 7);
        ownerCheatButton("🏆 Мгновенная победа (с подтверждением)", 8);''')

once(java,
    '''        note.setText("Одиночная игра. Читы обнуляют итоговые очки. "
            + "Ускорение и неуязвимость — переключатели, ресурсы добавляются каждый раз.");''',
    '''        note.setText("Только одиночная игра. Читы обнуляют очки. "
            + "Ускорение ×20 действует только на твою сторону. "
            + "Рубка дерева ускоряется для всех.");''')

# In all remaining callbacks, visible/gone acts on the ScrollView, not the
# always-VISIBLE inner LinearLayout. Initial visibility above is now VISIBLE.
a=java.read_text()
a=a.replace("ownerCheatMenu.setVisibility(View.GONE)", "ownerCheatScroll.setVisibility(View.GONE)")
a=a.replace("ownerCheatMenu.setVisibility(View.VISIBLE)", "ownerCheatScroll.setVisibility(View.VISIBLE)")
a=a.replace("ownerCheatMenu.getVisibility()", "ownerCheatScroll.getVisibility()")
# Re-repair the initial child visibility that was intentionally always VISIBLE:
needle='''        ownerCheatMenu.setPadding(ownerDp(10),ownerDp(10),ownerDp(10),ownerDp(10));
        ownerCheatScroll.setVisibility(View.VISIBLE);'''
if needle not in a: raise RuntimeError("Initial menu child anchor missing")
a=a.replace(needle,needle.replace("ownerCheatScroll.setVisibility(View.VISIBLE)",
                               "ownerCheatMenu.setVisibility(View.VISIBLE)"),1)
java.write_text(a)

once(java,
    '''value > 0 ? "Чит выполнен" : "Чит отклонён (нет активной миссии)",''',
    '''value == 102 ? "Ускорение ×20 ВКЛ (только твоя сторона)"
                        : value == 202 ? "Обычная скорость восстановлена"
                        : value > 0 ? "Чит выполнен" : "Чит отклонён",''')

once(gradle,"applicationId 'net.wargushd.game.cheats.v2'",
            "applicationId 'net.wargushd.game.cheats.v3'")
once(gradle,"versionName '3.4.91-cheats-native-2'",
            "versionName '3.4.91-cheats-extended-3'")
once(strings,'<string name="app_name">WargusHD Cheats v2</string>',
             '<string name="app_name">WargusHD Cheats v3</string>')
assert 'ownerCheatMenu.setVisibility(View.GONE)' not in java.read_text()
assert 'ownerCheatScroll.setVisibility(View.GONE)' in java.read_text()
assert 'case 8: word = "unite the clans"' in video.read_text()
print("GAMEPLAY_V3_PATCH_OK",True)
