# Reverse Engineering Findings: Yu-Gi-Oh! BAM Pocket (Client v1.11.2)

## 1. Configuration & Key Parameters

### 1.1 `work/apk/assets/config/mmog.xml`
- **Config Loader**: `com.frimastudio.common.core.engine.Util.as:138` (`LoadConfigFile`), parsed in `Util.as:156-175` (`OnConfigLoaded`) into a 2-level dictionary `_configVar[section][name]`. Accessed via `(ManagerA.Util as IUtil).GetVar(section, varName)` (`Util.as:194-203`). [VERIFIED]
- **server (`<var name="server" value="Http"/>`)**:
  - Read by `com.frimastudio.common.core.engine.Engine.as:424` (`InitServerCom`) and `com.frimastudio.snowstorm.project.engine.MobileEngine.as:34` (`InitServerCom`).
  - Instantiates `ServerCom.GetInstance("Http")` -> returns `com.frimastudio.common.core.servercom.ServerComHTTP` (`com.frimastudio.common.core.engine.EngineServerCom.as:220`).
  - Sets connection type `mConnectionType = EProtocol.HTTP` (`EngineServerCom.as:228`). [VERIFIED]
- **serverUrl (`<var name="serverUrl" value="http://1-live-gs-ygoa.yugioh-bam.com/facebook/proxy.html"/>`)**:
  - Read by `EngineServerCom.as:247` (`Init`).
  - Configures default server host and port 80 (`EngineServerCom.as:255-256`).
  - Passed to `ServerComHTTP.as:240-263` (`Connect`), which replaces base domain with `domain:port` (i.e. `http://1-live-gs-ygoa.yugioh-bam.com:80/facebook/proxy.html`). [VERIFIED]
  - Policy file loaded: `Security.loadPolicyFile("http://1-live-gs-ygoa.yugioh-bam.com/crossdomain.xml")` (`ServerComHTTP.as:250`). [VERIFIED]
- **pvpServerUrl (`<var name="pvpServerUrl" value="http://1-live-pvp-ygoa.yugioh-bam.com/facebook/proxy.html~8080~844"/>`)**:
  - Read by `com.frimastudio.snowstorm.project.login.YGOMPvPLoginImpl.as:266` and `com.frimastudio.common.core.engine.EngineServerComPvp.as:23` via `com.frimastudio.util.serverurl.ServerURLParser.as:15-23`.
  - Parsed by splitting on `~`:
    - `ServerUrl`: `http://1-live-pvp-ygoa.yugioh-bam.com/facebook/proxy.html` [VERIFIED]
    - `ServerPort`: `8080` [VERIFIED]
    - `PolicyPort`: `844` [VERIFIED]
- **assetPath (`<var name="assetPath" value="/external_asset/android/"/>`)**:
  - Read by `com.frimastudio.snowstorm.project.externalfile.versionning.VersionControllerImpl.as:52`.
  - Base path for downloading external packages and asset manifests from CDN (`VersionControllerImpl.as:86, 259`, `ExternalFileControllerImpl.as:353`). [VERIFIED]
- **enable_encrypted_message (`<var name="enable_encrypted_message" value="true"/>`)**:
  - Read by `Engine.as:449` and `EngineServerCom.as:243`. Sets `mAllowEncryptedMessage = true`. [VERIFIED]
- **httpMessageBatching (`<var name="httpMessageBatching" value="true"/>`) & httpMaxBatchSize (`<var name="httpMaxBatchSize" value="5"/>`)**:
  - Read by `EngineServerCom.as:260-261` and passed to `ServerComHTTP.IsMessageBatchingEnable` and `ServerComHTTP.MaxBatchMessageCount`. [VERIFIED]
- **httpPoolSize (`<var name="httpPoolSize" value="1"/>`)**:
  - Read by `EngineServerCom.as:259`, creates 1 `HttpWorker` worker instance. [VERIFIED]

### 1.2 `work/apk/assets/config/publickey.xml`
- **Key Location & Loader**:
  - Read by `Engine.as:395-420` (`InitEncryption`, `OnPublicKeyLoaded`). Path `config/publickey.xml` (`Engine.as:67`).
  - Modulus & Exponent passed to `mRSAEncryption.SetPublicKey(_loc3_.Modulus, _loc3_.Exponent)` (`Engine.as:418`).
- **Key Parameters**:
  - `Modulus`: Hex string `64be7bb313e186846eb68e79c89edf0602e36607304bee06f277f3f14aa5d637ac6747e9b2687b4bf29c1e02f6d32eafe530d15c56e109125896cd7e11f10a5f` (64 bytes = 512-bit RSA). [VERIFIED]
  - `Exponent`: Hex string `010001` (65537 decimal). [VERIFIED]
- **Implementation**:
  - `com.frimastudio.as3ToolKit.security.RSAEncryption.as:31-35` uses `com.hurlant.crypto.rsa.RSAKey.parsePublicKey` (`RSAKey.as:60-63`).
  - Encryption uses PKCS#1 type 2 padding (`RSAKey.as:204-250`). [VERIFIED]

---

## 2. Request & Response Format, Serialization, and Batching

### 2.1 Transport Layer & Endpoints
- **Protocol**: HTTP 1.1 POST.
- **Client Class**: `com.frimastudio.common.core.servercom.HttpWorker.as:66-91`.
  - `URLRequest.method = URLRequestMethod.POST` (`HttpWorker.as:67`). [VERIFIED]
  - `URLRequest.contentType = "binary/octet-stream"` (`HttpWorker.as:21, 68`). [VERIFIED]
  - `URLLoader.dataFormat = URLLoaderDataFormat.BINARY` (`HttpWorker.as:71`). [VERIFIED]
- **Endpoints**:
  - Main Game Server: `http://1-live-gs-ygoa.yugioh-bam.com:80/facebook/proxy.html` [VERIFIED]
  - PvP Server: `http://1-live-pvp-ygoa.yugioh-bam.com:8080/facebook/proxy.html` [VERIFIED]
  - If request parameter string `param2` is passed: `url += "?r=" + param2;` (`HttpWorker.as:87`). [VERIFIED]

### 2.2 Client Request Serialization & Batching
- **Message Dispatch**:
  - Triggered by `MobileEngineServerCom.CallXTAMF(message)` -> `EngineServerCom.CallXTAMF(param1)` (`EngineServerCom.as:328-340`).
  - In HTTP mode (`mConnectionType == EProtocol.HTTP`), the raw object is handed directly to `mServerCom.SendData(object)` without socket framing (`EngineServerCom.as:330-338`). [VERIFIED]
- **Batching & Queueing**:
  - Handled in `com.frimastudio.common.core.servercom.ServerComHTTP.as:282-361`.
  - If a worker is available and `mPendingMessage` is empty, sent immediately (`ServerComHTTP.as:292-306`).
  - Otherwise, queued into `mPendingMessage: Vector.<Object>` (`ServerComHTTP.as:309`).
  - When a worker frees up (`SendPendingMessage`):
    - If `mIsMessageBatchingEnable == true` (configured true in `mmog.xml`), pulls up to `mMaxBatchMessageCount` (5) messages from the queue (`ServerComHTTP.as:336-348`).
    - Converts queue slice to an ActionScript `Array` and passes to `MarshallObject` (`ServerComHTTP.as:363-374`).
- **Binary Marshalling Format**:
  - Handled in `ServerComHTTP.as:376-389` (`MarshallObject`):
    ```actionscript
    var _loc2_:Array = param1 as Array;
    if(_loc2_ == null) {
       _loc2_ = [param1];
    }
    var _loc3_:ByteArray = new ByteArray();
    _loc3_.writeUTF(this.mHandler.ExternalId);
    _loc3_.writeObject(_loc2_);
    _loc3_.position = 0;
    _loc3_.compress();
    return _loc3_;
    ```
  - **Structure before compression**:
    1. `writeUTF(ExternalId)`: 2-byte unsigned short (big-endian) string length, followed by UTF-8 bytes of `ExternalId` (Facebook User ID string, or `""` if unauthenticated). [VERIFIED]
    2. `writeObject(_loc2_)`: AMF3 serialization of the `Array` of message objects. [VERIFIED]
  - **Compression**:
    - The entire resulting ByteArray is compressed using standard **zlib deflate** (`_loc3_.compress()`). [VERIFIED]

### 2.3 Server Response Deserialization
- **Handling**: `com.frimastudio.common.core.engine.EngineServerCom.as:476-545` (`OnReceivedData`).
- **Structure**:
  1. Header: 4-byte big-endian signed 32-bit integer return code (`_loc5_ = param1.readInt()`, `EngineServerCom.as:493`).
     - `_loc5_ == 0`: Success. [VERIFIED]
     - `_loc5_ != 0`: Error code returned by server; client disconnects (`EngineServerCom.as:494-499`). [VERIFIED]
  2. Body: All remaining bytes are read into `_loc2_: ByteArray`.
  3. Decompression: In HTTP mode, `_loc3_ |= FLAG_COMPRESSED` is set (`EngineServerCom.as:500`). `_loc2_.uncompress()` performs zlib inflate (`EngineServerCom.as:517-521`). [VERIFIED]
  4. AMF Parsing: `_loc4_ = _loc2_.readObject()` parses the AMF3 payload (`EngineServerCom.as:523`). [VERIFIED]
  5. Dispatch: If `_loc4_` is an `Array`, each element is dispatched to registered listeners via `BroadcastServerResponse`; if a single object, it is dispatched directly (`EngineServerCom.as:524-544`). [VERIFIED]

---

## 3. Encryption Schemes

### 3.1 RSA-512 Public Key Encryption
- **Files**:
  - `com.frimastudio.as3ToolKit.security.RSAEncryption.as:79-100` (`EncryptToBytes`).
  - `com.hurlant.crypto.rsa.RSAKey.as:60-63, 204-250`.
- **Key Source**: `work/apk/assets/config/publickey.xml`. Modulus = 512-bit hex, Exponent = 0x10001 (65537). [VERIFIED]
- **Padding**: PKCS#1 v1.5 Type 2 padding (`RSAKey.as:231-250`). [VERIFIED]
- **Usage**:
  - `com.frimastudio.snowstorm.core.player.amf.LoginRequest`:
    - `name: ByteArray` = RSA-encrypted username/Facebook UID (`BaseAuthentication.as:201`). [VERIFIED]
    - `password: ByteArray` = RSA-encrypted password/access token (`BaseAuthentication.as:202`). [VERIFIED]
  - `com.frimastudio.snowstorm.core.authentication.PvpAuthentication.as:60-61`:
    - `name` & `password` in PvP login. [VERIFIED]
  - `PlayerManager.as:313, 330, 344-346`:
    - Registration and credentials check. [VERIFIED]

### 3.2 Dynamic RC4 (ARC4) Symmetric Session Encryption
- **File**: `com.frimastudio.common.core.engine.EncryptionStrategy.as:1-125`.
- **Cipher**: ARC4 stream cipher (`com.hurlant.crypto.prng.ARC4`). [VERIFIED]
- **Session Key Generation**:
  - Client receives 32-bit signed integer `seed` from server in `GetTokenResponse.seed` (`GetTokenResponse.as:16`, `PlayerManager.as:483`). [VERIFIED]
  - Client calls `EncryptionStrategy.CreateCommunicationKey(seed)` (`BaseAuthentication.as:209`):
    - `mKeyIn` is initialized to 8 bytes: `[seed: 4 bytes int] [0: 4 bytes int]` (`EncryptionStrategy.as:62-67`). [VERIFIED]
    - `mKeyOut` copies `mKeyIn`.
- **Dynamic Per-Message Keying**:
  - For each outgoing message, the message counter is incremented (`++mMessageOutCount.Value`).
  - The last 4 bytes of `mKeyOut` are overwritten with the new counter (`EncryptionStrategy.as:93-94`).
  - `mEncryption.init(mKeyOut)` re-keys ARC4 with the 8-byte key `[seed, counter]` and encrypts in-place (`EncryptionStrategy.as:99-100`). [VERIFIED]
  - Analogous dynamic re-keying applies to decryption with `mKeyIn` and `mMessageInCount` (`EncryptionStrategy.as:106-113`). [VERIFIED]
- **HTTP vs Socket Applicability**:
  - `EngineServerCom.as:330-332` only passes messages through `SerializeSocketMessage` (which applies ARC4) when `mConnectionType != EProtocol.HTTP`. In HTTP mode, message payloads inside the HTTP POST body remain unencrypted at the transport level (only sensitive credentials inside `LoginRequest` fields are RSA-encrypted). [VERIFIED]

---

## 4. Message Sequence: App Start to Main Menu

### Phase 1: Local Engine Initialization
1. Entry point: `com.frimastudio.mobile.Main.as:46-60`.
2. `Main.InitGame` instantiates `MobileProjectEngine` (`Main.as:203`).
3. `MobileProjectEngine.Init()` populates `mInitSequence: Vector.<Step>` (`MobileProjectEngine.as:130-158`):
   - Step 1: `AddPrelauncherVisual` (displays initial loading bar).
   - Step 2: `InitEngine` (`MobileEngine.as:32-45`):
     - Loads `config/mmog.xml` (`Util.as:138`).
     - Loads `config/publickey.xml` and initializes RSA (`Engine.as:395-420`).
     - Initializes `MobileEngineServerCom` with `"Http"` (`MobileEngine.as:35-37`).
     - Initializes `MobileAuthentication` (`EngineServerCom.as:276-295`).

### Phase 2: Server Communication Initialization
4. Step 7: `InitializePvpCom` (`MobileProjectEngine.as:136, 551-556`):
   - Calls `YGOMPvPLogin.InitServerCom()` -> initializes `MobileEngineServerComPvp` with `"Http"` (`MobileEngine.as:47-53`).
5. Step 8: `InitializeServerCom` (`MobileProjectEngine.as:137, 544-549`):
   - Calls `YGOMLogin.InitServerCom()` (`YGOMLoginImpl.as:97-105`).
   - `ConnectEngine` (`YGOMLoginImpl.as:415-428`):
     - `ServerComHTTP.Connect("http://1-live-gs-ygoa.yugioh-bam.com/facebook/proxy.html", 80, 843)`.
     - Loads policy file `http://1-live-gs-ygoa.yugioh-bam.com/crossdomain.xml`.
   - `GetAppVersion` (`YGOMLoginImpl.as:430-435`):
     - Dispatches **HTTP Request #1**:
       - AMF Class: `com.frimastudio.snowstorm.project.player.amf.GetVersionRequest`
       - Payload: `compressed = true`, `encrypted = false`.
     - Expects **HTTP Response #1**:
       - AMF Class: `com.frimastudio.snowstorm.project.player.amf.GetVersionResponse`
       - Fields: `version: String` (e.g. `"android=1.11.2~ios=1.11.2"`), `cdn: String` (CDN host), `packageVersion: String`, `packageSize: String`.
     - `PlayerManagerGT.OnGetVersionResponse` (`PlayerManagerGT.as:236-252`):
       - Parses version string -> `mAppVersion = "1.11.2"`.
       - Stores CDN host -> `mPackageUrlServer = aResponse.cdn`.

### Phase 3: Game Data & Login (if cached token exists)
6. Step 9: `LoadGameData` (`MobileProjectEngine.as:138, 609-614`):
   - `YGOMData.Load()` reads local `.sav` files (`JSONSave_A.sav`, `JSONSave_B.sav`, or `PlayerInfo.sav`).
