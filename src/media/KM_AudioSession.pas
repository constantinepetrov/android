unit KM_AudioSession;
{$I KaM_Remake.inc}
interface
uses Classes, SyncObjs;
type
  TKMAudioInitState = (aisStarting, aisReady, aisFailed, aisStopped);
  TKMAudioBackend = class abstract
  public
    function Load: Boolean; virtual; abstract;
    function OpenDevice: Pointer; virtual; abstract;
    function CreateContext(aDevice: Pointer): Pointer; virtual; abstract;
    function MakeCurrent(aContext: Pointer): Boolean; virtual; abstract;
    function CreateBuffer(var aID: Cardinal): Boolean; virtual; abstract;
    function CreateSource(var aID: Cardinal): Boolean; virtual; abstract;
    function Setup: Boolean; virtual; abstract;
    procedure DeleteSource(aID: Cardinal); virtual; abstract;
    procedure DeleteBuffer(aID: Cardinal); virtual; abstract;
    procedure DestroyContext(aContext: Pointer); virtual; abstract;
    // On failure the handle remains owned/live; throw without consuming it.
    procedure CloseDevice(aDevice: Pointer); virtual; abstract;
  end;
  TKMAudioSession = class;
  TKMAudioInitThread = class(TThread)
  private
    fSession: TKMAudioSession;
  protected
    procedure Execute; override;
  public
    constructor Create(aSession: TKMAudioSession);
    function Cancelled: Boolean;
  end;
  // Owns backend, worker and all resources. Playback and destruction must be
  // serialized by the caller; only initialization runs concurrently.
  TKMAudioSession = class
  private
    fBackend: TKMAudioBackend;
    fWorker: TKMAudioInitThread;
    fLock: TCriticalSection;
    fState: TKMAudioInitState;
    fError: string;
    fDevice, fContext: Pointer;
    fBuffers, fSources: array of Cardinal;
    procedure Initialize;
    procedure Cleanup;
    function GetState: TKMAudioInitState;
    function GetError: string;
  public
    constructor Create(aBackend: TKMAudioBackend; aCount: Integer);
    destructor Destroy; override;
    procedure Stop;
    function Activate: Boolean;
    function Buffer(aIndex: Integer): Cardinal;
    function Source(aIndex: Integer): Cardinal;
    property State: TKMAudioInitState read GetState;
    property ErrorText: string read GetError;
    property Device: Pointer read fDevice;
  end;
implementation
uses SysUtils;
constructor TKMAudioInitThread.Create(aSession: TKMAudioSession);
begin
  inherited Create(True);
  FreeOnTerminate := False;
  fSession := aSession;
end;
function TKMAudioInitThread.Cancelled: Boolean;
begin Result := Terminated end;
procedure TKMAudioInitThread.Execute;
begin fSession.Initialize end;
constructor TKMAudioSession.Create(aBackend: TKMAudioBackend; aCount: Integer);
begin
  inherited Create;
  fBackend := aBackend;
  fLock := TCriticalSection.Create;
  if (aBackend = nil) or (aCount < 1) then raise Exception.Create('Invalid audio session');
  SetLength(fBuffers, aCount); SetLength(fSources, aCount);
  fState := aisStarting;
  fWorker := TKMAudioInitThread.Create(Self);
  fWorker.Start;
end;
function TKMAudioSession.GetState: TKMAudioInitState;
begin
  fLock.Enter;
  try Result := fState finally fLock.Leave end;
end;
function TKMAudioSession.GetError: string;
begin
  fLock.Enter;
  try Result := fError finally fLock.Leave end;
end;
procedure TKMAudioSession.Initialize;
var i: Integer;
  procedure Require(aSuccess: Boolean; const aStage: string);
  begin
    if not aSuccess then raise Exception.Create('OpenAL initialization failed: ' + aStage);
    if fWorker.Cancelled then raise Exception.Create('OpenAL initialization cancelled');
  end;
