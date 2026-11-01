program resunits_csv_probe;
{$mode delphi}
uses Classes, SysUtils, KM_Defaults, KM_CommonTypes, KM_Points, KM_ResTypes, KM_ResUnits;
var
  bytes: TFileStream; spec: TKMUnitSpecLegacy; sprite: TKMUnitSprite; sounds: TKMUnitSprite2;
  carry: array [WARE_MIN..WARE_MAX, dirN..dirNW] of TKMAnimLoop;
  units: TKMResUnits; lines: TStringList; i: Integer; dir, csv: string;
begin
  if ParamCount <> 1 then Halt(1);
  dir := IncludeTrailingPathDelimiter(ParamStr(1));
  ForceDirectories(dir + 'data' + PathDelim + 'defines');
  ExeDir := dir;
  FillChar(carry, SizeOf(carry), 0); FillChar(spec, SizeOf(spec), 0);
  FillChar(sprite, SizeOf(sprite), 0); FillChar(sounds, SizeOf(sounds), 0);
  spec.HitPoints := 20; spec.Attack := 4; spec.AttackHorse := 5;
  spec.Defence := 6; spec.Speed := 24; spec.Sight := 7;
  bytes := TFileStream.Create(dir + 'data' + PathDelim + 'defines' + PathDelim + 'unit.dat', fmCreate);
  try
    bytes.WriteBuffer(carry,SizeOf(carry));
    for i := 0 to 40 do begin bytes.WriteBuffer(spec,SizeOf(spec)); bytes.WriteBuffer(sprite,SizeOf(sprite)); bytes.WriteBuffer(sounds,SizeOf(sounds)); end;
  finally bytes.Free end;
  csv := dir + 'units.csv';
  units := TKMResUnits.Create;
  try units.ExportCSV(csv) finally units.Free end;
  lines := TStringList.Create;
  try
    lines.LoadFromFile(csv);
    if lines.Count < 2 then Halt(2);
    if lines[0] <> 'Name,HitPoints,Attack,AttackHorse,x4,Defence,Speed,x7,Sight,x9,x10,CanWalkOut,x11' then Halt(3);
    if Pos(',20,4,5,0,6,24,0,7,0,0,0,0,',lines[1]) = 0 then begin WriteLn(lines[1]); Halt(4) end;
    WriteLn('RESUNITS_CSV_OK synthetic fixture rows=',lines.Count);
  finally lines.Free end;
end.
