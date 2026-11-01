program terrain_test;
{$mode delphi}
uses KM_TerrainTypes;
var t: TKMTerrainTile;
begin
 FillChar(t,SizeOf(t),0); t.SetHeightExact(37); if t.Height<>37 then Halt(1);
 t.BaseLayer.Corner[2]:=True; if not t.BaseLayer.Corner[2] then Halt(2);
 t.BaseLayer.Corner[2]:=False; if t.BaseLayer.Corner[2] then Halt(3);
 WriteLn('TERRAIN_STATE_FIELDS_OK');
end.
