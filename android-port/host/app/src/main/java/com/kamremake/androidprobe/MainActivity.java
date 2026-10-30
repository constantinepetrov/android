package com.kamremake.androidprobe;

import android.app.Activity;
import android.opengl.GLES20;
import android.opengl.GLSurfaceView;
import android.os.Bundle;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.ScaleGestureDetector;
import android.widget.FrameLayout;
import android.widget.TextView;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.FloatBuffer;
import javax.microedition.khronos.egl.EGLConfig;
import javax.microedition.khronos.opengles.GL10;

/** Integration probe only: there is no game loop or original map here. */
public final class MainActivity extends Activity {
    static { System.loadLibrary("kamprobe"); }
    private static native int nativeSortProbe();
    private ProbeView view;
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        FrameLayout frame = new FrameLayout(this);
        int result = nativeSortProbe();
        view = new ProbeView(this);
        frame.addView(view);
        TextView label = new TextView(this);
        label.setText("Native Pascal KM_Sort: " + result + " (expected 134)\nIntegration probe • drag / pinch");
        label.setTextColor(0xffffffff);
        label.setBackgroundColor(0xb0000000);
        label.setPadding(16, 12, 16, 12);
        FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(-2, -2, Gravity.TOP | Gravity.START);
        frame.addView(label, params);
        setContentView(frame);
    }
    @Override protected void onPause() { view.onPause(); super.onPause(); }
    @Override protected void onResume() { super.onResume(); view.onResume(); }

    private static final class ProbeView extends GLSurfaceView {
        final ProbeRenderer renderer = new ProbeRenderer();
        final ScaleGestureDetector scale;
        float lastX, lastY;
        boolean dragging;
        ProbeView(Activity activity) {
            super(activity);
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
        int program;
        ProbeRenderer() { vertices.put(new float[]{-.5f,-.4f, .5f,-.4f, 0f,.5f}).position(0); }
        private int shader(int kind, String src) {
            int shader = GLES20.glCreateShader(kind);
            GLES20.glShaderSource(shader, src); GLES20.glCompileShader(shader);
            int[] ok = new int[1]; GLES20.glGetShaderiv(shader, GLES20.GL_COMPILE_STATUS, ok, 0);
            if (ok[0] == 0) throw new IllegalStateException(GLES20.glGetShaderInfoLog(shader));
            return shader;
        }
        @Override public void onSurfaceCreated(GL10 gl, EGLConfig config) {
            int vertex = shader(GLES20.GL_VERTEX_SHADER, "attribute vec2 p; uniform float z; uniform vec2 o; void main(){gl_Position=vec4(p*z+o,0.0,1.0);}");
            int fragment = shader(GLES20.GL_FRAGMENT_SHADER, "precision mediump float; void main(){gl_FragColor=vec4(0.9,0.65,0.18,1.0);}");
            program = GLES20.glCreateProgram(); GLES20.glAttachShader(program, vertex); GLES20.glAttachShader(program, fragment); GLES20.glLinkProgram(program);
            int[] ok = new int[1]; GLES20.glGetProgramiv(program, GLES20.GL_LINK_STATUS, ok, 0);
            if (ok[0] == 0) throw new IllegalStateException(GLES20.glGetProgramInfoLog(program));
            GLES20.glDeleteShader(vertex); GLES20.glDeleteShader(fragment);
        }
        @Override public void onSurfaceChanged(GL10 gl, int width, int height) { GLES20.glViewport(0, 0, width, height); }
        @Override public void onDrawFrame(GL10 gl) {
            GLES20.glClearColor(.08f,.13f,.12f,1f); GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT); GLES20.glUseProgram(program);
            int pos = GLES20.glGetAttribLocation(program,"p"); GLES20.glEnableVertexAttribArray(pos);
            GLES20.glVertexAttribPointer(pos,2,GLES20.GL_FLOAT,false,0,vertices);
            GLES20.glUniform1f(GLES20.glGetUniformLocation(program,"z"),zoom);
            GLES20.glUniform2f(GLES20.glGetUniformLocation(program,"o"),offsetX,offsetY);
            GLES20.glDrawArrays(GLES20.GL_TRIANGLES,0,3); GLES20.glDisableVertexAttribArray(pos);
        }
    }
}
