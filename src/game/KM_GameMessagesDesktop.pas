unit KM_GameMessagesDesktop;
{$I KaM_Remake.inc}
interface
uses KM_GameMessages, KM_GameMessageTypes, KM_Points, KM_InterfaceGamePlay;
type
  TKMDesktopGameMessages = class(TKMGameMessagePort)
  private
    fUI: TKMGamePlayInterface;
  public
    constructor Create(aUI: TKMGamePlayInterface);
    procedure Issue(aKind: TKMMessageKind; const aText: UnicodeString; const aLoc: TKMPoint); override;
  end;
implementation
uses SysUtils;
constructor TKMDesktopGameMessages.Create(aUI: TKMGamePlayInterface);
begin
  inherited Create;
  if aUI = nil then raise Exception.Create('Message port requires desktop gameplay UI');
  fUI := aUI;
end;
procedure TKMDesktopGameMessages.Issue(aKind: TKMMessageKind; const aText: UnicodeString; const aLoc: TKMPoint);
begin
  fUI.MessageIssue(aKind, aText, aLoc);
end;
end.
