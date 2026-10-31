program png_codec_smoke;
{$mode delphi}
uses SysUtils, KM_CommonTypes, KM_IoPNGAndroid;
var
  Pixels, Loaded: TKMCardinalArray;
  W, H: Word;
  I: Integer;
  Path: UnicodeString;
begin
  Path := IncludeTrailingPathDelimiter(GetTempDir(False)) + 'kam-png-codec-smoke.png';
  SetLength(Pixels, 6);
  Pixels[0] := $FF332211; Pixels[1] := $804477AA; Pixels[2] := $00123456;
  Pixels[3] := $FFFFFFFF; Pixels[4] := $7F010203; Pixels[5] := $CCABCDEF;
  SaveToPngAndroid(3, 2, Pixels, Path);
  try
    LoadFromPngAndroid(Path, W, H, Loaded);
    if (W <> 3) or (H <> 2) or (Length(Loaded) <> Length(Pixels)) then
      raise Exception.Create('PNG round-trip dimensions changed');
    for I := 0 to High(Pixels) do
      if Loaded[I] <> Pixels[I] then
        raise Exception.CreateFmt('PNG round-trip pixel %d differs: %.8x <> %.8x', [I, Loaded[I], Pixels[I]]);
    WriteLn('PNG_CODEC_RGBA_ALPHA_CRC_ROUNDTRIP_OK 3x2');
  finally
    if FileExists(Path) then DeleteFile(Path);
  end;
end.