7. Step 10: `AutomatedFacebookLogin` (`MobileProjectEngine.as:139, 558-563`):
   - `YGOMLogin.AutomatedLogin()` (`YGOMLoginImpl.as:107-115`).
   - If Facebook session is cached:
     - `LoginGame`: Calls `mEngineServerCom.Login(uid, accessToken)` (`YGOMLoginImpl.as:231`).
     - Triggers `BaseAuthentication.as:109-140`:
       - Step 2 (`GetToken`):
         - **HTTP Request #2**: `com.frimastudio.snowstorm.core.player.amf.GetTokenRequest`
         - **HTTP Response #2**: `com.frimastudio.snowstorm.core.player.amf.GetTokenResponse` (`token: String`, `seed: int`).
       - Step 3 (`InitializeSecureProtocol`):
         - Key set from `seed`.
       - Step 4 (`Login`):
         - **HTTP Request #3**: `com.frimastudio.snowstorm.core.player.amf.LoginRequest`
           - `token: String`
           - `name: ByteArray` (RSA encrypted UID)
           - `password: ByteArray` (RSA encrypted access token)
         - **HTTP Response #3**: `com.frimastudio.snowstorm.core.player.amf.LoginResponse` (`playerId: int`).
       - Step 5 (`GetServerTime`):
         - Handled locally in `PlayerManagerDalMobile.DoGetServerTimeRequest` (`resp.serverTime = new Date()`).
     - `LoginPvP`: Connects to `http://1-live-pvp-ygoa.yugioh-bam.com:8080/facebook/proxy.html`, logs in with username `"-1_" + uid` and password `"frima"` (`YGOMPvPLoginImpl.as:250`).
     - Loads server save if newer via `GetPlayerSaveRequest` / `GetPlayerSaveResponse` (`YGOMDataImpl.as:470-487`).
   - If no cached session: skips to next step.

### Phase 4: Asset Validation from CDN
8. Step 11: `ValidateAssets` (`MobileProjectEngine.as:140, 565-569`):
   - `ExternalFileController.Init()` -> `VersionControllerImpl.Init()` (`VersionControllerImpl.as:70-93`).
   - **HTTP GET Request**: `http://{PackageUrlServer}/external_asset/android/versionning.xml?time={timestamp}`
   - **HTTP GET Request**: `http://{PackageUrlServer}/external_asset/android/1.11.2/versionvalidator`
   - For each missing asset package:
     - **HTTP GET Request**: `http://{PackageUrlServer}/external_asset/android/1.11.2/{package_name}.zip`

### Phase 5: Local Client Setup & Login Screen
9. Steps 12-26 (`MobileProjectEngine.as:141-155`):
   - Loads fonts, common assets, initializes avatar & inventory managers, open quick shop, sets up transitions.
10. Step 27: `StartGame` (`MobileProjectEngine.as:156, 236-241`):
    - `StarlingModuleManager.ChangeModule(EStarlingModuleDefinition.LOGIN)` (`MobileProjectEngine.as:239`).
11. `com.frimastudio.snowstorm.module.login.LoginModule.as:100-155`:
    - **HTTP GET Request**: `http://{PackageUrlServer}/closepopupconfig.xml?time={timestamp}` (`LoginModule.as:120`).
    - Creates `LoginView` UI:
      - If user is not logged in: displays "Play Offline" (`BtnOffline`) and "Login with Facebook" (`BtnLogin`).
      - If user taps "Play Offline": `ShowLoginMenu(false)` reveals menu buttons (Story, Arena, Duel, Settings) and `BtnMainMenu`.
      - If user taps `BtnMainMenu`: calls `StarlingModuleManager.ChangeModule(EStarlingModuleDefinition.MAIN_MENU)` (`LoginModule.as:287-289`), transitioning into `MainMenuModule` (`com.frimastudio.snowstorm.module.mainmenu.MainMenuModule.as`).

---

## 5. Asset Downloading Pipeline & Package Format

### 5.1 Asset Manifest: `versionning.xml`
- **Remote Manifest URL**:
  - `http://{PackageUrlServer}{assetPath}versionning.xml?time={Date.getTime()}` (`com.frimastudio.snowstorm.project.externalfile.versionning.VersionControllerImpl.as:86`). [VERIFIED]
  - Loaded via `com.frimastudio.mobile.util.FrimaLoader.LoadXML` (`VersionControllerImpl.as:87`).
  - Query parameter `?time={timestamp}` acts as a cache-buster. [VERIFIED]
- **Local Storage & Fallback Cache**:
  - Local Path: `File.applicationStorageDirectory.resolvePath("versionning.xml")` (`VersionControllerImpl.as:107, 239`). [VERIFIED]
  - Target on Android AIR: `/data/data/air.com.konami.ygo/com.konami.ygo/Local Store/versionning.xml` (present in backup files). [VERIFIED]
  - File attribute: `myFile.preventBackup = true` (`VersionControllerImpl.as:240`). [VERIFIED]
  - **Fallback Hierarchy**:
    1. In DEV, QA, or STAGING environments, the client first attempts to read `File.applicationDirectory.resolvePath("externalpackage/versionning.xml")` (`VersionControllerImpl.as:74-83`). [VERIFIED]
    2. In standard/production runs, the client fetches the manifest from the remote CDN URL (`VersionControllerImpl.as:84-88`). [VERIFIED]
    3. If remote fetch succeeds:
       - Parses the XML into memory (`VersionControllerImpl.as:101, 146-162`).
       - Overwrites the local file via `UpdateLocalVersionningFile`: writes UTF-8 bytes to `File.applicationStorageDirectory.resolvePath("versionning.xml")` (`VersionControllerImpl.as:102, 237-245`). [VERIFIED]
       - Triggers server version validation (`VersionControllerImpl.as:103`).
    4. If remote fetch fails (or `PackageUrlServer` is null):
       - Checks if local `File.applicationStorageDirectory.resolvePath("versionning.xml")` exists (`VersionControllerImpl.as:107-108`).
       - If local cache exists, parses it locally (`VersionControllerImpl.as:120-126`). [VERIFIED]
       - If neither is available, dispatches `VersionControllerEvent.INIT_FAILED` (`VersionControllerImpl.as:129`), which retries once before displaying an error popup (`ExternalFileControllerImpl.as:167-179`). [VERIFIED]

### 5.2 Manifest Structure & Target Version Resolution
- **XML Schema** (from `Local Store/versionning.xml`):
  ```xml
  <versionning>
    <latestgameversion>
      <var value="1.11.1"/>
    </latestgameversion>
    <version value="1.11.1">
      <package name="anim" version="1.1.7" uncompressedsize="15203218" compressedsize="14979328"/>
      <package name="series1" version="1.1.3" uncompressedsize="12554662" compressedsize="12426606"/>
      ...
    </version>
    <version value="1.10.1">...</version>
  </versionning>
  ```
- **Parsing Logic**:
  - `<latestgameversion><var value="..."/></latestgameversion>` sets `mLatestGameVersion` (`VersionControllerImpl.as:153-156`). [VERIFIED]
  - Each `<version value="...">` tag stores an array of `VersionnedAssetData` entries inside `mVersionData[versionId]` (`VersionControllerImpl.as:159, 164-175`):
    - `Name`: `asset.@name` (e.g. `"login"`) [VERIFIED]
    - `Version`: `asset.@version` (e.g. `"1.1.5"`) [VERIFIED]
    - `UncompressedSize`: `asset.@uncompressedsize` (bytes, e.g. `795494`) [VERIFIED]
    - `CompressedSize`: `asset.@compressedsize` (bytes, e.g. `793567`) [VERIFIED]
- **Version Resolution Hierarchy (`CurrentGameVersion` property)**:
  - Client reads its own version `mCurrentGameVersion` from `config/mmog.xml` `<client><version value="1.11.2"/></client>` (`VersionControllerImpl.as:51`). [VERIFIED]
  - `VersionControllerImpl.as:200-207` evaluates:
    ```actionscript
    public function get CurrentGameVersion() : String
    {
       if(this.IsInformationAvailableForVersion(this.mCurrentGameVersion))
       {
          return this.mCurrentGameVersion;
       }
       return this.mLatestGameVersion;
    }
    ```
  - If the client's version (`1.11.2`) exists in `versionning.xml`, it uses `1.11.2`.
  - If the client's version is NOT present in `versionning.xml` (as in the real v1.11.2 client reading the backup `versionning.xml`), it falls back to `mLatestGameVersion` (`"1.11.1"`). [VERIFIED]

### 5.3 URL Construction Schema
1. **Server Version Validator Probe**:
   - Format: `"http://" + mPlayerManager.PackageUrlServer + mExternalAssetPath + CurrentGameVersion + "/" + "versionvalidator"` (`VersionControllerImpl.as:259`). [VERIFIED]
   - Example: `http://1-live-gs-ygoa.yugioh-bam.com/external_asset/android/1.11.1/versionvalidator`
2. **Package Archive Download**:
   - Format: `"http://" + mPlayerManager.PackageUrlServer + VersionController.ExternalAssetPath + VersionController.CurrentGameVersion + "/" + aAssetToLoad.Name + ".zip"` (`ExternalFileControllerImpl.as:353`). [VERIFIED]
   - Example (UI module): `http://1-live-gs-ygoa.yugioh-bam.com/external_asset/android/1.11.1/login.zip`
   - Example (Cards): `http://1-live-gs-ygoa.yugioh-bam.com/external_asset/android/1.11.1/series1.zip`
3. **Component Parameter Sources**:
   - `PackageUrlServer`: Received dynamically from game server in `GetVersionResponse.cdn` (`PlayerManagerGT.as:248`). [VERIFIED]
   - `assetPath` (`mExternalAssetPath`): Defined in `work/apk/assets/config/mmog.xml` as `"/external_asset/android/"` (`VersionControllerImpl.as:52`). [VERIFIED]
   - `CurrentGameVersion`: Resolved version string (`"1.11.2"` or fallback `"1.11.1"`) (`VersionControllerImpl.as:200-207`). [VERIFIED]
   - `Name`: Canonical package name from `EExternalAsset` (`ExternalFileControllerImpl.as:353`). [VERIFIED]
   - Extension: Constant `".zip"` (`ExternalFileControllerImpl.as:43`). [VERIFIED]

### 5.4 Pre-Download Validation & Integrity Checks
- **1. Server Version Validator Check**:
  - `VersionController.CheckIfCurrentVersionIsAvailableOnServer` opens an asynchronous `flash.net.URLStream` to the `versionvalidator` URL (`VersionControllerImpl.as:252-261`). [VERIFIED]
  - Events:
    - `Event.OPEN`, `Event.COMPLETE`, or `ProgressEvent.PROGRESS` (>1 event): sets `mCurrentVersionAvailableOnServer = true` (`VersionControllerImpl.as:266-289`). [VERIFIED]
    - `IOErrorEvent.IO_ERROR`: sets `mCurrentVersionAvailableOnServer = false` (`VersionControllerImpl.as:270-274`). [VERIFIED]
  - If unavailable on server, `ExternalFileController` displays `VersionUpdateData.VERSION_UNAVAILABLE` popup (`ExternalFileControllerImpl.as:294-298`). [VERIFIED]
- **2. Local Package Freshness Check (`ValidateVersion`)**:
  - For each asset package in `EExternalAsset.GetList()`, the client checks if the local package folder exists in `File.applicationStorageDirectory` (`ExternalFileControllerImpl.as:227-237`). [VERIFIED]
  - Checks for local marker file: `{assetPath}/{packageName}_version` (`ExternalFileControllerImpl.as:615`). [VERIFIED]
  - If the marker file exists, reads the UTF string content (`ExternalFileControllerImpl.as:621-623`).
  - Compares content string with `VersionController.GetAssetVersion(CurrentGameVersion, packageName)` from `versionning.xml` (`ExternalFileControllerImpl.as:624`). [VERIFIED]
  - If file is missing or string does not match the manifest version: the package is marked invalid and pushed to `mMissingPackageList` (`ExternalFileControllerImpl.as:241-244`). [VERIFIED]
- **3. Disk Space & Bandwidth Calculation**:
  - Client sums sizes across all missing packages (`ExternalFileControllerImpl.as:305-323`):
    - `neededSpace += assetData.UncompressedSize` [VERIFIED]
    - `loadingSpace += assetData.CompressedSize` [VERIFIED]
  - Checks against available device storage: `neededSpace <= File.applicationStorageDirectory.spaceAvailable` (`ExternalFileControllerImpl.as:320-323`). [VERIFIED]
  - If insufficient: halts download and shows `VersionUpdateData.NOT_ENOUGH_DISK_SPACE_STATE` popup showing required MB (`neededSpace / 1048576`) (`ExternalFileControllerImpl.as:329-332`). [VERIFIED]
  - If sufficient: shows `VersionUpdateData.EXTRA_CONTENT_REQUIRED_STATE` popup informing user of download size in MB (`loadingSpace / 1048576`) and awaits user confirmation before starting download (`ExternalFileControllerImpl.as:325, 335-340`). [VERIFIED]

### 5.5 Package File Format & Extraction Pipeline
- **Container Format**: Standard PKZIP archive (`.zip`) (`ExternalFileControllerImpl.as:43, 458-459`). [VERIFIED]
- **Download Concurrency**:
  - Downloaded using up to 4 parallel `flash.net.URLLoader` instances in binary mode (`URLLoaderDataFormat.BINARY`) (`ExternalFileControllerImpl.as:47, 358, 445-451`). [VERIFIED]
- **In-Memory Zip Decompression**:
  - Extracted in memory using `deng.fzip.FZip` (`myzip.loadBytes(loader.data)`, `ExternalFileControllerImpl.as:458-460`). [VERIFIED]
- **Non-Blocking Time-Sliced Extraction**:
  - Unpacking runs in native stage `ENTER_FRAME` handler `OnInstallFile` (`ExternalFileControllerImpl.as:371, 509-587`). [VERIFIED]
  - Frame budget: up to 15 ms per frame in foreground (`INSTALL_TIME_LIMIT = 15`), or up to 30 ms per frame in background (`INSTALL_TIME_LIMIT_BACKGROUND_MODE = 30`) (`ExternalFileControllerImpl.as:51-54, 518-520`). [VERIFIED]
  - Directory entries ending in `"/"` are skipped (`ExternalFileControllerImpl.as:525`). [VERIFIED]
  - Target Path: `File.applicationStorageDirectory.resolvePath((assetPath + filename).toLowerCase())` (`ExternalFileControllerImpl.as:388-393`). [VERIFIED]
  - File attribute: `myFile.preventBackup = true` (`ExternalFileControllerImpl.as:393`). [VERIFIED]
- **Version Marker Creation**:
  - If the zip contains a file with `"version"` in its filename, its content is saved as `mCurrentPackageVersion` (`ExternalFileControllerImpl.as:527-530`). [VERIFIED]
  - If omitted, default version `"0.0.0"` is generated (`ExternalFileControllerImpl.as:542-546`). [VERIFIED]
  - Once all files in the package are extracted, client calls `SaveFileOnDevice` to write the marker file:
    `{assetPath}/{packageName}_version` containing the package version string (`ExternalFileControllerImpl.as:547`). [VERIFIED]

### 5.6 External Asset Package Inventory (26 Packages)
Verified from `com.frimastudio.snowstorm.project.externalfile.enum.EExternalAsset.as:10-60` and `Local Store/versionning.xml`:

| Package Name | Target Directory (`Local Store/...`) | Typical Contents |
|---|---|---|
| `series1` | `asset/cards/` | Card images (`4007_1.jpg` ...), `series1_version` |
| `series2` | `asset/cards/` | Card images (`10008_1.jpg` ...), `series2_version` |
| `anim` | `asset/anim/` | Character/duel animation assets |
| `common` | `asset/common/` | Shared UI texture atlases (`common_all_1.png`, `common_all_1.xml`) |
| `cardgamebg` | `asset/misc/cardgamebg/` | Duel arena playmat backgrounds |
| `mapbackground` | `asset/misc/mapbackground/` | World map section backgrounds |
| `mapcharacter` | `asset/misc/mapcharacter/` | Campaign map character sprites |
| `maplibrary` | `asset/misc/maplibrary/` | Map visual objects |
| `mappreview` | `asset/misc/mappreview/` | Chapter preview images |
| `arena` | `asset/module/arena/` | Arena UI texture atlas (`arena_all.png`, `arena_all.xml`) |
| `cardgamecommon`| `asset/module/cardgamecommon/`| In-game duel icons, slots, effect sprites |
| `crafting` | `asset/module/crafting/` | Card crafting UI atlas |
| `deckbuilder` | `asset/module/deckbuilder/` | Deck builder interface atlas |
| `duelground` | `asset/module/duelground/` | Duel ground module atlas |
| `filters` | `asset/module/filters/` | Card search & filter dropdown atlas |
| `hud` | `asset/module/hud/` | Player status bar, coins, duel points HUD atlas |
| `login` | `asset/module/login/` | Login screen atlas (`login_all.png`, `login_all.xml`) |
| `livepvpgame` | `asset/module/livepvpgame/` | Real-time PvP arena duel UI |
| `mainmenu` | `asset/module/mainmenu/` | Main hub menu atlas |
| `shop` | `asset/module/shop/` | Booster pack shop interface atlas |
| `tournament` | `asset/module/tournament/` | Tournament bracket & rewards UI |
| `transition` | `asset/transition/` | Scene transition animations |
| `world` | `asset/world/` | Story mode world map system atlas |
| `guild` | `asset/module/guild/` | Guild system UI atlas |
| `menubackground`| `asset/misc/menubackground/` | Main menu full-screen background graphics |
| `font` | `asset/font/` | Bitmap fonts and descriptors (`font_version`) |

