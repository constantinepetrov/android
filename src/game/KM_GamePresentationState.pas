unit KM_GamePresentationState;
{$I KaM_Remake.inc}
interface
uses
  KM_CommonClasses;

type
  // Session-owned access to the persistent part of the local game view.
  // The byte layout is part of the existing save format: implementations must
  // preserve call order and must not add a private header/version here.
  TKMGamePresentationState = class abstract
  public
    procedure SavePreviewState(aStream: TKMemoryStream); virtual; abstract;
    procedure LoadPreviewState(aStream: TKMemoryStream); virtual; abstract;
    procedure SaveSinglePlayerState(aStream: TKMemoryStream); virtual; abstract;
    procedure LoadSinglePlayerState(aStream: TKMemoryStream); virtual; abstract;
  end;

implementation
end.
