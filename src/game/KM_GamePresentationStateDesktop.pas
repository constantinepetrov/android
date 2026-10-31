unit KM_GamePresentationStateDesktop;
{$I KaM_Remake.inc}
interface
uses
  KM_CommonClasses, KM_GamePresentationState, KM_InterfaceGamePlay;

type
  // Compatibility adapter. It deliberately delegates to the original UI
  // serializers so existing desktop save bytes and ordering remain unchanged.
  TKMDesktopGamePresentationState = class(TKMGamePresentationState)
  private
    fGamePlayInterface: TKMGamePlayInterface; // Owned by TKMGame
  public
    constructor Create(aGamePlayInterface: TKMGamePlayInterface);
    procedure SavePreviewState(aStream: TKMemoryStream); override;
    procedure LoadPreviewState(aStream: TKMemoryStream); override;
    procedure SaveSinglePlayerState(aStream: TKMemoryStream); override;
    procedure LoadSinglePlayerState(aStream: TKMemoryStream); override;
  end;

implementation
uses
  SysUtils;

constructor TKMDesktopGamePresentationState.Create(aGamePlayInterface: TKMGamePlayInterface);
begin
  inherited Create;
  if aGamePlayInterface = nil then
    raise Exception.Create('Desktop game presentation state requires the gameplay interface');
  fGamePlayInterface := aGamePlayInterface;
end;

procedure TKMDesktopGamePresentationState.SavePreviewState(aStream: TKMemoryStream);
begin
  fGamePlayInterface.SaveMinimap(aStream);
end;

procedure TKMDesktopGamePresentationState.LoadPreviewState(aStream: TKMemoryStream);
begin
  fGamePlayInterface.LoadMinimap(aStream);
end;

procedure TKMDesktopGamePresentationState.SaveSinglePlayerState(aStream: TKMemoryStream);
begin
  fGamePlayInterface.Save(aStream);
end;

procedure TKMDesktopGamePresentationState.LoadSinglePlayerState(aStream: TKMemoryStream);
begin
  fGamePlayInterface.Load(aStream);
end;

end.
