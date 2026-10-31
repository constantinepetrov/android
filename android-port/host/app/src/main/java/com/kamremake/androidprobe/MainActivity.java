package com.kamremake.androidprobe;

import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.opengl.GLES20;
import android.opengl.GLSurfaceView;
import android.os.Bundle;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.WindowInsets;
import android.graphics.Insets;
import android.view.ScaleGestureDetector;
import android.widget.FrameLayout;
import android.widget.TextView;
import android.widget.Button;
import android.net.Uri;
import java.io.InputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.FloatBuffer;
import javax.microedition.khronos.egl.EGLConfig;
import javax.microedition.khronos.opengles.GL10;

/** Integration probe only: there is no game loop or original map here. */
public final class MainActivity extends Activity {
    static native int nativeSortProbe();
    static final String DIAGNOSTIC_ACTION = "com.kamremake.androidprobe.DIAGNOSTIC";
    private ProbeView view;
    private TextView label;
    private boolean nativeFinished;
    private volatile boolean mapPending;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final BroadcastReceiver diagnostics = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            String stage = intent.getStringExtra("stage");
            String detail = intent.getStringExtra("detail");
            if ("MAP".equals(stage) || "ERROR".equals(stage)) mapPending = false;
            if ("MAP".equals(stage)) {
                int[] map = intent.getIntArrayExtra("map");
                if (map != null && map.length >= 3 && map.length == 3 + map[0] * map[1]) {
                    view.renderer.setMap(map);
                    label.setText("Diagnostic height/terrain colours (not game graphics)\n" + map[0] + " × " + map[1] + " tiles: " + (map.length - 3) + "  height sum: " + map[2]);
                } else label.setText("ERROR: invalid native map response");
            } else label.setText(stage + ": " + detail);
            if ("JNI".equals(stage) || "ERROR".equals(stage)) nativeFinished = true;
            if ("JNI".equals(stage) && getIntent().getBooleanExtra("synthetic_test", false)) {
                getIntent().removeExtra("synthetic_test");
                startService(new Intent(MainActivity.this, NativeProbeService.class).putExtra("selfTest", true));
            }
        }
    };
    private void graphicsReady() {
        if (isFinishing() || isDestroyed()) return;
        label.setText("OpenGL ES: ready; starting isolated Pascal process");
        startService(new Intent(this, NativeProbeService.class));
        handler.postDelayed(() -> {
            if (!nativeFinished && !isFinishing() && !isDestroyed())
                label.setText("Native process did not respond; inspect logcat and tombstone");
        }, 15000);
    }
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        FrameLayout frame = new FrameLayout(this);
        IntentFilter filter = new IntentFilter(DIAGNOSTIC_ACTION);
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(diagnostics, filter, Context.RECEIVER_NOT_EXPORTED);
        else registerReceiver(diagnostics, filter);
        view = new ProbeView(this);
        frame.addView(view);
        label = new TextView(this);
        label.setText("Activity ready; waiting for OpenGL ES");
        label.setTextColor(0xffffffff);
        label.setBackgroundColor(0xb0000000);
        label.setPadding(16, 12, 16, 12);
        FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(-2, -2, Gravity.TOP | Gravity.START);
        frame.addView(label, params);
        Button open = new Button(this); open.setText("Open .map");
        FrameLayout.LayoutParams buttonParams = new FrameLayout.LayoutParams(-2, -2, Gravity.BOTTOM | Gravity.END);
        frame.addView(open, buttonParams);
        open.setOnClickListener(v -> {
            Intent pick = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*");
            startActivityForResult(pick, 17);
        });
        frame.setOnApplyWindowInsetsListener((v, insets) -> {
            int left, top, right, bottom;
            if (Build.VERSION.SDK_INT >= 30) {
                Insets safe = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
                left = safe.left; top = safe.top; right = safe.right; bottom = safe.bottom;
            } else {
                left = insets.getSystemWindowInsetLeft(); top = insets.getSystemWindowInsetTop();
                right = insets.getSystemWindowInsetRight(); bottom = insets.getSystemWindowInsetBottom();
                if (Build.VERSION.SDK_INT >= 28 && insets.getDisplayCutout() != null) {
                    left = Math.max(left, insets.getDisplayCutout().getSafeInsetLeft());
                    top = Math.max(top, insets.getDisplayCutout().getSafeInsetTop());
                    right = Math.max(right, insets.getDisplayCutout().getSafeInsetRight());
                    bottom = Math.max(bottom, insets.getDisplayCutout().getSafeInsetBottom());
                }
            }
            FrameLayout.LayoutParams safe = (FrameLayout.LayoutParams) label.getLayoutParams();
            safe.setMargins(left, top, right, bottom);
            label.setLayoutParams(safe);
            FrameLayout.LayoutParams buttonSafe = (FrameLayout.LayoutParams) open.getLayoutParams();
            buttonSafe.setMargins(left, top, right, bottom); open.setLayoutParams(buttonSafe);
            final int safeTop = top;
            label.post(() -> {
                int[] location = new int[2];
                label.getLocationOnScreen(location);
                android.util.Log.i("KaMProbe", "INSETS_" + (location[1] >= safeTop ? "OK" : "FAIL")
                        + " labelTop=" + location[1] + " safeTop=" + safeTop);
            });
            return insets;
        });
        setContentView(frame);
        frame.requestApplyInsets();
    }
    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request != 17 || result != RESULT_OK || data == null || data.getData() == null) return;
        Uri uri = data.getData(); label.setText("Importing map…");
        new Thread(() -> {
            try (InputStream in = getContentResolver().openInputStream(uri)) {
                if (in == null) throw new java.io.IOException("Cannot open selected file");
                File file = new File(getFilesDir(), "selected.map");
                try (FileOutputStream out = new FileOutputStream(file)) {
                    byte[] buffer = new byte[16384]; int n, total = 0;
                    while ((n = in.read(buffer)) != -1) {
                        total += n; if (total > 4 * 1024 * 1024) throw new java.io.IOException("Map exceeds 4 MiB limit");
                        out.write(buffer, 0, n);
                    }
                }
                mapPending = true;
                startService(new Intent(this, NativeProbeService.class).putExtra("mapPath", file.getAbsolutePath()));
                handler.postDelayed(() -> { if (mapPending) { mapPending = false; label.setText("Map parser did not respond; see logcat for native process failure"); } }, 15000);
            } catch (Exception failure) { runOnUiThread(() -> label.setText("Import error: " + failure.getMessage())); }
        }, "map-import").start();
    }
    @Override protected void onDestroy() { handler.removeCallbacksAndMessages(null); unregisterReceiver(diagnostics); super.onDestroy(); }
    @Override protected void onPause() { view.onPause(); super.onPause(); }
    @Override protected void onResume() { super.onResume(); view.onResume(); }

    private static final class ProbeView extends GLSurfaceView {
        final ProbeRenderer renderer;
        final ScaleGestureDetector scale;
        float lastX, lastY;
        boolean dragging;
        ProbeView(Activity activity) {
            super(activity);
            renderer = new ProbeRenderer((MainActivity) activity);
            setEGLContextClientVersion(2);
            setRenderer(renderer);
            scale = new ScaleGestureDetector(activity, new ScaleGestureDetector.SimpleOnScaleGestureListener() {
                @Override public boolean onScale(ScaleGestureDetector detector) {
                    renderer.zoom = Math.max(.25f, Math.min(4f, renderer.zoom * detector.getScaleFactor()));
                    return true;
                }
            });
        }
        @Override public boolean onTouchEvent(MotionEvent event) {
            scale.onTouchEvent(event);
            switch (event.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    lastX = event.getX(); lastY = event.getY(); dragging = true; break;
                case MotionEvent.ACTION_POINTER_DOWN:
                    dragging = false; break;
                case MotionEvent.ACTION_MOVE:
                    if (dragging && !scale.isInProgress() && event.getPointerCount() == 1) {
                        float x = event.getX(), y = event.getY();
                        if (getWidth() > 0 && getHeight() > 0) {
                            renderer.offsetX += 2f * (x - lastX) / getWidth();
                            renderer.offsetY -= 2f * (y - lastY) / getHeight();
                        }
                        lastX = x; lastY = y;
                    }
                    break;
                case MotionEvent.ACTION_UP: case MotionEvent.ACTION_CANCEL: case MotionEvent.ACTION_POINTER_UP:
                    dragging = false; break;
                default: break;
            }
            return true;
        }
    }
    private static final class ProbeRenderer implements GLSurfaceView.Renderer {
        volatile float zoom = 1f, offsetX, offsetY;
        final FloatBuffer vertices = ByteBuffer.allocateDirect(6 * 4).order(ByteOrder.nativeOrder()).asFloatBuffer();
        int program, textureProgram, texture;
        volatile int[] pendingMap, currentMap;
        int mapWidth, mapHeight;
        boolean reported;
        void setMap(int[] map) { currentMap = map; pendingMap = map; }
        final MainActivity activity;
        ProbeRenderer(MainActivity activity) { this.activity = activity; vertices.put(new float[]{-.5f,-.4f, .5f,-.4f, 0f,.5f}).position(0); }
        private int shader(int kind, String src) {
            int shader = GLES20.glCreateShader(kind);
            GLES20.glShaderSource(shader, src); GLES20.glCompileShader(shader);
            int[] ok = new int[1]; GLES20.glGetShaderiv(shader, GLES20.GL_COMPILE_STATUS, ok, 0);
            if (ok[0] == 0) throw new IllegalStateException(GLES20.glGetShaderInfoLog(shader));
            return shader;
        }
        @Override public void onSurfaceCreated(GL10 gl, EGLConfig config) {
          pendingMap = currentMap; mapWidth = 0; mapHeight = 0;
          try {
            int vertex = shader(GLES20.GL_VERTEX_SHADER, "attribute vec2 p; uniform float z; uniform vec2 o; void main(){gl_Position=vec4(p*z+o,0.0,1.0);}");
            int fragment = shader(GLES20.GL_FRAGMENT_SHADER, "precision mediump float; void main(){gl_FragColor=vec4(0.9,0.65,0.18,1.0);}");
            program = GLES20.glCreateProgram(); GLES20.glAttachShader(program, vertex); GLES20.glAttachShader(program, fragment); GLES20.glLinkProgram(program);
            int[] ok = new int[1]; GLES20.glGetProgramiv(program, GLES20.GL_LINK_STATUS, ok, 0);
            if (ok[0] == 0) throw new IllegalStateException(GLES20.glGetProgramInfoLog(program));
            GLES20.glDeleteShader(vertex); GLES20.glDeleteShader(fragment);
            vertex = shader(GLES20.GL_VERTEX_SHADER, "attribute vec2 p; varying vec2 uv; uniform float z; uniform vec2 o; void main(){uv=(p+1.0)*0.5;gl_Position=vec4(p*z+o,0.0,1.0);}");
            fragment = shader(GLES20.GL_FRAGMENT_SHADER, "precision mediump float; varying vec2 uv; uniform sampler2D tex; void main(){gl_FragColor=texture2D(tex,vec2(uv.x,1.0-uv.y));}");
            textureProgram = GLES20.glCreateProgram(); GLES20.glAttachShader(textureProgram,vertex); GLES20.glAttachShader(textureProgram,fragment); GLES20.glLinkProgram(textureProgram);
            GLES20.glGetProgramiv(textureProgram,GLES20.GL_LINK_STATUS,ok,0);
            if (ok[0] == 0) throw new IllegalStateException(GLES20.glGetProgramInfoLog(textureProgram));
            GLES20.glDeleteShader(vertex); GLES20.glDeleteShader(fragment);
            int[] ids = new int[1]; GLES20.glGenTextures(1, ids, 0); texture = ids[0];
          } catch (RuntimeException failure) {
            program = 0;
            android.util.Log.e("KaMProbe", "Graphics initialization failed", failure);
            activity.runOnUiThread(() -> activity.label.setText("ERROR: OpenGL ES: " + failure));
          }
        }
        @Override public void onSurfaceChanged(GL10 gl, int width, int height) { GLES20.glViewport(0, 0, width, height); }
        @Override public void onDrawFrame(GL10 gl) {
            if (program == 0) return;
            GLES20.glClearColor(.08f,.13f,.12f,1f); GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT); GLES20.glUseProgram(program);
            int[] map = pendingMap;
            if (map != null) {
                pendingMap = null; mapWidth = map[0]; mapHeight = map[1];
                ByteBuffer pixels = ByteBuffer.allocateDirect(mapWidth * mapHeight * 4);
                for (int i = 3; i < map.length; i++) {
                    int terrain = map[i] & 255, height = (map[i] >>> 8) & 255;
                    pixels.put((byte)Math.min(255, height * 3 + (terrain * 17 % 70)));
                    pixels.put((byte)Math.min(255, height * 3 + 35));
                    pixels.put((byte)(30 + terrain * 29 % 120)); pixels.put((byte)255);
                }
                pixels.position(0); GLES20.glBindTexture(GLES20.GL_TEXTURE_2D, texture);
                GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_MIN_FILTER, GLES20.GL_NEAREST);
                GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_MAG_FILTER, GLES20.GL_NEAREST);
                GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_WRAP_S, GLES20.GL_CLAMP_TO_EDGE);
                GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_WRAP_T, GLES20.GL_CLAMP_TO_EDGE);
                GLES20.glTexImage2D(GLES20.GL_TEXTURE_2D, 0, GLES20.GL_RGBA, mapWidth, mapHeight, 0, GLES20.GL_RGBA, GLES20.GL_UNSIGNED_BYTE, pixels);
                int error = GLES20.glGetError();
                if (error != GLES20.GL_NO_ERROR) { android.util.Log.e("KaMProbe", "MAP_TEXTURE_ERROR " + error); mapWidth = 0; }
                else android.util.Log.i("KaMProbe", "MAP_TEXTURE_UPLOADED " + mapWidth + "x" + mapHeight);
            }
            if (mapWidth > 0) {
                GLES20.glUseProgram(textureProgram); GLES20.glBindTexture(GLES20.GL_TEXTURE_2D, texture);
                FloatBuffer quad = ByteBuffer.allocateDirect(8*4).order(ByteOrder.nativeOrder()).asFloatBuffer();
                quad.put(new float[]{-1,-1, 1,-1, -1,1, 1,1}).position(0);
                int a = GLES20.glGetAttribLocation(textureProgram,"p"); GLES20.glEnableVertexAttribArray(a);
                GLES20.glVertexAttribPointer(a,2,GLES20.GL_FLOAT,false,0,quad);
                GLES20.glUniform1f(GLES20.glGetUniformLocation(textureProgram,"z"),zoom);
                GLES20.glUniform2f(GLES20.glGetUniformLocation(textureProgram,"o"),offsetX,offsetY);
                GLES20.glDrawArrays(GLES20.GL_TRIANGLE_STRIP,0,4); GLES20.glDisableVertexAttribArray(a); return;
            }
            int pos = GLES20.glGetAttribLocation(program,"p"); GLES20.glEnableVertexAttribArray(pos);
            GLES20.glVertexAttribPointer(pos,2,GLES20.GL_FLOAT,false,0,vertices);
            GLES20.glUniform1f(GLES20.glGetUniformLocation(program,"z"),zoom);
            GLES20.glUniform2f(GLES20.glGetUniformLocation(program,"o"),offsetX,offsetY);
            GLES20.glDrawArrays(GLES20.GL_TRIANGLES,0,3); GLES20.glDisableVertexAttribArray(pos);
            if (!reported) { reported = true; activity.runOnUiThread(activity::graphicsReady); }
        }
    }
}
