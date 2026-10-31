library kamprobe;
{$mode delphi}
uses KM_Sort, KM_AndroidMap;

type TIntArray = array[0..2] of LongInt;
function CompareInt(const A, B): Integer;
begin
  if PLongInt(@A)^ < PLongInt(@B)^ then Result := -1
  else if PLongInt(@A)^ > PLongInt(@B)^ then Result := 1
  else Result := 0;
end;

// JNI types are pointers here: this static Java method uses no JNIEnv API.
function Java_com_kamremake_androidprobe_MainActivity_nativeSortProbe(env, clazz: Pointer): LongInt; cdecl;
var values: TIntArray;
begin
  values[0] := 4; values[1] := 1; values[2] := 3;
  SortCustom(values, 0, 2, SizeOf(values[0]), @CompareInt);
  Result := values[0] * 100 + values[1] * 10 + values[2];
end;
// JNIEnv is a pointer to the JNI function-table pointer. Indices follow JNI 1.6.
type
  TGetUtf = function(e, str, copyFlag: Pointer): PAnsiChar; cdecl;
  TReleaseUtf = procedure(e, str: Pointer; chars: PAnsiChar); cdecl;
  TNewIntArray = function(e: Pointer; len: LongInt): Pointer; cdecl;
  TSetIntRegion = procedure(e, arr: Pointer; start, len: LongInt; data: PLongInt); cdecl;
  PTable = ^TTable;
  TTable = array[0..230] of Pointer;
function Java_com_kamremake_androidprobe_NativeProbeService_nativeReadMap(env, cls, path: Pointer): Pointer; cdecl;
var table: PTable; chars: PAnsiChar; values: TMapValues;
begin
  Result := nil;
  if (env = nil) or (path = nil) then Exit;
  table := PPointer(env)^;
  chars := TGetUtf(table^[169])(env, path, nil);
  if chars = nil then Exit;
  try
    if not ReadDiagnosticMap(string(chars), values) then Exit;
    Result := TNewIntArray(table^[179])(env, Length(values));
    if Result <> nil then TSetIntRegion(table^[211])(env, Result, 0, Length(values), @values[0]);
  finally
    TReleaseUtf(table^[170])(env, path, chars);
  end;
end;
exports Java_com_kamremake_androidprobe_MainActivity_nativeSortProbe,
        Java_com_kamremake_androidprobe_NativeProbeService_nativeReadMap;
begin
end.
