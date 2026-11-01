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
var i: Integer; bound: Boolean;
begin
  if fContext <> nil then
  begin
    try
      bound := fBackend.MakeCurrent(fContext);
      if bound then
      begin
        // Sources retain buffer references: delete sources first.
        for i := 0 to High(fSources) do
          if fSources[i] <> 0 then fBackend.DeleteSource(fSources[i]);
        for i := 0 to High(fBuffers) do
          if fBuffers[i] <> 0 then fBackend.DeleteBuffer(fBuffers[i]);
      end;
    finally
      try fBackend.MakeCurrent(nil);
      finally
        try fBackend.DestroyContext(fContext);
        finally
          fContext := nil;
          if fDevice <> nil then
          begin
            try fBackend.CloseDevice(fDevice) finally fDevice := nil end;
          end;
        end;
      end;
    end;
    // Destroying a context also releases objects if it could not be bound.
    for i := 0 to High(fSources) do fSources[i] := 0;
    for i := 0 to High(fBuffers) do fBuffers[i] := 0;
  end
  else if fDevice <> nil then
  begin
    try fBackend.CloseDevice(fDevice) finally fDevice := nil end;
  end;
end;
function TKMAudioSession.Activate: Boolean;
begin
  fLock.Enter;
  try
    Result := fState = aisReady;
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
  if fWorker <> nil then
  begin
    fWorker.Terminate;
    fWorker.WaitFor; // No Synchronize callbacks or logger references on worker.
    FreeAndNil(fWorker);
  end;
  Cleanup;
  if fLock <> nil then
  begin
    fLock.Enter;
    try fState := aisStopped finally fLock.Leave end;
  end;
end;
destructor TKMAudioSession.Destroy;
begin
  try Stop;
  finally fBackend.Free; fLock.Free; inherited end;
end;
end.