### 5.7 Integrity Checks & Absence of Cryptographic Hashes
- **Integrity Checks Present**:
  1. **ZIP Container Integrity**: Handled natively by `FZip` checking ZIP headers and deflated stream boundaries. Corrupted downloads fire `IOErrorEvent.IO_ERROR` or throw parse errors, caught by `OnPackageError` (`ExternalFileControllerImpl.as:474-488`). [VERIFIED]
  2. **Pre-Download Size Verification**: `uncompressedsize` and `compressedsize` XML attributes are checked against disk space before triggering download (`ExternalFileControllerImpl.as:305-333`). [VERIFIED]
  3. **Version String Match**: `{packageName}_version` marker file content must match `<package version="...">` in `versionning.xml` (`ExternalFileControllerImpl.as:624`). [VERIFIED]
  4. **Server Availability Probe**: `versionvalidator` probe ensures CDN directory exists before requesting packages (`VersionControllerImpl.as:259`). [VERIFIED]
- **Cryptographic Hashes**:
  - **No MD5, SHA-1, SHA-256, or explicit CRC32 verification** is performed by the client on downloaded packages or extracted assets. [VERIFIED]
  - The client accepts any valid ZIP archive provided its extracted files land in the designated path and the version marker matches `versionning.xml`. [VERIFIED]

---

## 6. Revival Server Implementation (`server/`)

### 6.1 Server Architecture
- `server/amf3.py`: Full AMF3 encoder and decoder implementing the Adobe AMF3 specification:
  - Reference tables for strings, objects, and traits.
  - Inline and referenced traits (sealed and dynamic properties).
  - Dense and associative arrays.
  - Raw `ByteArray` deserialization (as required by `LoginRequest.name` / `password` and `GetPlayerSaveResponse.playerSave`).
  - Signed U29 integer decoding (`0x04`) and 64-bit IEEE-754 float decoding (`0x05`).
  - Null, undefined, and boolean primitives (`0x00`, `0x01`, `0x02`, `0x03`).
  - Response constructors: `build_get_version_response`, `build_ping_response`, `build_get_token_response`, `build_login_response`, `build_get_player_save_response`, `build_abstract_exception`, `build_error_response`.
- `server/server.py`: Multi-threaded HTTP server (`http.server.ThreadingHTTPServer`):
  - Self-contained execution via `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` and `import amf3` (supporting both `python server/server.py` and `python -m server.server`).
  - CLI option `--version-string` defaulting to live server format `"android=1.11.2~ios=1.11.2"`.
  - Batch request handler decoding the AMF3 array and emitting exactly one response per request, in request order.
  - Dynamic on-demand PKZIP archive generation for the 26 packages from `input/` into `work/package_cache/` (never modifying `input/`).
  - Flash cross-domain policy (`/crossdomain.xml`), shutdown bypass config (`/closepopupconfig.xml`), version validator (`/versionvalidator`), and manifest (`/versionning.xml`).

### 6.2 Response Matching & Listener Architecture
- **Matching by Class Alias (NOT Array Position)**:
  - In `com.frimastudio.common.core.engine.EngineServerCom.as:431-434`, listeners register via `addMessageListener`:
    ```actionscript
    public function addMessageListener(param1:Class, param2:Function, param3:Boolean = false, param4:int = 0, param5:Boolean = true) : void
    {
       addEventListener(param1.EVENT_NAME, param2, param3, param4, param5);
    }
    ```
    (`PlayerManagerDal.as:51`: `mEngineCom.addMessageListener(GetVersionResponse, this.OnGetVersionResponse, false, 0, true)`). [VERIFIED]
  - When responses arrive in `EngineServerCom.as:524-544`, `BroadcastServerResponse` executes for each response object:
    ```actionscript
    var _loc3_:Event = param2 as Event;
    if(_loc3_ != null)
    {
       dispatchEvent(_loc3_);
    }
    ```
    ([EngineServerCom.as:670-674]). [VERIFIED]
  - Each response class extends `flash.events.Event` and sets its event type to `EVENT_NAME` (e.g. `GetVersionResponse.as:10, 24`: `super(EVENT_NAME)` where `EVENT_NAME = "com.frimastudio.snowstorm.project.player.amf.GetVersionResponse event"`). [VERIFIED]
  - When AMF3 `readObject()` parses the object, Flash's `registerClassAlias` mapping ([RegisterAlias.as:15-38]) instantiates the typed class, which dispatches by its event type.
  - Therefore, the client matches responses to registered handlers by **class alias** (event type), not by array position. Emitting responses in request order guarantees 1:1 request-response correspondence. [VERIFIED]

### 6.3 Error Signaling & Exception Semantics
- **Transport Level (Return Code)**:
  - The 4-byte big-endian integer header in the HTTP packet is the transport return code ([EngineServerCom.as:493]).
  - If `returnCode != 0`, the client treats this as fatal:
    ```actionscript
    if(_loc5_ != 0)
    {
       Log.Report(..., "Server return an error (return code = " + _loc5_ + ")", Log.INFO);
       this.Disconnect(new EngineEvent(EngineEvent.CONNECTION_LOST, EEngineErrorCode.DISCONNECT_BY_INVALID_RAW_DATA));
       return;
    }
    ```
    ([EngineServerCom.as:494-498]). [VERIFIED]
  - Consequently, HTTP transport packets must ALWAYS set return code `0` to prevent the client from disconnecting. [VERIFIED]
- **Application Level (`exception` Field)**:
  - Every game response class defines `public var exception: AbstractException` (e.g. `GetVersionResponse.as:12`, `GetPlayerSaveResponse.as:13`, `PingResponse.as:13`). [VERIFIED]
  - `AbstractException` has class alias `com.frimastudio.commons.amf.exception.AbstractException` ([AbstractException.as:3]). Properties: `message: String`, `stackTrace: Array`, `code: int`, `checked: Boolean`, `resourceNameId: Number`. [VERIFIED]
  - **Success Semantics**: `exception == null` (AMF3 `null` marker `0x01`) means the request succeeded. [VERIFIED]
  - **Failure Semantics**: `exception != null` indicates an error. The client logs `aResponse.exception.code` and halts that operation (e.g. `PlayerManagerGT.as:239-245`).
  - In `EngineServerCom.as:683-700` (`CatchServerException`), any response carrying an `exception` property is intercepted, logged, and formatted into an error report. [VERIFIED]
  - For unknown request classes, the server logs a WARNING and returns `*Response` with `exception: AbstractException(code=1, message="Unsupported request")`, rather than defaulting to `GetVersionResponse`. [VERIFIED]

### 6.4 Version String Parsing Analysis
- **Client Parsing Flow**:
  - `PlayerManagerGT.as:247`: `this.mAppVersion = this.ParseVersion(aResponse.version);` [VERIFIED]
  - `PlayerManagerGT.as:254-276` (`ParseVersion`):
    - If `version.indexOf("~") != -1`: splits on `~`, searches for tag `"android"` (`true == true ? "android" : "ios"`), and extracts `split("=")[1]`.
    - If `version.indexOf("~") == -1`: skips the delimiter block and returns `aVersionString` unmodified. [VERIFIED]
  - `YGOMLoginImpl.as:455-494` (`ValidateAppVersion`):
    - Splits `(Util as IUtil).GetVar("client", "version")` (`"1.11.2"`) by `.` -> `appVersionPart = ["1", "11", "2"]`.
    - Splits `mPlayerManager.AppVersion` by `.` -> `serverVersionPart`.
    - Evaluates `appVersionPart.length == 3 && serverVersionPart.length == 3`, then checks `appVersionPart >= serverVersionPart`. [VERIFIED]
  - **Plain vs Compound Form**:
    - The plain form `"1.11.2"` is safe for Android because `ParseVersion` returns it directly and `ValidateAppVersion` successfully compares `1.11.2 >= 1.11.2`. [VERIFIED]
    - However, the compound form `"android=1.11.2~ios=1.11.2"` was the actual live server format (finding confirmed in section 4) and safely supports both platform tags. The server defaults to this live format and provides `--version-string` CLI flag. [VERIFIED]

### 6.5 Package Extraction Simulation & Asset Diffing Results
- Implemented in `tests/simulate_install.py`, which downloads all 26 packages from the running revival server and extracts them reproducing `ExternalFileControllerImpl.as:388-393, 509-587`.
- **Package Integrity & Version Verification**:
  - All 26 packages download successfully over HTTP.
  - Every package `.zip` contains **exactly one** file with `"version"` in its name.
  - The content of each version file matches the 1.11.1 manifest entry in `versionning.xml` (`anim=1.1.7`, `arena=1.1.7`, `cardgamebg=1.1.3`, `cardgamecommon=1.1.6`, `common=1.1.9`, `crafting=1.1.5`, `deckbuilder=1.1.6`, `duelground=1.1.4`, `filters=1.1.4`, `guild=1.1.6`, `hud=1.1.4`, `login=1.1.5`, `livepvpgame=1.1.0`, `mainmenu=1.1.10`, `mapbackground=1.1.6`, `mapcharacter=1.1.4`, `maplibrary=1.1.3`, `mappreview=1.1.6`, `menubackground=1.1.0`, `shop=1.1.9`, `tournament=1.1.4`, `transition=1.1.4`, `world=1.1.9`, `series1=1.1.3`, `series2=1.1.10`, `font=1.1.5`). [VERIFIED]
- **File Tree Diff**:
  - Total expected files in `input/.../Local Store/asset/`: 1,627 files.
  - Total installed files in simulated client temp directory: 1,627 files.
  - Missing in installed: **0**.
  - Extra in installed: **0**.
  - Size mismatches: **0**.
  - **Card asset duplication**: Both `series1.zip` and `series2.zip` currently package all card images from `asset/cards/` (with `series1_version` in `series1.zip` and `series2_version` in `series2.zip`). When the client extracts both, all card images overwrite identically, resulting in a 100% complete card database without missing assets. [VERIFIED]

### 6.6 Verified vs Inferred Elements Summary
- **VERIFIED**:
  1. AMF3 request framing: 2-byte `ExternalId` length, UTF-8 `ExternalId`, AMF3 array, zlib compressed (`ServerComHTTP.as:376-389`).
  2. AMF3 response framing: 4-byte int return code (0), zlib compressed AMF3 array (`EngineServerCom.as:493-524`).
  3. Response listener dispatching by class alias / event name (`EngineServerCom.as:431-434, 670-674`).
  4. Response error representation via `exception: AbstractException` (`AbstractException.as:3-16`, `EngineServerCom.as:683-700`).
  5. Version parsing logic in `PlayerManagerGT.as:254-276` and validation in `YGOMLoginImpl.as:455-494`.
  6. 26 packages, paths, and extraction rules (`EExternalAsset.as:10-60`, `ExternalFileControllerImpl.as:388-393, 509-587`).
  7. Manifest structure and version validator probe (`VersionControllerImpl.as:86, 259`).
  8. Hardcoded port 80 for HTTP server connections (`EngineServerCom.as:255-256`).
  9. `pvpServerUrl` format (`<url>~<serverPort>~<policyPort>`) parsed by `ServerURLParser.as:18-23` and dispatched via `ServerComHTTP.as:249-251` and `YGOMPvPLoginImpl.as:266-267`.
- **INFERRED**:
  1. `GetVersionResponse.packageVersion` and `packageSize`: Defined as `String` in `GetVersionResponse.as:16-18`, but unused by `PlayerManagerGT.as:236-252`. Set to `None`.
  2. Live `closepopupconfig.xml` content: Original Konami production XML is unavailable; empty `<closepopupconfig/>` XML satisfies `LoginModule.as:133-146`.
  3. Online authentication credentials: `GetTokenResponse.token` and `seed` mock values for online login if bypassed offline mode is not used.
  4. PvP live gameplay server protocol: While `pvpServerUrl` configuration and HTTP initialization via `ETechnology.HTTP` (`YGOMPvPLoginImpl.as:282`) are verified, real-time multiplayer duel handling beyond the initial handshake is inferred.

---

### 6.7 Deployment & Security Hardening Architecture
- **Cloudflare Tunnel Integration**:
  - Tunnel ingress maps public hostname `ygo.eclip5e.com` directly to `http://localhost:8087`.
  - Client builds plain HTTP URLs (`"http://" + host + path`) and connects to port 80 (`EngineServerCom.as:255-256`). Cloudflare "Always Use HTTPS" must be disabled for this hostname to prevent `301`/`302` redirects that break the Adobe AIR client. [VERIFIED]
- **Request Hardening**:
  - **1 MiB POST Body Cap**: Any POST request exceeding 1 MiB (`1,048,576` bytes) is rejected immediately with HTTP 413 Payload Too Large. [VERIFIED]
  - **4 MiB Decompressed Payload Limit**: Uses `zlib.decompressobj().decompress(body, max_length=4*1024*1024)` to safeguard against decompression bomb attacks. Payloads exceeding 4 MiB decompressed return HTTP 413. [VERIFIED]
  - **Socket Timeout**: Enforces a 30-second socket timeout on handler connections to prevent slowloris resource exhaustion. [VERIFIED]
  - **Exact Route Whitelist**: Only exact known paths (`/crossdomain.xml`, `/closepopupconfig.xml`, `/external_asset/android/versionning.xml`, `/external_asset/android/<ver>/versionvalidator`, `/external_asset/android/<ver>/<pkg>.zip`, `/facebook/proxy.html`) are served. All unknown GET/POST requests return HTTP 404; other methods return HTTP 405. [VERIFIED]
  - **Thread-Safe Package Building**: Per-package `threading.Lock` protects concurrent archive creation. Temp archives are written to unique `{pkg}_{uuid}.tmp` files and atomically moved into place via `os.replace`. [VERIFIED]
  - **`--prebuild` CLI Flag**: Allows prebuilding all 26 package zips into `work/package_cache/` ahead of server launch. [VERIFIED]
- **Auditing & Logging**:
  - Extracts the real client IP from `CF-Connecting-IP`, falling back to the TCP socket address. [VERIFIED]
  - Logs all requests (method, path, status, client IP) to both stdout and a `RotatingFileHandler` (`work/server_requests.log`, 10 MB per file, 5 backups). [VERIFIED]

---

### 6.8 APK Patcher Architecture (`tools/patch_apk.py`)
- **mmog.xml Target Modifications**:
  - `serverUrl` in `<http>`: Patched to `http://ygo.eclip5e.com/facebook/proxy.html`. [VERIFIED]
  - `pvpServerUrl` in `<http>`: Patched to `http://ygo.eclip5e.com/facebook/proxy.html~80~844`. [VERIFIED]
  - `serverUrl` in `<reporting>`: Patched to `http://ygo.eclip5e.com/facebook/proxy.html`. [VERIFIED]
  - `openGraphServerUrl` in `<facebook>`: Patched to `http://ygo.eclip5e.com`. [VERIFIED]
