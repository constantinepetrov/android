unit KM_GameMessages;
{$I KaM_Remake.inc}
interface
uses KM_CommonClasses, KM_GameMessageTypes, KM_Points, KM_MessageStack;
type
  TKMGameMessagePort = class abstract
  public
    procedure Issue(aKind: TKMMessageKind; const aText: UnicodeString; const aLoc: TKMPoint); virtual; abstract;
  end;

  // Actual local message state for a host without desktop controls.
  // This persists only the MessageStack segment, not an entire UI/body save.
  TKMStoredGameMessages = class(TKMGameMessagePort)
  private
    fStack: TKMMessageStack;
  public
    constructor Create;
    destructor Destroy; override;
    procedure Issue(aKind: TKMMessageKind; const aText: UnicodeString; const aLoc: TKMPoint); override;
    procedure Save(aStream: TKMemoryStreamBinary);
    procedure Load(aStream: TKMemoryStreamBinary);
    property Stack: TKMMessageStack read fStack;
  end;
implementation
uses SysUtils, Classes;
constructor TKMStoredGameMessages.Create;
begin
  inherited Create;
  fStack := TKMMessageStack.Create;
end;
destructor TKMStoredGameMessages.Destroy;
begin
  fStack.Free;
  inherited;
end;
procedure TKMStoredGameMessages.Issue(aKind: TKMMessageKind; const aText: UnicodeString; const aLoc: TKMPoint);
begin
  fStack.Add(aKind, aText, aLoc);
end;
procedure TKMStoredGameMessages.Save(aStream: TKMemoryStreamBinary);
begin
  fStack.Save(aStream);
end;
procedure TKMStoredGameMessages.Load(aStream: TKMemoryStreamBinary);
var
  start: Int64;
  count, i: Integer;
  n: Word;
  kind: TKMMessageKind;
  flag: Byte;
  marker: AnsiString;
  candidate: TKMMessageStack;
  procedure Require(aBytes: Int64);
  begin
    if (aBytes < 0) or (aBytes > aStream.Size - aStream.Position) then
      raise EReadError.Create('Truncated message stack');
  end;
  procedure MarkerEquals(const expected: AnsiString);
  begin
    Require(SizeOf(n)); aStream.ReadBuffer(n, SizeOf(n));
    Require(n);
    SetLength(marker, n);
    if n > 0 then aStream.ReadBuffer(marker[1], n);
    if marker <> expected then raise EReadError.Create('Invalid message stack marker');
  end;
begin
  start := aStream.Position;
  candidate := nil;
  try
    // Validate the legacy binary segment before its unchecked typed reads.
    MarkerEquals('MessageStack');
    Require(SizeOf(count)); aStream.ReadBuffer(count, SizeOf(count));
    if (count < 0) or (count > (aStream.Size - aStream.Position) div 2) then
      raise EReadError.Create('Invalid message count');
    for i := 0 to count - 1 do
    begin
      MarkerEquals('StackMessage');
      Require(SizeOf(TKMPoint)); aStream.Position := aStream.Position + SizeOf(TKMPoint);
      Require(SizeOf(n)); aStream.ReadBuffer(n, SizeOf(n));
      Require(Int64(n) * SizeOf(WideChar));
      aStream.Position := aStream.Position + Int64(n) * SizeOf(WideChar);
      Require(SizeOf(kind) + SizeOf(flag));
      aStream.ReadBuffer(kind, SizeOf(kind));
      if (Ord(kind) < Ord(Low(TKMMessageKind))) or (Ord(kind) > Ord(High(TKMMessageKind))) then
        raise EReadError.Create('Invalid message kind');
      aStream.ReadBuffer(flag, SizeOf(flag));
      if flag > 1 then raise EReadError.Create('Invalid message read flag');
    end;
    aStream.Position := start;
    candidate := TKMMessageStack.Create;
    candidate.Load(aStream);
    fStack.Free;
    fStack := candidate;
    candidate := nil;
  except
    aStream.Position := start;
    candidate.Free;
    raise;
  end;
end;
end.
