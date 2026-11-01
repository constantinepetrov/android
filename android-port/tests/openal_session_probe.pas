program openal_session_probe;
{$mode delphi}
uses cthreads, SysUtils, OpenAL, KM_AudioSession, KM_OpenALBackend;
var S: TKMAudioSession; deadline: QWord;
begin
  WriteLn('Handle bytes: THandle=',SizeOf(THandle),' OpenAL=',SizeOf(TOpenALLibraryHandle),' pointer=',SizeOf(Pointer));
  if SizeOf(TOpenALLibraryHandle)<>SizeOf(Pointer) then raise Exception.Create('Truncated loader handle');
  S:=TKMAudioSession.Create(TKMOpenALBackend.Create,3);
  try
    deadline:=GetTickCount64+5000;
    while (S.State=aisStarting) and (GetTickCount64<deadline) do Sleep(1);
    if S.State<>aisReady then raise Exception.Create('Init failed: '+S.ErrorText);
    if alcGetCurrentContext<>nil then raise Exception.Create('Worker did not release context');
    if not S.Activate then raise Exception.Create('Playback thread could not bind context');
    if (alcGetCurrentContext=nil) or (S.Source(2)=0) or (S.Buffer(2)=0) then
      raise Exception.Create('Missing context or audio objects');
    if alGetError<>AL_NO_ERROR then raise Exception.Create('OpenAL object creation error');
    S.Stop;
    if alcGetCurrentContext<>nil then raise Exception.Create('Context not released on stop');
  finally S.Free end;
  WriteLn('PASS real Linux OpenAL Soft null backend: init, context transfer, objects, teardown (NOT Android runtime)');
end.
