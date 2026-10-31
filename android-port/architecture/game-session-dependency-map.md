# Game session and UI dependency map

This is a source-level map of the original Pascal client. It is deliberately not a claim that the Android client runs a game session.

## Authoritative session path

`KM_Game.TKMGame` owns the session and the authoritative tick counter (`fParams.Tick`). Its lifecycle is:

1. `Create` allocates options, savepoint tracking, script runtime, terrain/hands/AI containers and the active desktop interface. With `aRender=nil`, the interface fields are nil; that path is documented for random-map generation and is not a supported headless game session.
2. `CreateFromScript` loads a mission using the normal map/mission loaders, creates player hands, pathfinding, input processing and script/event state.
3. `AfterStart` calls `gHands.AfterMissionInit`, seeds deterministic random state, writes the replay base save, runs `ProcMissionStart`, synchronizes the interface and viewport, and reinitializes the render pool.
4. `UpdateGame` is the frame scheduler. It accounts for speed and catch-up, then calls `PlayNextTick`.
5. `PlayNextTick` rejects paused/stopping sessions, establishes the pointer-block interval and dispatches by mode. Singleplayer/campaign uses `PlayGameTick`; multiplayer first checks received commands; replay uses `PlayReplayTick`; map editor advances editor/visual state.
6. `PlayGameTick` is the real deterministic simulation path. Before incrementing the tick it handles savepoints/autosaves; it increments `fParams.Tick`, applies planned `TKMGameInputProcess` commands, then updates scripting, terrain, AI fields, hands, spectator, pathfinding and projectiles, in that order, followed by timers and tick-boundary commands/checks. Exceptions and replay consistency checks remain part of this path.

The AI, terrain, units/houses/hands, pathfinding, projectiles, scripting and GIP modules are game state/logic. `KM_GameInputProcess` is not a view model: it stores, orders, replays and serializes game input commands. UI and scripts issue those same commands through its `Cmd...` methods. Replacing this queue or calling subsystem updates in an invented order would change replay determinism and multiplayer semantics.

## State and persistence responsibilities

- Map and terrain state are loaded through the original map loaders and held by `gTerrain`; player, unit and house state is created through `gHands` and the corresponding original entity modules.
- `TKMGameInputProcess` owns planned/stored commands and replay timers; `TKMGame.SaveGameToStream` and load methods serialize the session, command state, script state and game entities.
- The game wrapper also serializes presentation-owned state through `fGamePlayInterface.Save/Load` and `SaveMinimap/LoadMinimap`; multiplayer local save data includes a minimap. Scripted overlays/messages, selection, replay marks and menu state are also reached through the interface. Those fields cannot be discarded as “UI-only” without defining a compatible Android representation and preserving the existing save format.
- `AfterStart`, victory/defeat/hold, autosave notifications, pause, game speed, messages, replay markers and network wait states publish effects to the interface. Some callbacks are informative; others carry user decisions or serialized state and need typed request/response handling.

## Concrete desktop coupling

- `KM_Game` interface imports `KM_InterfaceGame`, `KM_InterfaceGamePlay`, and `KM_InterfaceMapEditor`; its private fields and public accessors expose the concrete interface classes. This imports UI into the session unit before implementation compilation begins.
- `KM_InterfaceGame` derives from `TKMUserInterfaceCommon` and directly uses project controls, minimap and viewport. Its own interface uses LCL `Controls` and `KM_ControlsBase`; it is not just a handful of platform constants.
- `KM_InterfaceGamePlay` builds the complete gameplay GUI from controls and GUI pages. Its interface uses `LCLIntf`, `LCLType`, `Controls`, and numerous GUI modules. It owns persistent message/minimap/replay state as well as rendering and user interaction.
- `KM_Controls` and `KM_ControlsBase` implement KaM's custom controls, but still import LCL `Controls`; their implementations additionally use `LCLIntf/LCLType` for virtual keys and mouse/key state. This is the source of the widgetset path to `WSReferences`, not a dependency of terrain/hand simulation.
- `KM_Game` implementation itself uses `LCLType`/ `Controls` and `Dialogs` for a replay-failure confirmation, in addition to desktop app/window and render-pool globals.
- `KM_Render` and `KM_RenderUI` are not presentation-neutral today: the current implementation imports `dglOpenGL` and issues fixed-function/immediate-mode calls (`glBegin`, `GL_QUADS`, matrix stack, clip planes, etc.). Removing LCL does not make that renderer usable in GLES; it needs a separate GLES renderer consuming the same game state.

## Minimum safe separation boundary

The seam belongs between the session/tick model and a typed presentation port, not between the tick and its existing simulation subsystems. It needs two explicit parts:

1. **Transient presentation effects / requests:** game message, overlay, pause/hold decision, victory/defeat, replay marker, viewport request, network status and presentation refresh. Requests that affect continuation must return an explicit typed result; they cannot be silently dropped.
2. **Persistent local presentation state:** the data currently serialized by the game UI methods (message stack/minimap/local multiplayer view/replay UI state). The contract must serialize this state using the current versioned format, or use a deliberate save-version migration. The Android and desktop adapters must round-trip identical values.

Desktop's adapter should delegate to the current `TKMGamePlayInterface`/`TKMMapEdInterface`, retaining current menus and rendering. Android's adapter should translate touch/command input into the original `TKMGameInputProcess.Cmd...` operations and publish state to an Android renderer. No empty implementation can satisfy this contract.

The current field types and consumers prevent a safe one-file conditional compile: `KM_Game`, `KM_GameInputProcess`, scripting actions, render pool and map-editor/gameplay GUI callers all expose or dereference concrete interface classes. The first implementation slice should migrate one vertical seam (session effects plus persistent UI state) to project-owned records/interfaces, retain the desktop adapter, then compile the same simulation units with the Android adapter. Only after that seam is typed and both save/load paths agree should `TKMGame` construction and a real singleplayer `PlayNextTick` harness be attempted.

## Verified boundary and next blocker

The last client compile reports in PR diagnostics must be classified by configuration. Unpatched FPC 3.2.2 Pascal Script currently fails in `InvokeCall.inc` because its code calls `Rtti.Invoke` with 4/5 arguments while FPC's API requires 6; this is separate from the controlled Android overlay. The PR's latest overlay diagnostic has progressed past that point and reports `dglOpenGL` / `TRect` in the real client dependency graph. Until the exact latest Actions log is attached, that is a reported next compile boundary, not a successful `KM_Game` compile. An Android ARM64 runtime call of `TKMGame.PlayNextTick` has not been made.

A passing fog-of-war JNI test proves the original `TKMFogOfWar` state update, not a game session. The current headless tick is blocked by the coupled construction/persistence/presentation contract above, and the full visual client is independently blocked by the fixed-function renderer. Keep these claims separate in all CI/reporting.
