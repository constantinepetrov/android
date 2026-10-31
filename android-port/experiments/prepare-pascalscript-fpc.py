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
p = output / 'InvokeCall.inc'
s = p.read_text()
assert s.startswith('function TPSExec.InnerfuseCall')
s = s.replace('Invoke(Address, Args, SysCalConv, nil);', 'InvokeCompat(Address, Args, SysCalConv, nil, IsStatic, IsConstr);')
s = s.replace('Invoke(Address,', 'InvokeCompat(Address,')
s = s.replace('Double(InvokeCompat(Address,Args,SysCalConv,TypeInfo(Single),IsStatic).AsExtended)', 'InvokeCompat(Address,Args,SysCalConv,TypeInfo(Single),IsStatic).AsExtended')
s = s.replace('Double(InvokeCompat(Address,Args,SysCalConv,TypeInfo(Double),IsStatic).AsExtended)', 'InvokeCompat(Address,Args,SysCalConv,TypeInfo(Double),IsStatic).AsExtended')
s = s.replace('    ResValue: TValue;\nbegin', '    ResValue: TValue;\n    RttiMethod: TRttiMethod;\nbegin')
record_anchor = "      {$ENDIF}\n      else\n//          writeln(stderr, 'Result type not implemented!');"
record_case = """      {$ENDIF}
      {$IFDEF FPC}
      btRecord:
      begin
        // Resolve the record type from the imported instance method's RTTI.
        if _Self = nil then
          Exit(False);
        ctx := TRttiContext.Create;
        try
          for RttiMethod in ctx.GetType(TObject(_Self).ClassType).GetMethods do
            if (RttiMethod.CodeAddress = Address)
              and Assigned(RttiMethod.ReturnType)
              and (RttiMethod.ReturnType.TypeKind = tkRecord) then
            begin
              ResValue := InvokeCompat(Address, Args, SysCalConv,
                RttiMethod.ReturnType.Handle, IsStatic);
              Result := CopyArrayContents(res.dta,
                ResValue.GetReferenceToRawData, 1, res.aType);
              Exit;
            end;
        finally
          ctx.Free;
        end;
        Exit(False);
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
print('Prepared diagnostic Pascal Script overlay (no runtime support claimed)')
