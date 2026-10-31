package com.revival.web
{
   import flash.net.SharedObject;
   import flash.utils.ByteArray;
   import starling.core.Starling;

   // Browser build only (tools/as3_patches.py WEB_EDITS, YGO_WEB=1; unused in the APK). In the browser (Ruffle)
   // there is no app storage: downloaded content is read from the server under STORAGE (the content packages,
   // extracted, tools/build_web.py), and the local save lives in a SharedObject (the browser's localStorage).
   public class Web
   {
      // relative to the page: <origin>/storage/asset/...
      public static const STORAGE:String = "storage/";

      private static var mSaves:SharedObject;

      public function Web()
      {
         super();
      }

      // The page's host[:port] (the page passes it as the "origin" parameter): content and the startup text come
      // from where the page came from, whatever host the game server names. Falls back to aDefault.
      public static function Host(aDefault:String) : String
      {
         try
         {
            var origin:String = String(Starling.current.nativeStage.loaderInfo.parameters.origin || "");
            if(origin != "")
            {
               return origin;
            }
         }
         catch(error:Error)
         {
         }
         return aDefault;
      }

      public static function ReadSave(aName:String) : ByteArray
      {
         var copy:ByteArray = null;
         try
         {
            var stored:ByteArray = Saves().data[aName] as ByteArray;
            if(stored != null && stored.length > 0)
            {
               copy = new ByteArray();
               copy.writeBytes(stored);
               copy.position = 0;
            }
         }
         catch(error:Error)
         {
         }
         return copy;
      }

      public static function WriteSave(aName:String, aBytes:ByteArray) : void
      {
         try
         {
            Saves().data[aName] = aBytes;
            Saves().flush();
         }
         catch(error:Error)
         {
         }
      }

      public static function DeleteSave(aName:String) : void
      {
         try
         {
            delete Saves().data[aName];
            Saves().flush();
         }
         catch(error:Error)
         {
         }
      }

      private static function Saves() : SharedObject
      {
         if(mSaves == null)
         {
            mSaves = SharedObject.getLocal("revival_web_save","/");
         }
         return mSaves;
      }
   }
}
