program ps_game_probe;
{$mode delphi}
uses SysUtils, uPSCompiler, uPSRuntime, uPSUtils, KM_Points;
type
 TFacade=class
   bias:Integer;
   function Point(X,Y:Integer):TKMPoint;
   procedure OutValue(X:Integer; out V:Integer);
 end;
function TFacade.Point(X,Y:Integer):TKMPoint;begin Result:=TKMPoint.New(X+bias,Y) end;
procedure TFacade.OutValue(X:Integer; out V:Integer);begin V:=X+bias end;
function OnUses(Sender:TPSPascalCompiler; const Name:AnsiString):Boolean;
var c:TPSCompileTimeClass;
begin
 Result:=Name='SYSTEM';if not Result then Exit;
 Sender.AddTypeS('TKMPoint','record X,Y: Integer; end');
 c:=Sender.AddClassN(nil,'TFacade');
 c.RegisterMethod('function Point(X,Y:Integer):TKMPoint');
 c.RegisterMethod('procedure OutValue(X:Integer; var V:Integer)');
 AddImportedClassVariable(Sender,'Utils','TFacade');
end;
var c:TPSPascalCompiler;e:TPSExec;ci:TPSRuntimeClassImporter;o:TFacade;data:AnsiString;i:integer;
const source='var p: TKMPoint; n: Integer; begin p := Utils.Point(4,9); Utils.OutValue(8,n); if (p.X <> 11) or (p.Y <> 9) or (n <> 15) then begin n:=1 div (n-n); end; end.';
begin
 c:=TPSPascalCompiler.Create;c.OnUses:=@OnUses;
 if not c.Compile(source) then begin for i:=0 to c.MsgCount-1 do WriteLn(c.Msg[i].MessageToString);Halt(1) end;
 c.GetOutput(data);c.Free;
 ci:=TPSRuntimeClassImporter.Create;with ci.Add(TFacade) do begin RegisterMethod(@TFacade.Point,'Point'); RegisterMethod(@TFacade.OutValue,'OutValue') end;
 e:=TPSExec.Create; RegisterClassLibraryRuntime(e,ci);if not e.LoadData(data) then begin WriteLn('load failed');Halt(2) end;
 o:=TFacade.Create;o.bias:=7;PSRegisterRecordReturnType(@TFacade.Point,TypeInfo(TKMPoint));SetVariantToClass(e.GetVarNo(e.GetVar('UTILS')),o);
 if not e.RunScript then begin WriteLn('run failed ',e.ExceptionString);Halt(3) end;
 WriteLn('PASCAL_SCRIPT_POINT_AND_OUT_OK (test facade using real TKMPoint.New)');e.Free;ci.Free;o.Free;
end.
