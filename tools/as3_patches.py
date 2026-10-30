"""
Source edits applied by tools/patch_as3.py: {class: [(old, new), ...]}. Each `old` is a snippet of the
FFDec-decompiled class and must occur exactly once. Keep edits small and anchored on stable lines.
"""

# --- Game data override (notes/findings.md 6.33) ---------------------------------------------------------
# Data files under config/ normally come from the APK. A downloaded "gamedata" package (asset/gamedata/ in
# app storage, marker asset/gamedata/gamedata_version) overrides them when its version is newer than the
# APK's own config/gamedata_version. Decided once per launch, so one session never mixes data versions.
LOADER = "com.frimastudio.as3ToolKit.net.Loader"
LOADER_EDITS = [
    ("""   import flash.utils.getTimer;
""", """   import flash.utils.getTimer;
   import flash.filesystem.File;
   import flash.filesystem.FileMode;
   import flash.filesystem.FileStream;
"""),
    ("""      private static const MAXIMUM_RETRY_LOADING:int = 5;
""", """      private static const MAXIMUM_RETRY_LOADING:int = 5;

      private static var sGameDataChecked:Boolean = false;

      private static var sGameDataActive:Boolean = false;

      private static var sSessionGameDataVersion:String = "";

      public static function ReadGameDataVersion(aFile:File) : String
      {
         var stream:FileStream = null;
         var text:String = "";
         if(aFile != null && aFile.exists)
         {
            stream = new FileStream();
            stream.open(aFile,FileMode.READ);
            text = stream.readUTFBytes(stream.bytesAvailable);
            stream.close();
         }
         return text.replace(/\\s/g,"");
      }

      public static function CompareGameDataVersion(aLeft:String, aRight:String) : int
      {
         var left:Array = aLeft.split(".");
         var right:Array = aRight.split(".");
         var length:int = Math.max(left.length,right.length);
         var a:int = 0;
         var b:int = 0;
         for(var i:int = 0; i < length; i++)
         {
            a = i < left.length ? int(parseInt(left[i])) : 0;
            b = i < right.length ? int(parseInt(right[i])) : 0;
            if(a != b)
            {
               return a > b ? 1 : -1;
            }
         }
         return 0;
      }

      public static function get BundledGameDataVersion() : String
      {
         return ReadGameDataVersion(File.applicationDirectory.resolvePath("config/gamedata_version"));
      }

      public static function get DownloadedGameDataVersion() : String
      {
         return ReadGameDataVersion(File.applicationStorageDirectory.resolvePath("asset/gamedata/gamedata_version"));
      }

      public static function get GameDataActive() : Boolean
      {
         var downloaded:String = null;
         if(!sGameDataChecked)
         {
            sGameDataChecked = true;
            try
            {
               downloaded = DownloadedGameDataVersion;
               sGameDataActive = downloaded != "" && CompareGameDataVersion(downloaded,BundledGameDataVersion) > 0;
               sSessionGameDataVersion = sGameDataActive ? downloaded : BundledGameDataVersion;
            }
            catch(error:Error)
            {
               sGameDataActive = false;
            }
         }
         return sGameDataActive;
      }

      public static function get ActiveGameDataVersion() : String
      {
         return GameDataActive ? sSessionGameDataVersion : BundledGameDataVersion;
      }

      public static function get GameDataChangedSinceStart() : Boolean
      {
         var downloaded:String = null;
         var bundled:String = null;
         if(!sGameDataChecked)
         {
            return false;
         }
         try
         {
            downloaded = DownloadedGameDataVersion;
            bundled = BundledGameDataVersion;
            return (downloaded != "" && CompareGameDataVersion(downloaded,bundled) > 0 ? downloaded : bundled) != sSessionGameDataVersion;
         }
         catch(error:Error)
         {
         }
         return false;
      }
"""),
    ("""      private function BuildURL(aWorker:Worker) : void
      {
""", """      private function BuildURL(aWorker:Worker) : void
      {
         var gameDataFile:File = null;
         if(aWorker.mUnversionnedURL.indexOf("config/") == 0 && GameDataActive)
         {
            gameDataFile = File.applicationStorageDirectory.resolvePath("asset/gamedata/" + aWorker.mUnversionnedURL.split("?")[0]);
            if(gameDataFile.exists)
            {
               aWorker.mURLRequest.url = gameDataFile.url;
               return;
            }
         }
"""),
]

EXTERNAL_ASSET = "com.frimastudio.snowstorm.project.externalfile.enum.EExternalAsset"
EXTERNAL_ASSET_EDITS = [
    ("""      public static const FONT:EExternalAsset = new EExternalAsset(mId++,"font","asset/font/");
""", """      public static const FONT:EExternalAsset = new EExternalAsset(mId++,"font","asset/font/");

      public static const GAMEDATA:EExternalAsset = new EExternalAsset(mId++,"gamedata","asset/gamedata/");
"""),
]

