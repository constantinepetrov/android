program window_settings_probe;
{$mode delphi}
{$codepage utf8}
uses SysUtils, KM_MainSettings, KM_WindowParams, KM_WindowTypes, KM_IoXML, KM_Defaults, KM_Points;
procedure Check(ok: Boolean; const msg: string);
begin if not ok then raise Exception.Create(msg) end;
procedure Fixture(const name: string; state,position,width,height: Integer; reset: Boolean; fixed: Boolean = False);
var d,reloaded: TKMXmlDocument; s: TKMainSettings; w: TKMXmlNode; saved: string;
begin
  d:=TKMXmlDocument.Create; s:=TKMainSettings.Create(1280,900); reloaded:=TKMXmlDocument.Create;
  try
    d.LoadFromFile(IncludeTrailingPathDelimiter(ParamStr(1))+name+'.xml');
    s.Root:=d.Root; s.LoadFromXML;
    Check(WindowStateToXMLCode(s.WindowParams.State)=state,name+' state');
    Check(WindowPositionToXMLCode(s.WindowParams.Position)=position,name+' position');
    Check(s.WindowParams.NeedResetToDefaults=reset,name+' reset');
    Check(s.WindowParams.FixedPosition=fixed,name+' fixed');
    Check((s.WindowParams.Width=width) and (s.WindowParams.Height=height),name+' size');
    d.Root.AddOrFindChild('Main').Attributes['Obsolete'] := 'remove';
    d.Root.FindNode('Main').AddChild('Obsolete');
    d.Root.AddOrFindChild('Other').Attributes['Label'] := 'KaM Ж & < >';
    s.SaveToXML; saved:=d.Text; reloaded.Text:=saved;
    Check(not reloaded.Root.FindNode('Main').HasAttribute('Obsolete'),'Clear retained obsolete attribute');
    Check(not reloaded.Root.FindNode('Main').HasChild('Obsolete'),'Clear retained obsolete child');
    Check(reloaded.Root.FindNode('Other').Attributes['Label'].AsString='KaM Ж & < >','UTF8/escaping or unrelated section damaged');
    Check(reloaded.Root.ChildsCount=2,'element child count includes whitespace');
    Check(reloaded.Root.Childs[1].Attributes['Label'].AsString='KaM Ж & < >','element child indexing');
    w:=reloaded.Root.FindNode('Main').FindNode('Window');
    Check(w.Attributes['State'].AsInteger(-1)=state,name+' saved state');
    Check(w.Attributes['Position'].AsInteger(-1)=position,name+' saved position');
    Check(w.Attributes['Width'].AsInteger(-1)=width,name+' saved width');
    Check(w.Attributes['Height'].AsInteger(-1)=height,name+' saved height');
    Check(w.Attributes['FixedPosition'].AsBoolean= fixed,name+' saved fixed');
    s.Root:=reloaded.Root; s.LoadFromXML;
    Check(WindowStateToXMLCode(s.WindowParams.State)=state,name+' second load state');
    if name='malformed' then Check((s.WindowParams.Left=-1) and (s.WindowParams.Top=-1),'bad coordinate defaults');
    WriteLn('PASS XML ',name,' state=',state,' position=',position);
  finally s.Free; d.Free; reloaded.Free end;
end;
procedure Model;
var p: TKMWindowParams; r: TKMWindowParamsRecord; monitors: TKMPointArray;
begin
  p:=TKMWindowParams.Create;
  try
    r.Width:=1;r.Height:=1;r.Left:=30;r.Top:=40;r.State:=kwsMaximized;r.Position:=kwpScreenCenter;
    p.ApplyWindowParams(r,True);
    Check((p.Width=RESOLUTION_WIDTH_MIN) and (p.Height=RESOLUTION_HEIGHT_MIN),'minimum sizes');
    Check(p.IsChanged and p.NeedResetToDefaults,'apply flags');
    p.FixedPosition:=True; r.Position:=kwpDesktopCenter; p.ApplyWindowParams(r);
    Check(p.Position=kwpScreenCenter,'fixed position changed');
    Check(not p.NeedResetToDefaults,'apply defaults flag');
    p.LockParams; r.Width:=1600;r.Height:=1000;r.Left:=100;r.Top:=200;r.State:=kwsNormal;
    p.ApplyWindowParams(r,True);
    Check((p.Width=RESOLUTION_WIDTH_MIN) and (p.Left=30) and (p.Top=40) and (p.State=kwsMaximized) and not p.NeedResetToDefaults,'lock changed params');
    p.UnlockParams;p.FixedPosition:=False;p.ApplyWindowParams(r);
    Check((p.Width=1600) and (p.Height=1000) and (p.Position=kwpDesktopCenter) and (p.State=kwsNormal),'unlock/fixed release');
    SetLength(monitors,1); monitors[0]:=TKMPoint.New(1920,1080);
    Check(p.IsValid(monitors),'valid window rejected');
    p.State:=kwsMinimized;Check(not p.IsValid(monitors),'minimized accepted');
    p.State:=kwsFullScreen;Check(not p.IsValid(monitors),'fullscreen accepted as custom window');
    p.State:=kwsNormal;p.Left:=1900;Check(not p.IsValid(monitors),'offscreen accepted');
  finally p.Free end;
  WriteLn('PASS real window model LockParams FixedPosition minimum sizes validity');
end;
var state,position,normalized: Integer;
begin
  DBG_SKIP_WRITING_TO_DISK:=False;SKIP_SETTINGS_SAVE:=False;
  for state:=0 to 2 do
    for position:=0 to 7 do
    begin
      normalized:=state;if state=1 then normalized:=0;
      Fixture(Format('legacy-%d-%d',[state,position]),normalized,position,1200,800,False,True);
    end;
  Fixture('negative',0,0,RESOLUTION_WIDTH_MIN,RESOLUTION_HEIGHT_MIN,False);
  Fixture('high',2,7,1200,800,False);
  Fixture('extensions',2,7,1200,800,False);
  Fixture('no-main',0,0,0,0,True);
  Fixture('malformed',0,4,1280,900,False);
  Fixture('defaults',0,4,1280,900,False);
  Fixture('missing-left',0,0,0,0,True);
  Fixture('missing-top',0,0,0,0,True);
  Fixture('empty',0,0,0,0,True);
  Model;
  WriteLn('WINDOW_SETTINGS_XML_OK 33 fixtures; minimized normalized before save; actual LoadFromXML/SaveToXML');
end.
