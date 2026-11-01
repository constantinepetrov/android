unit KM_IoPNG;
{$I KaM_Remake.inc}
interface
uses
  KM_CommonTypes
  {$IFDEF WDC}, PNGImage{$ENDIF}
  {$IFDEF FPC}{$IFDEF ANDROID}, KM_IoPNGAndroid{$ELSE}, BGRABitmap, BGRABitmapTypes{$ENDIF}{$ENDIF};

procedure SaveToPng(aWidth, aHeight: Word; const aPixelData: TKMCardinalArray; const aFilename: UnicodeString);
procedure LoadFromPng(const aFile: UnicodeString; var aWidth, aHeight: Word; var aPixelData: TKMCardinalArray);

implementation
uses SysUtils;

procedure SaveToPng(aWidth, aHeight: Word; const aPixelData: TKMCardinalArray; const aFilename: UnicodeString);
var
  {$IFDEF WDC} Png: PNGImage.TPngImage; {$ENDIF}
  {$IFDEF FPC}{$IFNDEF ANDROID} Png: TBGRABitmap; {$ENDIF}{$ENDIF}
  I, K: Integer;
  T: Cardinal;
begin
  {$IFDEF ANDROID}
  KM_IoPNGAndroid.SaveToPngAndroid(aWidth, aHeight, aPixelData, aFilename);
  Exit;
  {$ENDIF}
  ForceDirectories(ExtractFilePath(aFilename));
  {$IFDEF WDC}
    Png := TPngImage.CreateBlank(COLOR_RGBALPHA, 8, aWidth, aHeight);
    try
      for I := 0 to aHeight - 1 do
      for K := 0 to aWidth - 1 do
      begin
        T := aPixelData[I * aWidth + K];
        Png.Canvas.Pixels[K, I] := T and $FFFFFF;
        Png.AlphaScanline[I]^[K] := T shr 24;
      end;
      Png.SaveToFile(aFilename);
    finally Png.Free; end;
  {$ENDIF}
  {$IFDEF FPC}{$IFNDEF ANDROID}
    Png := TBGRABitmap.Create(aWidth, aHeight, BGRABlack);
    try
      for I := 0 to aHeight - 1 do
      for K := 0 to aWidth - 1 do
      begin
        T := aPixelData[I * aWidth + K];
        Png.CanvasBGRA.Pixels[K,I] := T and $FFFFFF;
        Png.AlphaPixel(K, I, 255);
      end;
      Png.SaveToFile(aFilename);
    finally Png.Free; end;
  {$ENDIF}{$ENDIF}
end;

procedure LoadFromPng(const aFile: UnicodeString; var aWidth, aHeight: Word; var aPixelData: TKMCardinalArray);
var
  {$IFDEF WDC}
  Png: TPngImage;
  T: Byte;
  {$ENDIF}
  {$IFDEF FPC}{$IFNDEF ANDROID} Png: TBGRABitmap; {$ENDIF}{$ENDIF}
  I, K: Integer;
begin
  {$IFDEF ANDROID}
  KM_IoPNGAndroid.LoadFromPngAndroid(aFile, aWidth, aHeight, aPixelData);
  Exit;
  {$ENDIF}
  {$IFDEF WDC}
    Png := TPngImage.Create;
    try
      Png.LoadFromFile(aFile);
      aWidth := Png.Width; aHeight := Png.Height;
      SetLength(aPixelData, Png.Width * Png.Height);
      case Png.TransparencyMode of
        ptmNone:
          for K:=0 to Png.Height-1 do for I:=0 to Png.Width-1 do
            aPixelData[K * Png.Width + I] := cardinal(Png.Pixels[I,K]) or $FF000000;
        ptmBit:
          begin
            T := 0;
            if TChunktRNS(Png.Chunks.ItemFromClass(TChunktRNS)).DataSize > 0 then
              T := TChunktRNS(Png.Chunks.ItemFromClass(TChunktRNS)).PaletteValues[0];
            for K := 0 to Png.Height - 1 do for I := 0 to Png.Width - 1 do
              if PByteArray(Png.Scanline[K])^[I] = T then
                aPixelData[K * Png.Width + I] := cardinal(Png.Pixels[I,K]) and $FFFFFF
              else
                aPixelData[K * Png.Width + I] := cardinal(Png.Pixels[I,K]) or $FF000000;
          end;
        ptmPartial:
          for K := 0 to Png.Height - 1 do for I := 0 to Png.Width - 1 do
          begin
            T := Png.AlphaScanline[K]^[I];
            aPixelData[K * Png.Width + I] := cardinal(Png.Pixels[I,K]) or (T shl 24);
          end;
      else
        raise Exception.Create('Unknown PNG transparency mode');
      end;
    finally Png.Free; end;
  {$ENDIF}
  {$IFDEF FPC}{$IFNDEF ANDROID}
    Png := TBGRABitmap.Create(aFile);
    try
      aWidth := Png.Width; aHeight := Png.Height;
      SetLength(aPixelData, Png.Width * Png.Height);
      for K:=0 to Png.Height-1 do for I:=0 to Png.Width-1 do
        aPixelData[K * Png.Width + I] := cardinal(Png.GetPixel(I,K).red) or (cardinal(Png.GetPixel(I,K).green) shl 8) or
                                        (cardinal(Png.GetPixel(I,K).blue) shl 16) or (cardinal(Png.GetPixel(I,K).alpha) shl 24);
    finally Png.Free; end;
  {$ENDIF}{$ENDIF}
end;

end.