begin
  try
    Require(fBackend.Load, 'load');
    fDevice := fBackend.OpenDevice; Require(fDevice <> nil, 'device');
    fContext := fBackend.CreateContext(fDevice); Require(fContext <> nil, 'context');
    Require(fBackend.MakeCurrent(fContext), 'bind context');
    for i := 0 to High(fBuffers) do
    begin
      Require(fBackend.CreateBuffer(fBuffers[i]) and (fBuffers[i] <> 0), 'buffer');
      Require(fBackend.CreateSource(fSources[i]) and (fSources[i] <> 0), 'source');
    end;
    Require(fBackend.Setup, 'listener/distance');
    // Standard alcMakeContextCurrent is process-global. Release it on the init
    // worker before publishing readiness; the playback thread binds explicitly.
    Require(fBackend.MakeCurrent(nil), 'release init context');
    fLock.Enter;
    try fState := aisReady finally fLock.Leave end;
  except
    on E: Exception do
    begin
      try Cleanup;
      except on C: Exception do
        begin
          fLock.Enter;
          try fError := 'Cleanup: ' + C.Message + '; ' finally fLock.Leave end;
        end;
      end;
      fLock.Enter;
      try fError := fError + E.Message; fState := aisFailed finally fLock.Leave end;
    end;
  end;
end;
procedure TKMAudioSession.Cleanup;
var i: Integer; bound, detached: Boolean; errors: string;
  procedure Remember(const aStage, aMessage: string);
  begin
    if errors <> '' then errors := errors + '; ';
    errors := errors + aStage + ': ' + aMessage;
  end;
begin
  errors := '';
  if fContext <> nil then
  begin
    bound := False;
    try bound := fBackend.MakeCurrent(fContext);
    except on E: Exception do Remember('bind cleanup context', E.Message) end;
    if bound then
    begin
      // Continue freeing independent objects after a failure. Successful releases
      // are invalidated immediately, so a retry never deletes a stale ID.
      for i := 0 to High(fSources) do
        if fSources[i] <> 0 then
          try
            fBackend.DeleteSource(fSources[i]); fSources[i] := 0;
          except on E: Exception do Remember('delete source', E.Message) end;
      for i := 0 to High(fBuffers) do
        if fBuffers[i] <> 0 then
          try
            fBackend.DeleteBuffer(fBuffers[i]); fBuffers[i] := 0;
          except on E: Exception do Remember('delete buffer', E.Message) end;
    end;
    detached := False;
    try detached := fBackend.MakeCurrent(nil);
    except on E: Exception do Remember('detach cleanup context', E.Message) end;
    if detached then
    begin
      try
        fBackend.DestroyContext(fContext);
        fContext := nil;
        // Context destruction releases any remaining objects even if binding
        // or individual deletions failed. Do this BEFORE closing the device.
        for i := 0 to High(fSources) do fSources[i] := 0;
        for i := 0 to High(fBuffers) do fBuffers[i] := 0;
      except on E: Exception do Remember('destroy context', E.Message) end;
    end
    else Remember('detach cleanup context', 'context retained for retry');
  end;
  if (fContext = nil) and (fDevice <> nil) then
  begin
    try
      fBackend.CloseDevice(fDevice);
      fDevice := nil; // A failed close retains the handle for the next Stop.
    except on E: Exception do Remember('close device', E.Message) end;
  end;
  if errors <> '' then raise Exception.Create(errors);
end;
function TKMAudioSession.Activate: Boolean;
begin
  fLock.Enter;
  try
    Result := (fState = aisReady) and (fContext <> nil) and (fDevice <> nil);
    if Result and not fBackend.MakeCurrent(fContext) then
    begin
      fState := aisFailed;
      fError := 'OpenAL playback context could not be bound';
      Result := False;
    end;
  finally fLock.Leave end;
end;
function TKMAudioSession.Buffer(aIndex: Integer): Cardinal;
begin Result := fBuffers[aIndex] end;
function TKMAudioSession.Source(aIndex: Integer): Cardinal;
begin Result := fSources[aIndex] end;
procedure TKMAudioSession.Stop;
begin
  try
    if fWorker <> nil then
    begin
      fWorker.Terminate;
      fWorker.WaitFor; // No Synchronize callbacks or logger references on worker.
      FreeAndNil(fWorker);
    end;
    try Cleanup;
    except
      on E: Exception do
      begin
        fLock.Enter;
        try
          if fError <> '' then fError := fError + '; ';
          fError := fError + 'Stop: ' + E.Message;
        finally fLock.Leave end;
        raise;
      end;
    end;
  finally
    // Also covers a teardown exception: no destroyed context can remain ready.
    if fLock <> nil then
    begin
      fLock.Enter;
      try fState := aisStopped finally fLock.Leave end;
    end;
  end;
end;
destructor TKMAudioSession.Destroy;
begin
  try Stop;
  finally fBackend.Free; fLock.Free; inherited end;
end;
end.
