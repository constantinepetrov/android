unit Controls;
{$I KaM_Remake.inc}
{$IFNDEF ANDROID}
  {$MESSAGE FATAL 'Android Controls compatibility unit must not be used by desktop builds'}
{$ENDIF}
interface
uses
  Classes,
  KM_ControlsTypes;

type
  // Game code only consumes input values from Controls; it does not need the
  // Lazarus widgetset class hierarchy in an Android client.
  TMouseButton = KM_ControlsTypes.TMouseButton;

const
  mbLeft   = KM_ControlsTypes.mbLeft;
  mbRight  = KM_ControlsTypes.mbRight;
  mbMiddle = KM_ControlsTypes.mbMiddle;
  mbExtra1 = KM_ControlsTypes.mbExtra1;
  mbExtra2 = KM_ControlsTypes.mbExtra2;

  VK_LBUTTON = KM_ControlsTypes.VK_LBUTTON;
  VK_RBUTTON = KM_ControlsTypes.VK_RBUTTON;
  VK_MBUTTON = KM_ControlsTypes.VK_MBUTTON;
  VK_BACK = KM_ControlsTypes.VK_BACK;
  VK_TAB = KM_ControlsTypes.VK_TAB;
  VK_RETURN = KM_ControlsTypes.VK_RETURN;
  VK_SHIFT = KM_ControlsTypes.VK_SHIFT;
  VK_CONTROL = KM_ControlsTypes.VK_CONTROL;
  VK_MENU = KM_ControlsTypes.VK_MENU;
  VK_ESCAPE = KM_ControlsTypes.VK_ESCAPE;
  VK_PRIOR = KM_ControlsTypes.VK_PRIOR;
  VK_NEXT = KM_ControlsTypes.VK_NEXT;
  VK_END = KM_ControlsTypes.VK_END;
  VK_HOME = KM_ControlsTypes.VK_HOME;
  VK_LEFT = KM_ControlsTypes.VK_LEFT;
  VK_UP = KM_ControlsTypes.VK_UP;
  VK_RIGHT = KM_ControlsTypes.VK_RIGHT;
  VK_DOWN = KM_ControlsTypes.VK_DOWN;
  VK_DELETE = KM_ControlsTypes.VK_DELETE;
  VK_F1 = KM_ControlsTypes.VK_F1;
  VK_F12 = KM_ControlsTypes.VK_F12;

function GetKeyState(aVirtualKey: Word): SmallInt;

implementation
function GetKeyState(aVirtualKey: Word): SmallInt;
begin
  Result := KM_ControlsTypes.GetKeyState(aVirtualKey);
end;
end.
