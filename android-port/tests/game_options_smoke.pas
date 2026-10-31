program game_options_smoke;
{$mode delphi}
uses KM_GameOptions, KM_CommonClasses, KM_MapTypes, KM_Defaults;
var source, restored: TKMGameOptions; stream: TKMemoryStreamBinary;
begin
  source := TKMGameOptions.Create;
  restored := TKMGameOptions.Create;
  stream := TKMemoryStreamBinary.Create;
  try
    if (source.Peacetime <> DEFAULT_PEACE_TIME) or (source.SpeedPT <> 1) then Halt(1);
    source.Peacetime := 37;
    source.SpeedPT := 1.5;
    source.SpeedAfterPT := 0.5;
    source.RandomSeed := 123456;
    source.Save(stream);
    stream.Position := 0;
    restored.Load(stream);
    if (restored.Peacetime <> 37) or (restored.SpeedPT <> 1.5) or
       (restored.SpeedAfterPT <> 0.5) or (restored.RandomSeed <> 123456) then Halt(2);
    restored.Reset;
    if (restored.Peacetime <> DEFAULT_PEACE_TIME) or (restored.RandomSeed <> 0) or
       (restored.MissionDifficulty <> mdNone) then Halt(3);
    WriteLn('game options save/load/reset OK');
  finally
    stream.Free; restored.Free; source.Free;
  end;
end.
