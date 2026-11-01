program game_messages_smoke;
{$mode delphi}
uses SysUtils, Classes, KM_GameMessages, KM_GameMessageTypes, KM_MessageStack,
  KM_Points, KM_CommonClasses;
var
  port: TKMGameMessagePort;
  state, restored: TKMStoredGameMessages;
  legacy: TKMMessageStack;
  a,b,c: TKMemoryStreamBinary;
  i: Integer;
  failed: Boolean;
begin
  state := TKMStoredGameMessages.Create;
  restored := TKMStoredGameMessages.Create;
  legacy := TKMMessageStack.Create;
  a := TKMemoryStreamBinary.Create; b := TKMemoryStreamBinary.Create; c := TKMemoryStreamBinary.Create;
  try
    port := state;
    port.Issue(mkHouse, 'House needs stone', KMPoint(17,23));
    port.Issue(mkQuill, UnicodeString('Warning ') + WideChar($0416), KMPOINT_ZERO);
    state.Stack[0].IsRead := True;
    legacy.Add(mkHouse, 'House needs stone', KMPoint(17,23));
    legacy.Add(mkQuill, UnicodeString('Warning ') + WideChar($0416), KMPOINT_ZERO);
    legacy[0].IsRead := True;
    legacy.Save(a); state.Save(b);
    if (a.Size <> b.Size) or not CompareMem(a.Memory,b.Memory,a.Size) then Halt(1);
    b.Position := 0; restored.Load(b);
    if (b.Position <> b.Size) or (restored.Stack.CountStack <> 2) or
       (restored.Stack[0].Loc.X <> 17) or not restored.Stack[0].IsRead or
       (restored.Stack[1].Text <> legacy[1].Text) then Halt(2);
    restored.Save(c);
    if (a.Size <> c.Size) or not CompareMem(a.Memory,c.Memory,a.Size) then Halt(3);
    for i := 0 to a.Size - 1 do
    begin
      b.Clear; a.Position := 0; b.CopyFrom(a,i); b.Size := i; b.Position := 0;
      failed := False;
      try restored.Load(b); except on E: Exception do failed := True; end;
      if not failed or (b.Position <> 0) or (restored.Stack.CountStack <> 2) then Halt(4);
    end;
    b.Clear; a.Position := 0; b.CopyFrom(a,a.Size); b.Position := 2;
    b.Write(Byte(0)); b.Position := 0;
    failed := False;
    try restored.Load(b); except on E: Exception do failed := True; end;
    if not failed then Halt(5);
    WriteLn('REAL_MESSAGES_OK typed dispatch, legacy byte parity, Unicode/read flag, roundtrip, truncation/corruption rejection');
  finally
    c.Free; b.Free; a.Free; legacy.Free; restored.Free; state.Free;
  end;
end.
