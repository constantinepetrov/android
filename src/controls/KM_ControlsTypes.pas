unit KM_ControlsTypes;
{$I KaM_Remake.inc}
interface


type
  {$IFDEF ANDROID}
  // The game controls consume button identity, not an LCL widget. Keep the
  // same mouse-button values for the Android input adapter.
  TMouseButton = (mbLeft, mbRight, mbMiddle, mbExtra1, mbExtra2);
  {$ENDIF}

  TKMAllowedChars = (
    acDigits,   // Only 0..9 digits, for numeric input
    acHex,      // Only 0..9 A..F a..f, for input hex values (colors)
    acANSI7,    // #33..#123,#125,#126 - only basic latin chars and symbols for user nickname, except |
    acFileName, // Exclude symbols that can't be used in filenames
    acText,     // Anything is allowed except for eol symbol
    acAll       // Anything is allowed
  );

const
  CTRL_HIGHLIGHT_COEF_DEF = 0.4;


implementation


end.
