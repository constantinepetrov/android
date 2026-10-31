unit KM_FogScenario;
{$mode delphi}
interface
function RunFogScenario: Boolean;
implementation
uses KM_FogOfWar, KM_Points, KM_CommonClasses;

// Uses original game state, reveal/cover, serialization and tick-update methods.
// It is a subsystem scenario, not a TKMGame.PlayGameTick.
function RunFogScenario: Boolean;
var a,b: TKMFogOfWar; stream: TKMemoryStreamBinary; x,y,t: Integer;
begin
  Result := False;
  a := TKMFogOfWar.Create(8,8,True);
  b := TKMFogOfWar.Create(8,8,True);
  stream := TKMemoryStreamBinary.Create;
  try
    a.RevealCircle(TKMPoint.New(3,3),2,180);
    if (a.Revelation[3,3] <> 180) or (a.Revelation[0,0] <> 0) then Exit;
    a.CoverCircle(TKMPoint.New(3,3),0);
    if (a.Revelation[3,3] <> 0) or (a.Revelation[3,4] <> 180) then Exit;
    for t := 1 to 7 do a.UpdateState(True);
    a.Save(stream); stream.Position := 0; b.Load(stream);
    for t := 1 to 20 do begin a.UpdateState(True); b.UpdateState(True) end;
    for y := 0 to 7 do for x := 0 to 7 do
      if (a.Revelation[y,x] <> b.Revelation[y,x]) or
         (a.RenderRevelation[y,x] <> b.RenderRevelation[y,x]) then Exit;
    if (a.Revelation[3,4] >= 180) or (a.Revelation[3,3] <> 0) then Exit;
    Result := True;
  finally stream.Free; b.Free; a.Free end;
end;
end.
