package com.revival.friends
{
   import com.frimastudio.mobile.device.DeviceManager;
   import com.frimastudio.snowstorm.project.facebook.FacebookManagerMobile;
   import com.frimastudio.snowstorm.project.facebook.FacebookMobile;
   import com.frimastudio.snowstorm.project.facebook.FacebookProxy;
   import com.frimastudio.snowstorm.project.popup.PopupManager;
   import com.revival.profile.ProfilePopupData;
   import flash.geom.Rectangle;
   import flash.media.StageWebView;
   import starling.core.Starling;

   // Friends manager (Duel Ground > Friends button): the server's friends page (server/friends_page.py) in the
   // in-app web view. "Profile" on the page closes it with ?view=<uid>, which opens that player's profile here.
   // The Duel Ground friend list shows changes the next time it opens. Returns false if it could not open.
   public class FriendsManager
   {
      private static const APP_ID:String = "145583478967400";

      public function FriendsManager()
      {
         super();
      }

      public static function Open() : Boolean
      {
         var webView:StageWebView = null;
         var width:Number = NaN;
         var height:Number = NaN;
         try
         {
            webView = new StageWebView();
            webView.stage = Starling.current.nativeStage;
            width = Math.min(webView.stage.stageWidth * 0.8,1000);
            height = webView.stage.stageHeight * 0.85;
            webView.viewPort = new Rectangle((webView.stage.stageWidth - width) * 0.5,(webView.stage.stageHeight - height) * 0.5,width,height);
            FacebookMobile.dialog("/revival_friends",OnClosed,Starling.current.nativeStage,webView,APP_ID,DeviceManager.GetInstance().IsMobile,{"access_token":(FacebookProxy as FacebookManagerMobile).AccessToken});
            return true;
         }
         catch(error:Error)
         {
         }
         return false;
      }

      private static function OnClosed(aResult:Object, aFail:Object) : void
      {
         try
         {
            if(aResult != null && aResult.view != null && String(aResult.view).length > 0)
            {
               PopupManager.Show(new ProfilePopupData(String(aResult.view),String(aResult.view) == String(FacebookProxy.OwnUser.uid)));
            }
         }
         catch(error:Error)
         {
         }
      }
   }
}
