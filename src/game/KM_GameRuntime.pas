unit KM_GameRuntime;
{$I KaM_Remake.inc}
interface
uses
  KM_CommonTypes, KM_GameTypes, KM_MediaTypes;

type
  TKMReplayMismatchDecision = (rmdContinue, rmdContinueAlways, rmdStop);

  // Host services required by the real game session, kept independent of desktop Forms.
  TKMGameHostCallbacks = record
    StopGame: procedure(aMsg: TKMGameResultMsg; const aText: UnicodeString) of object;
    StartReplay: procedure(const aSavePath: UnicodeString) of object;
    CampaignSoundPath: function(const aSound: AnsiString; aFormat: TKMAudioFormat): UnicodeString of object;
    GameSpeedChanged: TSingleEvent;
    GlobalTickCount: function: Cardinal of object;
    GetGameTickInterval: function: Cardinal of object;
    SetGameTickInterval: procedure(aInterval: Cardinal) of object;
    LockGame: function: Boolean of object;
    UnlockGame: TKMEvent;
    ReplayMismatch: function(const aText: UnicodeString): TKMReplayMismatchDecision of object;
    NewGameSingleSave: procedure(const aSaveName: UnicodeString) of object;
    PrintScreen: procedure(const aFilename: UnicodeString) of object;
    PrepageStopGame: procedure(aMsg: TKMGameResultMsg) of object;
    NewGameMapEditor: procedure(const aPath: UnicodeString; aSizeX, aSizeY: Integer; aMapFullCRC, aMapSimpleCRC: Cardinal; aMultiplayerLoadMode: Boolean) of object;
    TryLoadSavePoint: function(aTick: Integer): Boolean of object;
    GetChatText: function: UnicodeString of object;
    RenderGameFrame: TKMEvent;
    GameOptionsChanged: TKMEvent;
    GameTickDuration: function: Single of object;
  end;

var
  KMGameHost: TKMGameHostCallbacks;

function KMHostGetGlobalTickCount: Cardinal;
function KMHostGetGameTickInterval: Cardinal;
procedure KMHostSetGameTickInterval(aInterval: Cardinal);
function KMHostLockGame: Boolean;
procedure KMHostUnlockGame;
procedure KMHostStopGame(aMsg: TKMGameResultMsg; const aText: UnicodeString);
procedure KMHostStartReplay(const aSavePath: UnicodeString);
function KMHostCampaignSoundPath(const aSound: AnsiString; aFormat: TKMAudioFormat): UnicodeString;
function KMHostReplayMismatch(const aText: UnicodeString): TKMReplayMismatchDecision;
procedure KMHostNewGameSingleSave(const aSaveName: UnicodeString);
procedure KMHostPrintScreen(const aFilename: UnicodeString);
procedure KMHostPrepageStopGame(aMsg: TKMGameResultMsg);
procedure KMHostNewGameMapEditor(const aPath: UnicodeString; aSizeX, aSizeY: Integer; aMapFullCRC, aMapSimpleCRC: Cardinal; aMultiplayerLoadMode: Boolean);
function KMHostTryLoadSavePoint(aTick: Integer): Boolean;
function KMHostGetChatText: UnicodeString;
procedure KMHostRenderGameFrame;
procedure KMHostGameOptionsChanged;
function KMHostGetGameTickDuration: Single;

implementation
uses SysUtils;

function KMHostGetGlobalTickCount: Cardinal;
begin
  if not Assigned(KMGameHost.GlobalTickCount) then
    raise Exception.Create('Android game host has no global tick clock');
  Result := KMGameHost.GlobalTickCount();
end;

function KMHostGetGameTickInterval: Cardinal;
begin
  if not Assigned(KMGameHost.GetGameTickInterval) then
    raise Exception.Create('Android game host has no tick scheduler');
  Result := KMGameHost.GetGameTickInterval();
  if Result = 0 then raise Exception.Create('Android game host returned a zero tick interval');
end;

procedure KMHostSetGameTickInterval(aInterval: Cardinal);
begin
  if (aInterval = 0) or not Assigned(KMGameHost.SetGameTickInterval) then
    raise Exception.Create('Android game host cannot update the tick interval');
  KMGameHost.SetGameTickInterval(aInterval);
end;

