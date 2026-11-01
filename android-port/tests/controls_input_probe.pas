program controls_input_probe;
{$mode delphi}
uses Classes, KM_ControlsTypes;
var shift: TShiftState;
begin
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
  WriteLn('CONTROLSBASE_INPUT_TYPES_OK button/key transitions, modifiers, SmallInt bounds');
end.
