program map_header_semantics;
{$mode delphi}
uses SysUtils, KM_CommonClasses, KM_MapHeader, KM_MapLegacyTile;
var s: TKMemoryStreamBinary; w, h, rev: Integer; dataSize: Cardinal; rejected: Boolean; tile: TKMLegacyMapTile; i: Integer;
procedure ReadHeader;
begin
  s.Position := 0; w := -1; h := -1; rev := -1; dataSize := 0;
  LoadMapHeader(s, w, h, rev, dataSize);
end;
begin
  s := TKMemoryStreamBinary.Create;
  try
    s.Write(Integer(128)); s.Write(Integer(64));
    ReadHeader;
    if (w <> 128) or (h <> 64) or (rev <> 0) then Halt(1);
    s.Clear;
    s.Write(Integer(0)); s.WriteW(UnicodeString('r9000')); s.Write(Cardinal(123));
    s.Write(Integer(96)); s.Write(Integer(80));
    ReadHeader;
    if (w <> 96) or (h <> 80) or (rev <> 9000) or (dataSize <> 123) then Halt(2);
    s.Clear;
    s.Write(Integer(-1)); s.Write(Integer(64));
    rejected := False;
    try ReadHeader except on E: Exception do rejected := True end;
    if not rejected then Halt(3);
    s.Clear;
    s.Write(Byte(14)); s.Write(Byte(0)); s.Write(Byte(33)); s.Write(Byte(7));
    s.Write(Byte(0)); s.Write(Byte(255));
    for i := 1 to 17 do s.Write(Byte(i));
    s.Position := 0;
    ReadLegacyMapTile(s, tile);
    if (tile.Terrain <> 14) or (tile.Height <> 33) or (tile.Rotation <> 3) or
       (tile.Obj <> 255) or (s.Position <> 23) then Halt(4);
    WriteLn('original map header and legacy tile semantics OK');
  finally s.Free end;
end.
