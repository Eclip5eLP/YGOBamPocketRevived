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

### 6.24 Repo, deploy path, auto-reload (2026-10-28)
- Git repo initialised by the user; first commits `dfdd47c`, `8d9b7a3`. `.gitignore` excludes game data (input/, work/, apk/swf/ane/ace/sav), third-party tools (FFDec, AIR SDK, Harman license PDF), server secrets and user data (server/data/* except publickey.xml), env/dev files. `.gitattributes` forces LF (run.sh / service file run on Linux).
- `tools/patch_swf.py` no longer ships disassembled game code: the OnPurchaseComplete P-code is exported from the SWF at build time and the 6 instructions are inserted after an anchor (PCODE_INSERTIONS). Output byte-identical to the previous build (decompressed SWF compared). [VERIFIED]
- Deployment = `Y:/Documents/PythonBots/YGOBamPocketRevival/` (a network drive mapped to the server). No SSH login is available to me, so `server.py` now re-execs itself when `server/*.py` change and compile (`watch_and_reload`, `--no-auto-reload` to disable). Tested in a scratch copy: change -> reload; syntax error -> skipped with warning, server keeps running. In-memory sessions are lost on reload. Needs one manual service restart to activate. [VERIFIED locally]
- Live login test on ygo.eclip5e.com: pending. I don't create accounts on the production host, so the user runs it. `work/game_release.apk` installed on the Pixel.

### 6.25 Phase 2: friends, friend duels, invites (2026-10-28)
- **How friend features work client-side** (work/as3):
  - Duel Ground lists `FacebookManagerMobile.GetFriendList(true)` = FQL rows with is_app_user (`module/duelground/DuelGroundModule.as:379-383`).
  - A friend duel is an AI duel against the friend's deck from `GetDeckByExternalIdRequest{externalId}` -> `deck` = comma-separated card template ids; empty = client default deck (`:536-575`, `project/arena/ArenaManagerYGO.as:320-349`). Duel results and friend-help cooldowns live in the client save (`FriendDataUtil.FriendReadyForHelp`).
  - `RelationManagerProject.OnFriendHelpRequested` has no callers, so FriendHelpRequest is never sent.
  - Invite: `InviteFriendsPopup` lists GetFriendList(false). `FacebookManagerMobile.InviteFriends` opens `/dialog/apprequests?to=..&access_token=..` in an in-game StageWebView; it closes when the location reaches LOGIN_SUCCESS_URL (`DialogWindow.as`; `#_=_` = failure). [VERIFIED code]
- **Implementation**:
  - `accounts.py`: friends.json (mutual friends + outgoing requests); players/<uid>.json (arena deck, relation timestamps).
  - `fakefb.py`: FQL returns friends (is_app_user true) + all other players (false, "(!) " prefix when they requested you); `/fb/dialog/apprequests` turns invites into friend requests (mutual invite = friends), compact page, Close -> redirect_uri.
  - `game.py`: GetDeckByExternalId (Arena deck -> isDefaultDeck items -> 15 strongest collection cards, max 3 copies), SetDuelArenaDeck, GetRelationsProject, CompleteDuelFriend, FriendHelp.
  - `patch_swf.py`: DialogWindow URLs -> `<fb>/dialog`.
  - `server.py`: ping-only batches logged at debug.
  - `tests/test_friends.py` passes. [VERIFIED]
- **Device** (dev server, devtester + devfriend):
  - MAIN MENU shows Arena / Teams / Friends / Tournament enabled.
  - FRIENDS DUEL GROUND lists devfriend with FIGHT!. FIGHT -> GetDeckByExternalId -> duel devtester vs devfriend (3600 LP). Surrender -> DUEL REWARD (+1 CP) and online save upload.
  - ADD FRIENDS lists the other registered players. Selecting one + INVITE FRIENDS -> our page in the in-game web view ("request sent"); Close returns to the game. [VERIFIED screenshots work/logs/p2_*]
- **Limits**: new friends appear only after the game logs in again (the FQL friend list is fetched at login). Real-time PvP, Arena, Teams and Tournaments are not implemented.
- Deployed to Y: (auto-reload worked, 03:51:35); release APK rebuilt with the dialog patch and installed on the Pixel.

### 6.26 Login kept across connection loss; remembered browser login; minimal pages

- **Cause of "logged out after connection loss"** [VERIFIED]: `FacebookManagerMobile.InitFacebook` sends the saved
  token (SharedObject "diskCache") to Graph `/me` via `FacebookMobile.init` -> `verifyAccessToken`
  (`work/as3/.../project/facebook/FacebookMobile.as:191-245`). Any failure calls
  `OnInitFacebookComplete(null, error)` -> `OnLoginFailed(true)`, which clears diskCache
  (`FacebookManagerMobile.as:89-94, 221-233`). With no token, `YGOMLoginImpl.IsNewLogin` is true and LOG IN opens
  the browser (`YGOMLoginImpl.as:192-215, 501-521`).
  - **Network failure reproduced**: live release build, airplane mode → CONNECTION LOST → PLAY OFFLINE → network
    back → LOG IN opened Chrome (live log 04:07:45).
  - **Your earlier logout** at 03:52:42 was a different trigger: the live `/me` returned 400 for a token issued by
    the local dev server, because the release build was installed over the dev build.
- **Network vs rejected-token failure** [VERIFIED]: a network failure passes the `IOErrorEvent` (empty body) or
  `SecurityErrorEvent` as the error (`AbstractFacebookRequest.as:160-198`). A JSON reply with `error_code` is passed
  as the parsed object (`AbstractFacebook.as:147-154`).
- **Client fix** (`tools/patch_swf.py` PCODE_INSERTIONS, `OnInitFacebookComplete`, body index 4): if `aFail` is
  non-null and has no `error` property → `OnLoginFailed(false)` + return. Otherwise the original wipe runs.
  FFDec decompiles it as intended.
- **Server change**: `/me` for an unknown token now answers HTTP 200 `{"error":{...},"error_code":190,...}`. The
  client reliably gets an object with `error` and clears the token, so a player is never stuck with a dead token.
- **Device test** (dev build, local server) [VERIFIED]:
  1. Logged in, then removed `adb reverse` → CONNECTION LOST → PLAY OFFLINE → restored the route → LOG IN logged
     straight in with the stored token. No browser; `/me` 200, Login OK main + pvp.
  2. Deleted that token server-side and restarted → `/me` error → LOG IN opened the browser.
- **Remember cookie** (`server/fakefb.py` REMEMBER_COOKIE, `Path=/fb/`, 60 days, HttpOnly, SameSite=Lax): every
  successful login sets it. The OAuth page then shows only "Continue as <name>" / "Use another account".
  - Device: one tap → app (log "FB: remembered login", Login OK). [VERIFIED]
- **Pages trimmed**: title + inputs + two buttons. No explanatory text; the redirect page is only a fallback
  button. Invite page lines shortened.

### 6.27 Phase 3a: Arena + leaderboards; sessions survive restarts

- **Client flow** [VERIFIED code]:
  - ArenaModule.InitQueue (`module/arena/ArenaModule.as:224-238`): LoseUnfinishedDuels → SetDuelArenaDeck →
    CompleteDuelArena for pending duels → GetDuelArena{cardTemplatesId} → GetHighScores.
  - StartDuelArena is cache-only on the client (`ArenaManagerYGO.as:171-188`): no request was seen on the device.
    A surrendered arena duel is reported as DEFEAT the next time the Arena opens (seen on the device, log 04:25:34).
  - `LoadOpponentName` waits for one Graph name per duel and never completes with 0 duels
    (`ArenaManagerYGO.as:351-372`), so there are always 5 duels (NBR_DUELS, `ui/ArenaModuleUI.as:44-46`).
  - DuelDisplay needs matchScore/50 to be a multiplier of 1/2/4/8/16 (`ui/DuelDisplay.as:170-195`,
    `EArenaConst.as:6`). CompletedDuelBlocker offers new duels at lastDateGenerated + 1 day for nextResetCost
    (`ui/CompletedDuelBlocker.as:94-99`).
  - PayDuelArena: the client checks and deducts INGAME coins itself (`ArenaManagerYGO.as:130-154`).
  - GetHighScoresResponse fields: `leaderboardygo/amf/*`. playerHighScoreWeekly is used without a null check in
    ArenaModule.ValidateArenaQuest, so it is always sent.
- **Server rules** (`server/arena.py`, our design; the original logic is unknown) [INFERRED design]:
  - 5 opponents per day: real players first, then practice bots (uid 900000000+n, names served by fake Graph)
    using a real deck.
  - Win = 50 × stage multiplier and the stage goes up; a loss resets the stage.
  - Reset costs 100 coins.
  - Weekly score and all-time score; a real opponent's aiVictories/aiDefeat record how its deck did.
- **Sessions**: game sessions were in memory only, so every server restart (deploy, auto-reload) made the phone's
  next request fail with "no logged-in session". Seen on the device: SendPlayerSave rejected, Pro popup stuck.
  Logged-in sessions are now persisted to `server/data/sessions.json` (7 days).
- **Tests**: `tests/test_arena.py` (two accounts): duel set, scores 50/100/0/50, bonus, idempotent completion,
  deck stats, code -1, leaderboards, paid reset. All OK. A bot fill on an empty store gives 5 named bots.
- **Device** (dev build) [VERIFIED screenshots work/logs/p3_*]:
  - Free Pro → ARENA shows 5 opponents with scores and the Next Win ladder 50..800.
  - FIGHT starts the duel with the opponent's deck (friend help offered). Surrender → loss reported.
  - STATISTICS shows 0-1 and deck 1-0.

### 6.28 Phase 3b: Teams, tournament registration and leaderboards

- **Teams** [VERIFIED code: `project/guild/GuildManager.as`, see `server/teams.py` docstring]:
  - JoinTeam (the server picks the team), CancelJoinTeam, GetTeam, guild GetPlayerInfo, GetTeamInfo
    (rank, score, top50).
  - Team contribution: GetNewScoreToken + NewScore (the token is single use).
  - 20 teams (`config/ace/guild/guild_team_template.ace`).
  - Our rules [INFERRED design]: you join the least populated team; scores are weekly, using the same week
    boundary as GetGlobalInfo.nextResetDate.
  - Weekly team reward bundles are NOT handed out yet.
- **Tournament** [VERIFIED code]: registered = a TournamentLevel exists (`module/tournament/util/TournamentUtil.as:53`).
  - GetTournamentInfo now returns a null level until RegisterTournament. The client pays the 5 DP entry fee
    locally (`logic/BuyTournamentEntryFeeFlow.as`).
  - Start level 81 = rank 15 / token 0 (`config/ace/tournament/tournament_level_template.ace`; ladder via
    levelTemplateAfter/Before).
  - Top / previous leaderboards are served; CancelTournamentMatch returns OK.
- **Server pushes (needed for phase 4)** [VERIFIED code]: every element of a response array is broadcast to its
  message listeners (`common/core/engine/EngineServerCom.as:520-543`), so notifications (PlayCombatNotification,
  PlayCombatEndNotification, ...) can ride on any response, e.g. the PvP ping (`mmog.xml`
  ping_pvp_frequency 2000 ms).
  - Tournament matches (PlayCombatTournament → notification → live duel) are real-time PvP and belong to phase 4.
- **Arena**: friends are drawn first as opponents.
- **Tests**: `tests/test_teams.py` OK. Arena, friends, login and AMF tests still OK.
- **Device** (dev build) [VERIFIED screenshots work/logs/p3_14..21]:
  - Teams: FIND A TEAM → "Welcome to Team Akiza" → MY TEAM (rank, time left, members).
  - Logging in with a null tournament level works.
  - Tournament: SIGN UP (5 DP) → RegisterTournament → "Please build a Dark deck" (the deck rule of template 21).
- **Popup text** updated (Friends / Arena / Teams available, live duels not yet). The heredoc route turned `\x`
  into `\x`; it was fixed via a script file. Auto-reload refused the broken file (compile check), so the live and
  dev servers kept running.
- **Deployed** to Y: (live reload 04:33:47; checked: popup, login page, /me error JSON).
  - Release APK rebuilt with the keep-login patch and installed. It shows LOG IN once, because the dev-server
    token on the phone is not valid on live.

### 6.29 Production release 1.0.0 (2026-10-28)

- **Name "Yugioh BAM Pocket Revived"** everywhere users see it:
  - login page title / h1 (`server/fakefb.py`);
  - startup popup (`CLOSE_POPUP_CONFIG_XML`);
  - server banner;
  - APK launcher label: descriptor `<name>`/`<filename>` via `build_game_adt.py --name`; versionName 1.0.0 via
    `<versionLabel>`.
- **Startup popup** [VERIFIED code]: BigInfoPopup renders the text with `htmlText` and then `setTextFormat` for the
  whole field (`AssetCreationUtil.GetImageFromHtmlTextField`, `AssetCreationUtil.as:100-135`) into a bitmap. One
  font size, no clickable links. The footer is therefore plain lines (repo link, "By Eclip5e"). The text was
  shortened until all of it fits without scrolling (device screenshot work/logs/final6.png).
- **Release signing**: new key `work/release.p12` (CN=Yugioh BAM Pocket Revived, O=Eclip5e, RSA 2048, 30 years;
  cert SHA-256 10:4B:D4:9D:...:E5:04). The password is in `work/release-signing.txt`; both files are git-ignored
  and must be backed up. Earlier builds used `work/debug.keystore`, so switching from them needs an uninstall.
- **One-command build**: `tools/build_release.py` (stub ANEs → patch_swf → build_game_adt). ADT path works on
  Windows (`adt.bat`) and Unix (`adt`).
- **Repo cleanup**:
  - Removed the scripts of the abandoned hand-packaging route: bisect_control, build_hello_air, build_ygo_adt,
    detailed_apk_diff, diff_apks, patch_exit_hook, setup_air_runtime, patch_apk (its `patch_mmog_xml` moved into
    build_game_adt), test_patched_apk.
  - Removed `download_airsdk.py`, which accepted the SDK license via the URL.
  - Removed DEPLOY.md (now in README).
  - `deploy/run.sh` and the service are generic templates (PUBLIC_HOST).
  - LAN address removed from the notes; it is still present in older commits.
  - No log token, private key or password in any tracked file or in history (grep over `git log -p`).
- **Final APK** `work/release/YugiohBAMPocketRevived-1.0.0.apk` (34 MB) [VERIFIED, aapt + keytool]:
  - package air.com.konami.ygo, versionCode 1011002, versionName 1.0.0, label "Yugioh BAM Pocket Revived";
  - arm64-v8a, targetSdk 28, no BILLING permission;
  - mmog.xml points to ygo.eclip5e.com; publickey.xml = the repo's/server's key.
- **Fresh install on the Pixel** [VERIFIED]: content download from live (84.65 MB) → login screen → Play Offline →
  new popup → LOG IN opens the live login page titled "Yugioh BAM Pocket Revived".
  - Not tested end-to-end: logging in with this build, because the only live account is the user's.
- **Original game content kept**: a one-time local "Breaking News: tournaments are live" popup
  (`NewsControllerImpl.DisplayNews`, shown once per install via LAST_NEWS_SEEN).

### 6.30 Live stats day 1, leaderboard "only me" fix, live-PvP feasibility (2026-10-29)

- **Live server data** (`server/data` on the server, read 2026-10-29 ~10:45):
  - 42 accounts, 41 of them created and logged in within 24 h; 13 logged in within 6 h, 5 within 1 h.
  - 35 online saves; 29 players with arena data, 4 in a team, 4 tournament sign-ups.
  - 0 friendships.
- **Leaderboard showed only yourself** [VERIFIED code + live data]:
  - The popup opens with "Friends only" checked (`module/arena/popup/ui/LeaderboardPopupUI.as:231`
    `IsChecked = true`, list chosen in `LeaderboardPopup.UpdateScoreInfoDisplay`, `:87-111`).
  - With no friends, the friend boards held only the player. The global boards on the live data were correct
    (7 all-time, 4 weekly).
  - Server fix (`server/arena.py` high_scores):
    - friends = client list + server friend list;
    - a player with no friends gets the full board in the friends view.
  - Test: `tests/test_arena.py` friendless player C. Deployed (live reload 10:50:49); on a copy of the live data
    the friends view now lists 4 weekly / 7 all-time entries.
- **Live PvP needs no APK change as far as the code shows** [VERIFIED code / INFERRED end-to-end, untested]:
  - Lockstep relay: `BamReadyRequest{slotCard, checksumBefore, roundNumber, forfeit}` →
    `BamReadyNotification{slotCard}`; `StartRound`, `BamEnd{checksum, externalIdWinner}` →
    `BamEndNotification{winnerExternalId, redeemCode}`; `ChecksumErrorNotification`,
    `OpponentSurrenderedNotification` (`project/livepvp/amf/*`, `LivePvPManager.as:152-280`,
    `module/cardgame/flowhandling/flowhandler/LivePvPFlow.as:132-260`).
  - Each phone simulates the duel; the server only relays and compares checksums. No rules engine is needed.
  - RNG seed = the starting player's uid on both clients (`module/cardgame/effect/EffectHandler.as:119-136`).
  - Matchmaking: `project/readyforcombat/amf/*` (queue, SendCombat/AcceptCombat, PlayerMatchingInQueueNotification).
  - Server pushes ride on responses (6.28). In PvP mode the client pings every 2 s
    (`YGOMPvPLoginImpl.EnterPvpMode` → `MobileEngineServerComPvp.SetPvpPingFrequency`, mmog.xml 2000), i.e. the
    original game already did PvP over HTTP polling.
  - Open risks:
    - the main and PvP engines share one ServerComHTTP; delivery of notifications to the PvP engine is unverified;
    - where the client gets the opponent's deck is unknown;
    - these need a 2-device test.

### 6.31 Friend "(!)" mark; expanding the game with new cards, packs and story maps (2026-10-30, read-only)
- **"(!)" not shown in Add Friends** [VERIFIED code + live data]:
  - The server's FQL list does mark incoming requests: `(!) name` (`server/fakefb.py` `_fql_friends`).
  - The invite row displays `FacebookCache...FirstName` from the Graph `/<id>` lookup
    (`module/duelground/display/InviteFriendSlot.as:118-168`), and that lookup has no mark. The FQL name is
    only used for sorting (`InviteFriendsPopup.as:269, 306-315`). The user decided to leave it as is.
- **Where the game's content is defined**:
  - Configs are plain `zlib(AMF3 array)` with no signature or hash [VERIFIED: decoded with `server/amf3.py`,
    0 bytes left over]. They ship only in the APK: `config/ace/**` (`work/apk/assets/config/ace`).
    - Cards: `inventory/item_template.ace`.
    - Shop: `shop/shop.ace`.
    - Crafting: `crafting/crafting.ace`.
    - Loot: `loot/*.ace`.
    - Story maps: `worldmap/storymaptemplate.ace`, `storynodetemplate.ace`, `worldnodetemplate.ace`.
  - Paths come from mmog.xml vars (`ShopManager.Init` `shop_path`, mmog.xml:304-319) or constants
    (`WorldmapManagerYGO.as:55-59`).
  - Art is in the downloaded content (Local Store `asset/cards/`, via `CardLoadingUtil.as:17-80` and
    `representation/*.ace`). The server can update it.
  - `DataRefreshManager.RefreshCachedData` (reloads the ace files with `?v=`) exists, but nothing in the client
    calls it [VERIFIED: rg over the scripts]. So the server cannot make the client reload its configs.
- **Booster packs are hard-coded in the game code** [VERIFIED]:
  - `module/shop/view/enum/EBoosterPackInfo.as`: 9 packs; each has a fixed card id list, cost, shop item id,
    rarity odds and visual frame.
  - A new pack therefore needs a SWF patch plus shop/loot ace edits, i.e. an APK update.
- **"Coming soon" cards** [VERIFIED code; counts from the decoded ace]:
  - `BuyCardPopup.GetCardStatus` (`:202-233`) checks, in order: buyable shop item, crafting recipe,
    EBoosterPackInfo list, tournament theme reward. Anything else is "Coming soon".
  - Of 1183 card templates: 698 booster, 170 shop, 19 tournament, 296 coming soon (crafting has 101 products,
    none of them coming soon).
  - The 296 are mostly series 2: 271, plus 16 of series 99, 7 of series 1 and 2 of series 98. 260 of them are
    backorder shop items in `shop.ace`.
  - 289 of the 296 already have card art on every phone (art present: 1176/1183 cards overall; missing
    1149, 1150, 1356-1360).
  - 295 of them have effects. Whether they have localized names: unknown (not checked).
  - So these appear to be finished but unreleased cards (INFERRED).
- **Server-only way to hand out any card** [VERIFIED code path / INFERRED end-to-end, untested]:
  - At login, `YGOMLoginImpl.GetTournamentReward` (`:282-297`) sends `GetTournamentRewardRequest`.
  - `InventoryManagerGame.OnGetTournamentRewardResponse`/`ShowTournamentReward`/`ConsumeTournamentReward`
    (`:724-840`) then, for each `TournamentReward{id, itemTemplateId, itemQuantity, TournamentTemplateId,
    levelTemplateId, EliteRank}` paired with an `Item` of the same itemTemplateId:
    - shows a popup (`TournamentNewRankPopup` for cards, `TournamentEliteRewardPopup` for currency);
    - adds the item to the local inventory and saves;
    - records the reward id in `save.rewardReceived` and sends `RewardConsumedRequest`.
  - The popup text is tournament-themed: "new rank" + theme name (`TournamentNewRankPopup.as:80-93`).
  - Our server currently returns an empty list (`server/game.py` `get_tournament_reward`).
  - `GetRewardsResponse` (REFUND/GUILD) only credits currency (`InventoryManagerGame.ConsumeReward`
    `:672-697`).
- **Story maps** [VERIFIED counts]:
  - 48 story map templates: map 1 is the world map; 47 are reached from 47 world nodes.
  - 2447 story nodes. The map layout XML is embedded in the template (`xml` field).
  - Unlock dates on world nodes are all in 2012/2013, so everything is unlocked.
  - A new map needs new ace rows (map, nodes, world node, opponents), localization and art. Only the art is
    server-side, so a new map is APK work.
- **One-time APK change that would make later content server-driven** [VERIFIED part / INFERRED design]:
  - `Loader.BuildURL` passes `http://` and `file:///` URLs through unchanged (`as3ToolKit/net/Loader.as:594-610`).
  - An APK whose config paths point into app storage (a new downloadable "config" package) or at the server
    would let config updates ship like content packages.
  - EBoosterPackInfo would still be code, unless it is patched to build its list from data.

### 6.32 Full expansion feasibility: cards, packs, maps, objectives, versioning, offline, sandbox (2026-10-30, read-only)
- **Cards are data** [VERIFIED]:
  - `inventory/item_template.ace` (1183 cards) holds stats, rarity, series, family, element, level and an
    `effects` list.
  - Each effect is `{triggerId, triggerDispatcherId, targetTypeId, target*/dispatcher* filters, effect{atk/def/hp
    modifier+operator, destroyCard, resurrect, grant/breakImmunity, silence, necro, oncePerGame, ...}}`.
  - The engine has 6 effect primitives: `module/cardgame/effect/EffectCreater.as:27-52`, with classes in
    `effectlist/`. Any new card that combines existing triggers, targets and primitives needs no code; a new
    mechanic does.
  - Name and description come from `resourceNameId`/`resourceDescriptionId`, looked up in
    `resource/<lang>/inventory.ace`.
    - Format: AMF object `{string: ByteArray, sortedByResourceId: [[id, offset]], sortedByUTF, guid, ...}`.
    - Each string is a 2-byte big-endian length followed by UTF-8 [VERIFIED by decoding: 8608 entries].
    - 292 of the 296 "coming soon" cards have English names. Their `resourceDescriptionId` is not in
      inventory.ace (where card text comes from: unknown).
  - Art is resolved through `representation/item_template_to_asset.ace` + `asset.ace` to
    `asset/cards/<name>_1.jpg` in the downloaded content (`CardLoadingUtil.as:17-80`).
- **Story maps are data + downloaded XML** [VERIFIED]:
  - Layout and duels are loaded from the downloaded content: `asset/world/Map<N>_level1.xml`
    (`module/map/map/StoryMap.as:147`).
  - Each `DuelNode` has `deckid` (opponent card list), `characterid`, `stringid` (dialogue), `rewardid`/
    `rewardqt`, `completionid`, `energycost`, `timer`, `Rules`, `nodelink`/`nodelocked`.
  - Node rows (energy, stars, unlocks) are in `worldmap/storynodetemplate.ace`; placement on the world map is in
    `worldnodetemplate.ace` + `storymaptemplate.ace`.
  - Art is Starling PNG + XML atlases: `misc/mapbackground` (backgroundmapN), `mapcharacter` (duelcharacterN),
    `mappreview`, `maplibrary`.
  - Text is in `resource/<lang>/MAP_0NN.ace`, `map_0NN.ace` and `DIALOG.ace`. The section name comes from the map
    id (`StoryMap.as:120-133`).
- **Booster packs** [VERIFIED]:
  - The pack definitions are code (`EBoosterPackInfo.as`).
  - Card odds are data: `loot/loot_template.ace` (weighted `lootItemTemplates` per pack), linked to the shop by
    `loot_shop_item_template.ace` (19 rows).
  - Shop entries are in `shop/shop.ace`.
  - Packs are rolled on the phone: `project/loot/LootManagerYGO.CreateBooster` `:195-230` uses `Random`, so they
    work offline.
  - Cover art is the frame `mVisualFrame` in `module/shop/shop_all_1.xml`. There are 11 frames
    `shop_booster_covers_0000..0010`, of which 9 are used.
  - There are 2 series icons. Series-specific code compares with `CardSeries.SERIE_1`
    (`ShopCollectionView.as:189-225`, `BuyBoosterPackShopDisplay.as:185-291`).
- **Objectives (quests) are data** [VERIFIED]:
  - `quest/quest_template.ace` has 376 quests. Each has steps with `actionTypeId` (21 kinds in use) and targets.
  - Unlocks: `requiredQuestId`, `unlockLevel` and dates (`QuestManagerYGO.CheckUnlockOtherQuest`).
  - Rewards come from `bundle/bundle_template.ace` (`QuestManagerYGO.GetRewardProductListForQuestTemplateId`
    `:487-492`). Text is in `resource/<lang>/quest.ace`.
  - Quests are tracked on the phone (`LocalQuestActionListener`).
- **Code changes beyond byte patches are possible** [VERIFIED compile / INFERRED runtime]:
  - `ffdec-cli -air -replace MobileGame.swf out.swf <class> <file.as>` recompiled a modified `EBoosterPackInfo`
    with a 10th pack.
  - Re-decompiling `out.swf` shows the new pack (scratchpad test, 2026-10-30). FFDec calls the feature
    experimental.
- **Version checks already in the game** [VERIFIED]:
  - APK gate:
    - `YGOMLoginImpl.ValidateAppVersion` (`:455-494`) compares mmog.xml `client/version` with the server's
      `GetVersionResponse.version` (our `--version-string`).
    - If the APK is older, it shows `VersionUpdateData.NEW_APP_UPDATE_STATE` and `OnContinueOffline` logs out to
      offline play (`:436-447`). Online features are locked; offline still works.
  - Content gate:
    - `versionning.xml` lists packages per game version, and each package has a version.
    - At startup, any package whose local `<name>_version` differs is downloaded again (5.4).
    - Packages live in app storage, so they work offline (5.1, 5.5).
  - Missing:
    - the client never sends its own version (`LoginRequest{name, password, token}`, `GetVersionRequest` has no
      fields), so the server cannot reject old clients by itself;
    - the ace configs ship in the APK, so a data change needs a new APK.
  - Fixes (INFERRED, not built):
    - a version query parameter on mmog.xml `serverUrl` (set at build time);
    - and/or a recompiled login class that sends the APK and content versions;
    - a recompiled loader (`as3ToolKit/net/Loader.BuildURL` `:594-610`) that reads `config/...` from app storage
      when a downloaded "gamedata" package has it, with the APK copy as fallback.
  - Risk: an old client meeting cards it doesn't know (friend duels, arena decks).
    `InventoryCacheLogic.GetTemplateById` returns null with a warning (`:320`); the callers likely crash
    (INFERRED). This is why online play must be gated on matching content.
- **Sandbox** [VERIFIED presence / unknown state]:
  - The AIR SDK has x86_64 Android runtimes (`work/airsdk/runtimes/air/android/device/x86_64`) and `bin/adl.exe`.
  - No Android emulator or SDK is installed (only `C:\Users\ultim\dev\adb\adb.exe`).
  - A hypervisor is present (Win32_ComputerSystem); whether WHPX is enabled is unknown (needs elevation).
  - The stub ANEs are built for `Android-ARM64` only (`tools/build_stub_anes.py:234-290`). An x86_64 build needs
    an `Android-x64` platform entry.

### 6.33 Expansion groundwork: sandbox, hybrid game data, data-driven packs, deck deletion (2026-10-30)
- **Emulator sandbox** [VERIFIED, emulator]:
  - Setup: Android SDK emulator + `system-images;android-34;default;x86_64`, AVD `ygo`, run headless
    (`-no-window`), WHPX acceleration; boot takes about 30 s.
  - Builds: `tools/build_release.py --arch x64` (ADT `-arch x64`; the stub ANEs now also declare
    `Android-x64`).
  - Port 80 on the device needs `adb root` (AOSP image) before `adb reverse tcp:80 tcp:8087`.
  - `tools/emu.py` handles start, install, launch, screenshots, taps and the log.
  - Result: full 85 MB content download, login, shop and deck builder all work in the emulator.
- **Load order** [VERIFIED code + emulator]:
  - Every data file loads during engine start (`MobileProjectEngine` step `InitEngine`; the managers' `Init`
    calls `LoadByte`).
  - The content download runs later (`ValidateAssets`, step 11). Startup popups render under the prelauncher
    until `RemovePrelauncherVisual`.
- **Hybrid game data** [VERIFIED, emulator]:
  - `tools/patch_as3.py` recompiles classes from their decompiled source plus our edits
    (`tools/as3_patches.py`), using `ffdec-cli -air -replace`.
  - Loader:
    - `Loader.BuildURL` serves `config/...` from app storage `asset/gamedata/` when the downloaded
      `gamedata_version` is newer than the APK's `config/gamedata_version`;
    - this is decided once per launch.
  - Package list: `EExternalAsset.GAMEDATA` adds a "gamedata" package.
  - Mid-session updates: `MobileProjectEngine.RemovePrelauncherVisual` shows "NEW CONTENT" and exits when the
    effective version changed during the launch.
  - Shared source: `tools/build_content.py` + `tools/content_mods.py` produce the APK's data and the package
    from the same mods.
  - Server: `server/content.py` adds a `<version value="1.12.0">` block to versionning.xml (old 1.11.x clients
    keep their 1.11.1 block) and serves overlay zips.
  - Tested in the emulator:
    - bundled 1.0.0 plus downloaded 1.0.1: the change shows only after a restart, then also with no network;
    - 1.0.1 → 1.0.2 shows the popup and the app exits;
    - a server downgrade re-downloads the data and falls back to the APK's copy.
- **.ace codec** [VERIFIED]:
  - `tools/ace.py` round-trips all 265 data files byte-identically.
  - Localization:
    - the game reads only `resource/<lang>/localization_section.ace`, an array of 106 sections
      (`Engine.ALL_LOCALIZATION_FILE`);
    - the key index is in code-point order (`StringFinder.GetString` binary search);
    - the text index is case-insensitive;
    - keys and resource ids share string offsets, which gives the pairing.
- **Booster packs** [VERIFIED, emulator]:
  - Pack shop items are `shopItemTypeId 4` with `itemTemplateId` = loot template id (1269 → 19).
  - `EBoosterPackInfo` also loads `config/boosterpacks.json` from game data.
  - "Wings of Destiny" (PACK_4_SERIES_2) is complete in the original data and is now released:
    - loot 26 / shop item 1414: 43 common ×5, 28 rare ×3, 16 ultra rare + 8 BAM legend ×1;
    - cover frame 9 (Galaxy-Eyes Photon Dragon);
    - all 95 cards have names and art.
  - Purchase and pack opening work in the emulator.
  - Not yet released:
    - "Blazing Wind" (PACK_6_SERIES_2): name, description, cards and cover frame 10 exist (the cover shows
      Brotherhood of the Fire Fist - Bear); no loot table.
    - "Immemorial Cataclysm" (PACK_5_SERIES_2): name, description and cards exist; no loot table, no cover.
  - The remaining 201 unreleased cards split by the archetypes in those two descriptions. The split is our
    assignment (INFERRED from the descriptions).
- **Deck deletion** [VERIFIED, emulator]:
  - On mobile, `InventoryManagerGame.DestroyDeck` only made a server request the DAL ignored
    (`InventoryManagerDalMobile.DoDestroyDeckRequest`: "Shouldn't be called anymore").
  - It now works locally:
    - cards are merged back into the collection stacks;
    - the deck and its card items are removed;
    - `YGOMData.Save`.
  - The deck chooser has DELETE with a confirmation (`TwoChoicePopupData`); the last deck can't be deleted.
  - The save contains only the remaining deck, with card counts restored.
  - Note: deck edits made in a session that ends through Android Back were not in the save
    (pre-existing behaviour, seen once).
- **Starter decks in the shop** [VERIFIED code / INFERRED effort]:
  - `module/shop/view/enum/EStarterPack.as` has 8 decks: name/description keys, card list, cost, shop item
    775-781, cover frame (`StarterDeck.as:47`) and chapter unlock.
  - Buying one: shop item → bundle products (`bundle_template.ace`) → `BundleManagerProject.BuildDeck`
    (`:585-606`) creates the deck.
  - More decks: the same data-driven approach as booster packs, plus bundle and shop rows and cover art.
- **Several main (world) maps** [VERIFIED code / INFERRED effort]:
  - The data model supports them:
    - `worldnodetemplate.worldMapTemplateId` (all 47 rows use 1);
    - `MapProgression.worldMapId`, the save's `worldMapArray`;
    - `YGOMDefaultDataUtil.CreateWorldMap(templateId)`.
  - The code assumes world map 1:
    - `WorldMap.CreateContent` loads `asset/world/WorldMap.xml`
      (`EMapModuleLibrary.WORLD_MAP_ASSET`);
    - `WorldMap.AddMapSpecificElements` uses template 1;
    - `WorldmapCacheLogic:305` and `WorldmapManagerDalMobile:104` use `GetWorldMapByTemplateId(1)`.
  - A second main map needs:
    - those classes patched to use the current world map;
    - its world map instance created on load for existing saves;
    - a switch control on the world map;
    - a `WorldMapN.xml`, background art and node and chapter data.
  - Chapter maps are already data plus downloaded XML (6.32).

### 6.34 Version gate, save compatibility, art pipeline (2026-10-30)
- **Version gate** [VERIFIED, tests + emulator]:
  - Client:
    - `ServerComHTTP.Connect` appends `?v=<mmog client/version>&d=<game data version in effect>` to the game
      server URL, so every request carries both;
    - "UPDATE NOW" (`NewAppUpdate`, `VersionUnavailable`) opens GitHub releases instead of Google Play.
  - Server (`server/content.py` gate, `server/server.py`):
    - with `work/content/manifest.json` present, the minimum APK is `game_version` and the required data is the
      current gamedata version;
    - `GetVersionResponse.version` = minimum APK version, so older APKs show their own "NEW UPDATE AVAILABLE"
      popup (PLAY OFFLINE / UPDATE NOW; `YGOMLoginImpl.ValidateAppVersion`) at startup and again on LOG IN;
    - everything except GetVersion and Ping from a client without matching `v`/`d` gets an "Update required"
      exception; the first public APK sends neither and is refused;
    - the startup popup starts with an update notice for IPs whose latest GetVersionRequest had an outdated
      `v`;
    - `--no-version-gate` turns the gate off. Without `work/content` there is no gate at all, so deploying this
      server code alone does not lock anyone out.
  - `tests/test_version_gate.py`: old/older/outdated-data clients are refused; an up-to-date client logs in.
  - Emulator: the 1.0.0-equivalent build shows the update popup and notice, downloads content and plays offline;
    the new build logs in with `v=1.12.0&d=1.0.0`.
  - Not done: recompiling `LoginModule`. With an edit there, the upgraded app hung at the end of startup; it
    started normally without the edit. That's why the popup text is chosen by IP.
- **Save compatibility** [VERIFIED, emulator]:
  - Upgrading the 1.0.0-equivalent install in place keeps its save (deck "OldDeck" with 3 cards, collection).
  - The new APK only downloads the 0.73 MB gamedata package; all other content is reused.
  - Nothing in the save format changed. Deck deletion uses existing item/container fields.
  - New cards only add item rows, which old APKs never see (they are refused online and keep their own save).
- **Startup smoke test**: `tools/emu.py smoke APK [--fresh]` installs, launches, answers the startup popups
  and passes when the login screen loads (the server sees `closepopupconfig.xml`). It caught a failure as a
  hang and passes for the fresh old APK, the upgrade, and the current build.
- **Art pipeline** [VERIFIED, emulator]:
  - Texture atlas lists (`asset/list/module/*_list.xml`, in the APK) are now game data, with the same override
    as `config/`.
  - `content_mods.add_atlas_frames` ships a second atlas page `<atlas>_2` in the module's package and lists it.
  - Starling `AssetManager.getTextureNames` merges and sorts frame names across pages
    (`starling/assets/AssetManager.as:143-153`), so `shop_booster_covers_0011` is frame 11.
  - Tested with a recolored copy of cover 9 shown as the Wings of Destiny cover.

### 6.35 Several main maps, in-app login, no Facebook logo, browser version (2026-10-30)
- **Several world (main) maps** [VERIFIED, emulator]:
  - The original data model already allows them: `YGOMDefaultDataUtil.EXTENSION_WORLD_TEMPLATE_ID = 2`
    (unused), `worldnodetemplate.worldMapTemplateId`.
  - Save migration exists and runs on every load: `YGOMDataImpl.SetupPlayerData` → `ValidateJSONSave` →
    `ValidateQuest/ValidateWorld/ValidateStory`. It adds new quests, world nodes and chapters, but no missing
    world maps; our `ValidateMissingWorldMaps` adds that.
  - Changes:
    - `WorldMap.CreateContent` loads `asset/world/worldmap<N>.xml` for N > 1;
    - a "WORLD N" button cycles through the save's world maps and saves `MapProgression.worldMapId`;
    - `GetWorldNodeByStoryMapTemplateId` and `DoUnlockWorldNodeRequest` no longer assume map 1;
    - `WorldNodeEnum` makes entries for chapters it doesn't know.
  - New chapter ids need:
    - story map, story node and star template rows;
    - `asset/world/map<id-1>_level1.xml`;
    - `mappreview_preview<id-1>`;
    - localization sections `map_0<id-1>` (dialogue), `map` `WORLD_NODE_INFO_MAP_ID_<id-1>` and `world_map`
      `NAME_CHAPTER<id-1>`.
  - Chapters 16 and up (`EBamProConst.WORLD_MAP_GATE`) are BAM Pro gated, so new chapters are too unless
    changed.
  - Test (`YGO_TEST_CONTENT=1`, `tools/content_test_mods.py`): map 2 with one node opening chapter 60, a copy of
    chapter 1.
  - Not yet solved: world map 2 uses map 1's background and banner ("ALBA LITORA"), which are classes in the
    world XML (`backgroundWorld`, `maplibrary`). A real second map needs its own background art.
- **In-app login** [VERIFIED, emulator]:
  - `FacebookManagerMobile.Authorize` used `navigateToURL` (system browser).
  - It now uses a StageWebView over the game, the same mechanism as the invite dialog (`InviteFriends`,
    800x400).
  - The `fb<appId>://authorize` redirect is caught (LOCATION_CHANGING/CHANGE) and passed to the original
    `ProcessLogin`.
  - Back or the page's Cancel link (`#error=cancelled`) cancels.
  - The web view has its own cookie store, so "Continue as" works inside the game after the first login there.
- **Facebook logo**: removed in code at all 4 login buttons (`MainMenuView`, `LoginView` ×2,
  `AdvantageLoginPopup`); texture names `common_login_facebook_ico`, `loginpopup_loginbutton_ico`.
- **Browser version** [INFERRED unless stated]:
  - Browsers no longer run SWF natively. The game is AS3 on Starling/Stage3D (457 of 2929 classes import
    starling), plus a few AIR-only APIs [VERIFIED counts]:
    - `flash.filesystem` 14 files;
    - `StageWebView` 4;
    - `NativeApplication` 11.
  - Option A, Ruffle (open-source Flash Player in WebAssembly):
    - runs the SWF itself, no rewrite;
    - needs a web build that swaps the AIR-only classes (file storage → browser storage, packages fetched from
      the server instead of unzipped to disk, web view → popup/iframe);
    - unknown: how well Ruffle handles Stage3D/AGAL for Starling, and its performance. A one-day experiment
      would settle it (needs downloading Ruffle).
  - Option B, server-side Android streamed to the browser (e.g. an Android container + WebRTC/scrcpy-style
    streaming):
    - runs the unchanged x86_64 APK;
    - costs roughly one CPU core and 1–2 GB RAM per concurrent player on the server, plus input latency.
  - Option C, port to HTML5 (e.g. OpenFL/Haxe): a large rewrite.
  - Option D (not a browser): a Windows/macOS desktop build from the same SWF with the AIR SDK and desktop
    stub extensions, for little effort.
- **Pack split proposal**: `notes/pack_split_proposal.md`.
  - 146 of the 201 remaining unreleased cards match the archetypes in the two pack descriptions: 73 for
    Immemorial Cataclysm, 73 for Blazing Wind.
  - 55 match neither. They're mostly series 98/99 legends (arena/promo cards), plus 5 series-1 commons that are
    the starter backup cards new saves already receive (`BackupCardAssociation`).

### 6.36 Quick fixes: shop popup, leaderboard, settings, BAM Pro always on, energy never runs out (2026-10-30)

All in `tools/as3_patches.py` (section "Quick fixes"), emulator-tested (x64 build, local dev server).

- **Server info popup** [VERIFIED]: `PopupManagerUtil.ShowCurrencyPopup` (`PopupManagerUtil.as:94-100`) called
  `ShowApplicationClosePopup()` on every currency shop open. Call removed; the startup popup
  (`LoginModule.as:444`) is unchanged. Emulator: currency shop from the shop menu opens without it; startup still
  shows it.
- **Leaderboard** [VERIFIED]: `LeaderboardPopupUI.as:231` `IsChecked = true` → `false`;
  `LeaderboardPopup.UpdateScoreInfoDisplay` reads `FriendOnlyChecked`, so the first list is the global one.
  Emulator: opens unticked with all players.
- **Settings** [VERIFIED]: `OptionPopup.FORUM_URL` (`:48`) → the GitHub repository; the restore-purchases button
  and the "Already a BAM PRO?" text are hidden (`visible = false`, so the dispose code is untouched); the support
  block is moved up to the middle of the right column. Label `option/option_visit_forum` = "GitHub" (content mod
  `settings_github_text`).
- **BAM Pro always on** [VERIFIED]: every Pro check reads `BamProHandlerImpl.IsBamPro` (grep of `.IsBamPro`: login
  view banners and arena button, main menu, shop series 2 packs/cards, contextual offers, option popup, purchase
  handler); the getter now returns true and `GateBamPro` (which read the field `mIsBamPro`) uses the getter.
  Saves then store `isPremium: true` (`YGOMCacheUtil.as:208,298`). The one-time 25 DP Pro reward
  (`AppPurchaseHandlerImpl.ManageBamPro`) is no longer reachable for players who never "bought" Pro; not given
  automatically (adding DP during save load is riskier than the reward is worth). Emulator: fresh install shows the
  PRO badge, Arena opens for a new account, no upgrade banner.
- **Energy** [VERIFIED]: kept but never limiting. `EnergyManager.CurrentEnergy` getter tops the value up to
  `maximumEnergy` before returning it. Every reader goes through it: duel start check `StoryMap.as:489`,
  try-again checks `GameEndHandler.as:374,806`, the offline consume DAL `EnergyManagerDalMobile` (reads the
  getter, so it never fails for "not enough energy"), the widget, and the save writer `YGOMCacheUtil.as:194,284`.
  The HUD energy bar is no longer added to `PlayerInfoBar`'s element list, and the shop menu's "Energy" tile is
  not added (`ShopMenuView`). Node energy costs stay in data and are still printed in the duel info popups
  (cosmetic, `DuelInfoPopup.as:98`, `DuelStarPopup.as:170`). Emulator: an online save edited to energy 0 was
  loaded on a cleared device (sync popup, server save chosen; DP 60 → 110 after a purchase proves it was the
  loaded save), and the next upload had energy 200/200.

### 6.37 Map jump after dragging (2026-10-30)

- Cause [VERIFIED, `AbstractMap.as`]: `MoveDrag` (`:209-238`) moves `mScrollingEngine.x/y` directly and sets
  `mIsMovedByDragging`; while it is set, `Update` (`:482-501`) stops copying the camera viewport into the engine.
  The camera (`scrollingengine2d/camera/Camera.as`) keeps its viewport on the pointer (`IFocus`) and only moves by
  the pointer's movement deltas. `OnNodeSelectedEvent` (`:523-527`) cleared the flag, so the next `Update` snapped
  the map back to the old viewport around the pointer — usually the top of a chapter, where players start.
- Reproduced in the emulator (chapter 1 with completed nodes from an edited local save: drag up, tap the treasure
  node → map jumped back by the drag distance).
- Fix (`as3_patches.py` ABSTRACT_MAP): on node selection after a drag, the camera viewport takes over the dragged
  position (`ViewPort.x/y = -engine.x/y`, inside try/catch), then the flag is cleared. Emulator: the map stays put,
  the pointer walks to the tapped node, and the camera follows it again when it walks off-centre (tap on STORY at
  the top edge scrolled the map along). Applies to world maps too (same base class).

### 6.38 Energy leftovers hidden; runtime pack guard (2026-10-30)

- Energy on screen [VERIFIED code + emulator]: `DuelInfoPopup` (energy icon + cost next to the duel button) and
  `DuelStarPopup` (icon + cost on every challenge button) no longer add them; the button labels are centred.
  `TryAgainPopup` loses the energy icon and number on its button (code only; not reached in the emulator, it needs
  a lost duel). `StoryMap.EnergyCostNode` skips the "-N" energy animation and continues like a free node
  (`OnEnergyCostDone(null)`, the path the original takes for cost 0). Node hover tooltips (`StoryNodeTooltip*`,
  web mouse-over) are untouched; they don't appear on touch. Emulator: duel star popup shows plain "OK" buttons,
  "Replay Duel" starts the duel at once.
- Pack guard [VERIFIED emulator]: `ShopManagerProject.BuyShopItem` refuses a LOOT shop item whose loot table is
  missing or has no items, before the currency is taken (warning "PACK UNAVAILABLE ... Nothing was spent.",
  returns `PASS_DATE`). If the check itself throws, the purchase proceeds as before. Test: content built with Blazing
  Wind's loot groups emptied → refused, DP unchanged (1,507); Legend of the Dragon and Immemorial Cataclysm still
  open (also right after a refusal). The game fills `LootShopItemTemplate.lootGroups` from `loot_template` at
  runtime (the shop-item rows have `lootGroups: null` in data), which the guard reads.

### 6.39 Collection menu; new-class build step (2026-10-30)

- **Collection** [VERIFIED emulator]: a COLLECTION button in the main menu's top row (between Edit Deck and
  Shop; `MainMenuView.AddCollectionButton`, inside try/catch, so a missing icon or text leaves the original 9
  buttons). It opens the shop module directly in the card view with `ShopCardView.CollectionMode` (static flag,
  cleared in `ShopModule.Dispose`):
  - list: every card the deck builder knows (`CardTemplateListUtil.GenerateCardTemplateDataList`, sorted by name,
    fusion results excluded like in the deck builder): 1,141 cards; owned quantity per card ("3 x"), unowned cards
    at 45 % opacity, no buy buttons (`BuyCardShopDisplay.CreateBuyButton` returns early).
  - footer: "owned / shown" count; FILTERS opens the normal filter screen with the "My Cards Only" and
    "Tournament cards" boxes (FilterModule data `[true,true,...]`); tested "My Cards Only" → "5 / 5".
  - tapping a card opens the full card popup; BACK closes the shop module (back to the main menu).
  - The normal shop path is unchanged (Shop → menu → Cards: 155 cards with prices, tested after using the
    collection).
- Icons and labels: content mod `mainmenu_icons` adds a second main menu atlas page (`mainmenu_all_2`, package
  mainmenu 1.1.11): Collection = the shop's card-stack icon, Profile = the front figure of the Friends icon,
  mirrored from its left half (for the profile button, not used yet). Texts `mainmenu/mainmenu_collection_text`,
  `mainmenu_profile_text` (en/fr). Existing installs get the package through the normal content download
  (0.53 MB, seen in the emulator).
- **New classes**: `tools/build_newclasses.py` (run by build_release.py between the byte patches and patch_as3):
  compiles `as3_new/**.as` with the SDK's `compc` against a SWC of the game SWF (FFDec `-swf2swc`, cached by
  hash in work/newclasses/) and inserts the library's DoABC tags before the game's first ShowFrame. With no
  `as3_new/` files it copies the SWF unchanged (current state; the collection needed no new class). Checked with a
  sample class: compiled, merged, listed by FFDec in the output SWF.

### 6.40 Collection layout like Edit Deck (first new AS3 classes) (2026-10-31)

- New classes in `as3_new/com/revival/collection/` (merged by tools/build_newclasses.py; first real use):
  `CollectionPanel` (layout), `CollectionScroller` (OptimizedScroller of columns; queues/frees card textures through
  QueuedCardLoader like CardScroller), `CollectionColumn` (3 small cards at 0.86 scale, owned count under each,
  unowned at 45 % opacity; remembers which card was touched), `CollectionColumnData`.
- Layout: 3-row grid scrolling horizontally on the left (cards sorted by name, filled column by column), shop
  slider under it, preview pane on the right (shop item frame + FullCardVisual at 0.6). Tap a small card → preview;
  tap the preview → FullCardPopup with the owned quantity. Filters and the "owned / shown" count as before (6.39).
- Hooked in `ShopCardView` collection mode (`CreateCollectionPanel`, try/catch): if the panel can't be built the
  previous shop-style list is shown instead (it is created anyway and only hidden).
- [VERIFIED emulator] grid, preview, popup, fast fling across the list (textures load), "My Cards Only" (5 / 5),
  smoke fresh + upgrade.

### 6.41 Profile (own profile, picture presets, rename, password); collection owned-first (2026-10-31)

- Server (`server/profiles.py`, routed by `server/fakefb.py` on the fake Graph API the client already uses):
  `revival_icons` (14 presets: card-art crops from content_mods.profile_icons → `<content>/server/icons/`),
  `<uid>/picture` (chosen preset, else the old default), `<uid>/revival_profile` (public JSON: name, picture,
  league, experience, stars, unique/total cards from the online save, deck = Game.deck_for, account creation),
  `POST me/revival_profile` (icon | rename | password) and `/fb/dialog/revival_profile` (edit page for the in-app
  web view). AccountStore.rename (uid unchanged, case-insensitive uniqueness) and change_password (old password
  required). tests/test_profile.py; all server tests pass.
- Client (new classes `as3_new/com/revival/profile/`): `ProfilePopup` (InfoPopup subclass via
  `ProfilePopupData.PopupClass`) loads the JSON and picture with URLLoader/Loader from
  `FacebookURLDefaults.GRAPH_URL`; network errors only show a message. EDIT PROFILE opens the edit page with
  `FacebookMobile.dialog("/revival_profile", ...)` (same StageWebView path as the invite dialog; Close returns
  to login_success, which closes the view), then reloads. Native text input was avoided on purpose (StageText
  positioning under Starling); the web page handles keyboard input.
- PROFILE button in the multiplayer row (`MainMenuView.AddProfileButton`, try/catch; greyed offline like
  Friends; offline tap → login-required popup).
- [VERIFIED emulator] profile opens with live stats; picture picked in the web view ("Picture changed."), Close
  → profile shows the new picture. Not yet run in the emulator: rename/password through the web view (server
  side covered by tests).
- Collection: owned cards first, then unowned, name order kept inside both groups (ShopCardView
  UpdateCollectionList). [VERIFIED emulator]
- Not done yet (profile part 2): viewing other players' profiles + "copy deck" (comes with the Friends rewrite),
  showing the deck's cards, league name instead of number.

### 6.42 Profile: Level wording, read-only deck view; fallback deck fix (2026-10-31)

- "League" is shown as "Level" (it is the player level shield in the HUD; save field `league.leagueTemplateId`).
- VIEW DECK (profile) opens `DeckViewPopup` (as3_new/com/revival/profile): the deck's cards 5x3 at 0.8 scale on
  empty slots like the deck builder, preview on the right (tap a card), full card popup from the preview (owned
  quantity shown on your own profile). Textures through QueuedCardLoader, freed on close. [VERIFIED emulator]
- Server: `Game.deck_for` fallback ("best cards") capped copies per save item, not per card (6x Dark Prisoner when
  the collection had two items of it); now max 3 per card. The profile names the deck source: "Online deck"
  (arena/friend deck), the default deck's name, or "Best cards (no deck set)". Server tests pass.

### 6.43 Friends manager (search, requests, remove, view profiles) (2026-10-31)

- Server `server/friends_page.py` (`/fb/dialog/revival_friends`, routed in fakefb.py): tabs Friends (Profile,
  Remove), Requests ("Added you": Accept / Decline; "Sent by you": Cancel; tab shows the incoming count), Find
  players (name search, prefix matches first, max 30; Add / Cancel / already friends). Pictures from
  `/fb/graph/<uid>/picture` (profile presets). Uses AccountStore.request_friend / remove_friend (remove also clears
  pending requests both ways). tests/test_friends_page.py; all 8 server tests pass.
- Client: the Duel Ground's ADD FRIENDS button opens it in the in-app web view (`as3_new/com/revival/friends/
  FriendsManager`, DuelGroundModule patch); if the web view can't open, the old invite popup is shown. "Profile"
  closes the view with `?view=<uid>` and opens `ProfilePopup` read-only (EDIT PROFILE only on your own).
  The Duel Ground friend list itself updates the next time it opens (reloading the module from inside itself would
  break its Back history).
- [VERIFIED emulator] request from a helper account shown under "Requests (1)" with its picture → Accept → listed
  under Friends → Profile → friend's read-only profile.
- Empty decks read "Deck: No deck yet" instead of "(0 cards)".
- Still open from the Friends item: choosing the online defense deck (today the last arena deck), "copy deck" on a
  friend's profile, pending-request badge on the main menu Friends button, the old Facebook-style invite list
  (kept as fallback).

### 6.44 Friends extras: all players list, request badge, copy deck, online deck choice (2026-10-31)

- Find players lists every player (newest first), 40 per page with Previous/Next; the box filters by name (prefix
  matches first). Measured on the dev server: 147 players → 4 ms, 27 KB per page; pictures `loading="lazy"`. Rows
  show Add / Accept (they already asked you) / Cancel / nothing (already friends).
- Request badge: `GET /fb/graph/me/revival_requests` → `{"incoming": n}`; `RequestBadge` (as3_new) adds the
  original "new" mark (`mainmenu_newcontent`) to the main menu FRIENDS button when n > 0. Online only, errors
  ignored. [VERIFIED emulator]
- Copy deck (friend's profile → COPY DECK, `DeckCopier`): counts the deck's cards against your free collection
  stacks (`GetCompleteDifferentFloatingCardList`, cards already in decks don't count); if anything is missing it
  says how many and builds nothing. Otherwise the same two steps as the deck builder: `BuildDeck` of an empty deck,
  then `UpdateFullDeck` with one entry per slot (quantity 1, id = the collection stack); the DAL takes each card out
  of the collection. Then `YGOMData.Save()`.
  - Lesson [VERIFIED]: a first version passed `BuildDeck` entries with quantity 3; `DoBuildDeckRequest` subtracts
    per entry from the unchanged cache object and the deck display shows one card per entry → a 5-card deck.
    BuildDeck is only meant for empty decks.
  - [VERIFIED emulator] fresh account, friend deck of its 5 cards x3 → "fr_59f38c copy" with 15 cards, 3600 LP in
    Edit Deck; copying again → "You are missing 15 cards".
- Online deck choice (profile → EDIT PROFILE → "Online deck"): lists the decks of your online save (server
  `Game.save_decks`, deck items de-duplicated: the client writes each deck item twice, YGOMCacheUtil inventory loop
  + deck loop) plus "Automatic"; the choice is stored as player data `defense_deck` (deck id). `Game.deck_source`
  order: chosen deck → arena deck → default deck → best cards. EDIT PROFILE now uploads the save first
  (`YGOMData.Save(true)`, waits for SAVE_COMPLETE/FAILED) so new decks are listed. [VERIFIED emulator + server]
- All 8 server test scripts pass; smoke fresh + upgrade OK.

### 6.45 Live PvP, part 1: protocol mapped, server relay + matchmaking (2026-10-31)

- Entry point [VERIFIED code]: only the Tournament starts live duels. DUEL (`TournamentDisplay.as:236-249`, needs a
  deck meeting the tournament requirement and the live PvP tutorial once) → `TournamentDuelSearchPopup` →
  `YGOMPvPLogin.EnterPvpMode()` (PvP connection pings every 2 s) + `TournamentManager.EnterTournamentQueue`
  (`PlayCombatTournamentRequest{cards = default deck amfCards, deckName, friendsNbr}`, `:443-464`). The popup closes
  when it has both `NewCombatNotification` (or a combat in the queue response) and `StartDuelNotification`; then
  `TournamentDuelFoundPopup` → `LivePvpUtil.LaunchLivePvpCombat` (`:49-71`): player1Id = starting player (also the
  RNG seed, 6.30), decks = card template id arrays, opponent name from the Facebook cache.
- Duel [VERIFIED code, `LivePvPFlow.as:158-300`]: after the coin flip each side sends StartRound once →
  StartRoundNotification. Each round BamReady{slotCard, checksumBefore (0 in round 1, else local+opponent checksum
  + round-1, identical on both phones), roundNumber} → BamReadyNotification{opponent's slotCard}. Round end and game
  end: BamEnd{checksum, externalIdWinner (0 = round only)} → BamEndNotification. Surrender = BamReady{forfeit}.
  Watchdog timeouts 40 s (start round, ready) / 20 s (end) (`ELivePvpTimeout.as`).
- Connections [VERIFIED]: Tournament, ReadyForCombat, LivePvP and Guild DALs send on `ManagerA.PvpEngineCom`;
  every object in a response array is dispatched to its listeners (`EngineServerCom.OnReceivedData:476-540`), so
  notifications can be appended to any response on that connection.
- Implementation:
  - The PvP connection now uses its own path `/facebook/pvp/proxy.html` (mmog.xml pvpServerUrl,
    `tools/build_game_adt.py`; `server.py` PVP_PATH, same handler). Queued notifications are appended to
    responses on that path only. Old APKs are gated anyway.
  - `server/livepvp.py`: FIFO queue (first come, first matched; random starting player), relay of StartRound /
    BamReady / BamEnd with round and checksum comparison (mismatch → ChecksumErrorNotification), surrender,
    45 s disconnect timeout (OpponentDisconnectedNotification), a new search abandons an unfinished duel. Duel end
    sends PlayCombatEndNotification{current tournament level}.
  - `tests/test_livepvp.py` plays two simulated clients through matchmaking, start, two rounds, a checksum
    mismatch, a surrender and queue cancel. All 9 server test scripts pass.
  - [VERIFIED emulator] the rebuilt APK logs in on the PvP path ("Login OK … pvp") and the Tournament screen loads.
- Next (part 2): a real duel between two emulators (second AVD); tournament level changes on win/loss (today the
  level is only echoed); possibly a friend challenge entry point (ReadyForCombat SendCombat/AcceptCombat) so live
  duels aren't limited to the tournament queue.

### 6.46 Live PvP part 2: tournament ranking, first real live duel between two emulators

- Ladder [VERIFIED data, `config/ace/tournament/tournament_level_template.ace`]: 76 levels, each {rank, token,
  levelTemplateBefore, levelTemplateAfter}. Start 81 = rank 15, 0 tokens. A win goes to levelTemplateAfter, a loss
  to levelTemplateBefore; -1 = no move (the 0-token level of each rank, 62..75 and 81, is its floor). Level 80 =
  rank 0 = Elite. Tokens per rank: 3 (ranks 15..11), 4 (10..6), 5 (5..2), rank 1 has 0..5.
- Client [VERIFIED code]: `PlayCombatEndNotification{tournamentLevel}` is kept by
  `TournamentManager.OnPlayCombatEndNotification` (`:511-516`); back on the Tournament screen
  `TournamentView.CheckNewLevelReceived` compares old and new rank/token (`TournamentUtil.GetRank`: Elite shows
  eliteToken) and animates a new rank or ±1 token. The top leaderboard is the Elite list
  (`TournamentScreenLeaderPopup`, sorted by eliteRank). Rewards (`tournament_reward_template.ace`) match on
  levelTemplateId and eliteRank range; Elite rewards for eliteRank 1..100, eliteRank 0 matches the 0..0 rows
  (`TournamentCacheLogic.GetTournamentRewardByLevel:279-291`).
- Our rules (`server/teams.py` Teams.record_result, LEVELS): win/loss moves along that chain. Elite: eliteToken
  +1 per win, -1 per loss, min 0 [INFERRED, the original server rule is unknown]; eliteRank = position among Elite
  players by eliteToken, then who got there first, 1..100, else 0. GetTopTournamentLeaderboard returns Elite players
  only. `server/livepvp.py` records a result whenever a duel ends with a winner: BamEnd winner, surrender,
  disconnect timeout, or leaving a duel for a new search (the leaver loses); both players get
  PlayCombatEndNotification with their new level. An out-of-sync duel counts for nobody.
- Tournament rule [VERIFIED code]: every tournament template has a deck requirement (`requirement_template.ace`:
  type 2 card family, 3 attribute, 4 none; template 5 = no restriction). `TournamentUtil.IsDeckValid` also needs a
  custom default deck (instant decks don't count) with at least one monster with defStat > 0
  (`DeckRequirementData.IsDeckValid`). The live PvP tutorial is a local game setting
  (`LivePvpUtil.IsLivePvpTutoNeeded`, EGameSettings.LIVE_PVP_TUTO_COMPLETED). Dev override:
  `YGO_TOURNAMENT_TEMPLATE=5` makes the dev server always run the no-restriction tournament.
- [VERIFIED emulator] Two emulators (AVD ygo on emulator-5560, AVD ygo2 on emulator-5562), each logged in to a
  local account, signed up (5 DP), with a custom play deck, after the tutorial: LIVE DUEL on both → matched in
  4 s, both see the opponent's name and 3600 LP, StartRound from both, 10 BamReady relayed, the opponent's cards
  appear and fight on each phone, no checksum error, the duel ended with a winner. Server: "winner 1000000150",
  levels 81 → 2 (winner) and 81 → 81 (loser). Back on the Tournament screen the winner shows the first rank-15
  token, the loser 0. Not seen: the win/lose screen itself (dismissed by my taps), surrender and disconnect on
  phones (covered by the server test).

### 6.47 Live PvP part 3: friend live duels

- The game's own friend-duel messages (`project/readyforcombat`: SendCombat{receiverExternalId, combatId,
  combatTemplateId}, AcceptCombat, RefuseCombat, AcceptedCombatNotification, CombatManager) have no UI that sends
  them in v1.11.2 [VERIFIED code: no caller of `ReadyforcombatManagerDal.DoSendCombatRequest`/`DoAcceptCombatRequest`
  outside the DAL]; the only live duel entry is the tournament queue (6.45). So friend duels reuse that queue.
- Design: the server pairs players on the tournament queue; a player who set a challenge
  (`POST /fb/graph/me/revival_challenge {to}`, friends only, `server/fakefb.py _challenge_post`) is paired only with
  that friend, and only when the friend queues with a challenge back (`server/livepvp.py` set_challenge /
  incoming_challenges, queue entries carry the target). Challenge duels are unranked (Duel.ranked); both still get
  PlayCombatEndNotification with their unchanged level. Cancel in the search popup (CancelTournamentMatch) drops the
  challenge; it also expires after QUEUE_SECONDS.
- Client (`as3_new/com/revival/friends/LiveChallenge.as`): the friends page closes with `?challenge=<uid>` ("Live
  duel" on a friend, "Accept" on a waiting challenge), or the profile's LIVE DUEL button (others' profiles);
  LiveChallenge posts the challenge, opens the Tournament screen (`TournamentManagerProxy.OpenTournamentModule`; the
  search/found popups need its assets, `TournamentModule.CreateAssetList`), and `TournamentView.InitComplete`
  (patched, TOURNAMENT_VIEW_EDITS) starts the game's own search popup → duel found popup → live duel, or the live
  PvP tutorial first. Needs a play deck (custom default deck) but not a tournament sign-up or the tournament's deck
  rule [VERIFIED emulator: the search popup only calls EnterTournamentQueue with GetDefaultDeck].
- Friends page: Friends tab lists "Waiting for a live duel with you" with Accept, and shows a count on the tab;
  `me/revival_requests` counts waiting challenges into `incoming` (main menu Friends badge) plus `challenges`.
- [VERIFIED emulator, two emulators] friend request + accept on the in-game friends page; emulator 1 "Live duel" →
  search popup, server "waiting, challenging <uid>"; emulator 2's Friends tab shows "Friends (1)" and the waiting
  challenge; Accept → paired at once ("challenge"), full duel to a winner, no checksum error, winner's tournament
  level unchanged (2). `tests/test_livepvp.py` adds: strangers can't challenge, a tournament player is not paired
  with a challenger, badge/page show the challenge, the pairing, unranked result. All 9 server test scripts pass.
- Note [VERIFIED code, `module/option/GameSettings.as` LoadFromSharedObject]: game settings (live PvP tutorial done,
  selected deck type, ...) reset to defaults whenever the app's install date changes, so after every APK update
  players see the live duel tutorial prompt again (original behaviour).
- Fixes after the emulator check: the profile's LIVE DUEL read the uid after closing the popup (popup data already
  disposed, so nothing was sent); now read first [VERIFIED emulator: "challenge: 1000000150 -> 1000000202"]. When
  the live PvP tutorial prompt comes up instead of the search, LiveChallenge clears the challenge (to=0), so a later
  tournament search isn't held for that friend [VERIFIED emulator: "-> 0" a second later].

### 6.48 Online status, challenge toast, settings kept across updates

- Online status: the game pings its main connection every 10 s while running [VERIFIED data, `config/mmog.xml`
  ping_frequency 10000]. The server marks a player online on any request of theirs (`Game.touch`, `server.py`
  after each AMF request) and online = seen in the last 40 s (`livepvp.ONLINE_SECONDS`). Friends page: online
  friends first with "Live duel", others show "offline" without it; profile JSON has `online`, and the profile's
  LIVE DUEL button only shows when true; `revival_challenge` refuses offline friends unless they are already
  waiting for you. [VERIFIED emulator] a running friend shows "Live duel"; after force-stopping the game on that
  emulator and ~50 s, it shows "offline".
- Challenge toast (`as3_new/com/revival/friends/ChallengeToast.as`, started with the main menu Friends badge):
  polls `me/revival_requests` every 15 s while logged in and not in a duel (now also returns
  `challengers [{uid, name}]`); a new challenger shows a bar at the top of any screen, "<name> challenges you to a
  live duel!" with ACCEPT (LiveChallenge.Start: challenge back → paired at once) and LATER, hidden after 30 s,
  each challenge shown once. [VERIFIED emulator] toast on the Tournament screen and on the main menu; ACCEPT →
  duel started ("live pvp 5 ... challenge"); a surrender on one phone ended it on the other.
- Settings across APK updates: `GameSettings.LoadFromSharedObject` dropped all saved settings when the app's install
  date changed [VERIFIED code]; patched (GAME_SETTINGS_EDITS) to keep them (missing keys still get defaults).
  [VERIFIED emulator] after installing the new APK the live duel went straight to the search (tutorial done
  before), and the startup "Breaking news" popup did not repeat.

### 6.49 Performance: startup and screen timings

- Tooling: builds with `YGO_PERF=1` (dev only; `tools/as3_patches.py` PERF_EDITS / PERF_MODULE_EDITS,
  `as3_new/com/revival/dev/Perf.as`) report each startup step (`MobileProjectEngine.ProcessNextStep`) and each screen
  change (`StarlingModuleManagerImpl.ChangeModule` → `OnModuleReady`) as `GET /perf?s=<name>&t=<ms since launch>`;
  read them from the dev server log. Release builds don't contain it.
- Startup [VERIFIED emulator, cold start, logged in]: 25.9 s to "Initialization complete", of which 15.0 s was
  "Initialize PushNotification": the Pushwoosh service is gone, our stub ANE never answers, and
  `MobileProjectEngine.StartPushWooshTimeout` waits a fixed `Timer(15000,1)`. So every player waited 15 s on every
  cold start, on any phone. Patched `InitPushNotification` to skip registration (MOBILE_ENGINE_EDITS): startup now
  11.0 s on the emulator. Remaining larger steps: prelauncher images 2.0 s, generic popup assets 1.0 s, automated
  login 1.76 s (several round trips plus client-side encryption; the server answers each in 1-2 ms), store data
  1.25 s (stub IAB, needed for the "Free" prices), transitions 0.26 s; asset steps are bound by the emulator's
  software GPU.
- Screens [VERIFIED emulator, ms from ChangeModule to ready]: main menu 13-30, collection 232, shop 231, edit deck
  339, crafting 385, friends 318, tournament 333, story map 772, arena 2789. Arena's server calls take ~120 ms
  (GetDuelArena 80-90 ms on the first call, then cached; leaderboard ~25 ms with ~260 accounts); the rest is the
  client loading arena assets. Not changed.
- Idle network: the PvP connection pings every 2 s only in PvP mode (search popup to duel end:
  `YGOMPvPLoginImpl.EnterPvpMode/ExitPvpMode`, `MobileEngineServerComPvp.SetPvpPingFrequency`), otherwise every 10 s
  (`mmog.xml` ping_frequency) [VERIFIED code]. The challenge toast adds one small request per 15 s while logged in.
- Server scaling note [INFERRED]: leaderboards, arena opponent picks and the Elite list scan all accounts per call
  (~25-90 ms at ~260 accounts); fine for now, worth caching if the player base grows a lot.
- Build fix: `as3_patches.PATCHES` had two keys for MobileProjectEngine (ENGINE and the new MOBILE_ENGINE); in a
  dict literal the later one silently replaces the earlier, so the normal build lacked the push fix (the timing
  build lacked the 3 older engine edits instead). Merged into one list; `tools/patch_as3.py` now refuses to build
  when a class is named twice. [VERIFIED emulator] normal build: 4 engine edits, smoke test login screen after
  19 s (31 s without the push fix, same emulator), main menu fine after login.

### 6.50 Ping traffic: a server bug made every client ping ~7 times per second; idle traffic now 6 requests/min

- Measuring: the server now logs one line per minute, "traffic last 60 s: N requests (main ping, pvp ping, pvp amf,
  challenge poll, other)" (`server/server.py` Traffic). Useful on the live server too.
- Bug [VERIFIED code + measurement]: our PingResponse had `ping: True` (`server/amf3.py build_ping_response`, set in
  the initial commit without a recorded reason). `EngineServerCom.OnPingResponse` answers `ping == true` with an
  immediate new Ping(), so every client pinged in a loop limited only by round-trip time, on both connections. One
  idle emulator: 900 requests/min (448 main + 448 PvP pings). Now `ping: False`: 16/min with the current APK
  (main 6, PvP 6, challenge poll 4). Server-only fix, so it helps all installed APKs once the server is deployed.
- What pings are for [VERIFIED code]: keep-alive plus a frame counter sync (`GameLoop.CurrentFrame`, not used
  anywhere else) and a carrier for server pushes. The server needs no keep-alive: sessions last 7 days from login
  (`Game.SESSION_SECONDS`); nothing is pushed on the main connection; live duel messages go over the PvP connection
  in PvP mode (2 s pings), and duel results arrive with the duel's last message.
- Reduced in the next APK: main ping 30 s (`build_game_adt.patch_mmog_xml` sets mmog.xml ping_frequency 30000);
  PvP connection idle ping 60 s (`MobileEngineServerComPvp` ForceStartPingCycle / SetNormalPingFrequency, PVP_COM_EDITS);
  PvP mode stays 2 s; challenge poll 20 s (ChallengeToast). Online status: any request in the last 70 s (was 40),
  and the challenge poll now counts. [VERIFIED emulator] idle client: 6 requests/min (challenge poll 3, main ping 2,
  PvP ping 1); during a live duel 2 s PvP pings as before; a full friend duel (toast → accept → winner, no checksum
  error) played normally; after the duel back to 6/min per client.
- Friends page: online players have a green dot on their picture; "offline" text removed (offline = no dot, no
  Live duel button). The dot's CSS class is `dot` (the page already uses `on` for the active tab).

### 6.51 Immemorial Cataclysm cover: best effort with the game's 155 px art

- All card pictures in the game data are 155x155 (`Local Store/asset/cards`, 1177 of 1184 files; the rest 143-144 px)
  [VERIFIED]; the original series 2 covers (`shop_all_1` frames 6-10, 220x313) show a sharp cut-out monster on a
  coloured radial background, drawn from larger art. The owner chose a best effort with the game's own art.
- `tools/content_mods.compose_cover` rewritten: radial gradient in the pack colour, the card art upscaled (bicubic +
  light unsharp mask) and faded at its edges with a soft oval mask, the banner from cover 9 recoloured; the shared
  template (logo, emblem, rail with gems, frame) is the per-pixel median of covers 6-10 with a soft alpha from how
  much the covers differ (one outlier allowed). This removed the fringe pixels around the gems and the speckled
  frame edge of the old composite. Shop package 1.1.12.
- [VERIFIED emulator] the shop asked to download the new shop package (2.78 MB), then showed the new cover in the
  booster list next to the original series 2 covers.

### 6.52 Card rewards: Arena weekly rewards, chapter-locked card shop entries, God card milestones

- Card shop availability [VERIFIED code + emulator]: `ShopManager` (`core/shop/ShopManager.as:450-474`) removes
  shop entries outside their startDate..endDate when the shop loads; buying checks the dates again
  (`ShopManagerProject.GetShopItemByTemplateID`). Only 155 of the 1148 card shop entries are on sale (most have
  placeholder dates around 3012). Correction of the 2026-10-31 analysis in notes/pack_split_proposal.md.
- Chapter-locked card shop entries: `as3_new/com/revival/shop/ShopUnlocks.as` (card → chapter; chapter N = world 1
  node with xmlNodeName N, cleared = `WorldNode.completed`, as `module/map/map/WorldMap.as:117` uses it);
  `ShopCardView.UpdateCardList` skips locked cards (SHOP_CARD_VIEW_EDITS). `tools/content_mods.revival_rewards`
  reads that table and adds 16 DP entries (shop item ids 3001+, dates 2014-2100, leagueRequired 1; 10 DP Ancient
  Sorcerer, 30 Gradius, 60 for the series 99 legends). [VERIFIED emulator] account with no cleared chapter: 155
  cards (all 16 hidden); a test build treating Ancient Sorcerer's chapter as cleared: 156 cards, Ancient Sorcerer
  for 10 DP, bought (DP 55 → 45).
- Arena weekly rewards (`server/rewards.py`): the original ARENA_REWARD bundles (bundle_template.ace type 6, 71
  bundles) grouped into 10 sets with cards that exist and have art, tiers of 3/3/3/2/1 cards [VERIFIED data]. Our
  rules [INFERRED, the original is unknown]: last week is paid once on the first inbox check after it ended,
  set = week mod 10; ranks 1-3 tiers 1-3, ranks 4-10 tier 4, 11-25 tier 5; single-card sets ranks 1-10. Arena now
  keeps last week's score (`last_weekly`). Data: `<content>/server/rewards.json` from the content build.
- God cards: Obelisk the Tormentor (1196) the first time a player reaches tournament rank 10, The Winged Dragon of
  Ra (1195) at rank 5 (`LivePvP._finish` → `Rewards.on_tournament_rank`); names added to the English inventory
  texts (they had none).
- Delivery: per-player reward inbox; `GET/POST /fb/graph/me/revival_rewards` (`server/fakefb.py`). Client
  `as3_new/com/revival/rewards/RewardInbox.as` checks it when the main menu opens: adds the cards like
  `InventoryManagerGame.ConsumeTournamentReward` (`ParseInventoryChange`), saves, shows the cards in the deck view
  popup with a message (DeckViewPopupData.Message), confirms each reward; received ids are also kept on the device
  (SharedObject) so a lost confirmation never adds a reward twice. [VERIFIED emulator] a granted Arena reward
  (B.E.S. ×3) showed as "ARENA REWARD" with the three cards and the text, was confirmed on the server, and the
  cards were in the collection (1× each).
- `tests/test_rewards.py`: week settled once, tiers by rank, 0 points nothing, both weekly/last_weekly count,
  milestones once each, consume once, built rewards.json sane. All 10 server test scripts pass.
- Follow-up (owner's choice): the 28 series 2 cards whose original card shop entries never went on sale (970, 975,
  1009-1011, 1053-1055, 1137-1139, 1148, 1180-1182, 1292-1294, 1299, 1300, 1351-1353, 1386, 1388, 1390, 1392,
  1401) are in ShopUnlocks too: their own entries get dates 2014-2100 and leagueRequired 1, original DP prices
  (Hidden Spellbook 999 → 60); chapters 6 (rare), 12 (ultra rare), 18 (legends), 24 (Stardust Dragon/Assault Mode,
  Realm of Light, Dark Magician of Chaos, Hidden Spellbook, Helios). The fusion results 1387, 1389, 1393 stay out
  (made in duels; originally 999 DP). 44 chapter-locked entries in all. [VERIFIED emulator] account with no
  cleared chapter: still 155 cards.

### 6.53 Copy Deck bug: decks it built hung the deck screen after an edit

- [VERIFIED emulator] On a deck built by profile > COPY DECK, any edit + Done left the deck overview on "Loading..."
  forever (the edit itself was saved); decks built by the game's own deck builder saved fine (same build, other
  account). No script error (dev build with the new uncaught-error reporter, `Perf.CatchErrors`).
- Cause [INFERRED from the code]: `DeckCopier` passed the cached deck object from ON_BUILD_DECK to
  `UpdateFullDeck`, whose local save (`InventoryManagerDalMobile.DoUpdateFullDeckRequest:261-281`) rewrites
  `deck.amfCards` in place; the deck builder passes a copy (`EditDeckScreen.SaveDeck` →
  `ConvertDeckToFullDeck`). DeckCopier now does the same. [VERIFIED emulator] a deck copied with the fix, then
  edited (card swapped) and saved: back to the overview at once. Copy Deck was never deployed, so no player has
  a broken deck; the old test deck on account cp22312 stays broken.

### 6.54 Fusion, card effects ("SPECIAL"), and room for new mechanics (investigation, nothing changed)

Fusion [VERIFIED code + data]:
- Data: 9 series 2 base monsters carry `CardTemplate.fusionData` (`project/inventory/amf/FusionData.as`):
  resultCardTemplateId plus ingredient conditions (level, card list, type, element/attribute, family/type of
  monster), ingredientCondition = all vs any. All 9 results have card art; results have 0 hearts (no LP).
  Naturia Beast + any Plant → Naturia Exterio; Thousand-Eyes Idol + any monster → Thousand-Eyes Restrict;
  Blast Juggler + Machine → Cyber Saurus; Cave Dragon + Dragon → Fiend Skull Dragon; Possessed Dark Soul +
  attribute 5 → Dark Balter; the four Six Samurai + one attribute each → the Legendary Six Samurai.
- Duel: dropping a card on your own monster in the same channel marks them to fuse when allowed
  (`LocalPlayerHand.WillFusionOccur`, `FusionUtil.IsFusionPossible`); at the round's fusion step
  (`RoundHandler.LaunchFusion` → `GameMatBO.CreateFusionCard`) both ingredients are removed and the result is
  placed in that channel, keeps immunity, fires the ON_FUSION trigger (32). The AI plans fusions too
  (`CardGameAI.IsFusionPossible`); card loading also preloads the result's art (`CardLoadingUtil`); a fusion
  tutorial (`FusionTutorial`, fixed decks in `EFlowHandlerList.FUSION_TUTO`) starts the first time a booster
  gives a fusion card (`FusionCardUtils.CheckForFusionTutorialFromLoot`, save flag fusionTutorialSeen).
- Never released: no live loot table or on-sale shop entry contained a fusion base. Now: 1354 Naturia Beast and
  the Six Samurai are in the revived packs (loot 27/28), 1386/1388/1390/1392 in the chapter-locked card shop; the
  results 1387/1389/1393 stay unsold (made in duels).
- Emulator: a duel with one Thousand-Eyes Idol in the deck did not draw it in 4 rounds, so a fusion was not seen
  on screen yet (needs a deck with several fusion pairs).

Card effects [VERIFIED code + data]:
- An effect row (`Effect.as`) = trigger (EffectTriggers, 30 kinds: round start/end conditions, card destroyed,
  LP gained/lost, attack, damage, stat changes, fusion, ...) + target (TargetTypes, 35 kinds: channels, all
  monsters/spells of a side, graveyards, ...) + what happens, built from six primitives only
  (`EffectCreater.CreateEffects`): stat change (ATK/DEF with + - × ÷), life points, destroy, grant immunity,
  break immunity, resurrect; plus flags (once per game, single activation, necro, silence, friend multiplier)
  and master/slave links to chain rows (e.g. Winged Kuriboh LV9: destroy spells, then +500 per spell destroyed).
- `cardEffectTypeId` (CardEffectTypes, 59 names: BOOST, CRIPPLE, SNEAK, ..., SPECIAL = 42) is only a label: the
  duel engine never reads it; it is used by the card filters (EContextMenu) and the instant-deck card scoring
  (EEffectCalculators). SPECIAL (281 rows) marks combinations that have no named category, e.g. Robbin' Goblin
  (trigger LP lost + heal 300), Dark Hole (round start: destroy all + lose 2500), Mirror Force. So "special"
  effects are built from the same primitives; a new one is a data row (with a description text).
- Behaviour the primitives cannot express (draw cards, switch control, discard, copy an effect, ...) needs new
  code: a new EffectBO subclass (`module/cardgame/effect/effectlist`) created by EffectCreater (patched), maybe
  a new trigger or target, the AI scoring, and the same code on both phones for live duels (lockstep checksums).

New mechanics (Synchro, Xyz) [INFERRED from the code above]:
- "Synchro-like" with data only: fusion already allows a level condition (ingredientCardLevelId) and a type
  condition; a pair rule like "level 4 + any Machine → X" works today. Limits: always exactly two cards, the
  second dropped onto the first in the same channel, the result replaces them in that channel.
- Real Synchro/Xyz (level sums, tuners, materials kept under the card and spent by effects, summoning from an
  extra deck) need new duel code: placement rules (LocalPlayerHand), a new step in RoundHandler next to
  LaunchFusion, AI support, visuals, deck builder rules for an extra deck, and new card data; both phones must
  run identical code for live duels. Feasible with new classes, effort L–XL; the data model (FusionData) is the
  natural starting point. New result cards also need art (only 155 px card pictures exist in the game data).

### 6.55 New cards from official scans; series3 card package; test world removed (2026-10-31)

- **Art box** [VERIFIED, 6 scans measured]: on the 421x614 card scans (YGOPRODeck's size) the art of a normal
  (non-Pendulum) card is x 49-371, y 111-433 (323x323), inside a grey bevel frame (columns 44-48 / 372-377, rows
  106-110 / 434-437). Identical on Cicada King, Veiler, Zeus, Nibiru, Ash, Apollousa. The game's own pictures
  (Local Store `asset/cards`, 155x155) are the full art box too. `tools/card_art.py` cuts the box by these ratios
  and scales to 155x155 (LANCZOS, JPEG q90); refuses images that are not card-shaped. On the 813x1185 scan the
  same ratios give a cut that matches YGOPRODeck's own `cards_cropped` image (mean difference ~5/255, JPEG noise).
  Pendulum cards (wider art box) are not handled.
- **Card download script** (owner's `dl/YGOCardDl.py`, not in the repo) [VERIFIED 2026-10-31, one card]: the API
  `db.ygoprodeck.com/api/v7/cardinfo.php` still answers; the image host it uses,
  `storage.googleapis.com/ygoprodeck.com/pics/<id>.jpg`, returns 403. Current URLs (from the API's `card_images`):
  `images.ygoprodeck.com/images/cards/<id>.jpg` (813x1185), `cards_small/`, and `cards_cropped/<id>.jpg` (art
  only, 624x624). Changing `self.imgapi` to the first fixes the script.
- **New card package `series3`** [VERIFIED emulator]: `EExternalAsset.SERIES3` ("series3", `asset/cards/`,
  tools/as3_patches.py EXTERNAL_ASSET_EDITS) holds only the pictures of new cards, so adding a card downloads a few
  KB instead of a new 27 MB series2 zip. Package install only writes files (`ExternalFileControllerImpl
  .SaveFileOnDevice`), so it shares `asset/cards/` with series1/2 safely; a package the server's versionning.xml
  does not list is skipped (`ValidateAsset`: `assetData != null`), so the APK works with servers or content without
  it. The server serves it from the content manifest (`content.package_zip`, no PACKAGE_PATHS entry needed);
  `build_content` packages with `PACKAGE_DIRS[name] = None` contain only overlay files. Version:
  `content_mods.NEW_CARDS_VERSION`.
- **`content_mods.add_card(ctx, id, base_id, name, scan, **fields)`**: copies a card template (new effect ids,
  fusion data cleared), name resource id 20000000000000 + id (en + fr), an `Asset` + `ItemTemplateToAsset` row
  (path `revival<id>_1.swf` → `asset/cards/revival<id>_1.jpg`), and the cut picture in series3.
  - Bug found on the way [VERIFIED emulator]: rows appended as plain dicts are encoded as untyped AMF objects; the
    card shop then stopped after its first card (no pictures, no card count). The rows must be `ace.AceObject`
    copies of an existing row (class alias `...representation.amf.Asset` / `ItemTemplateToAsset`). Any new row
    of an existing ace table: deepcopy a real row.
- Test (`YGO_TEST_CONTENT=1`, `tools/content_test_mods.test_new_card`): "Number 3: Cicada King" (template 9001,
  copy of Insect Soldiers of the Sky, level 3, 600/1250) for 1 DP in the card shop. [VERIFIED emulator] the game
  asked for 0.01 MB of extra content, wrote `revival9001_1.jpg` + `series3_version`, and the card shop listed 156
  cards with Cicada King showing its cut art and name.
- Card scans live in `content/card_scans/` (git-ignored: Konami art), or `YGO_CARD_SCANS`.
- **Test world 2 removed**: `second_world_map` was only applied with YGO_TEST_CONTENT and never reached the live
  content (live `world.zip` has only `worldmap.xml`); the WORLD button only shows with 2+ world maps in the save
  (`hud.bar.MapActionBar.AddWorldButton`, tools/as3_patches.py). The multi-map code stays: a new map ships as game data (gamedata package) + world/
  mappreview art packages, no APK, as long as it needs no new code.

### 6.56 Browser version spike: the game runs in Ruffle up to the content check (2026-10-31)

- Setup: Ruffle nightly 2026-10-31 self-hosted web build (`work/ruffle/`, from github.com/ruffle-rs/ruffle
  releases, MIT/Apache), page + game files + forward to the dev server on one origin (`tools/web_spike.py`), SWF and
  config built for that origin (`build_release.py --host 127.0.0.1:8090`). Browser: the desktop app's built-in
  Chromium 152 (WebGPU and WebGL2 available).
- [VERIFIED, console + screenshots] Ruffle's default renderer here is `wgpu-webgl`. Starling initialises
  ("Display Driver: Dummy Ruffle driver" is only Ruffle's `Context3D.driverInfo` stub text) and draws: the
  prelauncher loading screen with its progress bar, later the game's own UNEXPECTED ERROR popup (text, images,
  dimmed background). `?renderer=webgpu` gave a black page and later hung the tab: keep wgpu-webgl.
- [VERIFIED] Startup: the engine queue runs all 19 commands (config, encryption, ServerCom, localization, all
  managers, all ace data; AMF typed-object warnings like `lootCategoryId` on LootShopItemTemplate are skipped by
  Ruffle), then MobileProjectEngine steps 0-10 of 28, including the saved-login step (it called `/fb/graph/v2.0/me`).
- Fixed on the way: `GameSettings.LoadFromSharedObject` read `File.applicationDirectory.creationDate` (AIR-only,
  throws in Ruffle: Error #2037) and stopped startup; now in try/catch (GAME_SETTINGS_EDITS, harmless on Android).
- [VERIFIED] Blocker: step 10, "Validate all the needed assets and download the missing one"
  (ExternalFileControllerImpl). Ruffle's `flash.filesystem.File` is a stub (constructor, resolvePath, exists,
  applicationStorageDirectory, nativePath all logged as stubs), so every package looks missing and installing one
  fails → the game's error popup.
- Next (web variant, INFERRED design): a web-only patch set where content is read by URL instead of from app
  storage — skip the package check/download (`ExternalFileControllerImpl.ValidateAsset` → valid), and point the
  readers of `File.applicationStorageDirectory` (CardLoadingUtil, StoryMap, asset lists, our Loader gamedata patch)
  at `<origin>/asset/...` served from the extracted content (Local Store + overlays). Then login (StageWebView →
  page redirect/popup) and NativeApplication no-ops. Effort: M-L.

### 6.57 Browser build: from the content wall to the world map (2026-10-31)

- **Build layout** (owner's decision): the APK is the base; `tools/build_web.py` builds the browser version from
  the same pipeline plus web-only patches (`tools/as3_patches.py` WEB_EDITS, applied with YGO_WEB=1, never in the
  APK) and new classes `as3_new/com/revival/web/` (unused in the APK). Output `work/web/game` (SWF + config +
  asset, staged like the APK by `build_game_adt.stage_files`) and `work/web/storage` (our content packages
  extracted, lower-cased); `tools/web_spike.py` serves both plus the original content (Local Store) under
  `/storage/`, and forwards the rest to the dev server.
- **Page**: own loading bar (the page fetches the SWF with progress and passes the bytes to Ruffle,
  `splashScreen: false`); passes `origin` (= location.host) as a SWF parameter.
- **Web edits** [VERIFIED in the built-in browser, Chromium 152, Ruffle nightly 2026-10-31]:
  - `ExternalFileControllerImpl.Init`: files ready at once (no versionning file, no package check/download).
  - App storage → `Web.STORAGE` ("storage/", relative to the page): MobileProjectEngine (fonts),
    AssetManagerWrapperImpl (prefix + File objects → URL strings), ExternalAssetManager, ScrollingEngine2D,
    BackgroundChooser, OpponentPlayer, EMapModuleLibrary, StoryMap, BackgroundLoadingUtilImpl, CardLoadingUtil.
  - Local save: `Web.ReadSave/WriteSave/DeleteSave` (SharedObject `revival_web_save`) instead of
    `Data/JSONSave_A|B.sav` (YGOMDataImpl).
  - `ServerComHTTP.Connect` adds the hard-coded port 80 after the host (EngineServerCom): a URL that already has a
    port is kept (dev origin 127.0.0.1:8090 became "host:8090:80" and every game request failed before sending).
  - Store: `WebStoreHandler` (all products "Free", purchases succeed at once, like the APK's billing stub) instead
    of GooglePlayHandler; without it startup waited forever at step 18 ("Init app purchase manager").
  - Content host: `PlayerManagerGT` uses `Web.Host(cdn)` = the page's origin (the startup text,
    closepopupconfig.xml, came from the server's `cdn` host, unreachable from the dev page).
- **Result** [VERIFIED screenshots]: all 28 startup steps; title screen (LOG IN / PLAY OFFLINE), login advantages
  popup, our startup text, main screen, the news popup, and the story world map with HUD (DP/coins), side buttons and
  all nodes. Game requests reach the server (`POST /facebook/proxy.html` 200).
- **Open** (next): world map nodes show without their icons/numbers and the player marker, and a node click does
  nothing (the map module reports all 9 init commands done; cause unknown); LOG IN still uses StageWebView (AIR);
  extra booster packs (`EBoosterPackInfo.LoadExtraPacks` reads config/boosterpacks.json with FileStream) and world
  maps after the first (WorldMap patch checks the file) still use File; local save across reloads untested;
  production hosting (`/webgame` on the live server, https vs the game's http URLs) not started.

### 6.58 Browser version: login, https, /bam on the game server, booster packs (2026-10-31)

- Owner's test: the world map and chapters work in the browser (my "nodes ignore clicks" in 6.57 was a misclick
  or a still-loading map); saves survive a reload; LOG IN hung (StageWebView, AIR-only).
- **Login** [VERIFIED, built-in browser + dev server log]: WEB_EDITS on FacebookManagerMobile.OpenLoginWebView call
  `com.revival.web.WebLogin.Open` (ExternalInterface → page `revivalLogin(url)`); the page shows the login page in an
  iframe over the game (server/webgame.py PAGE). server/fakefb.py: the done page and the Cancel link post
  `{revivalLogin: link | null}` to the parent page when framed (unchanged in the app's web view: no frame); the page
  calls the game back (`revivalLoginDone`) → the original ProcessLogin. Test: a new account created in the frame →
  "Login OK" on the main and the PvP connection, main screen logged in; after a page reload the game logged in by
  itself (token in the SharedObject).
- **https** (live site is https only): Ruffle's `upgradeToHttps` (default on) turns the game's http:// URLs into
  https:// on an https page, so the build keeps `http://<host>` URLs. ServerComHTTP added the hard-coded port 80
  (would give https://host:80): the web build uses the URL as is. The login frame URL is upgraded by the page.
- **Game data version**: `Loader.BundledGameDataVersion` is baked in by build_web.py (YGO_WEB_GAMEDATA) — the APK
  reads config/gamedata_version from its files; requests now send `&d=1.0.0` (version gate).
- **Booster packs**: `EBoosterPackInfo.LoadExtraPacks` read config/boosterpacks.json from files; the page fetches it
  and passes it as the `boosterpacks` parameter (`Web.Param`). [VERIFIED] Wings of Destiny and Immemorial
  Cataclysm (with its new cover) in the browser's booster list.
- **Serving** (`server/webgame.py`, used by the game server and tools/web_spike.py): `/bam/` page, `/bam/ruffle/`,
  `/bam/storage/` (work/web/storage, then the server's Local Store, lower-cased), other `/bam/*` = game files;
  path traversal refused (tests/test_webgame.py). server.py `--web-dir` (default work/web), `--ruffle-dir`
  (work/ruffle), `--web-path` (/bam/); the page answers 404 until a web build and Ruffle are there. Ruffle `base` =
  the page's folder, so the game's relative URLs stay under /bam/. [VERIFIED dev server] /bam → 302 /bam/, page,
  SWF, ruffle.js, storage file 200.
- Page layout: the game area keeps 16:9 (black bars) — on a 4:3 window the menu was cut off at the sides.
- Note: a hidden browser pane throttles the page (background tab): the 19 MB download and loading took ~40 s
  there; curl gets the SWF in 0.03 s.
- Live deploy (with the release): `python tools/build_web.py --host ygo.eclip5e.com`, copy work/web and
  work/ruffle next to the live server (or pass --web-dir/--ruffle-dir), server.py + webgame.py + fakefb.py.
