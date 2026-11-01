unit KM_AndroidRttiProbe;
{$mode delphi}
interface
function ProbeUnconfiguredRtti: Integer;
implementation
uses SysUtils, Rtti, TypInfo;
function Increment(Value: LongInt): LongInt; cdecl;
begin Result := Value + 1 end;
function ProbeUnconfiguredRtti: Integer;
var args: TValueArray; output: TValue;
begin
  Result := -2;
  SetLength(args,1); args[0] := TValue.From<LongInt>(41);
  try
    output := Rtti.Invoke(@Increment,args,ccCdecl,TypeInfo(LongInt),True,False);
    if output.AsInteger = 42 then Result := 0 else Result := -1;
  except
    on E: ENotImplemented do Result := 1;
    on E: Exception do Result := -2;
  end;
end;
end.
