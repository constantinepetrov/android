program points_smoke;
{$mode delphi}
uses KM_Points;
var a, b, c: TKMPoint;
begin
  a := TKMPoint.New(2, 3);
  b := TKMPoint.New(4, 5);
  c := a + b;
  if (c.X <> 6) or (c.Y <> 8) then Halt(1);
  WriteLn('KM_Points addition: OK');
end.
