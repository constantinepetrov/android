library kamprobe;
{$mode delphi}
uses KM_Sort;

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
exports Java_com_kamremake_androidprobe_MainActivity_nativeSortProbe;
begin
end.
