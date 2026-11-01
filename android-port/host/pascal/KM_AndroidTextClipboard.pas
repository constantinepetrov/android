unit KM_AndroidTextClipboard;
{$mode delphi}
interface
uses KM_TextClipboard;
type
  // Construct around one native editor input call on the focused UI thread.
  // JNIEnv and local references never escape that call or cross threads.
  TKMAndroidClipboardScope = class
  private
    fEnv, fClass, fRead, fWrite: Pointer;
    fPrevious: TKMTextClipboardProvider;
    fInstalled: Boolean;
    procedure CheckException;
    function ReadText: UnicodeString;
    procedure WriteText(const aText: UnicodeString);
  public
    constructor Create(aEnv: Pointer);
    destructor Destroy; override;
  end;
implementation
uses SysUtils;
type
  TTable = array[0..230] of Pointer;
  PTable = ^TTable;
  TFindClass = function(e: Pointer; name: PAnsiChar): Pointer; cdecl;
  TMethodID = function(e, cls: Pointer; name, signature: PAnsiChar): Pointer; cdecl;
  TCallObjectA = function(e, cls, method, args: Pointer): Pointer; cdecl;
  TCallVoidA = procedure(e, cls, method, args: Pointer); cdecl;
  TNewString = function(e: Pointer; chars: PWideChar; len: LongInt): Pointer; cdecl;
  TStringLength = function(e, str: Pointer): LongInt; cdecl;
  TStringChars = function(e, str, copyFlag: Pointer): PWideChar; cdecl;
  TReleaseChars = procedure(e, str: Pointer; chars: PWideChar); cdecl;
  TDeleteRef = procedure(e, obj: Pointer); cdecl;
  TExceptionCheck = function(e: Pointer): Byte; cdecl;
  TExceptionClear = procedure(e: Pointer); cdecl;
function Table(e: Pointer): PTable;
begin Result := PPointer(e)^ end;
procedure TKMAndroidClipboardScope.CheckException;
begin
  if TExceptionCheck(Table(fEnv)^[228])(fEnv) <> 0 then
  begin
    TExceptionClear(Table(fEnv)^[17])(fEnv);
    raise Exception.Create('Android clipboard host call failed (focus/thread/content/access)');
  end;
end;
constructor TKMAndroidClipboardScope.Create(aEnv: Pointer);
var provider: TKMTextClipboardProvider;
begin
  inherited Create;
  if aEnv = nil then raise Exception.Create('Clipboard scope requires JNIEnv');
  fEnv := aEnv;
  fClass := TFindClass(Table(fEnv)^[6])(fEnv, 'com/kamremake/androidprobe/GameTextClipboard');
  CheckException;
  if fClass = nil then raise Exception.Create('Android text clipboard class unavailable');
  fRead := TMethodID(Table(fEnv)^[113])(fEnv, fClass, 'readText', '()Ljava/lang/String;');
  CheckException;
  fWrite := TMethodID(Table(fEnv)^[113])(fEnv, fClass, 'writeText', '(Ljava/lang/String;)V');
  CheckException;
  if (fRead = nil) or (fWrite = nil) then raise Exception.Create('Clipboard host methods unavailable');
  fPrevious := GetTextClipboardProvider;
  provider.ReadText := ReadText;
  provider.WriteText := WriteText;
  SetTextClipboardProvider(provider);
  fInstalled := True;
end;
destructor TKMAndroidClipboardScope.Destroy;
begin
  if fInstalled then SetTextClipboardProvider(fPrevious);
  if (fEnv <> nil) and (fClass <> nil) then TDeleteRef(Table(fEnv)^[23])(fEnv, fClass);
  inherited;
end;
function TKMAndroidClipboardScope.ReadText: UnicodeString;
var str: Pointer; chars: PWideChar; len: LongInt;
begin
  str := TCallObjectA(Table(fEnv)^[116])(fEnv, fClass, fRead, nil);
  CheckException;
  if str = nil then raise Exception.Create('Clipboard host returned null text');
  try
    len := TStringLength(Table(fEnv)^[164])(fEnv, str);
    chars := TStringChars(Table(fEnv)^[165])(fEnv, str, nil);
    CheckException;
    if chars = nil then raise Exception.Create('Clipboard UTF-16 access failed');
    try SetString(Result, chars, len);
    finally TReleaseChars(Table(fEnv)^[166])(fEnv, str, chars) end;
  finally TDeleteRef(Table(fEnv)^[23])(fEnv, str) end;
end;
procedure TKMAndroidClipboardScope.WriteText(const aText: UnicodeString);
var str: Pointer; args: array[0..0] of QWord;
begin
  str := TNewString(Table(fEnv)^[163])(fEnv, PWideChar(aText), Length(aText));
  CheckException;
  if str = nil then raise Exception.Create('Clipboard UTF-16 allocation failed');
  try
    args[0] := QWord(PtrUInt(str));
    TCallVoidA(Table(fEnv)^[143])(fEnv, fClass, fWrite, @args[0]);
    CheckException;
  finally TDeleteRef(Table(fEnv)^[23])(fEnv, str) end;
end;
end.
