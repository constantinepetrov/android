unit KM_TerrainSelection;
{$I KaM_Remake.inc}
interface
uses
  {$IFDEF FPC} Classes, Math, {$ELSE} System.Classes, System.Math, {$ENDIF}
  {$IFDEF ANDROID} KM_Clipboard, {$ELSE} Vcl.Clipbrd, {$ENDIF}
  {$IFDEF MSWindows} Winapi.Windows, {$ENDIF}
  KromUtils,
  KM_CommonClasses, KM_Points, KM_Terrain, KM_TerrainTypes, KM_TerrainPainter, KM_RenderPool, KM_ResTilesetTypes,
  KM_MapEdTypes, KM_Defaults;


type
  TKMSelectionEdit = (seNone, seNewRect, seResizeX1, seResizeY1, seResizeX2, seResizeY2, seMove);
  TKMSelectionMode = (smSelecting, smPasting);

  //* Flip axis
  TKMFlipAxis = (faHorizontal, faVertical);

  TKMBufferData = record
                    BaseLayer: TKMTerrainLayer;
                    LayersCnt: Byte;
                    Layer: array [0..2] of TKMTerrainLayer;
                    Height: Byte;
                    Obj: Byte;
                    IsCustom: Boolean;
                    BlendingLvl: Byte;
                    TerKind: TKMTerrainKind; //Used for brushes
                    TileOverlay: TKMTileOverlay;
                    TileOwner: TKMHandID;
                    FieldAge: Byte;
                    CornOrWine: Byte; //Indicate Corn or Wine field placed on the tile (without altering terrain)
                    CornOrWineTerrain: Byte; //We use fake terrain for maped to be able delete or alter it if needed
                  end;

  TKMSelection = class
  private class var
    CF_MAPDATA: Word; // Our own custom clipboard format
  private
    fTerrainPainter: TKMTerrainPainter;
    fSelectionEdit: TKMSelectionEdit;
    fSelPrevX, fSelPrevY: Integer;

    fPasteTypes: TKMTerrainSelectionPasteTypeSet;
    fSelectionRectF: TKMRectF; //Cursor selection bounds (can have inverted bounds)
    fSelectionRect: TKMRect; //Tile-space selection, at least 1 tile
    fSelectionMode: TKMSelectionMode;
    fSelectionBuffer: array of array of TKMBufferData;
    fLandTemp: TKMLand;
    fLandMapEdTemp: TKMMapEdLand;
    fLandTerKindTemp: TKMLandTerKind;
    fLastTiles : array[0..MAX_MAP_SIZE - 1,0..MAX_MAP_SIZE - 1] of Integer;

    function CheckTilesAround(const aX, aY, aTile: Integer): Boolean;

    procedure TileToBuffer(const aTile: TKMTerrainTile; const aMapEdTile: TKMMapEdTerrainTile;
                           const aPaintedTile: TKMPainterTile; var aBuffer: TKMBufferData);
    procedure BufferToTile(const aLandLoc: TKMPoint;
                           var aTile: TKMTerrainTile; var aMapEdTile: TKMMapEdTerrainTile;
                           var aPaintedTile: TKMPainterTile; const aBuffer: TKMBufferData);
    procedure Selection_SyncCellRect;
    procedure CopyBufferToTempLand(aUpdateMainLand: Boolean = False; aUpdateAll: Boolean = True);
    procedure DuplicateLandToTemp;
    procedure SyncTempLand;

    procedure SetMainLands;
    procedure SetTempLands;
  public
    constructor Create(aTerrainPainter: TKMTerrainPainter);
    destructor Destroy; override;

    procedure Resize;
    procedure Start;
    function HasDataInBuffer: Boolean;
    procedure Prepare;
    procedure RefreshLand;
    procedure Cancel;
    procedure CopyLandToBuffer; //Copies the selected are into buffer
    procedure PasteBegin; //Pastes the area from buffer and lets move it with cursor
    procedure PasteApply; //Do the actual paste from buffer to terrain
    procedure PasteCancel;
    procedure Flip(aAxis: TKMFlipAxis);
    procedure IncludePasteType(aPasteType: TKMTerrainSelectionPasteType);
    procedure ExcludePasteType(aPasteType: TKMTerrainSelectionPasteType);
    procedure ChangeSelectionRectangle(aLeft, aTop, aRight, aBottom: Integer);

    procedure SetNiceCoal; //Do the actual paste from buffer to terrain

    function TileWithinPastePreview(aX, aY: Word): Boolean;
    procedure Paint(aLayer: TKMPaintLayer; const aClipRect: TKMRect);
  end;


implementation
uses
  SysUtils,
  KM_Resource, KM_ResTileset,
  KM_HandsCollection,
  KM_GameParams, KM_GameSettings,
  KM_Game, KM_Cursor, KM_RenderAux, KM_CommonUtils;

