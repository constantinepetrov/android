unit KM_MapHeader;
{$I KaM_Remake.inc}
interface
uses KM_CommonClasses;

procedure LoadMapHeader(aStream: TKMemoryStream; var aMapX: Integer; var aMapY: Integer); overload;
procedure LoadMapHeader(aStream: TKMemoryStream; var aMapX: Integer; var aMapY: Integer; var aGameRev: Integer); overload;
procedure LoadMapHeader(aStream: TKMemoryStream; var aMapX: Integer; var aMapY: Integer; var aGameRev: Integer; var aMapDataSize: Cardinal); overload;

implementation
uses SysUtils, Math, KM_Defaults;

procedure LoadMapHeader(aStream: TKMemoryStream; var aMapX: Integer; var aMapY: Integer);
var
  GameRev: Integer;
begin
  LoadMapHeader(aStream, aMapX, aMapY, GameRev);
end;


procedure LoadMapHeader(aStream: TKMemoryStream; var aMapX: Integer; var aMapY: Integer; var aGameRev: Integer);
var
  MapDataSize: Cardinal;
begin
  LoadMapHeader(aStream, aMapX, aMapY, aGameRev, MapDataSize);
end;


//@Rey: Should we change "var" to "out" here and above? It would be more semantically correct in these cases
procedure LoadMapHeader(aStream: TKMemoryStream; var aMapX: Integer; var aMapY: Integer; var aGameRev: Integer; var aMapDataSize: Cardinal);
var
  GameRevision: UnicodeString;
  GameRev: Integer;
begin
  aStream.Read(aMapX); // Get map header to determine old (r6720 and earlier) or newer format

  aGameRev := 0;
  if aMapX = 0 then // Means we have not a standart KaM format map, but our own KaM_Remake format
  begin
    aStream.ReadW(GameRevision);
    if TryStrToInt(Copy(GameRevision, 2, Length(GameRevision) - 1), GameRev) then
      aGameRev := GameRev
    else
      raise Exception.Create('Unexpected game revision in map header');

    aStream.Read(aMapDataSize);
    aStream.Read(aMapX);
  end;

  aStream.Read(aMapY);
  if not InRange(aMapX, 1, MAX_MAP_SIZE) or not InRange(aMapY, 1, MAX_MAP_SIZE) then
    raise Exception.Create(Format('Can''t open the map cos it has wrong dimensions: [%d:%d]', [aMapX, aMapY]));
end;



end.
