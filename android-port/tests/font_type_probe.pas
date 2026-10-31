program font_test;
{$mode delphi}
uses KM_FontTypes, KM_HandTypes;
var s: TKMOverlayTextSettings;
begin s.Font:=fntArial; if Ord(s.Font)<>6 then Halt(1);s.Font:=fntMonospaced;if Ord(s.Font)<>7 then Halt(2);WriteLn('FONT_SHARED_TYPE_OK') end.
