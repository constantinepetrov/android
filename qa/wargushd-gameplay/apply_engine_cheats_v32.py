#!/usr/bin/env python3
"""WargusHD cheats v3.2: real action-path speed boost, reversible native wood toggle.

Apply to pristine WargusHD 3.4.91 AFTER the v1/v2/v3 and v3.1 Java-only
patches. No edits to retail assets. v3.1 and the official installation stay
untouched. It intentionally DOES NOT rely on mutable CPlayer Speed* values to
make the user's actions faster; it hooks the actual order progression instead.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: apply_engine_cheats_v32.py <upstream-wargushd>")
root = Path(sys.argv[1]).resolve()

def patch(path, old, new, expected=1):
    p = root / path
    s = p.read_text()
    count = s.count(old)
    if count != expected:
        raise RuntimeError(f"{path}: expected {expected} occurrences, got {count} of {old[:120]!r}")
    p.write_text(s.replace(old, new))
    print("PATCH", path, "count", count)

header = "src/include/launcher_bridge.h"
bridge = "src/stratagus/launcher_bridge.cpp"
video = "src/video/sdl.cpp"
java = "android/app/src/main/java/net/wargushd/game/WargusHDActivity.java"

patch(header, "extern int LauncherPollCheat();", """extern int LauncherPollCheat();

/// Real order-execution speed, native and per-player, independent of Lua
/// SetSpeeds / Player.Speed* assignments. Kind: 0=build, 1=train, 2=research,
/// 3=upgrade, 4=harvest, 5=return. A bit is recorded ONLY if a live order
/// actually consumes the speed multiplier.
extern int LauncherCheatSpeedMultiplier(int playerIndex, int kind);
extern int LauncherCheatSpeedOwner();
extern unsigned LauncherCheatSpeedActivityMask();
extern void LauncherSetCheatSpeedOwner(int playerIndex);
""")

patch(bridge, "static std::atomic<int> PendingCheat{0};", """static std::atomic<int> PendingCheat{0};

/// Native engine-side per-order accelerator; -1 means disabled. The action
/// methods read this on every simulation step; it never changes opponent speed.
static std::atomic<int> OwnerCheatFastPlayer{-1};
static std::atomic<unsigned> OwnerCheatFastTouched{0};

void LauncherSetCheatSpeedOwner(int playerIndex)
{
    OwnerCheatFastPlayer.store(playerIndex, std::memory_order_relaxed);
    OwnerCheatFastTouched.store(0u, std::memory_order_relaxed);
}

int LauncherCheatSpeedOwner()
{
    return OwnerCheatFastPlayer.load(std::memory_order_relaxed);
}

unsigned LauncherCheatSpeedActivityMask()
{
    return OwnerCheatFastTouched.load(std::memory_order_relaxed);
}