- **Port 80 and Parsing Citations**:
  - In `EngineServerCom.as:255-256`, the HTTP server port is hardcoded:
    ```actionscript
    _loc5_ = new Server();
    _loc5_.dns = _loc4_;
    _loc5_.port = 80;
    ```
    This confirms the client requires port 80 for its primary HTTP connection. [VERIFIED]
  - In `ServerURLParser.as:18-23`, `pvpServerUrl` is split by `"~"`:
    `_loc4_[0]` is the server URL, `_loc4_[1]` is `ServerPort`, and `_loc4_[2]` is `PolicyPort`. [VERIFIED]
  - In `ServerComHTTP.as:249-251`, the server URL is constructed via:
    ```actionscript
    var _loc4_:String = param1.substring(0,param1.indexOf("/",param1.indexOf("//") + 2));
    this.mServerUrl = param1.replace(_loc4_,_loc4_ + ":" + param2);
    ```
    Using port 80 keeps both primary and PvP communication on standard Cloudflare-supported HTTP port 80. [VERIFIED]
- **Target SDK Compatibility Patching (Android 14 and Android 15 Support)**:
  - **Android 14 & 15 Policy Constraints**:
    - Android 14 (API 34) enforced `minInstallableTargetSdkVersion = 23`.
    - Android 15 (API 35) raised this threshold to `minInstallableTargetSdkVersion = 24`. Any APK targeting API < 24 is blocked on Android 15 by the GUI package installer (`INSTALL_FAILED_DEPRECATED_SDK_VERSION`). The original BAM Pocket APK specified `targetSdkVersion="16"` (`uses-sdk` in `application.xml:22`). [VERIFIED]
  - **Binary AXML Patch**: `tools/patch_apk.py` locates the `targetSdkVersion` attribute index in the `AndroidManifest.xml` string pool and updates the 4-byte integer in the `START_TAG` chunk from `16` to `24`. [VERIFIED]
  - **AIR Application XML Patch**: Updates `android:targetSdkVersion="24"` in `assets/META-INF/AIR/application.xml`. [VERIFIED]
  - **Why API 24 (The Compatibility Sweet Spot)**:
    - Satisfies both Android 14 (`minInstallableTargetSdkVersion = 23`) and Android 15 (`minInstallableTargetSdkVersion = 24`) for clean GUI tap-to-install without ADB `--bypass-low-target-sdk-block`. [VERIFIED]
    - Allows plain HTTP traffic by default: Android 9 (API 28) disabled cleartext HTTP by default (`usesCleartextTraffic=false`), but apps targeting API 24 default to `usesCleartextTraffic=true`. [VERIFIED]
    - Allows v1 JAR signatures: Android 11+ (API 30+) enforces APK Signature Scheme v2 only for apps targeting API 30+. Apps targeting API 24 install seamlessly with v1 JAR signatures. [VERIFIED]
    - Avoids mandatory `android:exported`: Android 12 (API 31+) mandates explicit `android:exported` on all components with intent filters. Targeting API 24 avoids manifest parse failures on Android 12+. [VERIFIED]
- **ZIP Rewriting, Alignment & Signing Pipeline**:
  - Strips old signature files: `META-INF/*.SF`, `META-INF/*.RSA`, `META-INF/*.DSA`, and `META-INF/MANIFEST.MF`. [VERIFIED]
  - Preserves exact compression method for all other APK entries without recompression artifacts. [VERIFIED]
  - **4-Byte Zipalign**: Natively aligns all 269 uncompressed (stored) entries by padding local file header extra fields so their data begins on a 4-byte boundary, satisfying Linux/Android `mmap()` requirements for `assets/MobileGame.swf` and resource assets (0 misaligned entries). [VERIFIED]
  - **Signing**: Uses `jarsigner` (from JDK) with SHA-256 and a 2048-bit RSA key from `work/debug.keystore` (or `apksigner` if build-tools are present), verified with `jarsigner -verify` (`jar verified`). [VERIFIED]

---

### 6.9 Adobe AIR Runtime Architecture & Modern Device Requirements
- **Shared Runtime Detection in `classes.dex`**:
  - Main Activity: `air.com.konami.ygo.AppEntry` (`AndroidManifest.xml` string 37). [VERIFIED]
  - Captive Runtime Check: `AppEntry.loadCaptiveRuntimeClasses` (code_off=1202948) executes `Class.forName("com.adobe.air.AndroidActivityWrapper")`. In BAM Pocket, `com.adobe.air` classes are omitted from `classes.dex` (only `InstallOfferPingUtils` and `ResourceIdMap` are present). Thus, `loadCaptiveRuntimeClasses` returns `false`. [VERIFIED]
  - Shared Runtime Check: `AppEntry.isRuntimeInstalled` (code_off=1202560) calls `PackageManager.getPackageInfo("com.adobe.air", 0x100)`. If `NameNotFoundException` is caught, it invokes `showRuntimeNotInstalledDialog` (code_off=1203292) linking to `market://details?id=com.adobe.air`. [VERIFIED]
  - Hand-off: Once `com.adobe.air` is installed, `AppEntry.loadSharedRuntimeDex` (code_off=1203020) loads Adobe AIR's dex runtime to execute `assets/MobileGame.swf`. [VERIFIED]
- **Runtime Requirement for End-Users**:
  - Since Adobe AIR is no longer distributed on Google Play, running BAM Pocket on modern devices requires installing the standalone Adobe AIR APK (e.g. Adobe AIR 25 or 32) alongside `ygo_patched.apk`. [VERIFIED]
- **Native ABI Library Removal (`lib/armeabi-v7a/libNativeABI.so`)**:
  - **Diagnostic on Modern 64-Bit Hardware**: When installing on modern 64-bit-only devices (such as Google Pixel 7/8/9/10, where `ro.product.cpu.abilist = arm64-v8a`), the package installer initially failed with `INSTALL_FAILED_NO_MATCHING_ABIS: Failed to extract native libraries, res=-113`. [VERIFIED]
  - **Function of `libNativeABI.so`**: Inspection of `lib/armeabi-v7a/libNativeABI.so` (size 9560 bytes) revealed only basic stubs (`getNativeABI`, `libARMv7AMarker.so`). Verification against `classes.dex` confirmed that `System.loadLibrary` is never invoked and `libNativeABI` is never loaded at runtime; it was placed in the APK in 2012 solely as a Google Play Store architecture filter. [VERIFIED]
  - **Architecture-Neutral Patch**: `tools/patch_apk.py` strips `lib/armeabi-v7a/libNativeABI.so`. Without any native `.so` files, Android classifies the package as architecture-neutral (`ALL_ABIS`), allowing installation across `arm64-v8a`, `x86_64`, and `armeabi-v7a`. [VERIFIED]
  - **Live Verification**: `adb install -r -d work/ygo_patched.apk` outputs `Success` on Pixel 10 (Android 17 / SDK 37). Launching `air.com.konami.ygo/.AppEntry` successfully runs the process and presents the runtime dialog. [VERIFIED]

---

### 6.10 Modern OS Warning Suppression & Captive Runtime Bundling Architecture
- **Suppression of 'Built for an older version of Android' Dialog**:
  - **Diagnostic & Root Cause**: Android Framework (`AppWarnings.java` / `DeprecatedTargetSdkVersionDialog`) displays this prompt on app launch whenever `targetSdkVersion < ro.build.version.min_supported_target_sdk`. On Android 9 through Android 17 (verified on Pixel 10), `min_supported_target_sdk = 28`. Setting `targetSdkVersion = 24` was sufficient to pass package installation checks on Android 14/15, but remained below 28, causing the system warning to pop up. [VERIFIED]
  - **Resolution**: `tools/patch_apk.py` updates `targetSdkVersion` to `28` in both binary `AndroidManifest.xml` and `assets/META-INF/AIR/application.xml`. In addition, `android:usesCleartextTraffic="true"` is added to `<application>` in `application.xml` to ensure cleartext HTTP communication on port 80 remains permitted. [VERIFIED]
  - **Verification**: Installed and launched on Pixel 10 via ADB; UI hierarchy dump confirmed the system warning dialog is 100% eliminated, launching directly into the app. [VERIFIED]
- **Adobe AIR Captive Runtime Bundling Architecture**:
  - **AppEntry Dual-Mode Support**: In `classes.dex`, `AppEntry.loadCaptiveRuntimeClasses()` specifically tests:
    ```java
    Class.forName("com.adobe.air.AndroidActivityWrapper");
    Class.forName("com.adobe.air.AIRServiceAction");
    Class.forName("com.adobe.air.AndroidGcmRegistrationService");
    ```
    If these classes resolve, `AppEntry` switches to captive mode and bypasses `isRuntimeInstalled()` entirely, eliminating the need for standalone Adobe AIR. [VERIFIED]
  - **Multidex Injection (`classes2.dex`)**: Modern Android runtime (ART on Android 5.0+) natively loads secondary DEX files (`classes2.dex`, `classes3.dex`) into the main application classloader. The AIR runtime classes are packaged as `classes2.dex`, avoiding any need to disassemble or rewrite the original game's `classes.dex`. [VERIFIED]
  - **Revertable Backup Strategy**:
    - `work/ygo_patched_shared.apk` is automatically preserved as a verified backup of the clean shared-runtime build.
    - Captive bundling can be toggled via `--air-runtime <path>` or reverted at any time via `--no-captive` in `tools/patch_apk.py`. [VERIFIED]
  - **64-bit Device Constraint**:
    - Legacy Adobe AIR 32 only supported 32-bit ARM (`armeabi-v7a`).
    - 64-bit devices (such as Google Pixel 7/8/9/10) require 64-bit `arm64-v8a` native libraries (`libCore.so`), introduced in HARMAN AIR 33+ (June 2019). [VERIFIED]

---

### 6.11 Multi-ABI 64-Bit & 32-Bit Captive Runtime Integration & Verification
- **Dual-ABI Captive Runtime Bundle (HARMAN AIR 50.2.4.4)**:
  - **Fetched Archives**: Downloaded official HARMAN AIR 50.2.4.4 runtimes (`Runtime_arm8.apk` for 64-bit ARM8 and `Runtime_arm.apk` for 32-bit ARM7) into `work/air_runtime/`. [VERIFIED]
  - **Multidex Runtime Integration**: Packaged AIR runtime Java classes (`classes.dex`, 4,259,568 bytes) as `classes2.dex` alongside the game's original `classes.dex`, avoiding any Dex bytecode patching or toolchain recompilation. [VERIFIED]
  - **Multi-ABI Native Libraries**:
    - `lib/arm64-v8a/`: `libCore.so` (20,676,880 bytes), `libc++_shared.so` (1,058,904 bytes), `libysshared.so` (333,656 bytes). [VERIFIED]
    - `lib/armeabi-v7a/`: `libCore.so` (14,631,808 bytes), `libc++_shared.so` (657,000 bytes), `libysshared.so` (275,688 bytes). [VERIFIED]
    - Injected runtime assets: `assets/AdobeClean-Light.ttf`, `assets/index.html`. [VERIFIED]
- **ANE 64-Bit Compatibility**:
  - All 4 bundled ANEs (`RateBox`, `FlurryAnalytics`, `PushNotification`, `AndroidIAB`) contain exclusively `.swf` ActionScript bytecode and Java `.jar` libraries; none contain C/C++ native shared libraries. [VERIFIED]
  - `tools/patch_apk.py` duplicates `<platform name="Android-ARM">` descriptors to `<platform name="Android-ARM64">` across all 4 `extension.xml` files and mirrors `/META-INF/ANE/Android-ARM/` directory entries to `/META-INF/ANE/Android-ARM64/`. [VERIFIED]
- **Descriptor & Asset Path Alignment**:
  - `libCore.so` queries the root descriptor `META-INF/AIR/application.xml` in addition to `assets/META-INF/AIR/application.xml`. Both are populated and kept in sync. [VERIFIED]
  - Stored `.so` entries are aligned to 16,384-byte boundaries (16KB page alignment) for modern Android kernels; uncompressed assets are 4-byte aligned (0 misaligned entries). [VERIFIED]
- **Android 15+ PageSizeMismatchDialog & Focus Suppression**:
  - When an application is marked `android:debuggable="true"` on Android 15/16/17 (verified on Pixel 10), the system framework displays `AppWarnings.PageSizeMismatchDialog` at launch. [VERIFIED]
  - The modal dialog steals focus (`onWindowFocusChanged(false)`), triggering `Event.DEACTIVATE` in Adobe AIR and prompting the client prelauncher to initiate background exit. [VERIFIED]
  - Setting `android:debuggable="false"` in both binary `AndroidManifest.xml` and `assets/META-INF/AIR/application.xml` completely prevents `PageSizeMismatchDialog` from appearing, launching cleanly into the foreground. [VERIFIED]
- **Flash Engine Exit Interception (`libCore.so`)**:
  - **Hook Target at 0x72f004**: Virtual address `0x72f004` is an internal engine dispatch entry calling `0x7469a0` (tail call to vtable slot 4 `0x73ed18`, which triggers JNI `finish()`). While previously hypothesized to be `NativeApplication.nativeApplication.exit()`, whole-SWF P-code audit confirms that no AS3 `exit()` call is reachable during initial startup (+183 ms). Therefore, `0x72f004` is NOT proven to be `NativeApplication.exit()` and represents an internal native shutdown or unhandled exception path. [INFERRED]
  - **Suppression Hook**: `0x72f004` is intercepted with a diagnostic hook that logs to Android logcat via `__android_log_print` and returns 4 (`orr w0, wzr, #4; ret`), while `0x73ed18` is patched with `ret`. [INFERRED]
  - **Live Process Verification**: On a connected Google Pixel 10 (Android 17, `arm64-v8a`), the patched APK runs continuously in top-foreground (`curProcState=2`, `hasShownUi=true`), rendering landscape `SurfaceView` bounds `[353, 0][2245, 1080]` with 10 internal Flash threads active. [VERIFIED]

---

