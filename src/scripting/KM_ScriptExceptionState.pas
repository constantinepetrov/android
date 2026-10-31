unit KM_ScriptExceptionState;
{$I KaM_Remake.inc}

interface

procedure SetScriptExceptionOutsideScript(aValue: Boolean);
function GetScriptExceptionOutsideScript: Boolean;

implementation

var
  gScriptExceptionOutsideScript: Boolean;

procedure SetScriptExceptionOutsideScript(aValue: Boolean);
begin
  gScriptExceptionOutsideScript := aValue;
end;

function GetScriptExceptionOutsideScript: Boolean;
begin
  Result := gScriptExceptionOutsideScript;
end;

end.