int LauncherCheatSpeedMultiplier(int playerIndex, int kind)
{
    if (playerIndex >= 0 &&
        OwnerCheatFastPlayer.load(std::memory_order_relaxed) == playerIndex) {
        if (kind >= 0 && kind < 6) {
            OwnerCheatFastTouched.fetch_or(1u << kind, std::memory_order_relaxed);
        }
        return 20;
    }
    return 1;
}
""")

patch(bridge,
    "if (code < 1 || code > 8) {",
    "if (code < 1 || code > 9) {")

# Hook the REAL game's state transitions, not just editable player fields.
# Build progresses in 100ths, including the worker's progress-health effect.
patch("src/action/action_built.cpp", '#include "player.h"',
      '#include "player.h"\n#include "launcher_bridge.h"')
patch("src/action/action_built.cpp",
      "std::max(1, amount * unit.Player->SpeedBuild / SPEEDUP_FACTOR)",
      "std::max(1, amount * unit.Player->SpeedBuild / SPEEDUP_FACTOR)"
      " * LauncherCheatSpeedMultiplier(unit.Player->Index, 0)", expected=2)
patch("src/action/action_built.cpp",
      "std::max(1, amount * building.Player->SpeedBuild / SPEEDUP_FACTOR)",
      "std::max(1, amount * building.Player->SpeedBuild / SPEEDUP_FACTOR)"
      " * LauncherCheatSpeedMultiplier(building.Player->Index, 0)")
patch("src/action/action_train.cpp", '#include "player.h"',
      '#include "player.h"\n#include "launcher_bridge.h"')
patch("src/action/action_train.cpp",
      "std::max(1, player.SpeedTrain / SPEEDUP_FACTOR)",
      "std::max(1, player.SpeedTrain / SPEEDUP_FACTOR)"
      " * LauncherCheatSpeedMultiplier(player.Index, 1)")
patch("src/action/action_research.cpp", '#include "player.h"',
      '#include "player.h"\n#include "launcher_bridge.h"')
patch("src/action/action_research.cpp",
      "std::max(1, player.SpeedResearch / SPEEDUP_FACTOR)",
      "std::max(1, player.SpeedResearch / SPEEDUP_FACTOR)"
      " * LauncherCheatSpeedMultiplier(player.Index, 2)")
patch("src/action/action_upgradeto.cpp", '#include "player.h"',
      '#include "player.h"\n#include "launcher_bridge.h"')
patch("src/action/action_upgradeto.cpp",
      "std::max(1, player.SpeedUpgrade / SPEEDUP_FACTOR)",
      "std::max(1, player.SpeedUpgrade / SPEEDUP_FACTOR)"
      " * LauncherCheatSpeedMultiplier(player.Index, 3)")

# Wood and gold waiting time is set per trip, so the harvest multiplier takes
# effect for NEW resource cycles, and may not accelerate an existing chop until
# its current wait ends. Resource movement speed is deliberately unchanged.
patch("src/action/action_resource.cpp", '#include "player.h"',
      '#include "player.h"\n#include "launcher_bridge.h"')
patch("src/action/action_resource.cpp",
      "/ unit.Player->SpeedResourcesHarvest[resinfo.ResourceId]",
      "/ (unit.Player->SpeedResourcesHarvest[resinfo.ResourceId] * "
      "LauncherCheatSpeedMultiplier(unit.Player->Index, 4))", expected=3)
patch("src/action/action_resource.cpp",
      "unit.Player->SpeedResourcesReturn[resinfo.ResourceId] / SPEEDUP_FACTOR",
      "(unit.Player->SpeedResourcesReturn[resinfo.ResourceId] * "
      "LauncherCheatSpeedMultiplier(unit.Player->Index, 5)) / SPEEDUP_FACTOR")

# Replace v3 CPlayer-field manipulation completely: v3's static 'enabled' had
# no game-boundary invalidation and could be out of sync with restored saves.
p = root / video
s = p.read_text()
start = s.index("    // Speed is intentionally not")
end = s.index("\n#endif\n\n    // Observe-only debug bridge", start)
replacement = r'''    // Owner-only ×20 is now read by COrder_Built, Train, Research,
    // UpgradeTo and Resource at the actual moment they advance. The
    // per-action bitmask below is a diagnostic of *consumption*, not just
    // the value a cheat request wrote.
    struct WoodMode {
        bool enabled = false;
        int previous[PlayerMax]{};
    };
    static WoodMode wood;
    static unsigned long previousCycle = 0;
    // GameCycle goes backwards on mission restart/new scenario. Neither the
    // global fast-owner index nor the one-way hatchet state may leak over.
    if (GameCycle < previousCycle) {
        LauncherSetCheatSpeedOwner(-1);
        wood.enabled = false;
    }
    previousCycle = GameCycle;

    const int cheatCode = LauncherPollCheat();
    if (cheatCode > 0) {
        int answer = -cheatCode;
        if (cheatReady && ThisPlayer != nullptr) {
            if (cheatCode == 2) {
                const bool nowEnabled = LauncherCheatSpeedOwner() != ThisPlayer->Index;
                LauncherSetCheatSpeedOwner(nowEnabled ? ThisPlayer->Index : -1);
                if (Lua != nullptr) {
                    lua_pushboolean(Lua, 1);
                    lua_setglobal(Lua, "ischeater");
                }
                answer = nowEnabled ? 102 : 202;
                ErrorPrint("WARGUS_CHEATS speed order-multiplier %s for player %d\n",
                           nowEnabled ? "ON" : "OFF", ThisPlayer->Index);
            } else if (cheatCode == 6) {
                // 'hatchet' is irreversible in Wargus Lua (all players set to
                // 2600). Remember the exact old value for each player and
                // restore on the second tap, with no speed-mode interference.
                if (!wood.enabled) {
                    for (int i = 0; i < PlayerMax; ++i) {
                        wood.previous[i] = Players[i].SpeedResourcesHarvest[WoodCost];
                        Players[i].SpeedResourcesHarvest[WoodCost] = 2600;
                    }
                    wood.enabled = true;
                    answer = 106;
                } else {
                    for (int i = 0; i < PlayerMax; ++i) {
                        Players[i].SpeedResourcesHarvest[WoodCost] = wood.previous[i];
                    }
                    wood.enabled = false;
                    answer = 206;
                }
                if (Lua != nullptr) {
                    lua_pushboolean(Lua, 1);
                    lua_setglobal(Lua, "ischeater");
                }
            } else if (cheatCode == 9) {
                // 900+bitmask when ON, 800+bitmask when OFF; bits are set by
                // actual per-tick action handlers, not by the cheat button.
                const bool active = LauncherCheatSpeedOwner() == ThisPlayer->Index;
                answer = (active ? 900 : 800)
                       + int(LauncherCheatSpeedActivityMask() & 63u);
            } else {
                const char *word = nullptr;
                switch (cheatCode) {
                    case 1: word = "glittering prizes"; break;
                    case 3: word = "on screen"; break;
                    case 4: word = "it is a good day to die"; break;
                    case 5: word = "fill mana"; break;
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
    }'''
p.write_text(s[:start] + replacement + s[end:])
print("PATCH", video, "native order speed toggle, wood toggle, diagnostics")

# Make a separate v3.2 app so the working v3.1 remains available as fallback.
patch("android/app/build.gradle",
      "applicationId 'net.wargushd.game.cheats.v31'",
      "applicationId 'net.wargushd.game.cheats.v32'")
patch("android/app/build.gradle",
      "versionName '3.4.91-cheats-menu-fix-3.1'",
      "versionName '3.4.91-cheats-order-speed-3.2'")
patch("android/app/src/main/res/values/strings.xml",
      '<string name="app_name">WargusHD Cheats v3.1</string>',
      '<string name="app_name">WargusHD Cheats v3.2</string>')

patch(java,
      'ownerCheatButton("🪓 Быстрая рубка дерева (для всех игроков)", 6);',
      'ownerCheatButton("🪓 Быстрая рубка (все игроки): ВКЛ / ВЫКЛ", 6);')
patch(java,
      'ownerCheatButton("🏆 Мгновенная победа (с подтверждением)", 8);',
      'ownerCheatButton("🏆 Мгновенная победа (с подтверждением)", 8);\n'
      '        ownerCheatButton("🧪 Диагностика ×20: проверить работу движка", 9);')

# A real status read from action handlers (build/train/research/upgrade/
# harvesting/return), displayed in a dialog so its evidence remains readable.
patch(java,
      "    private void submitOwnerCheat(int command) {",
      r'''    private String ownerSpeedActivityDescription(int result) {
        if (result < 900) {
            return "Ускорение выключено. Включи ×20 и начни строить здание "
                + "или обучать солдат.";
        }
        int mask = result - 900;
        String[] tasks = {
            "строительство", "обучение войск", "исследования",
            "улучшения зданий", "добыча ресурсов", "возврат ресурсов"
        };
        StringBuilder b = new StringBuilder();
        b.append("×20 включено для своего игрока. Зафиксировано реальное ")
         .append("применение в обработчиках:");
        int seen = 0;
        for (int i = 0; i < tasks.length; ++i) {
            if ((mask & (1 << i)) != 0) {
                b.append("\n• ").append(tasks[i]);
                ++seen;
            }
        }
        if (seen == 0) {
            b.append("\nПока ни один обработчик не использовал ускорение. ")
             .append("Построй здание или закажи солдата, затем проверь снова.");
        }
        b.append("\n\nЭто подтверждает использование множителя движком, ")
         .append("но не замеряет реальное время выполнения.");
        return b.toString();
    }

    private void submitOwnerCheat(int command) {''')

p = root / java
s = p.read_text()
start = s.index("            } else if (what == 11) { // LauncherMsgCheatResult")
end = s.index("            } else if (what == MSG_RESULT_READY || what == MSG_ENGINE_EXIT) {",start)
s = s[:start] + r'''            } else if (what == 11) { // LauncherMsgCheatResult
                if (value >= 800 && value < 964) {
                    new android.app.AlertDialog.Builder(WargusHDActivity.this)
                        .setTitle("Проверка ускорения")
                        .setMessage(ownerSpeedActivityDescription(value))
                        .setPositiveButton("Понятно", null)
                        .show();
                } else {
                    android.widget.Toast.makeText(WargusHDActivity.this,
                        value == 102 ? "Ускорение ×20 ВКЛ (ход игровых действий)"
                        : value == 202 ? "Ускорение ×20 ВЫКЛ"
                        : value == 106 ? "Быстрая рубка ВКЛ (все игроки)"
                        : value == 206 ? "Быстрая рубка ВЫКЛ (обычная скорость)"
                        : value > 0 ? "Чит выполнен" : "Чит отклонён",
                        android.widget.Toast.LENGTH_SHORT).show();
                }
''' + s[end:]
p.write_text(s)
print("PATCH", java, "9 buttons, native order-speed diagnostics")

# Static regression checks. These do not claim the Fold has been tested.
s = (root / video).read_text()
assert 'case 6: word = "hatchet"' not in s
assert 'p.SpeedBuild = FAST' not in s
assert 'LauncherSetCheatSpeedOwner' in s
assert "GameCycle < previousCycle" in s
assert (root / bridge).read_text().count("OwnerCheatFastTouched.fetch_or") == 1
j = (root / java).read_text()
assert j.count("ownerCheatButton(") == 10
assert 'ownerCheatScroll.setVisibility(' in j
assert "ownerSpeedActivityDescription(value)" in j
for path in ("action_built","action_train","action_research","action_upgradeto","action_resource"):
    assert "LauncherCheatSpeedMultiplier" in (root / f"src/action/{path}.cpp").read_text()
print("V32_ENGINE_ACTION_HOOKS_STATIC_PASS")
print("V32_SEPARATE_APP_ID", "net.wargushd.game.cheats.v32")
print("V32_ON_DEVICE_TEST", "pending")
