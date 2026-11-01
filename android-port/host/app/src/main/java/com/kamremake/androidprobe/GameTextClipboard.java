package com.kamremake.androidprobe;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.os.Looper;
import java.lang.ref.WeakReference;

/** Text-only host API for a native editor input call on the focused UI thread. */
public final class GameTextClipboard {
    private static WeakReference<Activity> owner = new WeakReference<>(null);
    private GameTextClipboard() {}
    public static void initialize(Activity activity) { owner = new WeakReference<>(activity); }
    private static ClipboardManager manager() {
        Activity activity = owner.get();
        if (Looper.myLooper() != Looper.getMainLooper() || activity == null
                || activity.isFinishing() || !activity.hasWindowFocus())
            throw new IllegalStateException("Clipboard input requires the focused Activity UI thread");
        ClipboardManager result = (ClipboardManager) activity.getSystemService(Context.CLIPBOARD_SERVICE);
        if (result == null) throw new IllegalStateException("ClipboardManager unavailable");
        return result;
    }
    public static String readText() {
        ClipboardManager clipboard = manager();
        if (!clipboard.hasPrimaryClip()) return "";
        ClipData data = clipboard.getPrimaryClip();
        if (data == null || data.getItemCount() == 0)
            throw new IllegalStateException("Clipboard contents unavailable");
        CharSequence text = data.getItemAt(0).getText();
        if (text == null) throw new IllegalStateException("Clipboard does not contain plain text");
        return text.toString();
    }
    public static void writeText(String text) {
        if (text == null) throw new IllegalArgumentException("Null clipboard text");
        manager().setPrimaryClip(ClipData.newPlainText("KaM", text));
    }
}
