unit KM_IoPNGAndroid;
{$I KaM_Remake.inc}
interface
uses KM_CommonTypes;

procedure LoadFromPngAndroid(const aFile: UnicodeString; var aWidth, aHeight: Word; var aPixelData: TKMCardinalArray);
procedure SaveToPngAndroid(aWidth, aHeight: Word; const aPixelData: TKMCardinalArray; const aFilename: UnicodeString);

implementation
uses Classes, SysUtils, ZStream;

type
  TByteArray = array of Byte;

function ReadBE32(S: TStream): Cardinal;
var B: array[0..3] of Byte;
begin
  S.ReadBuffer(B, 4);
  Result := (Cardinal(B[0]) shl 24) or (Cardinal(B[1]) shl 16) or (Cardinal(B[2]) shl 8) or B[3];
end;

procedure WriteBE32(S: TStream; V: Cardinal);
var B: array[0..3] of Byte;
begin
  B[0] := V shr 24; B[1] := V shr 16; B[2] := V shr 8; B[3] := V;
  S.WriteBuffer(B, 4);
end;

function CRC32(S: TStream; Start, Count: Int64): Cardinal;
var I, K, RestorePosition: Int64; C: Cardinal; B: Byte;
begin
  RestorePosition := S.Position;
  S.Position := Start;
  C := $FFFFFFFF;
  for I := 1 to Count do begin
    S.ReadBuffer(B, 1);
    C := C xor B;
    for K := 0 to 7 do
      if (C and 1) <> 0 then C := (C shr 1) xor $EDB88320 else C := C shr 1;
  end;
  S.Position := RestorePosition;
  Result := not C;
end;

function Paeth(A, B, C: Integer): Byte;
var P, PA, PB, PC: Integer;
begin
  P := A + B - C; PA := Abs(P - A); PB := Abs(P - B); PC := Abs(P - C);
  if (PA <= PB) and (PA <= PC) then Result := A
  else if PB <= PC then Result := B else Result := C;
end;

procedure WriteChunk(S: TStream; const Name: AnsiString; Data: TStream; DataSize: Cardinal);
var C: Cardinal; Start: Int64;
begin
  WriteBE32(S, DataSize);
  Start := S.Position;
  S.WriteBuffer(Name[1], 4);
  if (Data <> nil) and (DataSize > 0) then begin
    Data.Position := 0;
    S.CopyFrom(Data, DataSize);
  end;
  C := CRC32(S, Start, S.Position - Start);
  WriteBE32(S, C);
end;

procedure LoadFromPngAndroid(const aFile: UnicodeString; var aWidth, aHeight: Word; var aPixelData: TKMCardinalArray);
const Signature: array[0..7] of Byte = (137,80,78,71,13,10,26,10);
var
  F, Compressed, Raw: TMemoryStream;
  Z: TDecompressionStream;
  InflateBuffer: array[0..32767] of Byte;
  InflateCount: Integer;
  ExpectedRawSize: Int64;
  Sig: array[0..7] of Byte;
  ChunkName: array[0..3] of AnsiChar;
  ChunkLen, W, H, ExpectedCRC: Cardinal;
  ChunkStart: Int64;
  BitDepth, ColorType, Interlace, Filter, Channels, Bpp: Byte;
  Palette, Transparency, IDAT, Row, Prev: TByteArray;
  I, J, X, Y, RowBytes, Sample: Integer;
  A, B, C, V: Integer;
  R, G, Bl, Al: Byte;
  TGray, TR, TG, TB: Word;
  HaveGray, HaveRGB: Boolean;
