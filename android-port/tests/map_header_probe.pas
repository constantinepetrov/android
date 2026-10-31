program map_header_probe;
{$mode delphi}
uses SysUtils, KM_CommonClasses, KM_MapHeader, KM_MapLegacyTile;
var stream: TKMemoryStreamBinary; w, h, rev: Integer; size: Cardinal; tile: TKMLegacyMapTile;
begin
  if not (ParamCount in [1, 4]) then begin
    WriteLn(StdErr, 'usage: map_header_probe <map> [expected-width expected-height expected-revision]');
    Halt(2);
  end;
  stream := TKMemoryStreamBinary.Create;
  try
    stream.LoadFromFile(ParamStr(1));
    w := 0; h := 0; rev := 0; size := 0;
    LoadMapHeader(stream, w, h, rev, size);
    WriteLn('width=', w, ' height=', h, ' revision=', rev, ' data_size=', size, ' bytes=', stream.Size);
    if (rev = 0) and (stream.Size - stream.Position >= 23) then begin
      ReadLegacyMapTile(stream, tile);
      WriteLn('first_tile terrain=', tile.Terrain, ' height=', tile.Height, ' rotation=', tile.Rotation, ' object=', tile.Obj);
    end;
    if (ParamCount = 4) and ((w <> StrToInt(ParamStr(2))) or (h <> StrToInt(ParamStr(3))) or
       (rev <> StrToInt(ParamStr(4)))) then Halt(1);
  finally stream.Free end;
end.
