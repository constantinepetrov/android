program game_presentation_port_smoke;
{$mode delphi}
uses
  KM_CommonClasses, KM_GamePresentationState;

type
  TTestPresentationState = class(TKMGamePresentationState)
  public
    procedure SavePreviewState(aStream: TKMemoryStream); override;
    procedure LoadPreviewState(aStream: TKMemoryStream); override;
    procedure SaveSinglePlayerState(aStream: TKMemoryStream); override;
    procedure LoadSinglePlayerState(aStream: TKMemoryStream); override;
  end;

procedure TTestPresentationState.SavePreviewState(aStream: TKMemoryStream);
begin
  aStream.Write(Byte($A1));
  aStream.Write(Word($1234));
end;

procedure TTestPresentationState.LoadPreviewState(aStream: TKMemoryStream);
var marker: Byte; value: Word;
begin
  aStream.Read(marker);
  aStream.Read(value);
  if (marker <> $A1) or (value <> $1234) then Halt(1);
end;

procedure TTestPresentationState.SaveSinglePlayerState(aStream: TKMemoryStream);
begin
  aStream.Write(Byte($B2));
  aStream.Write(LongInt(-321));
end;

procedure TTestPresentationState.LoadSinglePlayerState(aStream: TKMemoryStream);
var marker: Byte; value: LongInt;
begin
  aStream.Read(marker);
  aStream.Read(value);
  if (marker <> $B2) or (value <> -321) then Halt(2);
end;

var state: TTestPresentationState; previewStream, bodyStream: TKMemoryStreamBinary;
begin
  state := TTestPresentationState.Create;
  previewStream := TKMemoryStreamBinary.Create;
  bodyStream := TKMemoryStreamBinary.Create;
  try
    state.SavePreviewState(previewStream);
    state.SaveSinglePlayerState(bodyStream);
    if (previewStream.Size <> 3) or (bodyStream.Size <> 5) then Halt(3);
    previewStream.Position := 0;
    bodyStream.Position := 0;
    state.LoadPreviewState(previewStream);
    state.LoadSinglePlayerState(bodyStream);
    if (previewStream.Position <> previewStream.Size) or
       (bodyStream.Position <> bodyStream.Size) then Halt(4);
    WriteLn('GAME_PRESENTATION_PORT_ROUNDTRIP_OK');
  finally
    bodyStream.Free;
    previewStream.Free;
    state.Free;
  end;
end.