# New game data downloaded during this launch only applies from the next start: tell the player and close.
ENGINE = "com.frimastudio.mobile.MobileProjectEngine"
ENGINE_EDITS = [
    ("""   import flash.desktop.NativeApplication;
""", """   import flash.desktop.NativeApplication;
   import com.frimastudio.as3ToolKit.net.Loader;
   import com.frimastudio.snowstorm.project.popup.PopupManagerUtil;
"""),
    # popups during startup are drawn under the prelauncher visual, so ask after it is removed (last step)
    ("""         this.mPrelauncher = null;
         NativeApplication.nativeApplication.systemIdleMode = SystemIdleMode.NORMAL;
""", """         this.mPrelauncher = null;
         NativeApplication.nativeApplication.systemIdleMode = SystemIdleMode.NORMAL;
         if(Loader.GameDataChangedSinceStart)
         {
            PopupManagerUtil.ShowInfo("NEW CONTENT","New game content was downloaded. The game will now close. Start it again to play with the new content.").addEventListener(PopupManagerEvent.POPUP_CLOSED,this.OnGameDataUpdated);
         }
"""),
    ("""      private function LoadCommon() : void
      {
""", """      private function OnGameDataUpdated(aEvent:PopupManagerEvent) : void
      {
         NativeApplication.nativeApplication.exit();
      }

      private function LoadCommon() : void
      {
"""),
]

# --- Booster packs from data (notes/findings.md 6.33) ------------------------------------------------------
# The 9 original packs are code. Extra packs come from config/boosterpacks.json (game data: downloaded copy when
# active, else the APK's), read synchronously when the class initializes:
#   [{"shopItemId", "currency": "RMT"|"INGAME"|"CARD_PIECE", "cost", "id", "name", "description",
#     "guaranteed": [[rarityId, "5"], ...], "bonus": [[rarityId, "1:4"], ...], "cards": [templateId, ...],
#     "frame": cover frame in shop_booster_covers, "series": 1|2}]
BOOSTER_INFO = "com.frimastudio.snowstorm.module.shop.view.enum.EBoosterPackInfo"
BOOSTER_INFO_EDITS = [
    ("""   import com.frimastudio.snowstorm.project.inventory.enumeration.CurrencyTypes;
""", """   import com.frimastudio.snowstorm.project.inventory.enumeration.CurrencyTypes;
   import com.frimastudio.as3ToolKit.net.Loader;
   import flash.filesystem.File;
   import flash.filesystem.FileMode;
   import flash.filesystem.FileStream;
"""),
    ("""BOOSTER_PACK_9_ID,8,2);
""", """BOOSTER_PACK_9_ID,8,2);

      private static const mExtraPacksLoaded:Boolean = LoadExtraPacks();

      private static function ExtraPackCurrency(aName:String) : int
      {
         if(aName == "INGAME")
         {
            return CurrencyTypes.INGAME.Id;
         }
         if(aName == "CARD_PIECE")
         {
            return CurrencyTypes.CARD_PIECE.Id;
         }
         return CurrencyTypes.RMT.Id;
      }

      private static function LoadExtraPacks() : Boolean
      {
         var file:File = null;
         var stream:FileStream = null;
         var list:Array = null;
         var pack:Object = null;
         var pair:Array = null;
         var cardId:int = 0;
         var guaranteed:Vector.<RarityBoosterPackInfo> = null;
         var bonus:Vector.<RarityBoosterPackInfo> = null;
         var cards:Vector.<int> = null;
         try
         {
            file = File.applicationStorageDirectory.resolvePath("asset/gamedata/config/boosterpacks.json");
            if(!Loader.GameDataActive || !file.exists)
            {
               file = File.applicationDirectory.resolvePath("config/boosterpacks.json");
            }
            if(!file.exists)
            {
               return false;
            }
            stream = new FileStream();
            stream.open(file,FileMode.READ);
            list = JSON.parse(stream.readUTFBytes(stream.bytesAvailable)) as Array;
            stream.close();
            for each(pack in list)
            {
               if(GetBoosterByShopItemId(int(pack.shopItemId)) == null)
               {
                  guaranteed = new Vector.<RarityBoosterPackInfo>();
                  for each(pair in pack.guaranteed)
                  {
                     guaranteed.push(new RarityBoosterPackInfo(int(pair[0]),String(pair[1])));
                  }
                  bonus = new Vector.<RarityBoosterPackInfo>();
                  for each(pair in pack.bonus)
                  {
                     bonus.push(new RarityBoosterPackInfo(int(pair[0]),String(pair[1])));
                  }
                  cards = new Vector.<int>();
                  for each(cardId in pack.cards)
                  {
                     cards.push(cardId);
                     (int(pack.series) == 1 ? mCardTemplateIdSerie1List : mCardTemplateIdSerie2List).push(cardId);
                  }
                  new EBoosterPackInfo(int(pack.shopItemId),ExtraPackCurrency(String(pack.currency)),int(pack.cost),int(pack.id),String(pack.name),String(pack.description),guaranteed,bonus,cards,int(pack.frame),int(pack.series));
               }
            }
         }
         catch(error:Error)
         {
            return false;
         }
         return true;
      }
"""),
]

PATCHES = {
    LOADER: LOADER_EDITS,
    EXTERNAL_ASSET: EXTERNAL_ASSET_EDITS,
    ENGINE: ENGINE_EDITS,
    BOOSTER_INFO: BOOSTER_INFO_EDITS,
}
