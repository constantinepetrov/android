#!/usr/bin/env python3
"""Apply a self-contained touch cheats palette to pristine WargusHD 3.4.91 sources.

No native hooks, no game engine replacements, no retail assets. Uses SDL's
existing Java->native keyboard/text bridge and the app's packaged cheats.lua.
Android app ID is changed so it installs next to the original official WargusHD.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: python3 apply_cheat_palette.py /path/to/WargusHD")
root=Path(sys.argv[1]).resolve()
activity=root/"android/app/src/main/java/net/wargushd/game/WargusHDActivity.java"
gradle=root/"android/app/build.gradle"
assert activity.is_file() and gradle.is_file()

def replace_once(text,needle,replacement,where):
    assert text.count(needle)==1,(where,"expected single occurrence",needle,text.count(needle))
    return text.replace(needle,replacement,1)

a=activity.read_text()
a=replace_once(a,"import android.widget.FrameLayout;\n","import android.widget.FrameLayout;\nimport android.widget.LinearLayout;\n",str(activity))
# A small, click-through, floating toolbar. No LAN access; changes only single-player.
code=r'''
    /** Optional single-player toolbar; the shipping game already has a cheats.lua handler. */
    private TextView ownerCheatTab;
    private LinearLayout ownerCheatMenu;
    private boolean ownerCheatReady;

    private int ownerDp(float dp) {
        return Math.round(dp * getResources().getDisplayMetrics().density);
    }

    private void ownerCheatButton(String title, final String command) {
        TextView b = new TextView(this);
        b.setText(title);
        b.setTextSize(15f);
        b.setTextColor(0xFFFFFFFF);
        b.setBackgroundColor(0xFF354454);
        b.setPadding(ownerDp(14), ownerDp(12), ownerDp(14), ownerDp(12));
        b.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                if (!ownerCheatReady || isLanRequest()) {
                    return;
                }
                // Three stages via the already-loaded SDL input bridge:
                // Enter -> type the exact cheat phrase -> Enter.
                // Every ASCII character is sent as its own TEXTINPUT event
                // because this engine reads only the first char per event.
                org.libsdl.app.WargusHDKeys.submit(command);
                ownerCheatMenu.setVisibility(View.GONE);
            }
        });
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        p.bottomMargin = ownerDp(5);
        ownerCheatMenu.addView(b, p);
    }

    private void createOwnerCheatPalette() {
        if (overlayHost == null || isLanRequest()) {
            return;
        }
        ownerCheatTab = new TextView(this);
        ownerCheatTab.setText("⚙ ЧИТЫ");
        ownerCheatTab.setTextSize(14f);
        ownerCheatTab.setTextColor(0xFFFFFFFF);
        ownerCheatTab.setBackgroundColor(0xDC24384A);
        ownerCheatTab.setPadding(ownerDp(12),ownerDp(7),ownerDp(12),ownerDp(7));
        ownerCheatTab.setVisibility(View.GONE);
        FrameLayout.LayoutParams tab = new FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.WRAP_CONTENT,FrameLayout.LayoutParams.WRAP_CONTENT,
            Gravity.TOP | Gravity.RIGHT);
        tab.topMargin=ownerDp(18);
        tab.rightMargin=ownerDp(14);
        overlayHost.addView(ownerCheatTab,tab);

        ownerCheatMenu = new LinearLayout(this);
        ownerCheatMenu.setOrientation(LinearLayout.VERTICAL);
        ownerCheatMenu.setBackgroundColor(0xF0192532);
        ownerCheatMenu.setPadding(ownerDp(10),ownerDp(10),ownerDp(10),ownerDp(10));
        ownerCheatMenu.setVisibility(View.GONE);
        FrameLayout.LayoutParams panel = new FrameLayout.LayoutParams(
            ownerDp(280),FrameLayout.LayoutParams.WRAP_CONTENT,Gravity.TOP | Gravity.RIGHT);
        panel.topMargin=ownerDp(68);
        panel.rightMargin=ownerDp(14);
        overlayHost.addView(ownerCheatMenu,panel);
        ownerCheatButton("💰 Добавить ресурсы (+12000 золота)", "glittering prizes");
        ownerCheatButton("⚡ Ускорить / вернуть скорость", "make it so");
        ownerCheatButton("🗺 Открыть всю карту", "on screen");
        ownerCheatButton("🛡 Неуязвимость: переключить", "it is a good day to die");

        TextView note = new TextView(this);
        note.setText("Одиночная игра. Читы обнуляют итоговые очки. "
            + "Ускорение и неуязвимость — переключатели, ресурсы добавляются каждый раз.");
        note.setTextSize(11f);
        note.setTextColor(0xFFCAD1D9);
        note.setPadding(ownerDp(6),ownerDp(7),ownerDp(6),ownerDp(6));
        ownerCheatMenu.addView(note);
        ownerCheatTab.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                if (ownerCheatReady) {
                    ownerCheatMenu.setVisibility(
                        ownerCheatMenu.getVisibility()==View.VISIBLE ? View.GONE : View.VISIBLE);
                }
            }
        });
    }

'''
a=replace_once(a,"    private void createOverlayHost() {\n",code+"    private void createOverlayHost() {\n",str(activity))
a=replace_once(a,"        createOverlayHost();\n","        createOverlayHost();\n        createOwnerCheatPalette();\n",str(activity))
needle='        final int value = (param instanceof Integer) ? (Integer) param : 0;\n'
hook='''        final int value = (param instanceof Integer) ? (Integer) param : 0;
        if (ownerCheatTab != null) {
            if (what == MSG_LOADING_BEGIN) {
                ownerCheatReady = false;
                ownerCheatTab.setVisibility(View.GONE);
                ownerCheatMenu.setVisibility(View.GONE);
            } else if (what == MSG_LOADING_END) {
                ownerCheatReady = true;
                ownerCheatTab.setVisibility(View.VISIBLE);
            } else if (what == MSG_RESULT_READY || what == MSG_ENGINE_EXIT) {
                ownerCheatReady = false;
                ownerCheatTab.setVisibility(View.GONE);
                ownerCheatMenu.setVisibility(View.GONE);
            }
        }
'''
a=replace_once(a,needle,hook,str(activity))
activity.write_text(a)

# This class is deliberately within the existing SDL package, so it can call
# SDLInputConnection.nativeCommitText without reflection or other privileges.
helper=root/"android/app/src/main/java/org/libsdl/app/WargusHDKeys.java"
helper.parent.mkdir(parents=True,exist_ok=True)
assert not helper.exists()
helper.write_text(r'''package org.libsdl.app;

import android.view.KeyEvent;

/** Non-invasive owner UI bridge to the retail WargusHD Lua cheat handler. */
public final class WargusHDKeys {
    private WargusHDKeys() {}

    private static void enter() {
        SDLActivity.onNativeKeyDown(KeyEvent.KEYCODE_ENTER);
        SDLActivity.onNativeKeyUp(KeyEvent.KEYCODE_ENTER);
    }

    public static void submit(String phrase) {
        if (phrase == null
            || !(phrase.equals("glittering prizes")
                || phrase.equals("make it so")
                || phrase.equals("on screen")
                || phrase.equals("it is a good day to die"))) {
            throw new IllegalArgumentException("Unknown cheat phrase");
        }
        enter();
        for (int i=0; i<phrase.length(); ++i) {
            // C++ src/video/sdl.cpp reads only event.text.text[0], so send 1 char per event.
            SDLInputConnection.nativeCommitText(String.valueOf(phrase.charAt(i)), 1);
        }
        enter();
    }
}
''')

g=gradle.read_text()
g=replace_once(g,"applicationId 'net.wargushd.game'",
               "applicationId 'net.wargushd.game.cheats'  // parallel owner-only test",
               str(gradle))
g=replace_once(g,"versionName '3.4.91'",
               "versionName '3.4.91-cheats-test1'",str(gradle))
gradle.write_text(g)
print("PATCHED_ACTIVITY",activity)
print("PATCHED_HELPER",helper)
print("PATCHED_PACKAGE_ID","net.wargushd.game.cheats")
print("ORIGINAL_APPLICATION_UNTOUCHED",True)
