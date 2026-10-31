#!/usr/bin/env python3
"""Create an experimental FPC 3.2.2 source overlay; never modify the submodule.

The overlay adapts FPC 3.2.2 signatures and adds imported instance-method record
result marshalling. Keep it experimental until runtime smoke tests pass.
"""
import pathlib
import shutil
import sys

source, output = map(pathlib.Path, sys.argv[1:])
output.mkdir(parents=True, exist_ok=True)
for path in source.iterdir():
    if path.suffix.lower() in ('.pas', '.inc'):
        shutil.copyfile(path, output / path.name)
compiler = output / 'uPSCompiler.pas'
s = compiler.read_text()
a = '            var bType := GetTypeNo(BlockInfo, tmp).BaseType;\n            if not IsIntType(bType) and not (bType = btEnum) then'
b = '            if not IsIntType(GetTypeNo(BlockInfo, tmp).BaseType) and not (GetTypeNo(BlockInfo, tmp).BaseType = btEnum) then'
assert s.count(a) == 1, 'Pascal Script compiler source changed'
compiler.write_text(s.replace(a, b))
runtime = output / 'uPSRuntime.pas'
s = runtime.read_text()
decl = "function PSErrorToString(x: TPSError; const Param: tbtstring): tbtstring;\n"
assert s.count(decl) == 1, 'Pascal Script runtime declaration anchor changed'
s = s.replace(decl, decl + "{$IFDEF FPC}\nprocedure PSRegisterRecordReturnType(Address, ATypeInfo: Pointer);\n{$ENDIF}\n")
impl_anchor = "implementation\nuses\n  TypInfo"
impl_pos = s.find(impl_anchor)
assert impl_pos >= 0, 'Pascal Script runtime implementation anchor changed'
impl_end = s.index(";\n", impl_pos) + 2
registry = """
{$IFDEF FPC}
type
  TPSRecordReturnInfo = record
    Address: Pointer;
    ATypeInfo: Pointer;
  end;
var
  PSRecordReturnInfos: array of TPSRecordReturnInfo;

procedure PSRegisterRecordReturnType(Address, ATypeInfo: Pointer);
var
  i: Integer;
begin
  if (Address = nil) or (ATypeInfo = nil) then
    Exit;
  for i := 0 to High(PSRecordReturnInfos) do
    if PSRecordReturnInfos[i].Address = Address then
    begin
      PSRecordReturnInfos[i].ATypeInfo := ATypeInfo;
      Exit;
    end;
  SetLength(PSRecordReturnInfos, Length(PSRecordReturnInfos) + 1);
  PSRecordReturnInfos[High(PSRecordReturnInfos)].Address := Address;
  PSRecordReturnInfos[High(PSRecordReturnInfos)].ATypeInfo := ATypeInfo;
end;

function PSFindRecordReturnType(Address: Pointer): Pointer;
var
  i: Integer;
begin
  for i := 0 to High(PSRecordReturnInfos) do
    if PSRecordReturnInfos[i].Address = Address then
      Exit(PSRecordReturnInfos[i].ATypeInfo);
  Result := nil;
end;
{$ENDIF}
"""
s = s[:impl_end] + registry + s[impl_end:]
runtime.write_text(s)
p = output / 'InvokeCall.inc'
s = p.read_text()
assert s.startswith('function TPSExec.InnerfuseCall')
s = s.replace('Invoke(Address, Args, SysCalConv, nil);', 'InvokeCompat(Address, Args, SysCalConv, nil, IsStatic, IsConstr);')
s = s.replace('Invoke(Address,', 'InvokeCompat(Address,')
s = s.replace('Double(InvokeCompat(Address,Args,SysCalConv,TypeInfo(Single),IsStatic).AsExtended)', 'InvokeCompat(Address,Args,SysCalConv,TypeInfo(Single),IsStatic).AsExtended')
s = s.replace('Double(InvokeCompat(Address,Args,SysCalConv,TypeInfo(Double),IsStatic).AsExtended)', 'InvokeCompat(Address,Args,SysCalConv,TypeInfo(Double),IsStatic).AsExtended')
s = s.replace('    ResValue : TValue;\n', '    ResValue : TValue;\n    RecordTypeInfo : Pointer;\n')
record_anchor = "      else\n//          writeln(stderr, 'Result type not implemented!');"
record_case = """      {$IFDEF FPC}
      btRecord:
      begin
        // FPC 3.2.2 does not implement TRttiContext.GetDeclaredMethods.
        // The game registers exact method result metadata before running scripts.
        if _Self = nil then
          Exit(False);
        RecordTypeInfo := PSFindRecordReturnType(Address);
        if not Assigned(RecordTypeInfo) then
          Exit(False);
        ResValue := InvokeCompat(Address, Args, SysCalConv,
          PTypeInfo(RecordTypeInfo), IsStatic);
        Result := CopyArrayContents(res.dta,
          ResValue.GetReferenceToRawData, 1, res.aType);
        Exit;
      end;
      {$ENDIF}
      else
//          writeln(stderr, 'Result type not implemented!');"""
assert s.count(record_anchor) == 1, 'Pascal Script result-case anchor changed'
s = s.replace(record_anchor, record_case)
helper = '''{$IFDEF FPC}
// Experimental signature adapter only. It requires a compatible call manager.
function InvokeCompat(Address: Pointer; const Args: TArray<TValue>;
  CallConv: TCallConv; ReturnType: PTypeInfo; IsStatic: Boolean = True;
  IsConstructor: Boolean = False): TValue;
begin
  Result := Rtti.Invoke(Address, Args, CallConv, ReturnType, IsStatic, IsConstructor);
end;
{$ENDIF}
'''
p.write_text(helper + s)
print('Prepared FPC Pascal Script overlay with explicit record return registry')
