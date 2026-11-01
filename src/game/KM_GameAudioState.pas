unit KM_GameAudioState;
{$I KaM_Remake.inc}
interface
type
  TKMGameAudioStopQuery = function: Boolean of object;
procedure BindGameAudioState(aOwner: TObject; aQuery: TKMGameAudioStopQuery);
procedure UnbindGameAudioState(aOwner: TObject);
function GameAudioIsStopping: Boolean;
implementation
uses SysUtils;
var Owner: TObject; Query: TKMGameAudioStopQuery;
procedure BindGameAudioState(aOwner: TObject; aQuery: TKMGameAudioStopQuery);
begin
  if (aOwner = nil) or not Assigned(aQuery) then
    raise Exception.Create('Game audio state requires a live session query');
  Owner := aOwner;
  Query := aQuery;
end;
procedure UnbindGameAudioState(aOwner: TObject);
begin
  if Owner <> aOwner then Exit;
  Query := nil;
  Owner := nil;
end;
function GameAudioIsStopping: Boolean;
begin
  // No registered session has the same semantics as the original gGame=nil.
  Result := Assigned(Query);
  if Result then Result := Query();
end;
end.
