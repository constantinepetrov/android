program fpc_rtti_probe;
{$mode delphi}
uses SysUtils, Rtti, TypInfo;
function Add(A, B: LongInt): LongInt;
begin Result := A + B; end;
var values: TValueArray; value: TValue;
begin
  SetLength(values, 2);
  values[0] := TValue.From<LongInt>(20);
  values[1] := TValue.From<LongInt>(22);
  try
    value := Rtti.Invoke(@Add, values, ccReg, TypeInfo(LongInt), True, False);
    if value.AsInteger <> 42 then Halt(1);
    WriteLn('RTTI static call: OK');
  except on E: Exception do begin WriteLn('RTTI static call unavailable: ', E.ClassName, ': ', E.Message); Halt(2); end end;
  try
    value := Rtti.Invoke(@Add, values, ccReg, TypeInfo(LongInt), True, True);
    WriteLn('unexpected constructor support'); Halt(3);
  except on E: ENotImplemented do WriteLn('RTTI constructor: ENotImplemented (FPC 3.2.2)') end;
end.
