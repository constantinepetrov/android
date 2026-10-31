program map_header_semantics;
{$mode delphi}
uses SysUtils, KM_CommonClasses, KM_MapHeader;
var s: TKMemoryStreamBinary; w, h, rev: Integer; dataSize: Cardinal; rejected: Boolean;
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
    WriteLn('original map header: legacy, remake and invalid size OK');
  finally s.Free end;
end.
