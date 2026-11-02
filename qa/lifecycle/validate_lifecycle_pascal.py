#!/usr/bin/env python3
"""Compile and execute the ACTUAL patched AppPause/AppResume Pascal methods against fake game state."""
import argparse
from pathlib import Path
import subprocess
import tempfile

PREFIX = r"""
program LifecycleTest;
{$mode delphi}
uses SysUtils;
type
  TGameParams = class
    IsMultiPlayerOrSpec, IsMapEditor, IsReplay: Boolean;
  end;
  TGame = class
    Params: TGameParams;
    IsPaused: Boolean;
    constructor Create;
    destructor Destroy; override;
  end;
  TGameApp = class
    Game: TGame;
  end;
  TMusic = class
    Pauses, Resumes: Integer;
    procedure Pause;
    procedure Resume;
  end;
  TSettings = class
    Saves: Integer;
    procedure SaveSettings;
  end;
  TKeys = class
    Saves: Integer;
    procedure SaveToXML;
  end;
  TLog = class
    procedure AddTime(const AFormat: string; const AArgs: array of const);
  end;
  TKMMain = class
    fBackgroundPausedGame: TObject;
    fTickSchedule, fUpdateStateSchedule, fLastRenderTime: Cardinal;
    procedure AppPause;
    procedure AppResume;
  end;
var
  gHostAppActive: Boolean = True;
  gGameApp: TGameApp;
  gGameAppSettings: TSettings;
  gKeySettings: TKeys;
  gMusic: TMusic;
  gLog: TLog;
  FakeTime: Cardinal = 12345;
function TimeGet: Cardinal;
begin
  Result := FakeTime;
end;
procedure ALog(const aText: string);
begin
end;
constructor TGame.Create;
begin
  inherited Create;
  Params := TGameParams.Create;
end;
destructor TGame.Destroy;
begin
  Params.Free;
  inherited;
end;
procedure TMusic.Pause;
begin
  Inc(Pauses);
end;
procedure TMusic.Resume;
begin
  Inc(Resumes);
end;
procedure TSettings.SaveSettings;
begin
  Inc(Saves);
end;
procedure TKeys.SaveToXML;
begin
  Inc(Saves);
end;
procedure TLog.AddTime(const AFormat: string; const AArgs: array of const);
begin
  // Format checks the real Pascal varargs signature used by the source.
  WriteLn(Format(AFormat, AArgs));
end;
"""
SUFFIX = r"""
procedure Check(const Condition: Boolean; const LabelText: string);
begin
  if not Condition then
    raise Exception.Create('FAILED: ' + LabelText);
end;
procedure Reset(const M: TKMMain);
begin
  gHostAppActive := True;
  gGameApp.Game.Params.IsMultiPlayerOrSpec := False;
  gGameApp.Game.Params.IsMapEditor := False;
  gGameApp.Game.Params.IsReplay := False;
  gGameApp.Game.IsPaused := False;
  M.fBackgroundPausedGame := nil;
end;
var
  M: TKMMain;
  OldGame, NewGame: TGame;
begin
  gGameApp := TGameApp.Create;
  gGameApp.Game := TGame.Create;
  gMusic := TMusic.Create;
  gGameAppSettings := TSettings.Create;
  gKeySettings := TKeys.Create;
  gLog := TLog.Create;
  M := TKMMain.Create;
  try
    // Android pauses an unpaused SP game and restores exactly that pause.
    Reset(M);
    M.AppPause;
    Check(gGameApp.Game.IsPaused, 'background must pause running SP');
    Check(not gHostAppActive, 'background inactive');
    M.AppResume;
    Check(not gGameApp.Game.IsPaused, 'resume must unpause auto-paused SP');
    Check(gHostAppActive, 'foreground active');
    Check(M.fTickSchedule = FakeTime, 'ticks reset on return');
    Check(M.fUpdateStateSchedule = FakeTime, 'UI schedule reset on return');
    Check(M.fLastRenderTime = FakeTime, 'frame delta reset on return');

    // Never override the player's own pause.
    Reset(M);
    gGameApp.Game.IsPaused := True;
    M.AppPause;
    M.AppResume;
    Check(gGameApp.Game.IsPaused, 'manual pause must persist');

    // Duplicate callbacks must not destroy the ownership record.
    Reset(M);
    M.AppPause;
    M.AppPause;
    M.AppResume;
    Check(not gGameApp.Game.IsPaused, 'double onPause must restore');
    M.AppResume;
    Check(not gGameApp.Game.IsPaused, 'double onResume is idempotent');

    // Never apply a stale auto-pause to a different game.
    Reset(M);
    OldGame := gGameApp.Game;
    M.AppPause;
    NewGame := TGame.Create;
    gGameApp.Game := NewGame;
    M.AppResume;
    Check(not NewGame.IsPaused, 'new game must not be touched');
    gGameApp.Game := OldGame;
    NewGame.Free;
    OldGame.IsPaused := False;

    // Non-SP modes must retain their pause state.
    Reset(M);
    gGameApp.Game.Params.IsMultiPlayerOrSpec := True;
    M.AppPause; M.AppResume;
    Check(not gGameApp.Game.IsPaused, 'multiplayer not paused');
    Reset(M);
    gGameApp.Game.Params.IsMapEditor := True;
    M.AppPause; M.AppResume;
    Check(not gGameApp.Game.IsPaused, 'map editor not paused');
    Reset(M);
    gGameApp.Game.Params.IsReplay := True;
    M.AppPause; M.AppResume;
    Check(not gGameApp.Game.IsPaused, 'replay not paused');

    // Menu -> background -> foreground must not dereference a game.
    Reset(M);
    OldGame := gGameApp.Game;
    gGameApp.Game := nil;
    M.AppPause; M.AppResume;
    gGameApp.Game := OldGame;
    Check(M.fBackgroundPausedGame = nil, 'no stale game reference in menu');

    Check((gMusic.Pauses > 0) and (gMusic.Resumes > 0), 'music callbacks');
    Check((gGameAppSettings.Saves > 0) and (gKeySettings.Saves > 0), 'settings persisted');
    WriteLn('LIFECYCLE_SOURCE_BEHAVIOR_PASS');
  finally
    M.Free;
    gGameApp.Game.Free;
    gGameApp.Free;
    gMusic.Free;
    gGameAppSettings.Free;
    gKeySettings.Free;
    gLog.Free;
  end;
end.
"""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.read_text()
    assert source.count("procedure TKMMain.AppPause;") == 1
    assert source.count("procedure TKMMain.AppResume;") == 1
    before, tail = source.split("procedure TKMMain.AppPause;", 1)
    methods, after = tail.split("procedure TKMMain.UpdateFPS", 1)
    assert "fBackgroundPausedGame: TObject;" in before
    assert "fBackgroundPausedGame := nil;" in methods
    with tempfile.TemporaryDirectory(prefix="kam-lifecycle-") as temp:
        path = Path(temp) / "lifecycle_test.pas"
        path.write_text(PREFIX + "procedure TKMMain.AppPause;" + methods +
                        SUFFIX, encoding="utf-8")
        result = subprocess.run(["fpc", "-Mdelphi", "-o" + str(Path(temp) / "test"), str(path)],
                                text=True, capture_output=True, timeout=60)
        print(result.stdout[-2500:])
        print(result.stderr[-2500:])
        if result.returncode:
            raise SystemExit("Pascal compiler rejected actual lifecycle source")
        test = subprocess.run([str(Path(temp) / "test")], text=True,
                              capture_output=True, timeout=30)
        print(test.stdout)
        print(test.stderr)
        if test.returncode or "LIFECYCLE_SOURCE_BEHAVIOR_PASS" not in test.stdout:
            raise SystemExit("Actual lifecycle source failed behavior cases")
    print("PASSED: original Pascal methods compiled and executed in 7 scenario groups")

if __name__ == "__main__":
    main()
