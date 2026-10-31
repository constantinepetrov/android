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
    static native int nativeFogProbe();
    static final String DIAGNOSTIC_ACTION = "com.kamremake.androidprobe.DIAGNOSTIC";
    private ProbeView view;
    private TextView label;
    private boolean nativeFinished;
    private volatile boolean mapPending;
    private volatile int resumeGeneration;
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
        Button tiles = new Button(this); tiles.setText("Open Tileset.rxx");
        FrameLayout.LayoutParams tileParams = new FrameLayout.LayoutParams(-2, -2, Gravity.BOTTOM | Gravity.START);
        frame.addView(tiles, tileParams);
        tiles.setOnClickListener(v -> {
            Intent pick = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*");
            startActivityForResult(pick, 18);
        });
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
            FrameLayout.LayoutParams tileSafe = (FrameLayout.LayoutParams) tiles.getLayoutParams();
            tileSafe.setMargins(left, top, right, bottom); tiles.setLayoutParams(tileSafe);
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
        if ((request != 17 && request != 18) || result != RESULT_OK || data == null || data.getData() == null) return;
        Uri uri = data.getData();
        if (request == 18) {
            label.setText("Importing terrain sprites…");
            new Thread(() -> {
                try (InputStream in = getContentResolver().openInputStream(uri)) {
                    if (in == null) throw new java.io.IOException("Cannot open tileset");
                    java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream();
                    byte[] b = new byte[16384]; int n, total = 0;
                    while ((n=in.read(b)) != -1) {total += n; if(total>16*1024*1024) throw new java.io.IOException("Tileset exceeds 16 MiB");bytes.write(b,0,n);}
                    TilesetRxx tileset = TilesetRxx.read(bytes.toByteArray());
                    int[] map = view.renderer.currentMap;
                    if (map != null) for(int i=3;i<map.length;i++) if(!tileset.present[map[i]&255])
                        throw new java.io.IOException("Tileset lacks terrain sprite " + (map[i]&255));
                    view.renderer.setTiles(tileset);
                    runOnUiThread(() -> label.setText("Imported Tileset.rxx: terrain sprites (flat preview; no objects or simulation)"));
                } catch (Exception failure) { runOnUiThread(() -> label.setText("Tileset error: " + failure.getMessage())); }
            }, "tileset-import").start();
            return;
        }
        label.setText("Importing map…");
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
    @Override protected void onResume() { super.onResume(); view.onResume(); resumeGeneration++; }

    // Read-only snapshots for the instrumentation APK; no test control endpoint.
    float[] testTransform() { return new float[]{view.renderer.zoom, view.renderer.offsetX, view.renderer.offsetY}; }
    int testMapWidth() { return view.renderer.mapWidth; }
    int testSurfaceGeneration() { return view.renderer.surfaceGeneration; }
    int testResumeGeneration() { return resumeGeneration; }
    TextView testLabel() { return label; }
    void testRecreateGlContext() { view.onPause(); view.onResume(); }

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
        int program, textureProgram, tilesProgram, texture, atlasTexture;
        volatile TilesetRxx pendingTiles, currentTiles;
        volatile int[] pendingMap, currentMap;
        volatile int mapWidth, mapHeight, surfaceGeneration;
        boolean reported, mapDrawReported;
        void setMap(int[] map) {
            if(currentTiles != null) for(int i=3;i<map.length;i++) if(!currentTiles.present[map[i]&255]) {
                currentTiles=null; pendingTiles=null; break;
            }
            currentMap = map; pendingMap = map;
        }
        void setTiles(TilesetRxx tiles) { currentTiles=tiles; pendingTiles=tiles; pendingMap=currentMap; }
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
          pendingMap = currentMap; pendingTiles = currentTiles; mapWidth = 0; mapHeight = 0; surfaceGeneration++;
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
            vertex = shader(GLES20.GL_VERTEX_SHADER, "attribute vec2 p; varying vec2 uv; uniform float z; uniform vec2 o; void main(){uv=(p+1.0)*0.5;gl_Position=vec4(p*z+o,0.0,1.0);}");
            fragment = shader(GLES20.GL_FRAGMENT_SHADER, "precision highp float; varying vec2 uv; uniform sampler2D tex; uniform sampler2D atlas; uniform vec2 mapSize; void main(){vec2 pos=vec2(uv.x,1.0-uv.y)*mapSize; vec2 cell=floor(pos); vec2 local=fract(pos); vec4 d=texture2D(tex,(cell+0.5)/mapSize); float id=floor(d.r*255.0+0.5); float rot=floor(d.g*255.0+0.5); if(rot>2.5)local=vec2(1.0-local.y,local.x); else if(rot>1.5)local=1.0-local; else if(rot>0.5)local=vec2(local.y,1.0-local.x); vec2 a=(vec2(mod(id,16.0),floor(id/16.0))+local)/16.0; gl_FragColor=texture2D(atlas,a);}");
            tilesProgram=GLES20.glCreateProgram(); GLES20.glAttachShader(tilesProgram,vertex); GLES20.glAttachShader(tilesProgram,fragment); GLES20.glLinkProgram(tilesProgram);
            GLES20.glGetProgramiv(tilesProgram,GLES20.GL_LINK_STATUS,ok,0); if(ok[0]==0)throw new IllegalStateException(GLES20.glGetProgramInfoLog(tilesProgram));
            GLES20.glDeleteShader(vertex); GLES20.glDeleteShader(fragment);
            int[] ids = new int[2]; GLES20.glGenTextures(2, ids, 0); texture = ids[0]; atlasTexture=ids[1];
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
            TilesetRxx tiles=pendingTiles;
            if(tiles!=null) {
                pendingTiles=null; GLES20.glActiveTexture(GLES20.GL_TEXTURE1); GLES20.glBindTexture(GLES20.GL_TEXTURE_2D,atlasTexture);
                GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D,GLES20.GL_TEXTURE_MIN_FILTER,GLES20.GL_NEAREST);
                GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D,GLES20.GL_TEXTURE_MAG_FILTER,GLES20.GL_NEAREST);
                GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D,GLES20.GL_TEXTURE_WRAP_S,GLES20.GL_CLAMP_TO_EDGE);
                GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D,GLES20.GL_TEXTURE_WRAP_T,GLES20.GL_CLAMP_TO_EDGE);
                ByteBuffer atlas=ByteBuffer.allocateDirect(tiles.atlas.length); atlas.put(tiles.atlas).position(0);
                GLES20.glTexImage2D(GLES20.GL_TEXTURE_2D,0,GLES20.GL_RGBA,TilesetRxx.SIDE,TilesetRxx.SIDE,0,GLES20.GL_RGBA,GLES20.GL_UNSIGNED_BYTE,atlas);
                GLES20.glActiveTexture(GLES20.GL_TEXTURE0);
            }
            int[] map = pendingMap;
            if (map != null) {
                pendingMap = null; mapDrawReported = false; mapWidth = map[0]; mapHeight = map[1];
                ByteBuffer pixels = ByteBuffer.allocateDirect(mapWidth * mapHeight * 4);
                for (int i = 3; i < map.length; i++) {
                    int terrain = map[i] & 255, height = (map[i] >>> 8) & 255;
                    if(currentTiles!=null) { pixels.put((byte)terrain); pixels.put((byte)((map[i]>>>16)&3)); pixels.put((byte)0); }
                    else { pixels.put((byte)Math.min(255, height * 3 + (terrain * 17 % 70)));
                      pixels.put((byte)Math.min(255, height * 3 + 35)); pixels.put((byte)(30 + terrain * 29 % 120)); }
                    pixels.put((byte)255);
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
                int activeProgram=currentTiles==null?textureProgram:tilesProgram;
                GLES20.glUseProgram(activeProgram); GLES20.glActiveTexture(GLES20.GL_TEXTURE0); GLES20.glBindTexture(GLES20.GL_TEXTURE_2D, texture);
                if(currentTiles!=null) {
                    GLES20.glActiveTexture(GLES20.GL_TEXTURE1); GLES20.glBindTexture(GLES20.GL_TEXTURE_2D,atlasTexture);
                    GLES20.glUniform1i(GLES20.glGetUniformLocation(activeProgram,"atlas"),1);
                    GLES20.glUniform2f(GLES20.glGetUniformLocation(activeProgram,"mapSize"),mapWidth,mapHeight);
                    GLES20.glActiveTexture(GLES20.GL_TEXTURE0);
                }
                FloatBuffer quad = ByteBuffer.allocateDirect(8*4).order(ByteOrder.nativeOrder()).asFloatBuffer();
                quad.put(new float[]{-1,-1, 1,-1, -1,1, 1,1}).position(0);
                int a = GLES20.glGetAttribLocation(activeProgram,"p"); GLES20.glEnableVertexAttribArray(a);
                GLES20.glVertexAttribPointer(a,2,GLES20.GL_FLOAT,false,0,quad);
                GLES20.glUniform1f(GLES20.glGetUniformLocation(activeProgram,"z"),zoom);
                GLES20.glUniform2f(GLES20.glGetUniformLocation(activeProgram,"o"),offsetX,offsetY);
                GLES20.glDrawArrays(GLES20.GL_TRIANGLE_STRIP,0,4); GLES20.glDisableVertexAttribArray(a);
                if (!mapDrawReported && GLES20.glGetError() == GLES20.GL_NO_ERROR) {
                    mapDrawReported = true; android.util.Log.i("KaMProbe", "MAP_DRAWN");
                }
                return;
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
