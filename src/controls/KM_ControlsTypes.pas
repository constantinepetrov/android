unit KM_ControlsTypes;
{$I KaM_Remake.inc}
interface

{$IFDEF ANDROID}
type
  // These are game input values, not widgetset objects. Their ordering keeps
  // the familiar left/right/middle values used by the existing control code.
  TMouseButton = (mbLeft, mbRight, mbMiddle, mbExtra1, mbExtra2);

const
  VK_LBUTTON = 1;
  VK_RBUTTON = 2;
  VK_MBUTTON = 4;
  VK_BACK = 8;
  VK_TAB = 9;
  VK_RETURN = 13;
  VK_SHIFT = 16;
  VK_CONTROL = 17;
  VK_MENU = 18;
  VK_ESCAPE = 27;
  VK_PRIOR = 33;
  VK_NEXT = 34;
  VK_END = 35;
  VK_HOME = 36;
  VK_LEFT = 37;
  VK_UP = 38;
  VK_RIGHT = 39;
  VK_DOWN = 40;
  VK_DELETE = 46;
  VK_F1 = 112;
  VK_F12 = 123;

function GetKeyState(aVirtualKey: Word): SmallInt;
procedure KMInputSetKeyState(aVirtualKey: Word; aPressed: Boolean);
procedure KMInputSetButtonDown(aButton: TMouseButton; aPressed: Boolean);
{$ENDIF}

type
  TKMAllowedChars = (
    acDigits,
    acHex,
    acANSI7,
    acFileName,
    acText,
    acAll
  );

const
  CTRL_HIGHLIGHT_COEF_DEF = 0.4;

implementation

{$IFDEF ANDROID}
var
  KMInputKeyState: array[0..255] of Boolean;

function GetKeyState(aVirtualKey: Word): SmallInt;
begin
  Result := 0;
  if aVirtualKey > High(KMInputKeyState) then
    Exit;
  if KMInputKeyState[aVirtualKey] then
    Result := SmallInt($8000);
end;

procedure KMInputSetKeyState(aVirtualKey: Word; aPressed: Boolean);
begin
  if aVirtualKey <= High(KMInputKeyState) then
    KMInputKeyState[aVirtualKey] := aPressed;
end;

procedure KMInputSetButtonDown(aButton: TMouseButton; aPressed: Boolean);
begin
  case aButton of
    mbLeft:   KMInputSetKeyState(VK_LBUTTON, aPressed);
    mbRight:  KMInputSetKeyState(VK_RBUTTON, aPressed);
    mbMiddle: KMInputSetKeyState(VK_MBUTTON, aPressed);
  end;
end;
{$ENDIF}

end.
