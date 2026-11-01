program platform_services_probe;
{$mode delphi}
uses cthreads, Classes, SysUtils, KM_TextClipboard, KM_GameAudioState, KM_BassAndroid;
type
  THost = class
    Text: UnicodeString;
    Stopping, FailRead: Boolean;
    function ReadText: UnicodeString;
    procedure WriteText(const aText: UnicodeString);
    function IsStopping: Boolean;
  end;
  TThreadProbe = class(TThread)
    Rejected: Boolean;
    procedure Execute; override;
  end;
function THost.ReadText: UnicodeString;
begin
  if FailRead then raise Exception.Create('Host denied clipboard');
  Result := Text;
end;
procedure THost.WriteText(const aText: UnicodeString);
begin Text := aText end;
function THost.IsStopping: Boolean;
begin Result := Stopping end;
procedure TThreadProbe.Execute;
begin
  try KMReadClipboardText; except on E: Exception do Rejected := True end;
end;
var host, other: THost; p, empty: TKMTextClipboardProvider;
    worker: TThreadProbe; failed: Boolean; text: UnicodeString;
begin
  host := THost.Create; other := THost.Create;
  try
    if GameAudioIsStopping then Halt(1);
    BindGameAudioState(host, host.IsStopping);
    if GameAudioIsStopping then Halt(2);
    host.Stopping := True;
    if not GameAudioIsStopping then Halt(3);
    UnbindGameAudioState(other);
    if not GameAudioIsStopping then Halt(4);
    UnbindGameAudioState(host);
    if GameAudioIsStopping then Halt(5);
    FillChar(empty, SizeOf(empty), 0);
    SetTextClipboardProvider(empty);
    failed := False;
    try KMReadClipboardText; except on E: Exception do failed := True end;
    if not failed then Halt(6);
    p.ReadText := host.ReadText; p.WriteText := host.WriteText;
    SetTextClipboardProvider(p);
    text := UnicodeString('KaM ') + WideChar($0416) + WideChar(0) + WideChar($D83D) + WideChar($DE00);
    KMWriteClipboardText(text);
    if KMReadClipboardText <> text then Halt(7);
    worker := TThreadProbe.Create(False);
    try worker.WaitFor; if not worker.Rejected then Halt(8); finally worker.Free end;
    host.FailRead := True; failed := False;
    try KMReadClipboardText; except on E: Exception do failed := True end;
    if not failed or (host.Text <> text) then Halt(9);
    SetTextClipboardProvider(empty);
    if (SizeOf(LongBool) <> 4) or (SizeOf(LongWord) <> 4) or (SizeOf(QWord) <> 8) or (SizeOf(Single) <> 4) then Halt(10);
    try
      RequireAndroidBass;
      WriteLn('BASS_LIBRARY_PRESENT_VERSION_CHECK_ONLY');
    except
      on E: Exception do
      begin
        if AndroidBassAvailable or (Pos('libbass.so', E.Message) = 0) then Halt(11);
        WriteLn('BASS_MISSING_LIBRARY_REJECTED ', E.Message);
      end;
    end;
    WriteLn('PLATFORM_SERVICES_OK Unicode clipboard, thread isolation, errors, audio session state, ABI widths');
  finally
    UnbindGameAudioState(host);
    SetTextClipboardProvider(empty);
    other.Free; host.Free;
  end;
end.
