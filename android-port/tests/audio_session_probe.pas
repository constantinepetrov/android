program audio_session_probe;
{$mode delphi}
uses cthreads, SysUtils, Classes, SyncObjs, KM_AudioSession;
type
  TProbe = class
    Devices, Contexts, Buffers, Sources, Bound: Integer;
    Calls, FailAt: Integer;
    Freed: Boolean;
    Entered, ReleaseInit: TEvent;
    Gate: Boolean;
    constructor Create;
    destructor Destroy; override;
    function Step: Boolean;
  end;
  TBackend = class(TKMAudioBackend)
    P: TProbe;
    constructor Create(aProbe: TProbe);
    destructor Destroy; override;
    function Load: Boolean; override;
    function OpenDevice: Pointer; override;
    function CreateContext(aDevice: Pointer): Pointer; override;
    function MakeCurrent(aContext: Pointer): Boolean; override;
    function CreateBuffer(var aID: Cardinal): Boolean; override;
    function CreateSource(var aID: Cardinal): Boolean; override;
    function Setup: Boolean; override;
    procedure DeleteSource(aID: Cardinal); override;
    procedure DeleteBuffer(aID: Cardinal); override;
    procedure DestroyContext(aContext: Pointer); override;
    procedure CloseDevice(aDevice: Pointer); override;
  end;
  TDestroyer = class(TThread)
    Session: TKMAudioSession;
    Done: TEvent;
    ErrorText: string;
    constructor Create(aSession: TKMAudioSession);
    destructor Destroy; override;
    procedure Execute; override;
  end;
procedure Check(aOK: Boolean; const aMessage: string);
begin if not aOK then raise Exception.Create(aMessage) end;
constructor TProbe.Create;
begin inherited; Entered := TEvent.Create(nil,True,False,''); ReleaseInit := TEvent.Create(nil,True,False,'') end;
destructor TProbe.Destroy;
begin Entered.Free; ReleaseInit.Free; inherited end;
function TProbe.Step: Boolean;
begin Inc(Calls); Result := Calls <> FailAt end;
constructor TBackend.Create(aProbe: TProbe);
begin inherited Create; P := aProbe end;
destructor TBackend.Destroy;
begin P.Freed := True; inherited end;
function TBackend.Load: Boolean;
begin Result := P.Step end;
function TBackend.OpenDevice: Pointer;
begin
  if P.Gate then
  begin
    P.Entered.SetEvent;
    Check(P.ReleaseInit.WaitFor(5000) = wrSignaled, 'gate timed out');
  end;
  Result := nil;
  if P.Step then begin Inc(P.Devices); Result := Pointer(PtrUInt(1)) end;
end;
function TBackend.CreateContext(aDevice: Pointer): Pointer;
begin
  Check(P.Devices = 1, 'context without device'); Result := nil;
  if P.Step then begin Inc(P.Contexts); Result := Pointer(PtrUInt(2)) end;
end;
function TBackend.MakeCurrent(aContext: Pointer): Boolean;
begin
  Result := P.Step;
  if Result then
    if aContext = nil then P.Bound := 0 else begin Check(P.Contexts = 1,'bind invalid context'); P.Bound := 1 end;
end;
function TBackend.CreateBuffer(var aID: Cardinal): Boolean;
begin
  Check(P.Bound = 1,'buffer without context'); Inc(P.Buffers); aID := P.Buffers;
  Result := P.Step; // Even a failing call can have created an object.
end;
function TBackend.CreateSource(var aID: Cardinal): Boolean;
begin
  Check(P.Bound = 1,'source without context'); Inc(P.Sources); aID := P.Sources;
  Result := P.Step;
