# Browser version: research notes (2026-10-30)

Status (2026-10-31): Ruffle spike run (findings 6.56). The game runs in Ruffle far enough to settle the big
unknowns: AVM2 runs the 20 MB game, Starling/Stage3D draws (loading screen, the error popup with text and images),
all game data (ace/AMF) loads, all managers start. It stops at startup step 10 of 28, the content package check,
because Ruffle's `flash.filesystem.File` is a stub (never finds or writes files). Next: a web variant of the
platform glue (below), starting with content packages loaded by URL instead of unzipped to app storage.
Run it: `build_release.py --host 127.0.0.1:8090`, `python tools/web_spike.py`, open http://127.0.0.1:8090/
(Ruffle in work/ruffle/, nightly 2026-10-31 self-hosted web build).

## What the game is made of

- One SWF (`MobileGame.swf`, ~20 MB after our patches): AS3 game code on Starling (GPU 2D via Stage3D/AGAL) and
  Feathers UI. 2929 classes, 457 import `starling.*`, 15 import `flash.display3D` [VERIFIED counts].
- Runs inside Adobe AIR (captive runtime in the APK). Browsers dropped the Flash plugin (2020), so the SWF cannot
  run natively in any browser.
- AIR-only APIs the game uses [VERIFIED import counts]:
  - `flash.filesystem` (File/FileStream): 14 files. Content packages are unzipped to app storage and read from
    `File.applicationStorageDirectory` (ExternalFileControllerImpl, CardLoadingUtil, StoryMap, our Loader patch).
  - `flash.media.StageWebView`: 4 files (login and invite dialogs).
  - `flash.desktop.NativeApplication`: 11 files (exit, idle mode, invoke events, activate/deactivate).
  - `flash.net.SharedObject`: 6 files (Facebook token cache, settings). Works in Flash/Ruffle too.
  - Native extensions (billing, push, Flurry, RateBox): already stubs; a web build would use the AS3 default
    implementations or no-op stand-ins.
- Network: plain HTTP AMF3 to `/facebook/proxy.html`; works from a browser on the same origin (crossdomain.xml
  already served).

## Options

### A. Ruffle (Flash Player re-implementation in Rust/WebAssembly), most promising
- Runs the SWF itself in the browser: no rewrite of game logic or UI.
- Needs a "web build" of the SWF (same patch pipeline, tools/as3_patches.py) that replaces the AIR-only parts:
  - file storage → in-memory/IndexedDB-backed store; content packages fetched by URL instead of unzipped to disk
    (the Loader already accepts http URLs, Loader.BuildURL);
  - StageWebView login → a browser popup/redirect (the login page already exists on the server);
  - NativeApplication calls → no-ops;
  - saves stay in SharedObject (Ruffle stores them in localStorage) plus the existing online save.
- Big unknowns, to be tested first (a one-day spike):
  - Stage3D/AGAL support in Ruffle (Starling draws everything through it). Ruffle has partial Stage3D support via
    wgpu; whether Starling's shaders and texture formats work is unknown.
  - AS3/AVM2 completeness for a 20 MB commercial game (Feathers, Starling, deng.fzip, AMF serialization with
    registerClassAlias).
  - Performance on phones/low-end PCs.
- Needs network/software: downloading Ruffle (self-hosted build, MIT/Apache licensed). Ask before downloading.

### B. Stream the real Android app (server-side emulation)
- Run the unchanged x86_64 APK in Android containers on the server, stream video + input to the browser
  (WebRTC; e.g. ws-scrcpy, redroid/Anbox-style containers).
- Pros: zero game changes, identical behaviour.
- Cons: roughly 1 CPU core + 1–2 GB RAM per concurrent player, GPU encoding helps; input latency; bandwidth.
  Realistic only for a handful of simultaneous players on one server.

### C. Port to HTML5 (OpenFL/Haxe or a new engine)
- Full rewrite of rendering/UI glue; months of work. Only if A fails and B is too expensive.

### D. Desktop build (not a browser, cheap)
- Same SWF packaged with the AIR SDK for Windows/macOS (ADT `-target bundle`), with desktop stub ANEs.
  A few days of work; useful even if A works (players without Android).

## Recommendation / next step
1. When the APK feature work is done: a Ruffle spike. Load MobileGame.swf in a local Ruffle page with the server
   on the same origin, see how far startup gets (engine init, Starling context, login screen).
2. If it reaches the login screen: build the web variant (storage/login/NativeApplication replacements, served at
   /webgame by server.py with the game data and content packages).
3. If Stage3D is the blocker: decide between B (few players) and D (desktop) as interim options.

## Interactions with other planned work
- Everything we add to the APK through tools/as3_patches.py and game data (packs, world maps, profile, friends,
  collection menus) carries over to a Ruffle build automatically; only platform glue differs.
- The version gate needs a web client version (`v=`/`d=`) like the APK; the web build would report its own.
- Live PvP over HTTP polling works the same in a browser.
