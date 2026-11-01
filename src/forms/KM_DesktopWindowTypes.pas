unit KM_DesktopWindowTypes;
{$I KaM_Remake.inc}
interface
uses {$IFDEF WDC}UITypes,{$ENDIF} Forms, KM_WindowTypes;
function ToDesktopWindowState(aValue: TKMWindowState): TWindowState;
function FromDesktopWindowState(aValue: TWindowState): TKMWindowState;
function ToDesktopWindowPosition(aValue: TKMWindowPosition): TPosition;
function FromDesktopWindowPosition(aValue: TPosition): TKMWindowPosition;
implementation
uses SysUtils;
function ToDesktopWindowState(aValue: TKMWindowState): TWindowState;
begin
  case aValue of
    kwsNormal: Result := wsNormal;
    kwsMinimized: Result := wsMinimized;
    kwsMaximized: Result := wsMaximized;
    {$IFDEF FPC} // Lazarus 4.0 additions absent from VCL
    kwsFullScreen: Result := wsFullScreen;
    {$ENDIF}
  else raise EArgumentException.Create('Window state unsupported by this desktop toolkit');
  end;
end;
function FromDesktopWindowState(aValue: TWindowState): TKMWindowState;
begin
  case aValue of
    wsNormal: Result := kwsNormal;
    wsMinimized: Result := kwsMinimized;
    wsMaximized: Result := kwsMaximized;
    {$IFDEF FPC} // Lazarus 4.0 additions absent from VCL
    wsFullScreen: Result := kwsFullScreen;
    {$ENDIF}
  else raise EArgumentException.Create('Window state unsupported by this desktop toolkit');
  end;
end;
function ToDesktopWindowPosition(aValue: TKMWindowPosition): TPosition;
begin
  case aValue of
    kwpDesigned: Result := poDesigned;
    kwpDefault: Result := poDefault;
    kwpDefaultPosOnly: Result := poDefaultPosOnly;
    kwpDefaultSizeOnly: Result := poDefaultSizeOnly;
    kwpScreenCenter: Result := poScreenCenter;
    kwpDesktopCenter: Result := poDesktopCenter;
    kwpMainFormCenter: Result := poMainFormCenter;
    kwpOwnerFormCenter: Result := poOwnerFormCenter;
    {$IFDEF FPC} // Lazarus 4.0 additions absent from VCL
    kwpWorkAreaCenter: Result := poWorkAreaCenter;
    {$ENDIF}
  else raise EArgumentException.Create('Window position unsupported by this desktop toolkit');
  end;
end;
function FromDesktopWindowPosition(aValue: TPosition): TKMWindowPosition;
begin
  case aValue of
    poDesigned: Result := kwpDesigned;
    poDefault: Result := kwpDefault;
    poDefaultPosOnly: Result := kwpDefaultPosOnly;
    poDefaultSizeOnly: Result := kwpDefaultSizeOnly;
    poScreenCenter: Result := kwpScreenCenter;
    poDesktopCenter: Result := kwpDesktopCenter;
    poMainFormCenter: Result := kwpMainFormCenter;
    poOwnerFormCenter: Result := kwpOwnerFormCenter;
    {$IFDEF FPC} // Lazarus 4.0 additions absent from VCL
    poWorkAreaCenter: Result := kwpWorkAreaCenter;
    {$ENDIF}
  else raise EArgumentException.Create('Window position unsupported by this desktop toolkit');
  end;
end;
end.
