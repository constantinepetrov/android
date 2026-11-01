program desktop_window_types_probe;
{$mode delphi}
uses Interfaces, Forms, SysUtils, KM_WindowTypes, KM_DesktopWindowTypes;
var s: TWindowState; p: TPosition; i: Integer;
begin
  for s:=Low(TWindowState) to High(TWindowState) do
  begin
    if ToDesktopWindowState(FromDesktopWindowState(s))<>s then raise Exception.Create('state roundtrip');
    if WindowStateToXMLCode(FromDesktopWindowState(s))<>Ord(s) then raise Exception.Create('legacy state code');
  end;
  for p:=Low(TPosition) to High(TPosition) do
  begin
    if ToDesktopWindowPosition(FromDesktopWindowPosition(p))<>p then raise Exception.Create('position roundtrip');
    if WindowPositionToXMLCode(FromDesktopWindowPosition(p))<>Ord(p) then raise Exception.Create('legacy position code');
  end;
  // Named expectations pin the dependency's schema, independently of project enum ordinals.
  if (Ord(wsNormal)<>0) or (Ord(wsMinimized)<>1) or (Ord(wsMaximized)<>2)
    or (Ord(poDesigned)<>0) or (Ord(poDefault)<>1) or (Ord(poDefaultPosOnly)<>2)
    or (Ord(poDefaultSizeOnly)<>3) or (Ord(poScreenCenter)<>4) or (Ord(poDesktopCenter)<>5)
    or (Ord(poMainFormCenter)<>6) or (Ord(poOwnerFormCenter)<>7) then raise Exception.Create('desktop schema drift');
  for i:=0 to 2 do if WindowStateToXMLCode(WindowStateFromXMLCode(i))<>i then raise Exception.Create('state code');
  for i:=0 to 7 do if WindowPositionToXMLCode(WindowPositionFromXMLCode(i))<>i then raise Exception.Create('position code');
  WriteLn('DESKTOP_WINDOW_TYPES_OK actual Lazarus Forms/nogui; all 4 states and 9 positions in both directions; XML codes pinned');
end.
