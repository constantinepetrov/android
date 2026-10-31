package com.kamremake.androidprobe;

import android.app.Service;
import android.content.Intent;
import android.os.IBinder;
import android.util.Log;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** A fatal native fault must kill only the diagnostic subprocess. */
public final class NativeProbeService extends Service {
    // FPC 3.2.2 initializes process-global RTL state; never enter it concurrently.
    private static final ExecutorService PASCAL_WORKER = Executors.newSingleThreadExecutor(r -> {
        Thread thread = new Thread(r, "pascal-probe");
        thread.setDaemon(true);
        return thread;
    });
    static native int[] nativeReadMap(String path);
    static native int nativeFfiProbe();
    static native int nativeFfiScriptProbe();
    static native int nativeRealUtilsScriptProbe();
    private void report(String stage, String detail) {
        Log.i("KaMProbe", stage + ": " + detail);
        Intent message = new Intent(MainActivity.DIAGNOSTIC_ACTION);
        message.setPackage(getPackageName());
        message.putExtra("stage", stage);
        message.putExtra("detail", detail);
        sendBroadcast(message);
    }
    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        final Intent request = intent == null ? null : new Intent(intent);
        PASCAL_WORKER.execute(() -> {
            try {
                report("LOAD", "loading libkamprobe.so and Pascal RTL");
                System.loadLibrary("kamprobe");
                report("LOAD", "library and Pascal RTL initialized");
                if (request != null && request.getBooleanExtra("ffiTest", false)) {
                    System.loadLibrary("kamffi_probe");
                    int ffi = nativeFfiProbe();
                    if (ffi != 42) throw new IllegalStateException("FFI_ABI_FAILED code=" + ffi);
                    Log.i("KaMProbe", "FFI_ABI_OK self integer single out TKMPoint");
                    int script = nativeFfiScriptProbe();
                    if (script != 42) throw new IllegalStateException("FFI_SCRIPT_FAILED code=" + script);
                    Log.i("KaMProbe", "FFI_SCRIPT_OK facade self integer single out; invalid script rejected");
                    int gameUtils = nativeRealUtilsScriptProbe();
                    if (gameUtils != 42) throw new IllegalStateException("REAL_UTILS_SCRIPT_FAILED code=" + gameUtils);
                    report("FFI", "REAL_UTILS_SCRIPT_OK registered TKMScriptUtils.AbsI Self integer result; invalid script rejected");
                    return;
                }
                if (request != null && request.getBooleanExtra("selfTest", false)) {
                    java.io.File f = new java.io.File(getFilesDir(), "synthetic-test.map");
                    java.nio.ByteBuffer bytes = java.nio.ByteBuffer.allocate(8 + 4 * 23).order(java.nio.ByteOrder.LITTLE_ENDIAN);
                    bytes.putInt(2).putInt(2);
                    for (int i = 0; i < 4; i++) { bytes.put((byte)(i+1)).put((byte)0).put((byte)(10+i)).put((byte)0).put((byte)0).put((byte)255); bytes.position(bytes.position()+17); }
                    try (java.io.FileOutputStream out = new java.io.FileOutputStream(f)) { out.write(bytes.array(), 0, 12); }
                    if (nativeReadMap(f.getAbsolutePath()) != null) throw new IllegalStateException("Truncated map accepted");
                    Log.i("KaMProbe", "MAP_TRUNCATED_REJECTED");
                    try (java.io.FileOutputStream out = new java.io.FileOutputStream(f)) { out.write(bytes.array()); }
                    int[] test = nativeReadMap(f.getAbsolutePath());
                    if (test == null || test.length != 7 || test[0] != 2 || test[1] != 2 || test[2] != 46) throw new IllegalStateException("Synthetic map mismatch");
                    Intent result = new Intent(MainActivity.DIAGNOSTIC_ACTION).setPackage(getPackageName());
                    result.putExtra("stage", "MAP"); result.putExtra("map", test); sendBroadcast(result);
                    Log.i("KaMProbe", "MAP_SELFTEST_OK 2x2 heightSum=46");
                    return;
                }
                if (request != null && request.hasExtra("mapPath")) {
                    int[] map = nativeReadMap(request.getStringExtra("mapPath"));
                    if (map == null) report("ERROR", "Invalid, truncated, or unsupported map (only original KaM .map format supported)");
                    else {
                        Intent result = new Intent(MainActivity.DIAGNOSTIC_ACTION).setPackage(getPackageName());
                        result.putExtra("stage", "MAP"); result.putExtra("map", map);
                        sendBroadcast(result);
                        Log.i("KaMProbe", "MAP_OK " + map[0] + "x" + map[1] + " heightSum=" + map[2]);
                    }
                    return;
                }
                int rtti = MainActivity.nativeRttiProbe();
                if (rtti != 1) throw new IllegalStateException("Unexpected unconfigured RTTI result: " + rtti);
                Log.i("KaMProbe", "RTTI_NO_CALL_MANAGER_ENOTIMPLEMENTED");
                int fog = MainActivity.nativeFogProbe();
                if (fog != 88) throw new IllegalStateException("Pascal fog state mismatch: " + fog);
                Log.i("KaMProbe", "FOG_FLOW_OK reveal cover save/load and 20 updates");
                Log.i("KaMProbe", "FOG_STATE_UPDATE_OK 3x2 ticks=10 from=100 to=" + fog);
                int value = MainActivity.nativeSortProbe();
                report("JNI", "Native Pascal KM_Sort: " + value + " (expected 134)");
            } catch (Throwable failure) {
                Log.e("KaMProbe", "Native load or JNI failure", failure);
                report("ERROR", failure.toString());
            } finally {
                stopSelf(startId);
            }
        });
        return START_NOT_STICKY;
    }
    @Override public IBinder onBind(Intent intent) { return null; }
}
