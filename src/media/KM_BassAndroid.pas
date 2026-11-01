unit KM_BassAndroid;
{$I KaM_Remake.inc}
interface
// Narrow C ABI binding for the symbols actually used by KM_Music.
// The proprietary Android ARM64 libbass.so is NOT bundled in this repository.
const
  BASS_OK = 0;
  BASS_CONFIG_DEV_DEFAULT = 36;
  BASS_STREAM_AUTOFREE = $40000;
  BASS_ATTRIB_VOL = 2;
  BASS_ACTIVE_STOPPED = 0;
var
  BASS_GetVersion: function: LongWord; cdecl;
  BASS_SetConfig: function(option, value: LongWord): LongBool; cdecl;
  BASS_Init: function(device: LongInt; freq, flags: LongWord; win, clsid: Pointer): LongBool; cdecl;
  BASS_Stop: function: LongBool; cdecl;
  BASS_Free: function: LongBool; cdecl;
  BASS_StreamFree: function(handle: LongWord): LongBool; cdecl;
  BASS_ChannelStop: function(handle: LongWord): LongBool; cdecl;
  BASS_ChannelPause: function(handle: LongWord): LongBool; cdecl;
  BASS_ChannelPlay: function(handle: LongWord; restart: LongBool): LongBool; cdecl;
  BASS_StreamCreateFile: function(mem: LongBool; data: Pointer; offset, length: QWord; flags: LongWord): LongWord; cdecl;
  BASS_ErrorGetCode: function: LongInt; cdecl;
  BASS_ChannelSetAttribute: function(handle, attrib: LongWord; value: Single): LongBool; cdecl;
  BASS_ChannelGetAttribute: function(handle, attrib: LongWord; var value: Single): LongBool; cdecl;
  BASS_ChannelSlideAttribute: function(handle, attrib: LongWord; value: Single; time: LongWord): LongBool; cdecl;
  BASS_ChannelIsActive: function(handle: LongWord): LongWord; cdecl;
procedure RequireAndroidBass;
function AndroidBassAvailable: Boolean;
implementation
uses Dynlibs, SysUtils;
var LibraryHandle: TLibHandle;
function AndroidBassAvailable: Boolean;
begin Result := LibraryHandle <> NilHandle end;
procedure RequireAndroidBass;
var handle: TLibHandle;
  function Symbol(const name: AnsiString): Pointer;
  begin
    Result := GetProcedureAddress(handle, PAnsiChar(name));
    if Result = nil then raise Exception.Create('Android libbass.so missing symbol ' + string(name));
  end;
begin
  if AndroidBassAvailable then Exit;
  handle := LoadLibrary('libbass.so');
  if handle = NilHandle then
    raise Exception.Create('Android music requires a licensed ARM64 libbass.so: ' + GetLoadErrorStr);
  try
    PPointer(@BASS_GetVersion)^ := Symbol('BASS_GetVersion');
    PPointer(@BASS_SetConfig)^ := Symbol('BASS_SetConfig');
    PPointer(@BASS_Init)^ := Symbol('BASS_Init');
    PPointer(@BASS_Stop)^ := Symbol('BASS_Stop');
    PPointer(@BASS_Free)^ := Symbol('BASS_Free');
    PPointer(@BASS_StreamFree)^ := Symbol('BASS_StreamFree');
    PPointer(@BASS_ChannelStop)^ := Symbol('BASS_ChannelStop');
    PPointer(@BASS_ChannelPause)^ := Symbol('BASS_ChannelPause');
    PPointer(@BASS_ChannelPlay)^ := Symbol('BASS_ChannelPlay');
    PPointer(@BASS_StreamCreateFile)^ := Symbol('BASS_StreamCreateFile');
    PPointer(@BASS_ErrorGetCode)^ := Symbol('BASS_ErrorGetCode');
    PPointer(@BASS_ChannelSetAttribute)^ := Symbol('BASS_ChannelSetAttribute');
    PPointer(@BASS_ChannelGetAttribute)^ := Symbol('BASS_ChannelGetAttribute');
    PPointer(@BASS_ChannelSlideAttribute)^ := Symbol('BASS_ChannelSlideAttribute');
    PPointer(@BASS_ChannelIsActive)^ := Symbol('BASS_ChannelIsActive');
    if (BASS_GetVersion() shr 16) <> $0204 then raise Exception.Create('Android BASS 2.4 required');
    LibraryHandle := handle;
  except
    PPointer(@BASS_GetVersion)^ := nil;
    PPointer(@BASS_SetConfig)^ := nil;
    PPointer(@BASS_Init)^ := nil;
    PPointer(@BASS_Stop)^ := nil;
    PPointer(@BASS_Free)^ := nil;
    PPointer(@BASS_StreamFree)^ := nil;
    PPointer(@BASS_ChannelStop)^ := nil;
    PPointer(@BASS_ChannelPause)^ := nil;
    PPointer(@BASS_ChannelPlay)^ := nil;
    PPointer(@BASS_StreamCreateFile)^ := nil;
    PPointer(@BASS_ErrorGetCode)^ := nil;
    PPointer(@BASS_ChannelSetAttribute)^ := nil;
    PPointer(@BASS_ChannelGetAttribute)^ := nil;
    PPointer(@BASS_ChannelSlideAttribute)^ := nil;
    PPointer(@BASS_ChannelIsActive)^ := nil;
    UnloadLibrary(handle);
    raise;
  end;
end;
finalization
  if LibraryHandle <> NilHandle then UnloadLibrary(LibraryHandle);
end.
