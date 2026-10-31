program map_header_probe;
{$mode delphi}
uses SysUtils, KM_CommonClasses, KM_MapHeader, KM_MapLegacyTile;
var stream: TKMemoryStreamBinary; w, h, rev, i, objects: Integer; size: Cardinal; tile, first: TKMLegacyMapTile; heightSum: Int64;
begin
  if not (ParamCount in [1, 4, 7]) then begin
    WriteLn(StdErr, 'usage: map_header_probe <map> [expected-width expected-height expected-revision [expected-tiles expected-height-sum expected-object-tiles]]');
    Halt(2);
  end;
  stream := TKMemoryStreamBinary.Create;
  try
    stream.LoadFromFile(ParamStr(1));
    w := 0; h := 0; rev := 0; size := 0;
    LoadMapHeader(stream, w, h, rev, size);
    WriteLn('width=', w, ' height=', h, ' revision=', rev, ' data_size=', size, ' bytes=', stream.Size);
    if rev = 0 then begin
      if stream.Size - stream.Position < Int64(w) * h * 23 then
        raise Exception.Create('Truncated legacy map terrain data');
      objects := 0; heightSum := 0;
      for i := 0 to w * h - 1 do begin
        ReadLegacyMapTile(stream, tile);
        if i = 0 then first := tile;
        Inc(heightSum, tile.Height);
        if tile.Obj <> 255 then Inc(objects);
      end;
      WriteLn('first_tile terrain=', first.Terrain, ' height=', first.Height,
        ' rotation=', first.Rotation, ' object=', first.Obj);
      WriteLn('tiles=', w * h, ' height_sum=', heightSum, ' object_tiles=', objects);
      if (ParamCount = 7) and ((w * h <> StrToInt(ParamStr(5))) or
        (heightSum <> StrToInt64(ParamStr(6))) or (objects <> StrToInt(ParamStr(7)))) then Halt(3);
    end;
    if (ParamCount >= 4) and ((w <> StrToInt(ParamStr(2))) or (h <> StrToInt(ParamStr(3))) or
       (rev <> StrToInt(ParamStr(4)))) then Halt(1);
  finally stream.Free end;
end.
