unit KM_WindowTypes;
{$I KaM_Remake.inc}
interface
type
  // Values, not toolkit objects. XML codes are defined by the functions below.
  TKMWindowState = (kwsNormal, kwsMinimized, kwsMaximized, kwsFullScreen);
  TKMWindowPosition = (kwpDesigned, kwpDefault, kwpDefaultPosOnly, kwpDefaultSizeOnly, kwpScreenCenter, kwpDesktopCenter, kwpMainFormCenter, kwpOwnerFormCenter, kwpWorkAreaCenter);
const
  KM_WINDOW_STATE_DEFAULT_CODE = 0;
  KM_WINDOW_POSITION_DEFAULT_CODE = 4;
function WindowStateFromXMLCode(aCode: Integer): TKMWindowState;
function WindowPositionFromXMLCode(aCode: Integer): TKMWindowPosition;
function WindowStateToXMLCode(aState: TKMWindowState): Integer;
function WindowPositionToXMLCode(aPosition: TKMWindowPosition): Integer;
implementation
uses SysUtils;
function WindowStateFromXMLCode(aCode: Integer): TKMWindowState;
begin
  // Preserve the historical XML clamp, including LCL-only extra values.
  if aCode < 0 then aCode := 0;
  if aCode > 2 then aCode := 2;
  case aCode of
    0: Result := kwsNormal;
    1: Result := kwsMinimized;
    2: Result := kwsMaximized;
  else raise EArgumentException.Create('Invalid window state code');
  end;
end;
function WindowStateToXMLCode(aState: TKMWindowState): Integer;
begin
  case aState of
    kwsNormal: Result := 0;
    kwsMinimized: Result := 1;
    kwsMaximized: Result := 2;
    kwsFullScreen: Result := 3;
  else raise EArgumentException.Create('Invalid window state value');
  end;
end;
function WindowPositionFromXMLCode(aCode: Integer): TKMWindowPosition;
begin
  // Preserve the historical XML clamp, including LCL-only extra values.
  if aCode < 0 then aCode := 0;
  if aCode > 7 then aCode := 7;
  case aCode of
    0: Result := kwpDesigned;
    1: Result := kwpDefault;
    2: Result := kwpDefaultPosOnly;
    3: Result := kwpDefaultSizeOnly;
    4: Result := kwpScreenCenter;
    5: Result := kwpDesktopCenter;
    6: Result := kwpMainFormCenter;
    7: Result := kwpOwnerFormCenter;
  else raise EArgumentException.Create('Invalid window position code');
  end;
end;
function WindowPositionToXMLCode(aPosition: TKMWindowPosition): Integer;
begin
  case aPosition of
    kwpDesigned: Result := 0;
    kwpDefault: Result := 1;
    kwpDefaultPosOnly: Result := 2;
    kwpDefaultSizeOnly: Result := 3;
    kwpScreenCenter: Result := 4;
    kwpDesktopCenter: Result := 5;
    kwpMainFormCenter: Result := 6;
    kwpOwnerFormCenter: Result := 7;
    kwpWorkAreaCenter: Result := 8;
  else raise EArgumentException.Create('Invalid window position value');
  end;
end;
end.
