unit KM_TextClipboard;
{$I KaM_Remake.inc}
interface
type
  TKMTextClipboardProvider = record
    ReadText: function: UnicodeString of object;
    WriteText: procedure(const aText: UnicodeString) of object;
  end;
procedure SetTextClipboardProvider(const aProvider: TKMTextClipboardProvider);
function GetTextClipboardProvider: TKMTextClipboardProvider;
function KMReadClipboardText: UnicodeString;
procedure KMWriteClipboardText(const aText: UnicodeString);
implementation
uses SysUtils {$IFNDEF ANDROID}, Clipbrd{$ENDIF};
threadvar Provider: TKMTextClipboardProvider;
procedure SetTextClipboardProvider(const aProvider: TKMTextClipboardProvider);
begin
  if Assigned(aProvider.ReadText) <> Assigned(aProvider.WriteText) then
    raise Exception.Create('Clipboard requires both read and write operations');
  Provider := aProvider;
end;
function GetTextClipboardProvider: TKMTextClipboardProvider;
begin Result := Provider end;
function KMReadClipboardText: UnicodeString;
begin
  {$IFDEF ANDROID}
  if not Assigned(Provider.ReadText) then
    raise Exception.Create('Android text clipboard host is not bound on this input thread');
  Result := Provider.ReadText();
  {$ELSE}
  Result := Clipboard.AsText;
  {$ENDIF}
end;
procedure KMWriteClipboardText(const aText: UnicodeString);
begin
  {$IFDEF ANDROID}
  if not Assigned(Provider.WriteText) then
    raise Exception.Create('Android text clipboard host is not bound on this input thread');
  Provider.WriteText(aText);
  {$ELSE}
  Clipboard.AsText := aText;
  {$ENDIF}
end;
end.
