package com.revival.friends
{
   import com.facebook.graph.core.FacebookURLDefaults;
   import com.frimastudio.mobile.asset.AssetManagerWrapper;
   import com.frimastudio.snowstorm.project.facebook.FacebookManagerMobile;
   import com.frimastudio.snowstorm.project.facebook.FacebookProxy;
   import com.frimastudio.snowstorm.project.login.YGOMLogin;
   import flash.events.Event;
   import flash.events.IOErrorEvent;
   import flash.events.SecurityErrorEvent;
   import flash.net.URLLoader;
   import flash.net.URLRequest;
   import starling.display.DisplayObjectContainer;
   import starling.display.Image;

   // "New" mark on the main menu Friends button while friend requests are waiting (server: me/revival_requests).
   // Online only; any error leaves the button as it is.
   public class RequestBadge
   {
      public function RequestBadge()
      {
         super();
      }

      public static function Attach(aButton:DisplayObjectContainer) : void
      {
         var loader:URLLoader = null;
         var onDone:Function = null;
         try
         {
            if(aButton == null || !YGOMLogin.IsLogguedIn())
            {
               return;
            }
            ChallengeToast.Start();
            loader = new URLLoader();
            onDone = function(aEvent:Event):void
            {
               loader.removeEventListener(Event.COMPLETE,onDone);
               loader.removeEventListener(IOErrorEvent.IO_ERROR,onDone);
               loader.removeEventListener(SecurityErrorEvent.SECURITY_ERROR,onDone);
               try
               {
                  if(aEvent.type == Event.COMPLETE && int(JSON.parse(String(loader.data)).incoming) > 0 && aButton.stage != null)
                  {
                     var mark:Image = AssetManagerWrapper.GetImage("mainmenu_newcontent");
                     mark.touchable = false;
                     mark.x = 100;
                     aButton.addChild(mark);
                  }
               }
               catch(error:Error)
               {
               }
            };
            loader.addEventListener(Event.COMPLETE,onDone);
            loader.addEventListener(IOErrorEvent.IO_ERROR,onDone);
            loader.addEventListener(SecurityErrorEvent.SECURITY_ERROR,onDone);
            loader.load(new URLRequest(FacebookURLDefaults.GRAPH_URL + "/me/revival_requests?access_token=" + encodeURIComponent((FacebookProxy as FacebookManagerMobile).AccessToken) + "&t=" + new Date().time));
         }
         catch(error:Error)
         {
         }
      }
   }
}
