package com.kamremake.androidprobe;

import java.io.ByteArrayInputStream;
import java.io.DataInputStream;
import java.io.EOFException;
import java.io.IOException;
import java.io.InputStream;
import java.util.zip.InflaterInputStream;

/** Bounded reader for the non-unit RGBA RXX layout in KM_ResSprites.LoadFromRXXFile.
 * It produces only the first 256 legacy terrain sprites, not an RXA atlas or RX palette.
 */
final class TilesetRxx {
    static final int TILE=32, SIDE=16*TILE;
    final byte[] atlas = new byte[SIDE*SIDE*4];
    final boolean[] present = new boolean[256];
    private static int u16(DataInputStream in) throws IOException { int a=in.readUnsignedByte(), b=in.readUnsignedByte(); return a | (b<<8); }
    private static int i32(DataInputStream in) throws IOException { return u16(in) | (u16(in)<<16); }
    private static void skipExactly(DataInputStream in, int size) throws IOException {
        byte[] buffer=new byte[4096];
        while(size>0) {int n=in.read(buffer,0,Math.min(buffer.length,size)); if(n<0)throw new EOFException(); size-=n;}
    }
    static TilesetRxx read(byte[] input) throws IOException {
        if(input.length<4 || input.length>16*1024*1024) throw new IOException("Invalid RXX file size");
        int offset;
        if(input[0]=='R'&&input[1]=='X'&&input[2]=='X'&&input[3]=='1') offset=36;
        else if(input[0]=='R'&&input[1]=='X'&&input[2]=='X'&&input[3]=='2') {
            if(input.length<6) throw new IOException("Truncated RXX metadata");
            offset=6+(input[4]&255)+((input[5]&255)<<8);
        } else if((input[0]&255)==0x78 && (input[1]&255)==0xda) offset=0;
        else throw new IOException("Unsupported tileset: select Tileset.rxx, not RXA or RX");
        if(offset>=input.length) throw new IOException("Truncated RXX header");
        InputStream limited = new InputStream() {
            final InflaterInputStream z = new InflaterInputStream(new ByteArrayInputStream(input,offset,input.length-offset));
            long total;
            @Override public int read() throws IOException { int b=z.read(); if(b>=0 && ++total>64L*1024*1024)throw new IOException("RXX expanded size limit"); return b; }
            @Override public int read(byte[] b,int off,int len) throws IOException {int n=z.read(b,off,len); if(n>0 && (total+=n)>64L*1024*1024)throw new IOException("RXX expanded size limit");return n;}
            @Override public void close() throws IOException {z.close();}
        };
        try(DataInputStream in=new DataInputStream(limited)) {
            int count=i32(in); if(count<1||count>4096) throw new IOException("Invalid RXX sprite count");
            byte[] flags=new byte[count]; in.readFully(flags);
            TilesetRxx result=new TilesetRxx();
            for(int i=0;i<count;i++) {
                if(flags[i]==0) continue;
                if(flags[i]!=1) throw new IOException("Invalid RXX sprite flag");
                int w=u16(in),h=u16(in); u16(in);u16(in); // 16-bit size and signed pivot
                long pixels=(long)w*h;
                if(w<1||h<1||pixels>4L*1024*1024) throw new IOException("Invalid RXX sprite dimensions");
                if(i<256 && (w!=TILE||h!=TILE)) throw new IOException("Legacy terrain sprite is not 32x32");
                if(i<256) {
                    byte[] row=new byte[TILE*4]; int baseX=(i%16)*TILE,baseY=(i/16)*TILE;
                    for(int y=0;y<TILE;y++){in.readFully(row);System.arraycopy(row,0,result.atlas,((baseY+y)*SIDE+baseX)*4,row.length);}
                    result.present[i]=true;
                } else skipExactly(in,(int)(pixels*4));
                int hasMask=in.readUnsignedByte(); if(hasMask>1)throw new IOException("Invalid RXX mask flag");
                if(hasMask==1) skipExactly(in,(int)pixels);
            }
            return result;
        }
    }
}
