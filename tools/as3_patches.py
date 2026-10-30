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
         return GameDataActive ? DownloadedGameDataVersion : BundledGameDataVersion;
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

PATCHES = {
    LOADER: LOADER_EDITS,
    EXTERNAL_ASSET: EXTERNAL_ASSET_EDITS,
}
