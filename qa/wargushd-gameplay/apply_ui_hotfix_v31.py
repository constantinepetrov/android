#!/usr/bin/env python3
"""WargusHD v3.1: fix invisible scroll-menu regression, leave v3 engine unchanged.

Run AFTER apply_cheat_palette.py, apply_native_cheat_bridge.py and
apply_gameplay_v3.py. The v3 tab's click listener toggles the inner LinearLayout
rather than its GONE ScrollView parent. Therefore the menu can never be seen.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: apply_ui_hotfix_v31.py /path/to/upstream-wargushd")
root = Path(sys.argv[1]).resolve()
activity = root / "android/app/src/main/java/net/wargushd/game/WargusHDActivity.java"
gradle = root / "android/app/build.gradle"
strings = root / "android/app/src/main/res/values/strings.xml"

old_toggle = """                    ownerCheatMenu.setVisibility(
                        ownerCheatScroll.getVisibility()==View.VISIBLE ? View.GONE : View.VISIBLE);"""
new_toggle = """                    ownerCheatScroll.setVisibility(
                        ownerCheatScroll.getVisibility()==View.VISIBLE ? View.GONE : View.VISIBLE);"""

def replace_exact(path: Path, old: str, new: str):
    data = path.read_text()
    count = data.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected 1 match, got {count}: {old[:120]}")
    path.write_text(data.replace(old, new, 1))

replace_exact(activity, old_toggle, new_toggle)
replace_exact(gradle,
              "applicationId 'net.wargushd.game.cheats.v3'",
              "applicationId 'net.wargushd.game.cheats.v31'")
replace_exact(gradle,
              "versionName '3.4.91-cheats-extended-3'",
              "versionName '3.4.91-cheats-menu-fix-3.1'")
replace_exact(strings,
              '<string name="app_name">WargusHD Cheats v3</string>',
              '<string name="app_name">WargusHD Cheats v3.1</string>')

java = activity.read_text()
# Do not ever hide the inner menu: only the outer ScrollView is toggled.
assert new_toggle in java
assert old_toggle not in java
assert java.count("ownerCheatMenu.setVisibility(") == 1  # initial child = VISIBLE
assert "ownerCheatMenu.setVisibility(View.VISIBLE);" in java
assert "ownerCheatScroll.setVisibility(View.GONE);" in java
assert "ownerCheatScroll.addView(ownerCheatMenu);" in java
assert java.count("ownerCheatButton(") == 9  # method + 8 buttons
assert "submitOwnerCheat(command)" in java
print("V31_MENU_HOTFIX_STATIC_TEST_PASS")
print("V31_NATIVE_GAMEPLAY_UNCHANGED")
print("V31_SEPARATE_APP_ID", "net.wargushd.game.cheats.v31")
