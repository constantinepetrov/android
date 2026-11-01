program kromutils_smoke;
{$mode delphi}
uses KromUtils;
var data: array[0..3] of Byte;
begin
  data[0] := 0; data[1] := 1; data[2] := 2; data[3] := 255;
  if Adler32CRC(@data[0], 4) <> 16974090 then Halt(1);
  if GetFileExt('foo.map') <> 'MAP' then Halt(2);
  if Int2Fix(7, 3) <> '007' then Halt(3);
  if CountMatches('ababa', 'ab') <> 2 then Halt(4);
  if not CharInSet(WideChar(255), [AnsiChar(255)]) then Halt(5);
  if CharInSet(WideChar(256), [AnsiChar(0)]) then Halt(6);
  WriteLn('KromUtils Android conditional smoke: OK');
end.
