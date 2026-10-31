unit KM_AndroidScriptProbe;
{$mode delphi}
interface
function RunScriptProbe: Integer;
function RunRealUtilsScriptProbe: Integer;
implementation
uses SysUtils, uPSCompiler, uPSRuntime, uPSUtils, KM_Points, KM_ScriptingUtils;
function __android_log_write(priority: LongInt; tag, text: PChar): LongInt; cdecl; external 'log' name '__android_log_write';
procedure AndroidLog(const aText: AnsiString);
begin
  __android_log_write(6, 'KaMProbe', PChar(aText));
end;
type
  TScriptFacade = class
    Bias: Integer;
    function Add(Value: Integer): Integer;
    function Mix(Value: Single): Single;
    procedure OutValue(Value: Integer; out Output: Integer);
  end;
function TScriptFacade.Add(Value: Integer): Integer; begin Result := Bias + Value end;
function TScriptFacade.Mix(Value: Single): Single; begin Result := Bias + Value end;
procedure TScriptFacade.OutValue(Value: Integer; out Output: Integer); begin Output := Bias + Value end;
function RegisterScriptTypes(Sender: TPSPascalCompiler; const Name: AnsiString): Boolean;
var C: TPSCompileTimeClass;
begin
  Result := Name = 'SYSTEM'; if not Result then Exit;
  C := Sender.AddClassN(nil, 'TScriptFacade');
  if not C.RegisterMethod('function Add(Value: Integer): Integer') then Exit(False);
  if not C.RegisterMethod('function Mix(Value: Single): Single') then Exit(False);
  if not C.RegisterMethod('procedure OutValue(Value: Integer; var Output: Integer)') then Exit(False);
  Result := AddImportedClassVariable(Sender, 'Utils', 'TScriptFacade');
end;
function RunScriptProbe: Integer;
const Source = 'var n: Integer; f: Single; begin n := Utils.Add(35); if n <> 42 then n := 1 div (n-n); f := Utils.Mix(2.5); '
  + 'Utils.OutValue(8,n); if (n <> 15) or (f < 9.49) or (f > 9.51) then n := 1 div (n-n); end.';
var Compiler: TPSPascalCompiler; Exec: TPSExec; Importer: TPSRuntimeClassImporter;
    Instance: TScriptFacade; Data: AnsiString;
begin
  Result := -1; Compiler := nil; Exec := nil; Importer := nil; Instance := nil;
  try
    try
      Compiler := TPSPascalCompiler.Create; Compiler.OnUses := @RegisterScriptTypes;
      if not Compiler.Compile(Source) then begin Result := -2; Exit end;
      Compiler.GetOutput(Data);
      // Negative test must reject an invalid script, rather than accept a no-op.
      if Compiler.Compile('begin this_identifier_does_not_exist := 1; end.') then begin Result := -3; Exit end;
      FreeAndNil(Compiler);
      Importer := TPSRuntimeClassImporter.Create;
      with Importer.Add(TScriptFacade) do begin
        RegisterMethod(@TScriptFacade.Add, 'Add'); RegisterMethod(@TScriptFacade.Mix, 'Mix');
        RegisterMethod(@TScriptFacade.OutValue, 'OutValue');
      end;
      Exec := TPSExec.Create; RegisterClassLibraryRuntime(Exec, Importer);
      if not Exec.LoadData(Data) then begin Result := -4; Exit end;
      Instance := TScriptFacade.Create; Instance.Bias := 7;
      SetVariantToClass(Exec.GetVarNo(Exec.GetVar('UTILS')), Instance);
      if not Exec.RunScript then begin
        AndroidLog(AnsiString('REAL_UTILS_SCRIPT_RUNTIME_ERROR code=' + IntToStr(Ord(Exec.ExceptionCode)) + ' text=' + string(Exec.ExceptionString)));
        Result := -5; Exit
      end;
      Result := 42;
    except on E: Exception do Result := -6 end;
  finally Exec.Free; Importer.Free; Instance.Free; Compiler.Free end;
end;

function RegisterRealUtils(Sender: TPSPascalCompiler; const Name: AnsiString): Boolean;
var C: TPSCompileTimeClass;
begin
  Result := Name = 'SYSTEM';
  if not Result then Exit;
  Sender.AddTypeS('TKMPoint', 'record X, Y: Integer; end');
  C := Sender.AddClassN(nil, 'TKMScriptUtils');
  if not C.RegisterMethod('function AbsI(aValue: Integer): Integer') then Exit(False);
  if not C.RegisterMethod('function KMPoint(X, Y: Integer): TKMPoint') then Exit(False);
  Result := AddImportedClassVariable(Sender, 'Utils', 'TKMScriptUtils');
end;

function RunRealUtilsScriptProbe: Integer;
const Source = 'var n: Integer; p: TKMPoint; begin n := Utils.AbsI(-42); p := Utils.KMPoint(13,17); if (n <> 42) or (p.X <> 13) or (p.Y <> 17) then n := 1 div (n-n); end.';
var Compiler: TPSPascalCompiler; Exec: TPSExec; Importer: TPSRuntimeClassImporter;
    Instance: TKMScriptUtils; Data: AnsiString;
begin
  Result := -1; Compiler := nil; Exec := nil; Importer := nil; Instance := nil;
  try
    try
      Compiler := TPSPascalCompiler.Create; Compiler.OnUses := @RegisterRealUtils;
      if not Compiler.Compile(Source) then begin Result := -2; Exit end;
      Compiler.GetOutput(Data);
      if Compiler.Compile('begin this_identifier_does_not_exist := 1; end.') then begin Result := -3; Exit end;
      FreeAndNil(Compiler);
      Importer := TPSRuntimeClassImporter.Create;
      with Importer.Add(TKMScriptUtils) do begin
        RegisterMethod(@TKMScriptUtils.AbsI, 'AbsI');
        RegisterMethod(@TKMScriptUtils.KMPoint, 'KMPoint');
      end;
      Exec := TPSExec.Create; RegisterClassLibraryRuntime(Exec, Importer);
      if not Exec.LoadData(Data) then begin Result := -4; Exit end;
      Instance := TKMScriptUtils.Create;
      SetVariantToClass(Exec.GetVarNo(Exec.GetVar('UTILS')), Instance);
      if not Exec.RunScript then begin
        AndroidLog(AnsiString('REAL_UTILS_SCRIPT_RUNTIME_ERROR code=' + IntToStr(Ord(Exec.ExceptionCode)) + ' text=' + string(Exec.ExceptionString)));
        Result := -5; Exit
      end;
      Result := 42;
    except on E: Exception do Result := -6 end;
  finally Exec.Free; Importer.Free; Instance.Free; Compiler.Free end;
end;
end.
