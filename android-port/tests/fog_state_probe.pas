program fow_test;
{$mode delphi}
uses SysUtils, KM_FogOfWar;
var a,b:TKMFogOfWar; x,y,t:integer;
begin
 a:=TKMFogOfWar.Create(3,2,True); b:=TKMFogOfWar.Create(3,2,True);
 try
  for y:=0 to 1 do for x:=0 to 2 do begin a.Revelation[y,x]:=100;b.Revelation[y,x]:=100 end;
  for t:=1 to 10 do begin a.UpdateState(True);b.UpdateState(True) end;
  for y:=0 to 1 do for x:=0 to 2 do if (a.Revelation[y,x]<>88) or (a.Revelation[y,x]<>b.Revelation[y,x]) then Halt(1);
  a.UpdateState(False);for y:=0 to 1 do for x:=0 to 2 do if a.Revelation[y,x]<>88 then Halt(2);
  WriteLn('FOG_STATE_UPDATE_OK 3x2 ticks=10 from=100 to=88');
 finally a.Free;b.Free end;
end.