begin
  F := TFileStream.Create(aFile, fmOpenRead or fmShareDenyWrite);
  Compressed := TMemoryStream.Create;
  Raw := TMemoryStream.Create;
  try
    F.ReadBuffer(Sig, SizeOf(Sig));
    if not CompareMem(@Sig, @Signature, SizeOf(Sig)) then
      raise Exception.Create('Invalid PNG signature: ' + string(aFile));
    W := 0; H := 0; BitDepth := 0; ColorType := 0; Interlace := 0;
    SetLength(Palette, 0); SetLength(Transparency, 0); SetLength(IDAT, 0);
    TGray := 0; TR := 0; TG := 0; TB := 0; HaveGray := False; HaveRGB := False;
    while F.Position < F.Size do begin
      ChunkLen := ReadBE32(F);
      if ChunkLen > 67108864 then raise Exception.Create('PNG chunk exceeds 64 MiB');
      ChunkStart := F.Position;
      F.ReadBuffer(ChunkName, 4);
      if string(ChunkName) = 'IHDR' then begin
        if ChunkLen <> 13 then raise Exception.Create('Invalid PNG IHDR length');
        W := ReadBE32(F); H := ReadBE32(F);
        F.ReadBuffer(BitDepth, 1); F.ReadBuffer(ColorType, 1);
        F.Position := F.Position + 2; // compression and filter method
        F.ReadBuffer(Interlace, 1);
        // CRC is consumed and checked below.
      end else if string(ChunkName) = 'IDAT' then begin
        I := Length(IDAT);
        if Int64(I) + ChunkLen > 67108864 then raise Exception.Create('PNG compressed data exceeds 64 MiB');
        SetLength(IDAT, I + ChunkLen);
        if ChunkLen > 0 then F.ReadBuffer(IDAT[I], ChunkLen);
      end else if string(ChunkName) = 'PLTE' then begin
        SetLength(Palette, ChunkLen);
        if ChunkLen > 0 then F.ReadBuffer(Palette[0], ChunkLen);
      end else if string(ChunkName) = 'tRNS' then begin
        SetLength(Transparency, ChunkLen);
        if ChunkLen > 0 then F.ReadBuffer(Transparency[0], ChunkLen);
        if (ColorType = 0) and (ChunkLen = 2) then begin
          TGray := (Word(Transparency[0]) shl 8) or Transparency[1]; HaveGray := True;
        end else if (ColorType = 2) and (ChunkLen = 6) then begin
          TR := (Word(Transparency[0]) shl 8) or Transparency[1];
          TG := (Word(Transparency[2]) shl 8) or Transparency[3];
          TB := (Word(Transparency[4]) shl 8) or Transparency[5]; HaveRGB := True;
        end;
      end else begin
        F.Position := F.Position + ChunkLen;
      end;
      ExpectedCRC := ReadBE32(F);
      if CRC32(F, ChunkStart, 4 + ChunkLen) <> ExpectedCRC then
        raise Exception.CreateFmt('PNG CRC mismatch in %.4s chunk', [string(ChunkName)]);
      if string(ChunkName) = 'IEND' then Break;
    end;
    if (W = 0) or (H = 0) or (W > 65535) or (H > 65535) then
      raise Exception.Create('PNG dimensions are outside the KaM sprite format');
    if (BitDepth <> 8) or (Interlace <> 0) then
      raise Exception.CreateFmt('Unsupported Android PNG encoding (bit depth %d, interlace %d)', [BitDepth, Interlace]);
    case ColorType of
      0: Channels := 1;
      2: Channels := 3;
      3: Channels := 1;
      4: Channels := 2;
      6: Channels := 4;
    else
      raise Exception.CreateFmt('Unsupported PNG color type %d', [ColorType]);
    end;
    if (ColorType = 3) and ((Length(Palette) = 0) or ((Length(Palette) mod 3) <> 0)) then
      raise Exception.Create('Indexed PNG has no valid palette');
    if (Int64(W) * H > 16777216) then raise Exception.Create('PNG image exceeds 16 megapixels');
    RowBytes := Integer(W) * Channels; Bpp := Channels;
    if Length(IDAT) = 0 then raise Exception.Create('PNG contains no image data');
    Compressed.WriteBuffer(IDAT[0], Length(IDAT)); Compressed.Position := 0;
    ExpectedRawSize := Int64(H) * (RowBytes + 1);
    Z := TDecompressionStream.Create(Compressed);
    try
      repeat
        InflateCount := Z.Read(InflateBuffer, SizeOf(InflateBuffer));
        if InflateCount > 0 then begin
          if Raw.Size + InflateCount > ExpectedRawSize then
            raise Exception.Create('PNG decompressed data exceeds dimensions in IHDR');
          Raw.WriteBuffer(InflateBuffer, InflateCount);
        end;
      until InflateCount = 0;
    finally Z.Free; end;
    if Raw.Size <> ExpectedRawSize then
      raise Exception.Create('PNG decompressed data size does not match IHDR');
    SetLength(Row, RowBytes); SetLength(Prev, RowBytes);
    SetLength(aPixelData, W * H); Raw.Position := 0;
    for Y := 0 to H - 1 do begin
      Raw.ReadBuffer(Filter, 1); Raw.ReadBuffer(Row[0], RowBytes);
      if Filter > 4 then raise Exception.CreateFmt('Unknown PNG row filter %d', [Filter]);
      for X := 0 to RowBytes - 1 do begin
        A := 0; B := Prev[X]; C := 0;
        if X >= Bpp then begin A := Row[X-Bpp]; C := Prev[X-Bpp]; end;
        case Filter of
          1: V := Row[X] + A;
          2: V := Row[X] + B;
          3: V := Row[X] + ((A+B) div 2);
          4: V := Row[X] + Paeth(A,B,C);
        else V := Row[X]; end;
        Row[X] := Byte(V);
      end;
      for X := 0 to Integer(W)-1 do begin
        I := X * Channels; R := 0; G := 0; Bl := 0; Al := 255;
        case ColorType of
          0: begin R := Row[I]; G := R; Bl := R; if HaveGray and (Word(R) = TGray) then Al := 0; end;
          2: begin R := Row[I]; G := Row[I+1]; Bl := Row[I+2];
                 if HaveRGB and (Word(R) = TR) and (Word(G) = TG) and (Word(Bl) = TB) then Al := 0; end;
          3: begin Sample := Row[I]; J := Sample * 3;
                 if J + 2 >= Length(Palette) then raise Exception.Create('PNG palette index is out of range');
                 R := Palette[J]; G := Palette[J+1]; Bl := Palette[J+2];
                 if Sample < Length(Transparency) then Al := Transparency[Sample]; end;
          4: begin R := Row[I]; G := R; Bl := R; Al := Row[I+1]; end;
          6: begin R := Row[I]; G := Row[I+1]; Bl := Row[I+2]; Al := Row[I+3]; end;
        end;
        aPixelData[Y * Integer(W) + X] := Cardinal(R) or (Cardinal(G) shl 8) or (Cardinal(Bl) shl 16) or (Cardinal(Al) shl 24);
      end;
      Prev := Copy(Row, 0, RowBytes);
    end;
    aWidth := W; aHeight := H;
  finally Raw.Free; Compressed.Free; F.Free; end;
