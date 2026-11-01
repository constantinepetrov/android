program ffi_game_abi_probe;
// Diagnostic fixture: TProbe mirrors script binding signatures but is not
// TKMScriptUtils. TKMPoint.New is actual game code, not a simulation tick.
{$mode delphi}
uses ffi.manager, SysUtils, Rtti, TypInfo, KM_Points;
type TProbe=class
  bias: LongInt;
  function Add(a:LongInt):LongInt;
  function Mix(a:Single):Single;
  procedure Output(a:LongInt; out b:LongInt);
  function Point(x,y:LongInt):TKMPoint;
end;
function TProbe.Add(a:LongInt):LongInt;begin Result:=bias+a end;
function TProbe.Mix(a:Single):Single;begin Result:=bias+a end;
procedure TProbe.Output(a:LongInt; out b:LongInt);begin b:=bias+a end;
function TProbe.Point(x,y:LongInt):TKMPoint;begin Result:=TKMPoint.New(x+bias,y);end;
var o:TProbe; args:TValueArray;v:TValue; outval:LongInt;p:TKMPoint;
begin
 o:=TProbe.Create; o.bias:=7;
 SetLength(args,2);args[0]:=TValue.From<Pointer>(o);args[1]:=TValue.From<LongInt>(35);
 v:=Rtti.Invoke(@TProbe.Add,args,ccReg,TypeInfo(LongInt),False,False);WriteLn('instance=',v.AsInteger);if v.AsInteger<>42 then Halt(1);
 args[1]:=TValue.From<Single>(2.5);v:=Rtti.Invoke(@TProbe.Mix,args,ccReg,TypeInfo(Single),False,False);WriteLn('float=',v.AsExtended:0:1);if Abs(v.AsExtended-9.5)>0.001 then Halt(2);
 outval:=-1;SetLength(args,3);args[1]:=TValue.From<LongInt>(8);args[2]:=TValue.From<Pointer>(@outval);
 Rtti.Invoke(@TProbe.Output,args,ccReg,nil,False,False);WriteLn('out=',outval);if outval<>15 then Halt(3);
 args[1]:=TValue.From<LongInt>(4);args[2]:=TValue.From<LongInt>(9);
 try v:=Rtti.Invoke(@TProbe.Point,args,ccReg,TypeInfo(TKMPoint),False,False); v.ExtractRawData(@p);WriteLn('point=',p.X,',',p.Y);if (p.X<>11)or(p.Y<>9) then Halt(4);
 except on e:Exception do begin WriteLn('point exception: ',e.ClassName,': ',e.Message);Halt(5) end end;
 o.Free;
 WriteLn('FFI_GAME_ABI_OK (probe methods; real TKMPoint.New)');
end.
