unit KM_MapLegacyTile;
{$I KaM_Remake.inc}
interface
uses KM_CommonClasses;

type
  TKMLegacyMapTile = record
    Terrain, Height, Rotation, Obj: Byte;
  end;

// Reads the 23-byte original KaM terrain record using the engine stream.
procedure ReadLegacyMapTile(aStream: TKMemoryStream; out aTile: TKMLegacyMapTile);

implementation
uses Classes;
procedure ReadLegacyMapTile(aStream: TKMemoryStream; out aTile: TKMLegacyMapTile);
var rot: Byte;
begin
  aStream.Read(aTile.Terrain);
  aStream.Seek(1, soFromCurrent);
  aStream.Read(aTile.Height);
  aStream.Read(rot);
  aTile.Rotation := rot mod 4;
  aStream.Seek(1, soFromCurrent);
  aStream.Read(aTile.Obj);
  aStream.Seek(17, soFromCurrent);
end;
end.