function KMHostLockGame: Boolean;
begin
  if not Assigned(KMGameHost.LockGame) then
    raise Exception.Create('Android game host has no game-state lock');
  Result := KMGameHost.LockGame();
end;

procedure KMHostUnlockGame;
begin
  if not Assigned(KMGameHost.UnlockGame) then
    raise Exception.Create('Android game host has no game-state unlock');
  KMGameHost.UnlockGame();
end;

procedure KMHostStopGame(aMsg: TKMGameResultMsg; const aText: UnicodeString);
begin
  if not Assigned(KMGameHost.StopGame) then
    raise Exception.Create('Android game host cannot stop the current session');
  KMGameHost.StopGame(aMsg, aText);
end;

procedure KMHostStartReplay(const aSavePath: UnicodeString);
begin
  if not Assigned(KMGameHost.StartReplay) then
    raise Exception.Create('Android game host cannot restart a replay');
  KMGameHost.StartReplay(aSavePath);
end;

function KMHostCampaignSoundPath(const aSound: AnsiString; aFormat: TKMAudioFormat): UnicodeString;
begin
  if not Assigned(KMGameHost.CampaignSoundPath) then
    raise Exception.Create('Android game host has no campaign sound resolver');
  Result := KMGameHost.CampaignSoundPath(aSound, aFormat);
end;

function KMHostReplayMismatch(const aText: UnicodeString): TKMReplayMismatchDecision;
begin
  if not Assigned(KMGameHost.ReplayMismatch) then
    raise Exception.Create('Android game host cannot report replay consistency errors');
  Result := KMGameHost.ReplayMismatch(aText);
end;

procedure KMHostNewGameSingleSave(const aSaveName: UnicodeString);
begin
  if not Assigned(KMGameHost.NewGameSingleSave) then raise Exception.Create('Android host cannot load a saved game');
  KMGameHost.NewGameSingleSave(aSaveName);
end;

procedure KMHostPrintScreen(const aFilename: UnicodeString);
begin
  if not Assigned(KMGameHost.PrintScreen) then raise Exception.Create('Android host has no screenshot exporter');
  KMGameHost.PrintScreen(aFilename);
end;

procedure KMHostPrepageStopGame(aMsg: TKMGameResultMsg);
begin
  if not Assigned(KMGameHost.PrepageStopGame) then raise Exception.Create('Android host cannot transition from the active game');
  KMGameHost.PrepageStopGame(aMsg);
end;

procedure KMHostNewGameMapEditor(const aPath: UnicodeString; aSizeX, aSizeY: Integer; aMapFullCRC, aMapSimpleCRC: Cardinal; aMultiplayerLoadMode: Boolean);
begin
  if not Assigned(KMGameHost.NewGameMapEditor) then raise Exception.Create('Android host cannot open a map editor session');
  KMGameHost.NewGameMapEditor(aPath, aSizeX, aSizeY, aMapFullCRC, aMapSimpleCRC, aMultiplayerLoadMode);
end;

function KMHostTryLoadSavePoint(aTick: Integer): Boolean;
begin
  if not Assigned(KMGameHost.TryLoadSavePoint) then raise Exception.Create('Android host cannot load a save point');
  Result := KMGameHost.TryLoadSavePoint(aTick);
end;

function KMHostGetChatText: UnicodeString;
begin
  if not Assigned(KMGameHost.GetChatText) then raise Exception.Create('Android host has no chat state');
  Result := KMGameHost.GetChatText();
end;

procedure KMHostRenderGameFrame;
begin
  if not Assigned(KMGameHost.RenderGameFrame) then raise Exception.Create('Android host cannot render the current game frame');
  KMGameHost.RenderGameFrame();
end;

procedure KMHostGameOptionsChanged;
begin
  if not Assigned(KMGameHost.GameOptionsChanged) then raise Exception.Create('Android host cannot apply changed game options');
  KMGameHost.GameOptionsChanged();
end;

function KMHostGetGameTickDuration: Single;
begin
  if not Assigned(KMGameHost.GameTickDuration) then raise Exception.Create('Android host has no game tick duration');
  Result := KMGameHost.GameTickDuration();
  if Result <= 0 then raise Exception.Create('Android host returned an invalid game tick duration');
end;

end.