end;

procedure SaveToPngAndroid(aWidth, aHeight: Word; const aPixelData: TKMCardinalArray; const aFilename: UnicodeString);
const Signature: array[0..7] of Byte = (137,80,78,71,13,10,26,10);
var
  F, Data, Compressed: TMemoryStream;
  Z: TCompressionStream;
  Header: array[0..12] of Byte;
  Row: TByteArray;
  X, Y, N: Integer;
  C: Cardinal;
  Dir: string;
begin
  if (aWidth = 0) or (aHeight = 0) or (Length(aPixelData) < Integer(aWidth)*aHeight) then
    raise Exception.Create('Invalid PNG dimensions or pixel buffer');
  Dir := ExtractFilePath(string(aFilename)); if Dir <> '' then ForceDirectories(Dir);
  Data := TMemoryStream.Create; Compressed := TMemoryStream.Create;
  try
    Z := TCompressionStream.Create(clDefault, Compressed);
    try
      SetLength(Row, Integer(aWidth)*4+1);
      for Y := 0 to aHeight-1 do begin
        Row[0] := 0;
        for X := 0 to aWidth-1 do begin
          C := aPixelData[Y*Integer(aWidth)+X]; N := 1+X*4;
          Row[N] := C; Row[N+1] := C shr 8; Row[N+2] := C shr 16; Row[N+3] := C shr 24;
        end;
        Z.WriteBuffer(Row[0], Length(Row));
      end;
    finally Z.Free; end;
    Data.Position := 0;
    F := TFileStream.Create(string(aFilename), fmCreate);
    try
      F.WriteBuffer(Signature, SizeOf(Signature));
      FillChar(Header, SizeOf(Header), 0);
      Header[0] := aWidth shr 8; Header[1] := aWidth;
      Header[4] := aHeight shr 8; Header[5] := aHeight;
      Header[8] := 8; Header[9] := 6;
      Data.WriteBuffer(Header, SizeOf(Header));
      WriteChunk(F, 'IHDR', Data, SizeOf(Header));
      Compressed.Position := 0;
      WriteChunk(F, 'IDAT', Compressed, Compressed.Size);
      Data.Clear; WriteChunk(F, 'IEND', Data, 0);
    finally F.Free; end;
  finally Compressed.Free; Data.Free; end;
end;

end.
