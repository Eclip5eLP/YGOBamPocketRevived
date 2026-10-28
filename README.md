# Yugioh BAM Pocket Revived

A free, fan-run revival of **Yu-Gi-Oh! BAM Pocket**, the Android card game by Konami and Frima Studio that
was shut down on September 9 2016. The original game is repackaged for modern Android phones and talks to a
new community server instead of Konami's servers and Facebook. Not affiliated with Konami.

## How to play

1. Download the latest `YugiohBAMPocketRevived-*.apk` from
   [Releases](https://github.com/Eclip5eLP/YGOBamPocketRevived/releases).
2. Install it. Android asks you to allow installing apps from your browser or file manager.
   - Needs a 64-bit Android phone (arm64). Tested on a Pixel 10 with Android 17.
   - If you still have the original Konami app installed, uninstall it first: both use the same app id.
3. Open the game. On the first start it downloads about 85 MB of game content.
4. Tap **LOG IN** and create an account on the login page (username + password). You return to the game
   automatically. Your browser remembers you, so logging in later is one tap.
   - **PLAY OFFLINE** also works: story mode, deck building, shop and crafting need no account.

**What works**
- Story mode, deck editing, shop, crafting, objectives.
- Online save: your game is stored on the server and can be restored on a new phone (SYNC dialog).
- Friends: add players from *Add Friends* (both players invite each other), friend duels against their
  decks, friend help in duels.
- Arena: daily opponents (friends first), win streak bonuses, statistics, weekly and all-time leaderboards.
- Teams: join one of the 20 teams, earn team score in the Arena.
- Tournament: sign up and leaderboards.
- All purchases are free, including BAM Pro. No real money can ever be charged: the build contains no
  payment code.

**Not yet**
- Live duels against other players (real-time PvP) and tournament matches, which are live duels.
- Weekly team reward payouts.

New friends show up after restarting the game (the game loads its friend list at login).

---

## Building the APK

You only need this if you want to build the APK yourself, for example for your own server. The build uses
only the official HARMAN AIR SDK packager (ADT); no runtime files are hand-patched.

### Prerequisites

| What | Where it goes | Notes |
|---|---|---|
| Original game APK, v1.11.2 (`air.com.konami.ygo`) | `input/ygo.apk` | Not included; you must supply your own copy. |
| HARMAN AIR SDK **51.5.1.1** | `work/airsdk/` (so `work/airsdk/bin/adt` exists) | Download from [airsdk.harman.com](https://airsdk.harman.com/) and accept its license yourself. |
| JPEXS FFDec (CLI) | `tools/ffdec/ffdec-cli.jar` | [github.com/jindrapetrik/jpexs-decompiler](https://github.com/jindrapetrik/jpexs-decompiler) releases. |
| JDK 11+ (`java`, `javac`, `jar` on PATH) | | Tested with OpenJDK 21. |
| Python 3.10+ | | Standard library only. |

### Build

```bash
python tools/build_release.py --host ygo.eclip5e.com
```

This runs the whole pipeline:
1. `tools/build_stub_anes.py`: stub native extensions.
2. `tools/patch_swf.py`: game code patches.
3. `tools/build_game_adt.py`: server address, app descriptor, assets, signing.

The APK lands in `work/release/YugiohBAMPocketRevived.apk`. `--host` is the server the APK connects to
(plain HTTP, port 80).

Without `--keystore` the APK is signed with a throwaway development key. For a build you hand out, create
your own signing key once, keep it safe (every update must be signed with the same key) and pass it in:

```bash
work/airsdk/bin/adt -certificate -cn "Yugioh BAM Pocket Revived" -validityPeriod 30 2048-RSA work/release.p12 <password>
YGO_KEYSTORE_PASS=<password> python tools/build_release.py --host <your host> --keystore work/release.p12
```

On Windows use `work\airsdk\bin\adt.bat` and set the variable with `set YGO_KEYSTORE_PASS=...`.

The APK also carries the server's RSA public key (`server/data/publickey.xml`). It must match the private key
of the server you point it at (see below).

---

## Hosting your own server

The server (`server/`) is plain Python 3.10+ with no dependencies. It serves the game protocol, the 26 game
content packages, the login page and every online feature. Player data lives in `server/data/` as JSON files.

### 1. Game content

The server needs the game's downloaded content: the `Local Store` folder of an Android install that had
all extra content downloaded. Put it at:

```
input/data/data/air.com.konami.ygo/com.konami.ygo/Local Store/
    versionning.xml
    asset/...
```

This content is not included in the repository. Use `--input-dir` (or `LOCAL_STORE` for `deploy/run.sh`) for
another location. The packages are zipped on first request and cached in `work/package_cache/`.

### 2. Login key

```bash
python tools/gen_rsa_key.py --force
```

This creates `server/data/rsa_private.json` (secret, stays on the server) and `server/data/publickey.xml`.
Build your APK *after* this step, so it contains your public key.

### 3. Run

```bash
PUBLIC_HOST=ygo.example.com bash deploy/run.sh
```

The server listens on port 8087. The game only speaks plain HTTP on port 80, so put the server behind
something that maps `http://<PUBLIC_HOST>:80` to it, for example a Cloudflare Tunnel or a reverse proxy.
Important:
- **No HTTPS redirect** for this host. The game cannot follow `http → https` redirects; with Cloudflare, turn
  off *Always Use HTTPS* and *Automatic HTTPS Rewrites* for the host.
- Don't let bot or browser checks challenge `/facebook/*` and `/external_asset/*`: the game is not a browser.

`deploy/ygo-revival.service` is a systemd template for running it as a service.

### 4. Check it

```bash
curl http://ygo.example.com/                              # "Yugioh BAM Pocket Revived server OK"
python tests/live_check.py --base http://ygo.example.com  # protocol round trip
```

### Notes

- The server reloads itself when a file in `server/` changes and still compiles. Logged-in sessions survive
  restarts.
- Optional log endpoint: set `YGO_LOG_TOKEN` in the environment, then `GET /_logs?n=200` with header
  `X-Log-Token: <token>` returns the log tail. Without the variable the endpoint does not exist.
- Back up `server/data/`: it holds accounts (salted PBKDF2 password hashes), saves, friends and scores.

---

## Development

```bash
python server/server.py                       # local server on 127.0.0.1:8087
python tests/test_login_flow.py               # each test registers fresh accounts on the running server
python tests/test_friends.py
python tests/test_arena.py
python tests/test_teams.py
python tests/test_amf_requests.py             # starts its own server
python tests/simulate_install.py              # full content download, needs the game content
```

Testing on a phone without a public server: build with `--host 127.0.0.1` and run
`adb reverse tcp:80 tcp:8087`; the phone then reaches the local server over USB.
`tools/device_run.py` installs, launches and captures logcat and a screenshot.

---

## How it works

The detailed research log, with code references for every claim, is in [`notes/findings.md`](notes/findings.md).
In short:

### The original game
- An Adobe AIR (ActionScript 3) app, version 1.11.2. All game logic is in `MobileGame.swf`; card data and
  texts are zlib-compressed AMF files (`config/ace/*.ace`).
- **Protocol**:
  - Every request is an HTTP POST of `zlib(writeUTF(ExternalId) + AMF3 array of request objects)` to
    `/facebook/proxy.html`.
  - Responses are a 4-byte return code followed by a zlib-compressed AMF3 array.
  - Every object in a response array is delivered to its listener, so the server can also push messages
    (notifications).
- **Login**:
  - Originally Facebook only. The game logs into Facebook, then sends `LoginRequest{token, name, password}`
    with the Facebook id and access token, RSA-encrypted with `config/publickey.xml`.
  - A second login on the PvP connection uses `"-1_" + id` and a fixed password.
- **Content**: 26 zip packages listed in `versionning.xml`, downloaded from the content server on the
  first start.

### What we changed in the APK
- **Packaging**:
  - Repackaged with the official HARMAN AIR SDK 51.5.1.1 (`-target apk-captive-runtime -arch armv8`).
    Earlier attempts to transplant a modern AIR runtime into the old APK by hand all crashed at startup.
  - Descriptor:
    - namespace 51.1, so the game may draw under the camera cutout (`displayCutoutMode shortEdges`);
      otherwise one side was cut off;
    - targetSdk 28 (Android refuses apps targeting 16);
    - cleartext HTTP allowed;
    - push-notification components and the Google Play billing permission removed;
    - app name changed.
- **Stub native extensions**: the four native extensions (Flurry analytics, Pushwoosh, RateBox, Android
  in-app billing) are replaced by small Java stubs.
  - Without them, startup hung, because the game's code throws when an extension is missing.
  - The billing stub is a local emulator: every purchase succeeds instantly and for free, and there is no
    Google Play code in the APK.
- **Game code** (`tools/patch_swf.py`; byte patches of identical length plus two inserted snippets):
  - Purchases no longer require a login: `BamProPopup.PurchaseBamPro`, `CurrencyPopup.OnPurchaseProduct`,
    `BamProHandlerImpl.GateBamPro`.
  - Every purchase takes the direct store path (`AppPurchaseHandlerImpl.PurchaseProduct`); otherwise
    purchases hung waiting for a server check that never comes offline.
  - Store products are loaded at startup even offline (`MobileProjectEngine.LoadAppPurchaseData`), so prices
    show "Free" and the first tap buys.
  - A "Purchase complete." popup after each purchase (`AppPurchaseHandlerImpl.OnPurchaseComplete`).
  - The saved login is kept when the account check fails because of the network
    (`FacebookManagerMobile.OnInitFacebookComplete`). Originally any failure, even a dropped connection,
    logged the player out.
  - Facebook addresses (Graph API, OAuth login, dialogs, logout) point to the revival server's `/fb/`
    instead of facebook.com.
- **Data files**:
  - `mmog.xml` points at the revival server.
  - `publickey.xml` is replaced with our own RSA key.
  - The BAM Pro price text reads "FREE OF CHARGE!".

### The server
- **`server/server.py`**: HTTP server for the AMF gateway, content packages, the version manifest,
  `closepopupconfig.xml` (the startup popup text) and `crossdomain.xml`.
- **`server/fakefb.py`**: a minimal stand-in for the few Facebook endpoints the game uses. Nothing is sent to
  Facebook.
  - The login page creates and checks accounts and hands the game an access token through the
    `fb145583478967400://authorize` link.
  - `/me` and `/<id>` return the player.
  - The FQL friend query returns your friends as "app users" and other players as people to invite.
  - The invite dialog turns invites into friend requests.
- **`server/game.py`**: login (RSA key, sessions linked across the main and PvP connections), online save,
  friend duels (opponent deck from the friend's arena deck or save), relations and friend help.
- **`server/arena.py`**: daily opponents, scoring of 50 × the win-streak multiplier (1–16), statistics and
  leaderboards. The original server rules are unknown; these are ours.
- **`server/teams.py`**: teams, team scores, tournament sign-up and leaderboards.
- **`server/accounts.py`**: accounts, tokens, friends and per-player data on disk.

---

## License

The tooling and server code in this repository are released under the [MIT License](LICENSE). The license
covers only this project's own code, not the game or its assets (see the disclaimer below).

## Disclaimer

Yu-Gi-Oh! and Yu-Gi-Oh! BAM Pocket are trademarks of their respective owners (Kazuki Takahashi, Konami
and Frima Studio). I do not own the game, its code, its artwork or any of its assets, and I claim no rights
to them. This project only patches the original game so it can be played again after the official service
ended, for the purpose of game preservation. It is a non-commercial fan project, not affiliated with or
endorsed by Konami or Frima Studio; nothing is sold, and all in-game purchases are free.

The repository contains only original tooling and server code, not the game's files. If you are a rights
holder and want something removed, please open an issue.

*By Eclip5e*