end;
function TBackend.Setup: Boolean;
begin Check(P.Bound = 1,'setup without context'); Result := P.Step end;
procedure TBackend.DeleteSource(aID: Cardinal);
begin Check((P.Bound = 1) and (aID <> 0),'invalid source deletion'); Dec(P.Sources) end;
procedure TBackend.DeleteBuffer(aID: Cardinal);
begin Check((P.Bound = 1) and (P.Sources = 0) and (aID <> 0),'buffer deleted before sources'); Dec(P.Buffers) end;
procedure TBackend.DestroyContext(aContext: Pointer);
begin Check(P.Bound = 0,'destroy current context'); Dec(P.Contexts); P.Sources := 0; P.Buffers := 0 end;
procedure TBackend.CloseDevice(aDevice: Pointer);
begin Check(P.Contexts = 0,'close before context destruction'); Dec(P.Devices) end;
constructor TDestroyer.Create(aSession: TKMAudioSession);
begin inherited Create(True); FreeOnTerminate := False; Session := aSession; Done := TEvent.Create(nil,True,False,'') end;
procedure TDestroyer.Execute;
begin try Session.Free except on E: Exception do ErrorText := E.Message end; Done.SetEvent end;
destructor TDestroyer.Destroy;
begin Done.Free; inherited end;
procedure Balanced(P: TProbe);
begin Check(P.Freed and (P.Devices=0) and (P.Contexts=0) and (P.Buffers=0) and (P.Sources=0) and (P.Bound=0),'resources leaked') end;
procedure WaitInit(S: TKMAudioSession);
var deadline: QWord;
begin
  deadline := GetTickCount64+5000;
  while (S.State=aisStarting) and (GetTickCount64 < deadline) do Sleep(1);
  Check(S.State<>aisStarting,'init timed out');
end;
procedure Success;
var P: TProbe; S: TKMAudioSession;
begin
  P := TProbe.Create;
  try
    S := TKMAudioSession.Create(TBackend.Create(P),3);
    try
      WaitInit(S); Check(S.State=aisReady,S.ErrorText);
      Check((P.Bound=0) and (P.Sources=3) and (P.Buffers=3),'readiness before complete init/detach');
      Check(S.Activate and (P.Bound=1),'playback context transfer');
      Check((S.Buffer(2)<>0) and (S.Source(2)<>0),'missing IDs');
      S.Stop; S.Stop; Check(S.State=aisStopped,'stop not idempotent');
    finally S.Free end;
    Balanced(P);
  finally P.Free end;
  WriteLn('PASS success, context transfer, source-before-buffer cleanup, repeated stop');
end;
procedure Failures;
var stage: Integer; P: TProbe; S: TKMAudioSession;
begin
  // 1 load, 2 device, 3 context, 4 bind, 5..10 objects, 11 setup, 12 detach.
  for stage:=1 to 12 do
  begin
    P := TProbe.Create;
    try
      P.FailAt:=stage; S:=TKMAudioSession.Create(TBackend.Create(P),3);
      try
        WaitInit(S); Check(S.State=aisFailed,'failure published ready');
        Check((S.ErrorText<>'') and not S.Activate,'failure not propagated');
        Check((P.Devices=0) and (P.Contexts=0) and (P.Buffers=0) and (P.Sources=0),'failure cleanup delayed');
      finally S.Free end;
      Balanced(P);
    finally P.Free end;
  end;
  WriteLn('PASS 12 intermediate failures including partial object allocation and detach failure');
end;
procedure DestroyDuringInit;
var P: TProbe; S: TKMAudioSession; D: TDestroyer;
begin
  P:=TProbe.Create;
  try
    P.Gate:=True; S:=TKMAudioSession.Create(TBackend.Create(P),3);
    Check(P.Entered.WaitFor(5000)=wrSignaled,'worker did not enter backend');
    Check(S.State=aisStarting,'premature readiness');
    D:=TDestroyer.Create(S);
    try
      D.Start;
      try
        Check(D.Done.WaitFor(50)=wrTimeout,'destructor did not join worker');
        Check(not P.Freed,'backend freed while worker active');
      finally P.ReleaseInit.SetEvent end;
      Check(D.Done.WaitFor(5000)=wrSignaled,'destructor did not finish');
      D.WaitFor; Check(D.ErrorText='',D.ErrorText); Balanced(P);
    finally P.ReleaseInit.SetEvent; D.Free end;
  finally P.Free end;
  WriteLn('PASS destruction during blocked initialization joins before releasing backend');
end;
begin
  Success; Failures; DestroyDuringInit;
  WriteLn('Audio resource ownership tests passed (controlled backend; NOT Android OpenAL runtime)');
end.
