library kamffi_probe;
{$mode delphi}
// Isolated ABI test library: not a Pascal Script bridge and not production game.
uses ffi.manager, SysUtils, Rtti, TypInfo, KM_Points, KM_AndroidScriptProbe;
type
  TProbe = class
    Bias: Integer;
    function Add(A: Integer): Integer;
    function Mix(A: Single): Single;
    procedure OutValue(A: Integer; out Value: Integer);
    function Point(X,Y: Integer): TKMPoint;
  end;
function TProbe.Add(A: Integer): Integer; begin Result := Bias + A end;
function TProbe.Mix(A: Single): Single; begin Result := Bias + A end;
procedure TProbe.OutValue(A: Integer; out Value: Integer); begin Value := Bias + A end;
function TProbe.Point(X,Y: Integer): TKMPoint; begin Result := TKMPoint.New(X + Bias,Y) end;

// Return distinct failure codes without allowing Pascal exceptions across JNI.
function Java_com_kamremake_androidprobe_NativeProbeService_nativeFfiProbe(env, cls: Pointer): LongInt; cdecl;
var o: TProbe; args: TValueArray; value: TValue; outValue, stage: Integer; point: TKMPoint;
begin
  Result := -1; stage := 0; o := nil;
  try
    o := TProbe.Create;
    try
    o.Bias := 7;
    SetLength(args,2); args[0] := TValue.From<Pointer>(o); args[1] := TValue.From<Integer>(35);
    stage := 1; value := Rtti.Invoke(@TProbe.Add,args,ccReg,TypeInfo(Integer),False,False);
    if value.AsInteger <> 42 then begin Result := -2; Exit end;
    args[1] := TValue.From<Single>(2.5);
    stage := 2; value := Rtti.Invoke(@TProbe.Mix,args,ccReg,TypeInfo(Single),False,False);
    if Abs(value.AsExtended - 9.5) > 0.001 then begin Result := -3; Exit end;
    SetLength(args,3); outValue := -1; args[1] := TValue.From<Integer>(8); args[2] := TValue.From<Pointer>(@outValue);
    stage := 3; Rtti.Invoke(@TProbe.OutValue,args,ccReg,nil,False,False);
    if outValue <> 15 then begin Result := -4; Exit end;
    args[1] := TValue.From<Integer>(4); args[2] := TValue.From<Integer>(9);
    stage := 4; value := Rtti.Invoke(@TProbe.Point,args,ccReg,TypeInfo(TKMPoint),False,False);
    value.ExtractRawData(@point);
    if (point.X <> 11) or (point.Y <> 9) then begin Result := -5; Exit end;
    Result := 42;
    finally o.Free end;
  except on E: Exception do Result := -100 - stage end;
end;
function Java_com_kamremake_androidprobe_NativeProbeService_nativeFfiScriptProbe(env, cls: Pointer): LongInt; cdecl;
begin Result := RunScriptProbe end;
exports Java_com_kamremake_androidprobe_NativeProbeService_nativeFfiProbe,
        Java_com_kamremake_androidprobe_NativeProbeService_nativeFfiScriptProbe;
begin end.
