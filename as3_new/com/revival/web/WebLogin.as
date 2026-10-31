package com.revival.web
{
   import flash.external.ExternalInterface;

   // Browser build only (as3_patches.py WEB_EDITS): the login page opens in a frame over the game on the web page
   // (page function revivalLogin, tools/web_spike.py / server.py web page) instead of the Android web view. The page
   // calls back revivalLoginDone with the fb<appId>://authorize#... link the login page ends on (null = cancelled),
   // which goes to the game's own ProcessLogin.
   public class WebLogin
   {
      private static var mDone:Function;

      private static var mRegistered:Boolean;

      public function WebLogin()
      {
         super();
      }

      // false: no page to talk to (the caller keeps its own login path)
      public static function Open(aUrl:String, aDone:Function) : Boolean
      {
         try
         {
            if(!ExternalInterface.available)
            {
               return false;
            }
            if(!mRegistered)
            {
               ExternalInterface.addCallback("revivalLoginDone",OnDone);
               mRegistered = true;
            }
            mDone = aDone;
            ExternalInterface.call("revivalLogin",aUrl);
            return true;
         }
         catch(error:Error)
         {
         }
         return false;
      }

      private static function OnDone(aLocation:String) : void
      {
         var done:Function = mDone;
         mDone = null;
         if(done != null)
         {
            done(aLocation != null && aLocation != "" ? aLocation : null);
         }
      }
   }
}
