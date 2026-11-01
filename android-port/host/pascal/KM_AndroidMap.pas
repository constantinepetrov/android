unit KM_AndroidMap;
{$mode delphi}
interface
uses SysUtils, Classes;
type TMapValues = array of LongInt;
function ReadDiagnosticMap(const Path: string; out Values: TMapValues): Boolean;
implementation
uses KM_CommonClasses, KM_MapHeader, KM_MapLegacyTile;
function ReadDiagnosticMap(const Path: string; out Values: TMapValues): Boolean;
var f: TFileStream; s: TKMemoryStreamBinary; w,h,rev,i: Integer; dataSize: Cardinal; tile: TKMLegacyMapTile; sum: Int64;
begin
  Result := False; Values := nil;
  s := TKMemoryStreamBinary.Create;
  try
    try
      // Check size before loading the whole file, including hostile imports.
      f := TFileStream.Create(Path, fmOpenRead or fmShareDenyWrite);
      try
        if (f.Size < 8) or (f.Size > 4 * 1024 * 1024) then Exit;
        s.CopyFrom(f, f.Size);
      finally f.Free end;
      s.Position := 0;
      // Only the original KaM format is supported. Do not parse untrusted
      // variable-length Remake headers until their lengths are bounded.
      s.Read(w);
      if w = 0 then Exit;
      s.Position := 0; w := 0; h := 0; rev := 0; dataSize := 0;
      LoadMapHeader(s, w, h, rev, dataSize);
      if (rev <> 0) or (s.Size - s.Position < Int64(w) * h * 23) then Exit;
      SetLength(Values, 3 + w * h); sum := 0;
      Values[0] := w; Values[1] := h;
      for i := 0 to w * h - 1 do begin
        ReadLegacyMapTile(s, tile);
        Inc(sum, tile.Height);
        Values[3+i] := LongInt(tile.Terrain) or (LongInt(tile.Height) shl 8)
          or (LongInt(tile.Rotation) shl 16) or (LongInt(tile.Obj) shl 24);
      end;
      Values[2] := sum;
      Result := True;
    except
      Values := nil;
    end;
  finally s.Free end;
end;
end.
