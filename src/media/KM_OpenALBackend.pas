unit KM_OpenALBackend;
{$I KaM_Remake.inc}
interface
uses KM_AudioSession;
type
  TKMOpenALBackend = class(TKMAudioBackend)
  public
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
implementation
uses SysUtils, OpenAL;
procedure RestoreX87;
begin
  {$IF Defined(CPUX86) or Defined(CPUX64) or Defined(CPU386) or Defined(CPUX86_64)}
  Set8087CW($133F);
  {$IFEND}
end;
function TKMOpenALBackend.Load: Boolean;
begin
  Result := InitOpenAL;
  RestoreX87;
  if Result then
    Result := Assigned(alcOpenDevice) and Assigned(alcCreateContext)
      and Assigned(alcMakeContextCurrent) and Assigned(alGenBuffers)
      and Assigned(alGenSources) and Assigned(alGetError) and Assigned(alDistanceModel)
      and Assigned(alListenerfv) and Assigned(alSourceStop) and Assigned(alDeleteSources)
      and Assigned(alDeleteBuffers) and Assigned(alcDestroyContext) and Assigned(alcCloseDevice);
end;
function TKMOpenALBackend.OpenDevice: Pointer;
begin Result := alcOpenDevice(nil); RestoreX87 end;
function TKMOpenALBackend.CreateContext(aDevice: Pointer): Pointer;
begin Result := alcCreateContext(aDevice, nil); RestoreX87 end;
function TKMOpenALBackend.MakeCurrent(aContext: Pointer): Boolean;
begin Result := alcMakeContextCurrent(aContext); RestoreX87 end;
function TKMOpenALBackend.CreateBuffer(var aID: Cardinal): Boolean;
begin alGenBuffers(1, @aID); Result := alGetError = AL_NO_ERROR end;
function TKMOpenALBackend.CreateSource(var aID: Cardinal): Boolean;
begin alGenSources(1, @aID); Result := alGetError = AL_NO_ERROR end;
function TKMOpenALBackend.Setup: Boolean;
const orientation: array[0..5] of TALfloat = (0, 0, -1, 0, 1, 0);
begin
  alDistanceModel(AL_LINEAR_DISTANCE_CLAMPED);
  alListenerfv(AL_ORIENTATION, @orientation[0]);
  Result := alGetError = AL_NO_ERROR;
end;
procedure TKMOpenALBackend.DeleteSource(aID: Cardinal);
begin alSourceStop(aID); alDeleteSources(1, @aID) end;
procedure TKMOpenALBackend.DeleteBuffer(aID: Cardinal);
begin alDeleteBuffers(1, @aID) end;
procedure TKMOpenALBackend.DestroyContext(aContext: Pointer);
begin alcDestroyContext(aContext) end;
procedure TKMOpenALBackend.CloseDevice(aDevice: Pointer);
begin
  if not alcCloseDevice(aDevice) then raise Exception.Create('OpenAL device close failed');
end;
end.
