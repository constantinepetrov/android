package com.kamremake.androidprobe;

import android.app.Service;
import android.content.Intent;
import android.os.IBinder;
import android.util.Log;

/** A fatal native fault must kill only the diagnostic subprocess. */
public final class NativeProbeService extends Service {
    private void report(String stage, String detail) {
        Log.i("KaMProbe", stage + ": " + detail);
        Intent message = new Intent(MainActivity.DIAGNOSTIC_ACTION);
        message.setPackage(getPackageName());
        message.putExtra("stage", stage);
        message.putExtra("detail", detail);
        sendBroadcast(message);
    }
    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        new Thread(() -> {
            try {
                report("LOAD", "loading libkamprobe.so and Pascal RTL");
                System.loadLibrary("kamprobe");
                report("LOAD", "library and Pascal RTL initialized");
                int value = MainActivity.nativeSortProbe();
                report("JNI", "Native Pascal KM_Sort: " + value + " (expected 134)");
            } catch (Throwable failure) {
                Log.e("KaMProbe", "Native load or JNI failure", failure);
                report("ERROR", failure.toString());
            } finally {
                stopSelf(startId);
            }
        }, "pascal-probe").start();
        return START_NOT_STICKY;
    }
    @Override public IBinder onBind(Intent intent) { return null; }
}
