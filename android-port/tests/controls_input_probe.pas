program controls_input_probe;
{$mode delphi}
uses SysUtils, Classes, KM_ControlsTypes, KM_UtilsExt;
var shift: TShiftState;
begin
  try GetDoubleClickTime; Halt(13) except on E: EInvalidOpException do ; end;
  try KMInputConfigureDoubleClick(0); Halt(14) except on E: EArgumentException do ; end;
  KMInputConfigureDoubleClick(283);
  if GetDoubleClickTime <> 283 then Halt(15);
  KMInputConfigureDoubleClick(500);
  if GetDoubleClickTime <> 500 then Halt(16);
  shift := [ssShift, ssCtrl];
  if not (ssCtrl in shift) then Halt(1);
  KMInputSetButtonDown(mbLeft, True);
  if GetKeyState(VK_LBUTTON) >= 0 then Halt(2);
  KMInputSetButtonDown(mbLeft, False);
  if GetKeyState(VK_LBUTTON) <> 0 then Halt(3);
  KMInputSetKeyState(VK_CONTROL, True);
  if GetKeyState(VK_CONTROL) >= 0 then Halt(4);
  KMInputSetKeyState(VK_CONTROL, False);
  if GetKeyState(VK_CONTROL) <> 0 then Halt(5);
  if (Low(SmallInt) <> -32768) or (High(SmallInt) <> 32767) then Halt(6);
  KMInputSetKeyState(VK_SHIFT, True);
  KMInputSetKeyState(VK_MENU, True);
  KMInputSetKeyState(VK_CONTROL, True);
  shift := GetShiftState(mbLeft);
  if shift <> [ssLeft, ssShift, ssAlt, ssCtrl] then Halt(7);
  if GetMultiplicator(shift) <> 1000 then Halt(8); // Alt+left -> right; Ctrl ignored
  KMInputSetKeyState(VK_MENU, False);
  KMInputSetKeyState(VK_CONTROL, False);
  if GetMultiplicator(mbLeft) <> 100 then Halt(9);
  KMInputSetKeyState(VK_SHIFT, False);
  if GetMultiplicator(mbLeft) <> 1 then Halt(10);
  if GetMultiplicator(mbRight) <> 10 then Halt(11);
  if GetMultiplicator(mbMiddle) <> 0 then Halt(12);
  WriteLn('INPUT_MODIFIERS_OK real KM_UtilsExt Alt/RMB, Shift, Ctrl-ignore multipliers');
  WriteLn('CONTROLSBASE_INPUT_TYPES_OK button/key transitions, modifiers, SmallInt bounds');
end.