### 6.12 Black Screen & Early Exit Investigation (Variants A vs B)
- **Reproducible Test Variants**:
  - **Tooling**: Exit-suppression hook moved from scratch to documented script `tools/patch_exit_hook.py`, with `--exit-hook` flag integrated into `tools/patch_apk.py`. [VERIFIED]
  - **Variant A (Captive Runtime, No Hook)**: `work/ygo_variant_a.apk` built with clean `work/air_runtime/lib/arm64-v8a/libCore.so`. [VERIFIED]
  - **Variant B (Captive Runtime + Hook)**: `work/ygo_variant_b.apk` built with `--exit-hook` (hook installed at 0x77f1a0 intercepting 0x72f004 and patching 0x73ed18 to ret). [VERIFIED that the build was made; the log text "NativeApplication.exit() INTERCEPTED" is the hook author's own label, not evidence that 0x72f004 is exit()]
- **Evidence Comparison (Pixel 10, Android 17)**:
  - **Variant A Logcat (`work/logs/variant_a.txt`)**:
    - At `04:28:48.685`: `AIR RUNTIME: Starting in synchronous mode`. [VERIFIED]
    - At `04:28:48.868` (+183 ms): `AIR RUNTIME: finish`. Activity is destroyed and app exits. [VERIFIED]
  - **Variant B Logcat (`work/logs/variant_b.txt`)**:
    - At `04:29:38.428`: `AIR RUNTIME: Starting in synchronous mode`. [VERIFIED]
    - At `04:29:38.612` (+184 ms): `BAM_CORE: NativeApplication.exit() INTERCEPTED AND SUPPRESSED!`. [VERIFIED]
    - Process survives indefinitely in top-foreground (`u0_a325 18016 ... air.com.konami.ygo`). [VERIFIED]
  - **Revival Server Requests (`work/server_requests.log`)**:
    - 0 network requests arrived at `ygo.eclip5e.com` during either run (file size unchanged at 23,786 bytes). [VERIFIED]
  - **Visual Screen Inspection**:
    - Both `work/logs/variant_a.png` and `work/logs/variant_b.png` are 2424x1080 full-screen captures containing 0 non-black pixels (100% black). [VERIFIED]
- **FFDec Whole-SWF P-Code Search (`work/pcode/`, 2929 scripts)**:
  - **`exit` Call Sites**: Exactly 3 call sites exist in the entire SWF:
    1. `PrelauncherMobile.pcode:1012` (`com/frimastudio/snowstorm/module/prelauncher/PrelauncherMobile.as:188`): `NativeApplication.nativeApplication.exit()`, inside `Back()`. [VERIFIED]
    2. `LoginModule.pcode:2644` (`com/frimastudio/snowstorm/module/login/LoginModule.as:502`): `NativeApplication.nativeApplication.exit()`, inside `OnQuitPopupEvent()`. [VERIFIED]
    3. `MainMenuModule.pcode:2794` (`com/frimastudio/snowstorm/module/mainmenu/MainMenuModule.as:479`): `NativeApplication.nativeApplication.exit()`, inside `OnQuitPopupEvent()`. [VERIFIED]
  - **`fscommand quit`**: 0 occurrences across all 2,929 scripts. [VERIFIED]
  - **`Event.EXITING`**:
    - `Main.pcode:270, 957` (`com/frimastudio/mobile/Main.as:72, 115-119, 175`): `Main` registers an `EXITING` listener on `NativeApplication.nativeApplication`. The handler `OnExiting` invokes `Dispose()` to tear down Starling and remove event listeners. `Main` does not initiate exit. [VERIFIED]
  - **Back Button Caller Chain**:
    - `InputManager.as:107-122`: Handles `Keyboard.BACK` / `Keyboard.INSERT` from Android hardware navigation, invoking `ProcessBackable()`. [VERIFIED]
    - `PrelauncherMobile.as:42`: Registers as `IBackable` on `InputManagerProxy` in its constructor. [VERIFIED]
    - During automated launch without user touch/key events, `InputManager` receives no back events. [VERIFIED]
  - **`SupportsProfileUtils.as` & `DeviceManager.as` Inspection**:
    - `DeviceManager.as`: Contains 0 exit calls and 0 termination branches. Reads `applicationDescriptor` at lines 77 and 138; computes screen category at line 130. [VERIFIED]
    - `SupportsProfileUtils.as`: Contains 0 direct exit calls. Dispatches test requests via `stage3D.requestContext3D("auto", aProfile)` (line 33). On error (`ErrorEvent.ERROR` at line 51 or try/catch at lines 35-43), notifies callback with `(profile, false)`. [VERIFIED]
    - `Main.as:121-141`: In `OnContextProfileChecked`: tests `BASELINE_EXTENDED` -> falls back to `BASELINE` (line 131) via `setTimeout(..., 100)` -> falls back to `BASELINE_CONSTRAINED` (line 139) via `setTimeout(..., 100)`. If all three fail, line 137 throws `throw new ArgumentError("Failed to create a Context3D profile: " + profile);`. However, the claim that this unhandled `ArgumentError` terminates the runtime at +183 ms is UNVERIFIED and chronologically impossible: two 100 ms `setTimeouts` require >= 200 ms before reaching the throw, whereas the exit occurs at +183 ms. [INFERRED]
- **Stage3D Architecture & Runtime Version Differences**:
  - **Game Target**: Adobe AIR 20.0 (`xmlns="http://ns.adobe.com/air/application/20.0"` in `application.xml:2`), SWF version 31 (2015). [VERIFIED]
  - **Bundled Runtime**: HARMAN AIR 50.2.4.4 (`arm64-v8a`, 2024). [VERIFIED]
  - **Context3D Creation Sequence**:
    1. `Main.Find3DContext` (`Main.as:191`) tests `BASELINE_EXTENDED` via `SupportsProfileUtils.testProfile`.
    2. In `SupportsProfileUtils.as:75-83`, upon test context creation, it immediately calls `context3D.dispose(false)` (telling runtime not to recreate).
    3. `Main.InitStarling` (`Main.as:196`) creates `Starling` instance with the found profile.
    4. Starling requests `mStage3D.requestContext3D(renderMode, profile)` (`Starling.as:182`).
    5. On Starling `CONTEXT3D_CREATE`, `initialize()` (`Starling.as:287`) constructs `mRoot = new MobileProjectEngine()` (`Starling.as:311`) and dispatches `ROOT_CREATED`.
  - **Version Discrepancies & Failure Modes**:
    - **Surface & Context Disposal Semantics**: In modern Android EGL (Android 17 / Pixel 10), calling `context3D.dispose(false)` on the only Stage3D surface can destroy the underlying EGLSurface or put the driver in an unrecoverable state, causing Starling's subsequent `requestContext3D` to fail or stall without dispatching `ROOT_CREATED`. [INFERRED]
    - **Splash Screen Error**: HARMAN AIR 50 outputs `showSplash ERROR: android.content.res.Resources$NotFoundException: Resource ID #0x0` during Java `AIRRuntimeCheck`. However, the claim that this missing resource or splash failure causes the runtime termination is unverified (no source / no evidence that splash failure triggers exit). [INFERRED]
    - **Black Screen Persistence**: When exit is suppressed (Variant B), the app remains alive, but because `RemoveSplashScreen` (`Main.as:231`) or Starling render loop never completes a buffer swap (`present()`), the display buffer stays unpainted black. [INFERRED]

---

### 6.13 Instrumentation (Variant C), Control Test & Startup Exit Root Cause Analysis
- **Variant A Startup Logcat Warning/Error Audit (PID 17788 before exit at +183 ms)**:
  - Exact logcat WARN/ERROR lines from app PID 17788 before `finish` at `04:28:48.868`:
    1. `10-27 04:28:47.182 17788 17788 E .com.konami.ygo: Invalid resource ID 0x00000000.` [VERIFIED]
    2. `10-27 04:28:47.182 17788 17788 D AIRRuntimeCheck: showSplash ERROR: android.content.res.Resources$NotFoundException: Resource ID #0x0` [VERIFIED]
    3. `10-27 04:28:47.547 17788 17817 W InteractionJankMonitor: Initializing without READ_DEVICE_CONFIG permission. enabled=false, interval=1, missedFrameThreshold=3, frameTimeThreshold=64, package=air.com.konami.ygo` [VERIFIED]
  - Between `AIR RUNTIME: Starting in synchronous mode` (`04:28:48.685`) and `AIR RUNTIME: finish` (`04:28:48.868`), exactly 0 lines were logged by PID 17788. [VERIFIED]
- **Variant C (Instrumented SWF Diagnostics)**:
  - **Instrumentation**: `com.frimastudio.mobile.Main` and `SupportsProfileUtils` recompiled via FFDec (`work/MobileGame_variant_c.swf`) with diagnostic logging to native `stage` `TextField`, `trace()`, and HTTP GET to `http://ygo.eclip5e.com/_log?m=<urlencoded>`, plus `loaderInfo.uncaughtErrorEvents` hook. [VERIFIED]
  - **Server Route**: Added `/_log` endpoint to `server/server.py` returning 200 OK and logging `CLIENT_LOG: <msg>`. [VERIFIED]
  - **APK Packaging & Run**: `tools/patch_apk.py --custom-swf work/MobileGame_variant_c.swf --output-apk work/ygo_variant_c.apk` installed and launched on Google Pixel 10 (`work/logs/variant_c.txt`). [VERIFIED]
  - **Observation**:
    - `14:01:00.452`: `AIR RUNTIME: Starting in synchronous mode`. [VERIFIED]
    - `14:01:00.659`: `AIR RUNTIME: finish` (+207 ms). [VERIFIED]
    - Exactly 0 HTTP requests arrived at the revival server (`work/server_requests.log`), exactly 0 `[DIAG]` logcat lines appeared, and screen captured 100% black before activity destroy. [VERIFIED]
- **Control Test (Minimal AIR Application)**:
  - **Implementation**: Built standalone `work/minimal_control/Main.as` containing 0 Frima dependencies, testing `stage.stage3Ds[0].requestContext3D` for each profile and outputting to a native `TextField`. Compiled to `work/ControlApp.swf` via FFDec and packaged to `work/ygo_control.apk`. [VERIFIED]
  - **Execution**: Installed on Google Pixel 10 and launched (`work/logs/control.txt`, `work/logs/control.png`). [VERIFIED]
  - **Observation**:
    - `14:23:01.925`: `AIR RUNTIME: Starting in synchronous mode`. [VERIFIED]
    - `14:23:02.136`: `AIR RUNTIME: finish` (+211 ms). [VERIFIED]
    - 0 pixels rendered on screen (100% black screen). [VERIFIED]
  - **Conclusion**: The startup exit at ~+180-210 ms occurs identically across the original game SWF (Variant A), instrumented game SWF (Variant C), and a minimal test SWF (Control Test). The shutdown is independent of game SWF code and is triggered inside the captive runtime startup pipeline. [VERIFIED]
- **Captive Runtime Architecture & Exit Mechanism (`libCore.so` & `classes.dex`)**:
  - `AndroidActivityWrapper.finish()` (`classes.dex:0x18c3e8`) logs `AIR RUNTIME: finish` and terminates the Android Activity. [VERIFIED]
  - `AndroidActivityWrapper.finish()` is called via JNI from `libCore.so:0xdde188` (`com.adobe.air.AndroidActivityWrapper.finish()V`). [VERIFIED]
  - Native function `0x7469a0` invokes `AndroidActivityWrapper.finish()` via virtual dispatch. [VERIFIED]
  - Address `0x72f004` is slot `0x30` in Tamarin native method table `0x135f660` calling `0x7469a0`. [INFERRED: disassembly notes by previous agent; no disassembly listing saved in work/logs, not re-checked]
  - Embedded ActionScript bytecode in `libCore.so:0xeb57a0` (`runtime:Descriptor`, `runtime:Profiles`, `runtime:ProfileConfig`) handles runtime bootstrap, validating `application.xml`, profiles, extensions, and licensing/splash screen. [VERIFIED]
  - Embedded bootstrap scripts contain 15 calls to `ExitWithError` and 10 calls to `NativeApplication._exit()` (`multiname 45`). When validation fails, the runtime invokes native slot `0x30` (`0x72f004`), resulting in `finish()` at ~+180-210 ms. [INFERRED: the call counts are from the decompiled bootstrap; that a failing check is what drove the observed `finish` is NOT shown - no ExitWithError message was ever logged]
### 6.14 Runtime Bootstrap `ExitWithError` Call Sites Audit & Control APK Bisection
- **Bootstrap Decompilation**:
  - Embedded ActionScript ABC bytecode in `libCore.so:0xeb57a0` extracted and wrapped into SWF v31 (`work/runtime_embedded.swf`), then decompiled via FFDec to `work/runtime_scripts/scripts/runtime/`. [VERIFIED]
  - Bootstrap execution flow: `CaptiveAppEntry.as:3` -> `ExtendedAppEntry.as` / `AndroidMobileDeviceAppEntry.as:3` -> `ApplicationEntry.as:4` (subclass of `AppEntryCommon.as:8`) -> `AppRunner.as:17` -> `ContentPlayer.as:17`. [VERIFIED]
  - In `ADLAppEntry.as:230-297`, exactly 16 `ExitWithError` calls handle error dispatch from `AppRunner`, mapping directly to the error handling switch in `AppEntryCommon.as:43-97`. [VERIFIED]

- **Audit of 15 `ExitWithError` Call Sites vs `ygo_control.apk`**:
  | # | File:Line | Error / Event ID | Trigger Condition | Exit Message | Eval on `ygo_control.apk` | Evidence |
  |---|---|---|---|---|---|---|
  | 1 | `ADLAppEntry.as:233` | `ERROR_NO_DESC` (5001) | `FileUtils.readXMLFromFile(appXmlFile)` fails | `"application descriptor not found"` (code 6) | **PASS** | `assets/META-INF/AIR/application.xml` exists (7,017 B) and parses cleanly. [VERIFIED] |
  | 2 | `ADLAppEntry.as:236` | `ERROR_INVALID_DESC` (5000) | `Descriptor` validation fails / unknown namespace / patchLevel too low | `"invalid application descriptor: " + text` (code 7) | **PASS** | Namespace `http://ns.adobe.com/air/application/20.0` is in `Descriptor.as:43`. Fields `id`, `filename`, `versionNumber`, `initialWindow/content` match regexes in `Descriptor.as:1305-1456`. [VERIFIED] |
  | 3 | `ADLAppEntry.as:239` | `ERROR_NO_CONTENT` (5003) | `ContentPlayer.playContent` cannot find initial content SWF (`ENOENT` 3003) | `"initial content not found"` (code 8) | **PASS** | `MobileGame.swf` is present at both `assets/MobileGame.swf` and root `MobileGame.swf`. [VERIFIED] |
  | 4 | `ADLAppEntry.as:242` | `ERROR_LOAD_CONTENT` (5002) | Error loading SWF content or general `ContentPlayer.onError` | `"error while loading initial content"` (code 9) | **UNKNOWN** | Native loader in `libCore.so`. No error text emitted in logcat. [INFERRED] |
  | 5 | `ADLAppEntry.as:245` | `ERROR_PROFILE_NOT_SUPPORTED` (5005) | Current profile not in `descriptor.supportedProfiles` or native init fails | `"invalid profile specified '" + text + "'"` (code 10) | **PASS** | Descriptor specifies `mobileDevice` (`desktop mobileDevice`). Matches `AndroidMobileDeviceAppEntry.as:6`. [VERIFIED] |
  | 6 | `ADLAppEntry.as:248` | `ERROR_DEFAULT_PROFILE_NOT_SUPPORTED` (5006) | Default profile does not match `<supportedProfiles>` | `"default profile does not match <supportedProfile> in application descriptor"` (code 10) | **PASS** | Default profile `mobileDevice` is present in descriptor. [VERIFIED] |
  | 7 | `ADLAppEntry.as:251` | `ERROR_NOT_SUPPORTED_IN_PROFILE` (5012) | Extensions declared in descriptor but profile does not support native extensions | `text` (code 11) | **PASS** | `Descriptor.supportsNativeExtensions("mobileDevice")` is true; also tested with 0 extensions. [VERIFIED] |
  | 8 | `ADLAppEntry.as:254` | `ERROR_UNEXPECTED_PUBID` (5007) | Publisher ID present on namespace >= 1.5.3 | `"Argument -pubid not allowed with applications using the 1.5.3 or later namespace"` (code 2) | **PASS** | `META-INF/AIR/publisherid` does not exist; `pubIDLegacy == ""`. [VERIFIED] |
  | 9 | `ADLAppEntry.as:260` | `ERROR_DUPLICATE_EXTENSION` (5008), `ERROR_EXTENSION_MISSING` (5010), `ERROR_EXTENSION_DEPLOYMENT_MISMATCH` (5009), `ERROR_EXTENSION_XML_INVALID` (5011) | Duplicate ANE ID/platform, missing ANE folder, deployment type mismatch, or invalid extension XML | `"The content cannot be loaded because there was a problem loading an extension: " + text` (code 5) | **PASS / NOT CAUSE** | Purged all `<extensions>` and ANE dirs in variant (a); runtime still called `finish` at +442 ms. [VERIFIED] |
  | 10 | `ADLAppEntry.as:264` | `ERROR_EXTENSION_SWF_VERSION_INVALID` (5013), `ERROR_EXTENSION_APP_VERSION_MISMATCH` (5014) | ANE SWF version mismatch or minimum AIR version mismatch | `text` (code 5) | **PASS / NOT CAUSE** | Purged all extensions in variant (a); runtime still called `finish` at +442 ms. [VERIFIED] |
  | 11 | `ADLAppEntry.as:267` | `ERROR_ADL_SIMULATION_FAILED` (5015) | ADL simulation failure | `text` (code 12) | **PASS** | Real device execution; ADL simulation mode is not enabled (`underADL == false`). [VERIFIED] |
  | 12 | `ADLAppEntry.as:270` | Unhandled Error ID in error listener | `AppRunner` error listener default branch | `"unexpected error " + errorID` (code 5) | **UNKNOWN** | No unexpected error logged. [INFERRED] |
  | 13 | `ADLAppEntry.as:280` | `STATUS_SECONDARY` | Secondary instance detected via `LocalConnection` (`m_isForwarded == true`) | `"invocation forwarded to primary instance"` (code 1) | **PASS** | Process force-stopped before every launch (`adb shell am force-stop`); no other instance running. [VERIFIED] |
  | 14 | `ADLAppEntry.as:283` | Unhandled Status in status listener | `AppRunner` status listener default branch | `"unexpected status " + code` (code 5) | **PASS** | No status error event observed. [VERIFIED] |
  | 15 | `ADLAppEntry.as:292` | `UsageError` caught | Argument parsing / CLI usage error | `e1.message` (code `e1.exitCode`) | **PASS** | `ApplicationEntry.preprocessArguments()` strips argv[0] without CLI flags. [VERIFIED] |
  | 16 | `ADLAppEntry.as:296` | Top-level `Error` caught | Unhandled exception in bootstrap entry point | `"unknown error: " + e2.getStackTrace()` (code 5) | **UNKNOWN** | In `AppEntryCommon.as:111-114`, unhandled error directly invokes `Runtime.runtime.exit(5)`. [VERIFIED] |

- **Bisection Test Matrix on Google Pixel 10 (`ygo_control.apk`)**:
  - Tested using [`tools/bisect_control.py`](file:///e:/Documents/Docs/YGOBamPocketRevived/tools/bisect_control.py) against Google Pixel 10 (Android 17, `arm64-v8a`, serial `58051FDCR00159`):
    | Variant | Build Change Description | Survival Delta (ms) | Logcat Start -> Finish | Render Status | Result |
    |---|---|---|---|---|---|
    | **Baseline Control** | Minimal `ControlApp.swf` + full descriptor/ANE layout | +211 ms | `14:23:01.925` -> `14:23:02.136` | Black screen | Exited (`AIR RUNTIME: finish`) [VERIFIED] |
    | **(a) `variant_a_no_ext`** | Remove all `<extensions>` from descriptor + delete `META-INF/ANE` dirs | **+442 ms** | `21:49:13.024` -> `21:49:13.466` | Black screen | Exited (`AIR RUNTIME: finish`) [VERIFIED] |
    | **(b1) `variant_b1_assets_desc_only`** | Remove injected root `META-INF/AIR/application.xml` (keep only `assets/`) | +251 ms | `21:49:35.629` -> `21:49:35.880` | Black screen | Exited (`AIR RUNTIME: finish`) [VERIFIED] |
    | **(b2) `variant_b2_root_desc_only`** | Remove `assets/META-INF/AIR/application.xml` (keep only root) | +175 ms | `21:49:57.229` -> `21:49:57.404` | Black screen | Exited (`AIR RUNTIME: finish`) [VERIFIED] |
    | **(c) `variant_c_no_arm64_dup`** | Restore Android-ARM only (undo ARM64 duplication) | +177 ms | `21:50:17.600` -> `21:50:17.777` | Black screen | Exited (`AIR RUNTIME: finish`) [VERIFIED] |
    | **(d) `variant_d_mobile_only`** | `supportedProfiles = mobileDevice` | +110 ms | `21:50:39.575` -> `21:50:39.685` | Black screen | Exited (`AIR RUNTIME: finish`) [VERIFIED] |
    | **(e) `variant_e_ns_50_2`** | Update descriptor namespace to `http://ns.adobe.com/air/application/50.2` | +186 ms | `21:51:02.235` -> `21:51:02.421` | Black screen | Exited (`AIR RUNTIME: finish`) [VERIFIED] |
  - **Key Bisection Findings**:
    - None of the bisection variants survived past 500 ms or rendered their `TextField`. [VERIFIED]
    - Removing all extensions (`variant_a_no_ext`) nearly doubles survival time (+183 ms -> +442 ms), suggesting that ANE directory enumeration and parsing consumes ~230-260 ms, but exit still occurs immediately thereafter. [INFERRED: single run per variant, no repeats, no variance measured; the shift could be noise]
    - Modifying descriptor location, profiles, or namespaces shifts the exit timestamp between +110 ms and +442 ms, consistent with (not proof of) the exit being driven by synchronous bootstrap progression inside the hand-grafted captive runtime. [INFERRED: single runs]

### 6.15 Official Harman AIR SDK Verification, Device Test & APK Diff
- **Official AIR SDK Acquisition**:
  - Harman AIR SDK 51.5.1.1 for Windows downloaded from official distribution endpoint `https://assets.airsdk.dev/api/versions/51.5.1.1/sdks/AIRSDK_Windows.zip?license=accepted` (576.91 MB, extracted to `work/airsdk/`). [VERIFIED]
  - `work/airsdk/bin/adt.bat -version` confirmed `51.5.1.1`. [VERIFIED]

- **Minimal Hello-World (`work/hello_air/hello.apk`) on Google Pixel 10**:
  - Packaged via ADT: `adt -package -target apk-captive-runtime -arch armv8 -storetype pkcs12 -keystore work/debug.keystore -storepass android work/hello_air/hello.apk work/hello_air/application.xml -C work/hello_air ControlApp.swf`. [VERIFIED]
  - Note: By default without `-arch armv8`, ADT packages 32-bit `armeabi-v7a` which fails install on Google Pixel 10 with `INSTALL_FAILED_NO_MATCHING_ABIS`. With `-arch armv8`, 64-bit `lib/arm64-v8a/libCore.so` is packaged. [VERIFIED]
  - Installed and launched on Google Pixel 10 (`air.air.com.test.helloair/.AppEntry`):
    - `AIR RUNTIME: Version 51,5,1,1 - platform Android-ARM64` [VERIFIED]
    - `AIR RUNTIME: Starting in synchronous mode` [VERIFIED]
    - `AIRRuntimeCheck: AIR - showing Splash Screen - LIGHT mode` [VERIFIED]
    - `AIRRuntimeCheck: AIR - removed splash screen` [VERIFIED]
    - `AIR RUNTIME: finish` was **NOT CALLED**. The app survived past 500 ms, stayed alive indefinitely (PID 23589), and rendered the `ControlApp.swf` native `TextField` with dark green background (`0x003311` -> `RGB [0, 51, 17]`, non-black pixel count: 2,371,520). [VERIFIED]

- **Control App with YGO Package (`ygo_control_adt.apk`) on Google Pixel 10**:
  - Packaged via ADT using YGO package identity (`air.com.konami.ygo`, descriptor `application_ygo.xml` with `targetSdkVersion="28"`, icons, and `ControlApp.swf`). [VERIFIED]
  - Installed on Google Pixel 10 and launched:
    - `AIR RUNTIME: Version 51,5,1,1 - platform Android-ARM64` [VERIFIED]
    - `AIR RUNTIME: Starting in synchronous mode` [VERIFIED]
    - `AIRRuntimeCheck: AIR - removed splash screen` [VERIFIED]
    - `AIR RUNTIME: finish` was **NOT CALLED**. The app survived indefinitely (PID 24394) and rendered `ControlApp.swf` (`RGB [0, 51, 17]`, non-black pixel count: 1,166,400). [VERIFIED]

- **Structural Diff: Failing Patched Control (`ygo_control.apk`) vs Working ADT Build (`ygo_control_adt.apk`)**:
  | Dimension | Failing `ygo_control.apk` (Custom Packaging) | Working `ygo_control_adt.apk` (Official ADT) | Critical Impact |
  |---|---|---|---|
  | **DEX Architecture** | Multidex: 2015 game stub `classes.dex` (6.2 MB) + shared runtime `classes2.dex` (4.2 MB) | Single standalone captive `classes.dex` (539 KB, compiled from `runtimeClasses.jar`) | **SUSPECTED (unproven)**: In `ygo_control.apk`, `AppEntry` in `classes.dex` is the old 2015 shared runtime stub attempting to reflectively bind to shared runtime. In `ygo_control_adt.apk`, `AppEntry` is the captive runtime entry point. [INFERRED: the diff itself is real, but this row's causal contribution was never isolated] |
  | **License File** | Missing (`assets/META-INF/AIR/license.txt` absent) | Present (`assets/META-INF/AIR/license.txt`, 824 bytes, valid `LIC30...` free tier license) | **SUSPECTED (unproven)**: Modern HARMAN AIR runtime validates `license.txt` during bootstrap; without it or captive resources, it fails splash/license checks. [INFERRED: no code citation that the runtime validates license.txt; not isolated] |
  | **Captive Resources & ARSC** | Original 2015 `resources.arsc` without captive runtime drawables/layouts. Logcat: `showSplash ERROR: Resources$NotFoundException: Resource ID #0x0` | Captive `resources.arsc` + `res/layout/splash_screen_layout.xml` + `res/drawable/splash_portrait_light.png` + `res/drawable/ic_harman_logo.xml` | **SUSPECTED (unproven)**: When captive runtime initializes, it requires its bundled splash layouts and vector drawables in `resources.arsc`. [INFERRED: showSplash error is real (logcat) but no evidence it causes finish; not isolated] |
  | **Descriptor Namespace** | Injected root `META-INF/AIR/application.xml` + `assets/` with namespace `20.0` | `assets/META-INF/AIR/application.xml` only (no root descriptor), namespace `51.5` | Root descriptor is redundant; official ADT places it strictly at `assets/META-INF/AIR/application.xml`. [VERIFIED] |
  | **Native Library Packaging** | `libCore.so` stored uncompressed (method 0, 16KB ELF aligned) | `libCore.so` stored deflated (method 8, standard 4KB ELF alignment) | Method 8 compression is fully supported by Android package manager when extracted at install time. 16KB ELF alignment was not the cause of the exit. [VERIFIED] |
  | **Raw Marker Files** | Missing | `res/raw/rgba8888` (0 bytes), `res/raw/debuginfo` (0 bytes) | Bundled by ADT for display surface configuration. [VERIFIED] |

- **Re-review 2026-10-27 (Claude, takeover)**: The ADT build and the hand-grafted build differ simultaneously in DEX layout, license.txt, resources.arsc/captive resources, descriptor namespace (20.0 vs 51.5), extensions, root descriptor and zip layout. No single dimension was isolated, so none of the rows above is a demonstrated root cause. Only the aggregate is VERIFIED: hand-grafted packaging exits (`AIR RUNTIME: finish`), official ADT output of the same control SWF survives (work/logs/official_hello_air.txt, 6.15). The hand-graft path is abandoned (no libCore patches, no DEX/lib grafting); further root-causing of it has no value for the goal. [VERIFIED aggregate / INFERRED per-row]
- **License caveat**: `tools/download_airsdk.py` fetched the SDK with `?license=accepted`, i.e. the previous agent accepted the HARMAN AIR SDK license on the user's behalf. The license text shipped in the SDK is copied to `notes/AIR_SDK_license.pdf` (from `work/airsdk/AIR SDK license.pdf`) for the user to read. [VERIFIED]

### 6.16 Real game SWF packaged with official ADT (`work/game_adt_noext.apk`), 2026-10-27
- **Tooling**: `tools/build_game_adt.py` (staging + descriptor patch + ADT call), `tools/device_run.py` (install, cold launch, N s logcat, screenshot, PID sampling). [VERIFIED]
- **Inputs**: `assets/MobileGame.swf` taken from `input/ygo.apk` (sha1 c5cd0ec7...). NOTE: `work/MobileGame.swf` is NOT the original (sha1 1d8512ec...); do not use it as "the real game". [VERIFIED]
- **Staged**: 363 files from `assets/config/`, `assets/asset/`, `assets/icons/`; mmog.xml patched via `tools/patch_apk.py:patch_mmog_xml` (serverUrl / reporting serverUrl `http://ygo.eclip5e.com/facebook/proxy.html`, pvpServerUrl `...proxy.html~80~844`, openGraphServerUrl `http://ygo.eclip5e.com`). `<engine> void_list` (`0:1-live-lb-ygoa.yugioh-bam.com:9339`) left unpatched; whether HTTP mode reads it is unknown. [VERIFIED]
- **Descriptor** (`work/game_adt/application_game.xml`): `<extensions>` removed; the 7 ANE components removed (GCMBroadcastReceiver, arellomobile PushWebview/MessageActivity/PushHandlerActivity/PushGCMIntentService/AlarmReceiver, pushwoosh PushActivity); `android:usesCleartextTraffic="true"` added; PW_* meta-data and permissions kept. [VERIFIED]
- **ANE correction**: the 4 ANEs' Android platform code is Java (`nativeLibrary` = `RateBoxAPI.jar`, `libFlurryAnalytics.jar`, `libPushNotification.jar`, `AndroidIABAPI.jar` in their `extension.xml`), not 32-bit `.so`. The only `.so` in input/ygo.apk is `lib/armeabi-v7a/libNativeABI.so`. The platform is just named `Android-ARM`. The original `.ane` files are not present (the jars were merged into classes.dex). [VERIFIED]
- **Namespace**: ADT 51.5.1.1 accepted `http://ns.adobe.com/air/application/20.0` without warnings (rc 0, empty stdout/stderr, `work/logs/adt_build_ns20_sdk28.txt`). Binary manifest meta-data `namespaceVersion` = 0x41a00000 (20.0f). [VERIFIED]
- **targetSdk**: ADT keeps manifestAdditions `uses-sdk`. With the original targetSdkVersion=16: `adb install` -> `INSTALL_FAILED_DEPRECATED_SDK_VERSION: App package must target at least SDK version 24, but found 16`. Rebuilt with targetSdkVersion=28 -> install `Success`. [VERIFIED]
- **Binary manifest** (`aapt dump xmltree`, `work/logs/game_adt_noext_manifest.txt`): `usesCleartextTraffic=0xffffffff`, `debuggable=0x0`, `targetSdkVersion=0x1c`, `minSdkVersion=0xa`, `native-code: 'arm64-v8a'`, no ANE components, `.AppEntry` exported with MAIN/LAUNCHER and fb145583478967400 VIEW filter. APK contains `assets/META-INF/AIR/license.txt`, captive `classes.dex`, `lib/arm64-v8a/libCore.so`. [VERIFIED]
- **Asset diff**: every input `assets/config/**` and `assets/asset/**` file is present and byte-identical in the output APK except mmog.xml (intended); the SWF is identical. `assets/icons/*.png` are NOT under assets/ in the output: ADT turned the descriptor `<icon>` entries into `res/mipmap-*/icon.png`. No AS3 reference to `icons/` found in work/as3 (grep). [VERIFIED]
- **First device run (`work/logs/game_adt_noext_logcat.txt`, `_pid.txt`, `.png`)**: `AIR RUNTIME: Version 51,5,1,1 - platform Android-ARM64`, `Starting in synchronous mode` (22:43:02.911), `AIRRuntimeCheck: AIR - showing Splash Screen` (03.451), `removed splash screen` (07.338). No `AIR RUNTIME: finish`. PID 27944 alive in all 14 samples over 15 s. One caught exception: `ClassNotFoundException: com/adobe/fre/FREArray` (logged by AdobeAIR as "Exception caught from Java"; effect unknown). [VERIFIED]
  - **INVALID as a render/network test**: the phone was dozing with a secure keyguard showing (`mWakefulness=Dozing`, `isKeyguardShowing=true`). The log shows `wm_pause_activity ... sleep`, `Not drawing due to screen off`, `surfaceDestroyed`, `wm_on_stop_called` at 05.777. The black screenshot only shows the lock or doze state. 0 requests: local `work/server_requests.log` unchanged at 24,831 bytes (no local server listening on 8087; live server not checked). [VERIFIED]
- **Second device run, phone unlocked and awake (`work/logs/game_adt_noext_run2_logcat.txt`, `_run2.png`, `_run2_t60.png`)**: `isKeyguardShowing=false`, `mWakefulness=Awake`. PID 28696 alive for all 13 samples over 15 s and still alive at about 60 s. No `AIR RUNTIME: finish`. Splash shown at 22:45:59.259 and removed at 22:46:01.220. The screen shows the game's own Starling prelauncher: Konami tab top-left, Blue-Eyes art, "Yu-Gi-Oh! BAM Pocket" logo, a blue loading bar with a small green fill, and the Frima Studio logo cut off at the right edge. The 15 s and ~60 s frames are the same (no progress). Local `work/server_requests.log` unchanged (24,831 B); `dumpsys netstats detail` has no traffic record for UID 10325. The live server was not checked. [VERIFIED]
- **Where init stalls**: `MobileProjectEngine.as:130-157` defines 28 init steps. `UpdateProgressBar` (`:224-233`) sets progress = (stepIndex-1)/26 while step `stepIndex` runs. The measured green fill is 18 px of a ~490 px bar (x 1139-1156 of 1135-1633 at y=848 in `_run2_t60.png`), about 1/26, so the step running is index 2, `StartFlurry` (`:132`). [VERIFIED measurement / INFERRED step mapping; stage scaling ~2.3x makes a 1-stage-px minimum clip ~2 px, not 18]
- **Why it stalls**: `StartFlurry` (`MobileProjectEngine.as:737-755`) calls `FlurryAnalytics.Set*()` with no try/catch, and `ProcessNextStep()` comes only after them. `FlurryAnalytics.GetSingleton()` (`com/frimastudio/flurryanalytics/FlurryAnalytics.as:29-37`) throws `Error("FlurryAnalytics native extension is not supported on this platform.")` when `createExtensionContext` returns null (extension not packaged). The throw escapes `step.Execute()`, so the sequence never advances. Nothing appears in logcat because the release runtime does not print AS3 errors. [VERIFIED code path; INFERRED that this throw is what happened on device - no AS3 error output captured]
- **The other 3 wrappers with a null context** (next in line once Flurry is past):
  - `PushNotification.as:17-42`: null context only `trace("extCtx is null.")`, but `registerForPushNotification` (`:105-111`) calls `extCtx.call("registerPush")` whenever `isPushNotificationSupported` is true (`:74-77`, true when Capabilities.manufacturer contains "Android"). That is a null dereference (TypeError) in `InitPushNotification` (`MobileProjectEngine.as:462-472`). [VERIFIED code / INFERRED runtime]
  - `AndroidIAB.as:60-76`: constructor calls `extContext.call("ffiInitIAB")` in try/catch and rethrows `"Error initializing Android Billing protocol."`. `isSupported()` always returns true (`:90-93`). [VERIFIED]
  - `RateBox.as:60-76`, `:146-158`: `create()` path throws `"Error initializing RateBox protocol."` / `"Failed creating RateBox Extension Context."`. `isSupported()` always true (`:72-75`). [VERIFIED]
- **"Default platform" ANE route is not viable**: in every extension, the root `library.swf` is byte-identical to `META-INF/ANE/Android-ARM/library.swf` (sha1 Flurry ffc5fc10, IAB 6ade1bd6, RateBox 7276dd37, Pushwoosh ac55b234), and all contain `createExtensionContext`. These are the SWC/compile libraries, not AS3-only fallbacks. The APK has no `META-INF/ANE/default/` folder. A default-platform ANE built from these would run the same wrapper code with no native side, so the context stays null. Not attempted for that reason. The brief's claim of "AS3-only default library.swf" is false. [VERIFIED]

### 6.17 No-op stub ANEs (ADT-packaged) -> game reaches the login screen, 2026-10-27
- **Tool**: `tools/build_stub_anes.py` builds 4 ANEs under the original IDs (`com.frimastudio.FlurryAnalytics`, `com.pushwoosh.PushNotification`, `com.milkmangames.extensions.AndroidIAB`, `com.milkmangames.extensions.RateBox`), output `work/stub_anes/out/*.ane`.
  - Java: one `revival.anestub.<name>.StubExtension` (FREExtension) per extension. It registers every function name its AS3 wrapper calls (from `grep -o 'call("..."'` on the wrapper sources), logs `ANESTUB <id>.<fn>` via System.out (logcat tag `System.out`), and returns null. Compiled with `javac --release 8` against the SDK's `lib/android/FlashRuntimeExtensions.jar`. [VERIFIED]
  - AS3: the original `catalog.xml` + `library.swf` from input/ygo.apk zipped as the SWC and used as the platform `library.swf`. Wrapper code unchanged. Platform `Android-ARM64` only; no native `.so`. [VERIFIED]
  - The only non-null behaviour: AndroidIAB `ffiStartBillingService` dispatches StatusEvent code `BILLING_CONNECTION_FAILED`, level `{}`. Reason: `GooglePlayHandler.Init` (`com/frimastudio/mobile/apppurchase/handler/GooglePlayHandler.as:58-72`) waits for SERVICE_READY or SERVICE_NOT_SUPPORTED. `AndroidIAB.onExtStatus` (`AndroidIAB.as:273-306`) maps that code to SERVICE_NOT_SUPPORTED, so `OnServiceNotSupported` (`GooglePlayHandler.as:148-155`) calls `OnInitcomplete()` and marks purchases unsupported. Without it, init stalled forever at step 18 `InitAppPurchaseManager` (`work/logs/game_stubane_t2m.png`, bar about 0.63). [VERIFIED]
- **ADT behaviour, as observed**:
  - `-target ane` with the pkcs12 debug key: rc 8 `not an X509 code-signing certificate`. Built the ANEs unsigned instead (signing is optional per ADT usage text).
  - Extension namespace 33.1 with app namespace 20.0: rc 12 `Included native extension ... specifies namespace 'http://ns.adobe.com/air/extension/33.1' which is greater than the application namespace`.
  - Extension namespace 20.0 with platform `Android-ARM64`: accepted.
  - First stub version (capturing anonymous inner classes): app build rc 17, `dx tool failed ... NullPointerException ... JarClassFileReader$CreateMethodVisitor.visitParameter`. javac 21 writes nameless MethodParameters entries; rewritten with static nested classes, `javap` shows 0 MethodParameters, and ADT rc 0. [VERIFIED, work/logs/build_stub_anes*.txt, adt_build_stubane.txt]
- **APK `work/game_adt_stubane.apk`**:
  - `tools/build_game_adt.py --ns 20.0 --target-sdk 28 --extdir work/stub_anes/out`: keeps `<extensions>`, still without the 7 ANE manifest components, cleartext on.
  - Contains `assets/META-INF/AIR/extensions/<id>/META-INF/ANE/Android-ARM64/library.swf` for all 4, and all 4 `revival/anestub/*/StubExtension` classes in classes.dex.
  - On launch logcat shows `AdobeAIR: Loading extension <id> on Android-ARM64` for all 4. [VERIFIED, work/logs/game_stubane_logcat.txt]
- **Device result (`work/logs/game_stubane2_*`)**:
  - Stub calls in order: Flurry `Set*`/`StartSession`/`LogEvent` (22:58:27.916), Pushwoosh `registerPush` (27.917; the game then waits on its own 15 s timer, `MobileProjectEngine.as:688-693`), AndroidIAB `ffiInitIAB`/`ffiStartBillingService` -> `BILLING_CONNECTION_FAILED` (46.434), RateBox `ffiInitRateBox`/`ffiSetAutoPrompt`/`ffiOnLaunch` (46.656).
  - Screenshot at 22:59:00 (`game_stubane2_t80.png`) shows the **login screen**: Blue-Eyes art, "Yu-Gi-Oh! BAM Pocket" logo, a green "LOG IN" button with the Facebook logo, and a blue "PLAY OFFLINE" button. The Konami tab and the loading bar are gone. PID 30217 alive throughout, no `AIR RUNTIME: finish`. [VERIFIED]
  - The phone screen turned off at 22:57:37 (`screen_toggled: 0`, activity stopped) and back on at 22:58:24 (`screen_toggled: 1`, `wm_on_restart_called` 22:58:26.815). Init paused while stopped, so wall-clock durations from this run are not meaningful; the order of events is. The device's screen timeout is still active. [VERIFIED]
  - Server contact during `InitializeServerCom` / `LoadGameData` / `ValidateAssets` (steps 7-10): unknown. Local `work/server_requests.log` unchanged (no local server running). The live server log at ygo.eclip5e.com has not been checked. [unknown]

### 6.18 First live server contact, Play Offline, cutout/cut-off fix, close-popup fix, 2026-10-27
- **Live server log (pasted by user from ygo.eclip5e.com)**, same order for the 22:55 and 22:58 runs:
  1. `GET /crossdomain.xml` 200
  2. `POST /facebook/proxy.html` with 1 request, `com.frimastudio.snowstorm.project.player.amf.GetVersionRequest` (ExternalId ''), answered `android=1.11.2~ios=1.11.2`, cdn `ygo.eclip5e.com`
  3. `GET /external_asset/android/versionning.xml?time=...` 200 (21171 B)
  4. `GET /external_asset/android/1.11.1/versionvalidator` 200
  5. (22:58 run only, after login menu) `GET /closepopupconfig.xml?time=...` 200

  No package `.zip` was requested; the reason is unknown (packages possibly considered present or not needed yet). The first real protocol exchange (GetVersion over AMF3) works end to end. [VERIFIED by user-provided log]
- **User test**: Play Offline -> menus and a duel work (user report). [VERIFIED by user, not by me]
- **Cut-off root cause**: `Main.as:199-208` sizes the Starling viewport and stage from `DeviceManager.CapabilitieSize`, which is `Capabilities.screenResolutionX/Y` (`DeviceManager.as:129`), i.e. the full 2424x1080 panel. With the default display-cutout mode, Android gives the window only 2251x1080 (`surfaceChanged -- format=1 w=2251 h=1080`, game_adt_noext_run2_logcat.txt): 173 px black on the cutout side, and the 2424-wide frame loses its right 173 px. [VERIFIED surface size + code; that screenResolutionX reports 2424 is INFERRED from the 2424-2251=173 geometry]
- **Fix**: `<android><displayCutoutMode>shortEdges</displayCutoutMode>`. ADT at namespace 20.0 rejects it: `error 103: application.android.displayCutoutMode is an unexpected element/attribute` (work/logs/adt_build_cutout_ns20.txt). The element first appears in `templates/air/Descriptor.51.1.xsd`, so the descriptor namespace is now **51.1** (lowest that allows it; `namespaceVersion` meta-data 0x424c6666). Build: `python tools/build_game_adt.py --ns 51.1 --target-sdk 28 --extdir work/stub_anes/out --cutout shortEdges --out work/game_adt_cutout.apk`. [VERIFIED]
- **Device result (`work/logs/game_cutout_*`)**: `surfaceChanged -- format=1 w=2424 h=1080`. Login screen, Login Advantages popup, hub (gear at the left margin, LOG IN at the right margin) and Story map (back arrow flush top-left, sidebar intact) all render full width, nothing clipped. Play Offline from the login screen goes through the "LOGIN ADVANTAGES" confirmation to the hub. Minor: in the close popup some lines overrun the right edge of the text box by a few px ("BAM", "in"); likely font metrics, not investigated. [VERIFIED]
- **"Retired as of January 1 1970" popup**: `LoginModule.as:114-141` fetches `http://<PackageUrlServer>/closepopupconfig.xml`. Each child element becomes GameSettings `close_config_content_<lang>`, and the root `@transactionDate`/`@closeDate` become the dates. `ShowLoginMenu` (`LoginModule.as:435-446`) calls `PopupManagerUtil.ShowApplicationClosePopup()` unconditionally (`PopupManagerUtil.as:125-161`): it can't be suppressed from the server, only its text set. The previous server body had empty dates and no `<en>`/`<fr>`, so the client kept Konami's default text (`EGameSettings.as:89`) with an empty date, rendered as 1 January 1970. [VERIFIED code + screenshot game_cutout_offline2.png]
  - Server fix (`server/server.py` `CLOSE_POPUP_CONFIG_XML`): same shape as the shipped `assets/config/closepopupconfig.xml` (`<content transactionDate closeDate>` + `<en>`/`<fr>` CDATA), dates `08/31/2016 16:00:00 UTC-0700` (original close date), short preservation-server text. Verified locally (XML parses, root/children correct). Not yet deployed or seen on device. [VERIFIED local only]
- **Server `/_logs` endpoint**: `GET /_logs?n=N` (max 2000) returns the tail of `work/server_requests.log`. Returns 404 unless env `YGO_LOG_TOKEN` is set and header `X-Log-Token` matches (hmac.compare_digest). The token is never in the URL, so it is never logged. Local test: no token 404, wrong token 404, correct token 200. `tests/test_amf_requests.py` still passes. [VERIFIED local]

### 6.19 Live log endpoint, new close popup, fresh-install package download, 2026-10-27
- **`/_logs` on the live server**: HTTP 200 with the token header; earlier unauthenticated attempt from the user's IP logged as 404 at 23:29:02. Tails saved to `work/logs/live_server_tail.txt`. [VERIFIED]
- **Close popup**: after deploy, the hub popup shows the new preservation-server text with "%close_date%" rendered as "August 31 2016" (`work/logs/game_run3_popup.png`). [VERIFIED]
- **Why the main install never requested packages**: `ExternalFileControllerImpl.ValidateAsset` (`ExternalFileControllerImpl.as:217-282`) only queues a package when `File.applicationStorageDirectory/<path>/<name>_version` is missing or differs from the manifest version (`ValidateVersion`, `:609-631`). The main install `air.com.konami.ygo` (firstInstallTime 2026-10-27 01:26:47; all later builds were updates, so data was kept) skips the download, so its app storage already passes that check. What exactly is in it (earlier agent's restore?) is unknown: not readable without root, and `dumpsys diskstats` gives no per-package sizes on this build. [VERIFIED code + behaviour / INFERRED storage contents]
- **Fresh-install test without touching the user's save**: `tools/build_game_adt.py --app-id com.konami.ygo.dltest` (also renames the C2D permission names) -> `work/game_dltest.apk`, Android package `air.com.konami.ygo.dltest`, installed side by side. [VERIFIED]
  - Startup -> "EXTRA CONTENT REQUIRED / Download size: 84.65 Mb / DOWNLOAD NOW" (`work/logs/dltest_t75.png`).
  - After DOWNLOAD NOW the live server log shows all 26 packages `GET /external_asset/android/1.11.1/<pkg>.zip -> 200` between 23:37:06 and 23:37:35 (series1 27,107,232 B, series2 27,107,233 B, anim, common, cardgamebg, mapbackground, mapcharacter, maplibrary, mappreview, arena, cardgamecommon, crafting, deckbuilder, duelground, filters, hud, login, livepvpgame, mainmenu, shop, tournament, transition, world, menubackground, guild, font), then `closepopupconfig.xml` (login menu) at 23:37:38. [VERIFIED]
  - Fresh copy reached the login screen, then Play Offline -> hub with the new popup, then Story world map "ALBA LITORA" with a new player's values (200 energy, 10 DP, 100, 1,000). [VERIFIED screenshots dltest_*]
  - Deck editor collection shows the 5 starter cards (3x each). Two images were blank red frames at first and appeared within ~8 s (lazy load): `dltest_back1.png` vs `dltest_collection2.png`. [VERIFIED]
  - A new deck in the test copy got the name "test" while I dismissed the keyboard (probably a keyboard suggestion tap). Test copy only, not the user's install. [VERIFIED]
- Still open: series1/series2 both contain all card images (sizes nearly identical), whereas the manifest sizes suggest a real split; it works because both carry everything. Duel on a fresh install not yet tested by me; the user reported duels work on the main install. [unknown/INFERRED]

### 6.20 Free purchases (BAM Pro + currencies) without Facebook login, 2026-10-28
- **Purchases are granted client-side, no receipt validation**: `AppPurchaseHandlerImpl.OnPurchaseComplete` (`com/frimastudio/mobile/apppurchase/AppPurchaseHandlerImpl.as:124-160`) adds `product.CurrencyQty` via `CurrencyManager.UpdateCurrency`, or for BAM Pro runs `ManageBamPro` (`:302-314`: `IsBamPro = true`, plus `BamProRewardValue` DP if not already a Facebook-save Pro). The success event comes only from the store handler -> AndroidIAB ANE (`handler/GooglePlayHandler.as:208-282`). Pro is persisted in the local JSON save (`isPremium`, `YGOMDataImpl.as:735-752`). [VERIFIED code]
- **Products** (`apppurchase/enum/EAppPurchaseProduct.as:10-40`): `com.konami.ygo.bampro`, and DP/CP/cash `tiny|small|medium|big|huge` bundles (DP 50/110/250/700/1500, CP 200/400/1000/2200/5000, cash 4000/8000/200000/440000/1000000). [VERIFIED]
- **Login gates on purchases**: `BamProPopup.PurchaseBamPro` (`project/bampro/popup/BamProPopup.as:177-197`), `CurrencyPopup.OnPurchaseProduct` (`module/shop/view/popup/CurrencyPopup.as:212-235`) and `BamProHandlerImpl.GateBamPro` (`project/bampro/BamProHandlerImpl.as:62-78`) require `YGOMLogin.IsLogguedIn()`, which needs a Facebook user AND a game-server login (`project/login/YGOMLoginImpl.as:82-95`). Facebook URLs are hardcoded statics (`com/facebook/graph/core/FacebookURLDefaults.as`), so a server-only bypass is impossible. [VERIFIED]
- **Offline currency purchases would hang**: `PurchaseProduct` (`AppPurchaseHandlerImpl.as:~205-231`) runs `PlayerManagerGT.CheckSavedDateServer` for non-Pro products. Offline, `GetLastSavedDateServer` returns early (no Facebook user, `project/player/PlayerManagerGT.as:113-121`) and the 5 s timeout dispatches nothing (`:84-88`). [VERIFIED code]
- **Currency buy buttons are server-gated**: `CurrencyPopup.UpdateTransactionTime` (`CurrencyPopup.as:110-116`) enables them only while `PlayerManager.PlayerDate < close_popup_transaction_date`, i.e. the `transactionDate` attribute of `/closepopupconfig.xml`. With 2016 the buttons were dead (tap did nothing, `work/logs/freebuy_dp_after.png`). Only CurrencyPopup reads that date for gating; `closeDate` is display text only (`PopupManagerUtil.as:133-156`). [VERIFIED code + device]
- **Implementation**:
  1. `tools/build_stub_anes.py`: the AndroidIAB stub is now a free billing emulator (`revival.anestub.androidiab.StubExtension`). `ffiStartBillingService` -> `BILLING_CONNECTION_READY`. `ffiLoadInventory` -> `INVENTORY_LOADED` (requestId echoed, owned purchases, and for detail requests every sku with price "Free"). `ffiPurchaseItem` -> `PURCHASE_SUCCEEDED`. `ffiConsumeItem` -> `CONSUME_SUCCEEDED`. `ffiLoadInventory` was missing from the earlier no-op stub (called via `setTimeout(extContext.call, ...)`, `AndroidIAB.as:406-409`). [VERIFIED]
  2. `tools/patch_swf.py`: same-length ABC byte patches, resolved per DoABC2 tag (the SWF has 2929, one per class).
     - `callproperty IYGOMLogin::IsLogguedIn,0` -> `pop; pushtrue; nop` in PurchaseBamPro (x2), OnPurchaseProduct (x2) and GateBamPro (x1).
     - In `AppPurchaseHandlerImpl.PurchaseProduct`, `getproperty BAM_PRO` before `ifne` -> `pop; dup`, so every product takes the direct `mStoreHandler.BuyProduct` path, skipping the save-date check.

     Verification: decompressed SWF bodies identical in length, 16 bytes differ; FFDec 26.4.0 P-code export of the 4 classes differs from the original only at those 6 instructions, all branch labels unchanged (`work/logs/patch_swf_pcode_diff.txt`). [VERIFIED]
  3. `tools/build_game_adt.py --swf work/game_adt/MobileGame_patched.swf` -> `work/game_freebuy.apk`. The `com.android.vending.BILLING` permission is now removed from the descriptor. [VERIFIED]
  4. Server `closepopupconfig.xml`: `transactionDate="12/31/2099 ..."`, text updated (purchases free). [VERIFIED local parse; NOT yet deployed]
- **No-money guarantee**: the APK's dex contains no `com/android/vending/billing`, `IInAppBillingService` or `com/android/billingclient`; `aapt dump badging` shows no BILLING permission. The only purchase handler is the emulator, which never contacts any store. [VERIFIED]
- **Device (clean install, `work/logs/freebuy_*`)**:
  - Download -> Play Offline -> hub. Emulator up (`BILLING_CONNECTION_READY`, 00:04:46).
  - UPGRADE TO BAM PRO -> UPGRADE NOW: log shows `INVENTORY_LOADED` (requestId 20, all skus "Free"), then requestId 10, then `PURCHASE_SUCCEEDED` sku `com.konami.ygo.bampro`. Upgrade button disabled, hub shows the PRO badge, the upgrade banner is gone, Arena lost its PRO lock, DP 10 -> 35 (+25 Pro bonus). No login prompt.
  - After force-stop + relaunch the PRO badge is already on the login screen (persisted).
  - Currency shop lists every bundle as "Free", but taps did nothing until the server transactionDate change is deployed. [VERIFIED]
- **Cloudflare caching (INFERRED)**: on the clean install the client downloaded all packages, yet the origin log shows no `.zip` request between 00:01:59 and 00:04:44, so Cloudflare probably served them from its edge cache. Not yet checked via response headers.
- The BAM Pro popup still shows "ONLY $ 4.99 USD" (`EAppPurchaseProduct.DefaultPrice` before item details load). Cosmetic only. [VERIFIED screenshot]
- **Currency purchases after deploying `transactionDate` 2099 (2026-10-28, `work/logs/cur_*`)**:
  - Live `/closepopupconfig.xml` served the 2099 date; the client fetched it at 00:11:47. The currency buy buttons are enabled (green).
  - First tap of a session only loads item details. `CurrencyPopup` calls `AppPurchaseHandler.LoadData` while `IsInit == false` and does not auto-buy (`CurrencyPopup.as:219-224`, unlike `BamProPopup`). Labels change from the SWF default prices ($99.99 ...) to "Free". The second tap buys.
  - DP huge bundle: `PURCHASE_SUCCEEDED` -> `INVENTORY_LOADED` -> `CONSUME_SUCCEEDED` for `com.konami.ygo.dphugebundle`, DP 35 -> 1,535.
  - CP huge bundle: CP 100 -> 5,100.
  - Cash huge bundle: 1,000 -> 1,001,000.
  - After force-stop + relaunch, Story shows DP 1,535 / CP 5,100 / 1,001,000 (persisted in the local save). [VERIFIED]
- Remaining cosmetic issues: until the first tap per session, shop buttons show Konami's default dollar prices and the Pro popup shows "ONLY $ 4.99 USD"; the first currency tap only loads details. Nothing can be charged either way (no billing code in the APK). [VERIFIED]

### 6.21 Price labels, first-tap buy, purchase success popup, 2026-10-28
- **Pro popup price** is localisation text, not a store price: key `bam_pro_price` (`project/bampro/enum/EBamProLoc.as:18`, used at `BamProPopup.as:109`). `.ace` files are zlib-compressed AMF-ish data with length-prefixed strings. `tools/build_game_adt.py` `LOCALIZATION_PATCHES` replaces same-length: en `bam_pro.ace` + `localization_section.ace` "ONLY $ 4.99 USD" -> "FREE OF CHARGE!"; fr `localization_section.ace` "SEULEMENT $ 4.99 USD" -> "TOTALEMENT GRATUIT !". [VERIFIED device: a_propopup.png]
- **Prices at startup / first tap**: `MobileProjectEngine.LoadAppPurchaseData` (`MobileProjectEngine.as:769-788`) loads store details only if `YGOMLogin.IsConnected()`. Patched `callproperty IYGOMLogin::IsConnected,0 -> pop; pushtrue; nop; nop` (same length, P-code diff verified, `work/logs/patch_swf_pcode_diff2.txt`). Result: the shop shows "Free" on first open and the first tap buys (DP 35 -> 85 with one tap, a_shop_first.png / a_shop_buy.png). [VERIFIED]
- **Success popup**: FFDec `-replace` with edited P-code of `AppPurchaseHandlerImpl/private:OnPurchaseComplete` (method body index 10 in its DoABC2 tag; `tools/patches/AppPurchaseHandlerImpl.OnPurchaseComplete.pcode`). It inserts `PopupManagerUtil.ShowInfo("Success","Purchase complete.")` after the success branch dispatches PURCHASE_COMPLETED.
  - An unchanged FFDec round trip of that method gave a byte-identical decompressed SWF.
  - The patched P-code diff shows exactly the 6 inserted instructions, with labels shifted by 16.
  - On device: an InfoPopup "Success / Purchase complete. / OK" after both the Pro and the DP purchase (a_pro_success.png, a_shop_buy.png). [VERIFIED]
- Pipeline now: `tools/patch_swf.py` (5 same-length byte patches at 7 sites, then the FFDec P-code replacement) -> `work/game_adt/MobileGame_patched.swf` -> `tools/build_game_adt.py --ns 51.1 --target-sdk 28 --extdir work/stub_anes/out --cutout shortEdges --swf work/game_adt/MobileGame_patched.swf --out work/game_freebuy.apk`.

### 6.22 Custom login + online features: feasibility analysis, 2026-10-28
**Verdict: technically possible without contacting Facebook.** No blocker found in transport, crypto or login. Effort is substantial: every online feature needs server-side logic re-derived from client code (no original server code or traffic captures exist).

- **Facebook login is OAuth implicit flow through a StageWebView, URLs are static strings**:
  - `com/facebook/graph/core/FacebookURLDefaults.as` holds the URLs as static vars: GRAPH_URL, AUTH_URL, LOGIN_SUCCESS_URL, ...
  - `MobileLoginWindow.open` loads `AUTH_URL?client_id&redirect_uri=LOGIN_SUCCESS_URL&display&type=user_agent&scope` (`facebook/graph/windows/MobileLoginWindow.as:31-60`). `handleLocationChange` takes the URL variables (access_token, expires_in) once the web view reaches LOGIN_SUCCESS_URL (`:62-82`).
  - Then `FacebookMobile.verifyAccessToken` calls `api("/me")` and takes `uid = result.id` (`frimastudio/snowstorm/project/facebook/FacebookMobile.as:211-232`, `:283-303`).
  - Plan: repoint these statics to ygo.eclip5e.com (FFDec P-code replace of the class initializer). The server then serves its own login page and a minimal Graph API (/me, friends, picture). [VERIFIED code; plan INFERRED]
- **Game-server login** (`core/authentication/BaseAuthentication.as` MultiStepAuthentication): connection check -> GetTokenRequest (response: token, seed) -> InitializeSecureProtocol -> LoginRequest{token, name, password} -> GetServerTimeRequest -> LOGIN_SUCCESS.
  - name and password are `ManagerA.RSA.EncryptToBytes` with the key from `config/publickey.xml` (`Engine.as:395-420`). That file is a plain APK asset, so we can ship our own key pair and the server can decrypt. Konami's private key is not needed.
  - The engine calls `Login(OwnUser.uid, AccessToken)` (`project/login/YGOMLoginImpl.as:217-240`), so name = Facebook uid and password = access token.
  - Then: PvP login (`YGOMPvPLoginImpl`, same HTTP proxy via pvpServerUrl) -> `YGOMData.Load` -> GetRewards / GetTournamentReward (`YGOMLoginImpl.as:117-131`). [VERIFIED code]
- **No ARC4 in HTTP mode**: `CallXTAMF` uses `SerializeSocketMessage` (the only `EncryptionStrategy.Encrypt` call, `common/core/engine/EngineServerCom.as:342-377`) only when the connection is not HTTP (`:330-332`). On receive, HTTP forces flags = COMPRESSED and never decrypts (`:491-501`). The HTTP send path is `writeUTF(ExternalId)` + AMF + zlib (`common/core/servercom/ServerComHTTP.as:384-387`). [VERIFIED code]
- **PvP transport is HTTP too**: `EngineServerComPvp.Init` uses `ServerURLParser("http","pvpServerUrl")` -> ServerComHTTP (`common/core/engine/EngineServerComPvp.as:9-18`). The "policy port" only affects the Flash policy file. Cloudflare Tunnel can carry it. [VERIFIED code]
- **Server surface per feature** (request / notification classes in `project/*/amf`):
  - arena: 6 requests (GetDuelArena, StartDuelArena, CompleteDuelArena, PayDuelArena, SetDuelArenaDeck, GetDeckByExternalId)
  - tournament: 6 requests + 4 notifications
  - guild (teams): 8
  - readyforcombat (friends duel / matchmaking / PvP queue): 11 requests + 8 notifications
  - livepvp (real-time duel): BamReady, StartRound, BamEnd + 6 notifications
  - relation: FriendHelp, GetRelationsProject
  - league: 2 + 3 notifications
  - player / save: GetPlayerInfo, Get/SendPlayerSave, GetLastSavedDate, SendPlayerInfo
  - plus inventory, energy, quests, worldmap, rewards that the game calls once online.

  Notifications are server pushes; in HTTP mode they presumably ride along in response arrays. That mechanism is not yet verified.
- **Hard parts**:
  - Live PvP is the hardest: the duel is client-simulated with checksums (ChecksumErrorNotification), and the server only relays rounds. It needs two devices to test.
  - Friend invites / "inviting" use Facebook apprequests (`FacebookManagerMobile.as`), which would need the fake Graph API too.
- **Proposed phases**:
  1. Custom login + online save (fake Facebook OAuth + Graph /me, own RSA key, Token / Login / ServerTime / PvP login, GetPlayerInfo, Get/SendPlayerSave, GetLastSavedDate, rewards returning empty).
  2. Friends (account-based friend list via fake Graph friends + GetRelationsProject), friend help, friends duel vs AI deck (GetDeckByExternalId).
  3. Arena, tournaments, leagues, guilds (server-side state and leaderboards).
  4. Live PvP (queue, accept, round relay, end).

### 6.23 Phase 1 implemented: custom login + online save (2026-10-28, dev-tested on device via adb reverse)
- **SWF**: `tools/patch_swf.py --fb-base <url>` repoints 12 constant-pool strings (FacebookURLDefaults statics, FacebookManagerMobile.Authorize OAuth URL, FacebookMobile logout) to the server's `/fb`. Pool strings are rewritten per DoABC2 tag and tag headers rebuilt; FFDec decompiles the patched classes cleanly. [VERIFIED]
- **APK**: `config/publickey.xml` = own 1024-bit key (`tools/gen_rsa_key.py`; private key `server/data/rsa_private.json`). [VERIFIED]
- **Server**:
  - `server/accounts.py`: accounts with PBKDF2 hashes, access tokens, per-uid saves.
  - `server/fakefb.py`: login/register page, `/fb/graph/[v2.0/]me`, `/<id>`, `/<id>/picture`, FQL friends = [].
  - `server/game.py`: GetToken (session cookie), RSA Login (main: uid + access token; PvP: "-1_<uid>"/"frima", accepted only via the linked main-session cookie), GetServerTime, Get/SendPlayerSave, GetLastSavedDate, GetPlayerInfo (null), GetRewards / GetTournamentReward (empty), AccidentalZero, GetTournamentInfo (always an active template 2..21, 14-day rotation; a null tournament hangs the PvP login, TournamentManager.as:383-393), GetTeam (0), GetGlobalInfo, GetCombats ([]).
  - `tests/test_login_flow.py` end-to-end; `tests/test_amf_requests.py` updated; all pass. [VERIFIED]
- **Device results**:
  - LOG IN opens our page in Chrome; register/login redirects to `fb145583478967400://authorize#access_token=..` and the app resumes.
  - Main + PvP login OK, LOG IN button gone. AIR on Android sends cookies (verified). The client asks for `/fb/graph/v2.0/me` (versioned path).
  - Auto-login at app start with the cached token reaches the hub.
  - The online save upload is triggered by a currency purchase (24,807 B, a real JSON save).
  - Fresh reinstall + login -> the game's own SYNC dialog (device vs server). Choosing the server restores DP 135. [VERIFIED]
- **Known gaps**:
  - BAM Pro is not restored on a new install: Pro comes from the store entitlement / device save, not the cloud save (`YGOMDataImpl.SetBamProData`). Re-buying is free and gives no second DP bonus.
  - Phase 2+ features (friends, arena, PvP, guilds, tournaments) not implemented.
  - Release APK `work/game_release.apk` built but not yet tested against the deployed server.
