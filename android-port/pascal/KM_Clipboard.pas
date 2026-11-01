unit KM_Clipboard;
{$I KaM_Remake.inc}
{$IFNDEF ANDROID}
  {$MESSAGE FATAL 'KM_Clipboard is the Android in-process clipboard adapter'}
{$ENDIF}
interface

uses
  Classes;

type
  // Android editor selections remain copyable/pastable inside the game. The
  // adapter intentionally stores opaque stream formats; it does not pretend to
  // integrate with the OS clipboard, which has a different text/content API.
  TKMClipboard = class
  public
    function HasFormat(aFormat: Word): Boolean;
    procedure SetFormat(aFormat: Word; aStream: TStream);
    function GetFormat(aFormat: Word; aStream: TStream): Boolean;
  end;

var
  Clipboard: TKMClipboard;

implementation

uses
  SysUtils;

type
  TKMClipboardEntry = record
    Format: Word;
    Data: TMemoryStream;
  end;

var
  ClipboardEntry: TKMClipboardEntry;

function TKMClipboard.HasFormat(aFormat: Word): Boolean;
begin
  Result := (ClipboardEntry.Data <> nil) and (ClipboardEntry.Format = aFormat);
end;

procedure TKMClipboard.SetFormat(aFormat: Word; aStream: TStream);
begin
  if ClipboardEntry.Data = nil then
    ClipboardEntry.Data := TMemoryStream.Create;
  ClipboardEntry.Data.Clear;
  ClipboardEntry.Format := aFormat;
  aStream.Position := 0;
  ClipboardEntry.Data.CopyFrom(aStream, 0);
  ClipboardEntry.Data.Position := 0;
end;

function TKMClipboard.GetFormat(aFormat: Word; aStream: TStream): Boolean;
begin
  Result := HasFormat(aFormat);
  if not Result then
    Exit;
  ClipboardEntry.Data.Position := 0;
  aStream.Size := 0;
  aStream.Position := 0;
  aStream.CopyFrom(ClipboardEntry.Data, 0);
  aStream.Position := 0;
end;

initialization
  Clipboard := TKMClipboard.Create;

finalization
  FreeAndNil(ClipboardEntry.Data);
  FreeAndNil(Clipboard);

end.
