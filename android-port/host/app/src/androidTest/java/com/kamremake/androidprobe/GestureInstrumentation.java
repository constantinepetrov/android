package com.kamremake.androidprobe;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.ContentValues;
import android.content.Intent;
import android.content.IntentFilter;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Bundle;
import android.os.SystemClock;
import android.provider.MediaStore;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowInsets;
import android.widget.Button;
import android.widget.TextView;
import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/** Black-box input and image checks; runs only from the separate test APK. */
public final class GestureInstrumentation extends Instrumentation {
    private MainActivity activity;
    @Override public void onCreate(Bundle args) { super.onCreate(args); start(); }
    private void check(boolean ok, String message) { if (!ok) throw new AssertionError(message); }
    private interface Condition { boolean ready(); }
    private void await(Condition condition, String error) throws Exception {
        long end = SystemClock.uptimeMillis() + 30000;
        while (SystemClock.uptimeMillis() < end) { if (condition.ready()) return; Thread.sleep(100); }
        throw new AssertionError(error);
    }
    private Bitmap capture(String name) throws Exception {
        Thread.sleep(600);
        Bitmap bitmap = getUiAutomation().takeScreenshot();
        check(bitmap != null, "screenshot unavailable");
        File file = new File(activity.getFilesDir(), "qa-" + name + ".png");
        try (FileOutputStream out = new FileOutputStream(file)) { check(bitmap.compress(Bitmap.CompressFormat.PNG,100,out), "PNG save"); }
        return bitmap;
    }
    private int different(Bitmap a, Bitmap b) {
        int count=0, w=Math.min(a.getWidth(),b.getWidth()), h=Math.min(a.getHeight(),b.getHeight());
        for(int y=h/5;y<h*4/5;y+=8) for(int x=w/5;x<w*4/5;x+=8) if(a.getPixel(x,y)!=b.getPixel(x,y)) count++;
        return count;
    }
    private void touch(long down, long when, int action, float[] xs, float[] ys) {
        int n=xs.length; MotionEvent.PointerProperties[] props=new MotionEvent.PointerProperties[n];
        MotionEvent.PointerCoords[] coords=new MotionEvent.PointerCoords[n];
        for(int i=0;i<n;i++) { props[i]=new MotionEvent.PointerProperties(); props[i].id=i; props[i].toolType=MotionEvent.TOOL_TYPE_FINGER;
            coords[i]=new MotionEvent.PointerCoords(); coords[i].x=xs[i]; coords[i].y=ys[i]; coords[i].pressure=1; coords[i].size=1; }
        MotionEvent event=MotionEvent.obtain(down,when,action,n,props,coords,0,0,1,1,0,0,android.view.InputDevice.SOURCE_TOUCHSCREEN,0);
        sendPointerSync(event); event.recycle();
    }
    private void tap(float x,float y) {
        long t=SystemClock.uptimeMillis(); touch(t,t,MotionEvent.ACTION_DOWN,new float[]{x},new float[]{y});
        touch(t,t+50,MotionEvent.ACTION_UP,new float[]{x},new float[]{y});
    }
    private IntentFilter pickerFilter() throws Exception {
        IntentFilter filter=new IntentFilter(Intent.ACTION_OPEN_DOCUMENT);
        filter.addCategory(Intent.CATEGORY_OPENABLE); filter.addDataType("*/*"); return filter;
    }
    private void importThroughPickerResult() throws Exception {
        // Synthetic, non-copyrighted fixture in MediaStore; the picker result is
        // intercepted, but app's button, URI stream and private copy are real.
        ContentValues values=new ContentValues(); values.put(MediaStore.Downloads.DISPLAY_NAME,"kam-ci-fixture.map");
        values.put(MediaStore.Downloads.MIME_TYPE,"application/octet-stream");
        Uri uri=activity.getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI,values);
        check(uri!=null,"MediaStore insert");
        try {
            ByteBuffer data=ByteBuffer.allocate(8+64*64*23).order(ByteOrder.LITTLE_ENDIAN);
            data.putInt(64).putInt(64);
            for(int i=0;i<64*64;i++){data.put((byte)(i%64)).put((byte)0).put((byte)((i/64+i%64)%64)).put((byte)0).put((byte)0).put((byte)255);data.position(data.position()+17);}
            try(OutputStream out=activity.getContentResolver().openOutputStream(uri)){check(out!=null,"fixture stream");out.write(data.array());}
            Intent result=new Intent().setData(uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            ActivityMonitor monitor=addMonitor(pickerFilter(),new ActivityResult(Activity.RESULT_OK,result),true);
            Button button=findButton((View)activity.getWindow().getDecorView(), "Open .map"); check(button!=null,"open button missing");
            int[] xy=new int[2]; button.getLocationOnScreen(xy); tap(xy[0]+button.getWidth()/2f,xy[1]+button.getHeight()/2f);
            await(() -> activity.testMapWidth()==64 && activity.testLabel().getText().toString().contains("height sum: 129024"),"SAF import did not complete");
            check(monitor.getHits()>0,"picker was not opened"); removeMonitor(monitor);
        } finally {activity.getContentResolver().delete(uri,null,null);}
    }
    private Button findButton(View view, String text) {
        if(view instanceof Button && ((Button)view).getText().toString().equalsIgnoreCase(text)) return (Button)view;
        if(view instanceof android.view.ViewGroup){ android.view.ViewGroup g=(android.view.ViewGroup)view;
            for(int i=0;i<g.getChildCount();i++){Button b=findButton(g.getChildAt(i), text);if(b!=null)return b;}}
        return null;
    }
    private byte[] syntheticTileset() throws Exception {
        java.io.ByteArrayOutputStream raw=new java.io.ByteArrayOutputStream();
        java.io.ByteArrayOutputStream compressed=new java.io.ByteArrayOutputStream();
        try(java.util.zip.DeflaterOutputStream z=new java.util.zip.DeflaterOutputStream(compressed)) {
            ByteBuffer header=ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putInt(64); z.write(header.array());
            byte[] flags=new byte[64]; java.util.Arrays.fill(flags,(byte)1); z.write(flags);
            for(int tile=0;tile<64;tile++) {
                ByteBuffer meta=ByteBuffer.allocate(8).order(ByteOrder.LITTLE_ENDIAN);
                meta.putShort((short)32).putShort((short)32).putShort((short)0).putShort((short)0); z.write(meta.array());
                for(int i=0;i<32*32;i++) z.write(new byte[]{(byte)(tile*4),(byte)(255-tile*3),(byte)90,(byte)255});
                z.write(0);
            }
        }
        raw.write(new byte[]{'R','X','X','2',0,0}); raw.write(compressed.toByteArray()); return raw.toByteArray();
    }
    private void importTileset() throws Exception {
        byte[] bytes=syntheticTileset(); TilesetRxx decoded=TilesetRxx.read(bytes);
        check(decoded.present[63] && !decoded.present[64],"RXX flags decoded incorrectly");
        try {TilesetRxx.read(java.util.Arrays.copyOf(bytes,12));throw new AssertionError("truncated RXX accepted");} catch(java.io.IOException expected) {}
        ContentValues values=new ContentValues(); values.put(MediaStore.Downloads.DISPLAY_NAME,"kam-ci-tiles.rxx"); values.put(MediaStore.Downloads.MIME_TYPE,"application/octet-stream");
        Uri uri=activity.getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI,values);check(uri!=null,"tileset MediaStore");
        try {
            try(OutputStream out=activity.getContentResolver().openOutputStream(uri)){check(out!=null,"tileset stream");out.write(bytes);}
            Intent result=new Intent().setData(uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            ActivityMonitor monitor=addMonitor(pickerFilter(),new ActivityResult(Activity.RESULT_OK,result),true);
            Button button=findButton(activity.getWindow().getDecorView(),"Open Tileset.rxx");check(button!=null,"tileset button missing");
            int[] xy=new int[2];button.getLocationOnScreen(xy);tap(xy[0]+button.getWidth()/2f,xy[1]+button.getHeight()/2f);
            await(() -> activity.testLabel().getText().toString().contains("Imported Tileset.rxx"),"tileset import did not complete");
            check(monitor.getHits()>0,"tileset picker not opened");removeMonitor(monitor);
        } finally {activity.getContentResolver().delete(uri,null,null);}
    }
    private void checkpoint(String name) {
        android.util.Log.i("KaMProbe", "QA_STEP " + name);
        Bundle status=new Bundle(); status.putString("step",name); sendStatus(0,status);
    }
    @Override public void onStart() {
        Bundle result=new Bundle();
        try {
            Intent launch=new Intent(getTargetContext(),MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            checkpoint("launch"); activity=(MainActivity)startActivitySync(launch); waitForIdleSync();
            await(() -> activity.testLabel().getText().toString().contains("Native Pascal KM_Sort: 134"),"JNI 134 absent");
            checkpoint("import"); importThroughPickerResult();
            checkpoint("before"); Bitmap before=capture("before");
            int w=before.getWidth(),h=before.getHeight();
            check(w>0 && h>0,"empty screenshot");
            int samples=0, ref=before.getPixel(w/3,h/3);
            for(int y=h/3;y<h*2/3;y+=10) for(int x=w/3;x<w*2/3;x+=10) if(before.getPixel(x,y)!=ref) samples++;
            check(samples>50,"map screenshot blank or uniform");
            TextView label=activity.testLabel(); int[] loc=new int[2];label.getLocationOnScreen(loc);
            WindowInsets insets=activity.getWindow().getDecorView().getRootWindowInsets();
            int top=insets==null?0:insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout()).top;
            check(loc[1]>=top && loc[0]>=0 && loc[0]+label.getWidth()<=w && loc[1]+label.getHeight()<=h,"label outside safe screen");
            checkpoint("pan"); float[] initial=activity.testTransform();
            float x=w*.47f,y=h*.55f; long t=SystemClock.uptimeMillis();
            touch(t,t,MotionEvent.ACTION_DOWN,new float[]{x},new float[]{y});
            touch(t,t+60,MotionEvent.ACTION_MOVE,new float[]{x+w*.15f},new float[]{y+h*.06f});
            touch(t,t+100,MotionEvent.ACTION_UP,new float[]{x+w*.15f},new float[]{y+h*.06f});
            waitForIdleSync(); float[] pan=activity.testTransform(); Bitmap panned=capture("pan");
            check(Math.abs(pan[1]-initial[1])>.1f,"pan did not change offset");
            check(different(before,panned)>100,"pan did not change screen pixels");
            checkpoint("pinch"); t=SystemClock.uptimeMillis(); float x1=w*.42f,x2=w*.58f;
            touch(t,t,MotionEvent.ACTION_DOWN,new float[]{x1},new float[]{y});
            touch(t,t+30,MotionEvent.ACTION_POINTER_DOWN | (1<<MotionEvent.ACTION_POINTER_INDEX_SHIFT),new float[]{x1,x2},new float[]{y,y});
            for(int i=1;i<=8;i++) touch(t,t+30+i*40,MotionEvent.ACTION_MOVE,new float[]{x1-i*w*.025f,x2+i*w*.025f},new float[]{y,y});
            touch(t,t+400,MotionEvent.ACTION_POINTER_UP | (1<<MotionEvent.ACTION_POINTER_INDEX_SHIFT),new float[]{x1-w*.2f,x2+w*.2f},new float[]{y,y});
            touch(t,t+430,MotionEvent.ACTION_UP,new float[]{x1-w*.2f},new float[]{y});
            waitForIdleSync(); float[] zoom=activity.testTransform(); Bitmap pinched=capture("pinch");
            check(zoom[0]>pan[0]+.05f,"pinch did not change scale");
            check(different(panned,pinched)>100,"pinch did not change screen pixels");
            checkpoint("context"); int generation=activity.testSurfaceGeneration();
            runOnMainSync(() -> activity.testRecreateGlContext());
            await(() -> activity.testSurfaceGeneration()>generation && activity.testMapWidth()==64,"GL context/map not restored");
            Bitmap restored=capture("context-restored");
            check(different(pinched,restored)<100,"GL context restored with changed map image");
            checkpoint("tileset"); importTileset(); Bitmap textured=capture("tileset");
            check(different(restored,textured)>100,"RXX texture did not alter rendered map");
            android.util.Log.i("KaMProbe", "RXX_SYNTHETIC_RENDER_OK");
            android.util.Log.i("KaMProbe", "QA_PASSED pan="+pan[1]+" zoom="+zoom[0]+" context="+activity.testSurfaceGeneration());
            result.putString("result","QA_PASSED"); finish(Activity.RESULT_OK,result);
        } catch(Throwable failure) {
            android.util.Log.e("KaMProbe","QA_FAILED",failure);
            result.putString("failure",android.util.Log.getStackTraceString(failure)); finish(Activity.RESULT_CANCELED,result);
        }
    }
}
