package com.revival.friends
{
   import com.facebook.graph.core.FacebookURLDefaults;
   import com.frimastudio.mobile.asset.AssetManagerWrapper;
   import com.frimastudio.mobile.module.EStarlingModuleDefinition;
   import com.frimastudio.mobile.module.StarlingModuleManager;
   import com.frimastudio.snowstorm.project.facebook.FacebookManagerMobile;
   import com.frimastudio.snowstorm.project.facebook.FacebookProxy;
   import com.frimastudio.snowstorm.project.fonts.EFonts;
   import com.frimastudio.snowstorm.project.login.YGOMLogin;
   import com.frimastudio.snowstorm.project.ui.ECommonButton;
   import com.frimastudio.utils.button.Scale9Button;
   import flash.events.IOErrorEvent;
   import flash.events.SecurityErrorEvent;
   import flash.events.TimerEvent;
   import flash.geom.Point;
   import flash.net.URLLoader;
   import flash.net.URLRequest;
   import flash.utils.Timer;
   import starling.core.Starling;
   import starling.display.Quad;
   import starling.display.Sprite;
   import starling.events.Event;
   import starling.text.TextField;
   import starling.utils.HAlign;

   // In-game notice when a friend challenges you to a live duel: a bar at the top of the screen with ACCEPT (starts
   // the duel, LiveChallenge) and LATER. Polls me/revival_requests every POLL_MS while logged in, not during a duel;
   // each waiting challenger is shown once until their challenge ends. Started from the main menu (RequestBadge);
   // errors are ignored, the friends page still lists the challenge.
   public class ChallengeToast
   {
      private static const POLL_MS:int = 20000;

      private static const SHOW_MS:int = 30000;

      private static var mTimer:Timer;

      private static var mLoader:URLLoader;

      private static var mShown:Object = {};

      private static var mToast:Sprite;

      private static var mHideTimer:Timer;

      private static var mAccept:Scale9Button;

      private static var mLater:Scale9Button;

      private static var mUid:String;

      public function ChallengeToast()
      {
         super();
      }

      public static function Start() : void
      {
         try
         {
            if(mTimer != null)
            {
               return;
            }
            mTimer = new Timer(POLL_MS);
            mTimer.addEventListener(TimerEvent.TIMER,Poll);
            mTimer.start();
            Poll(null);
         }
         catch(error:Error)
         {
         }
      }

      private static function Poll(aEvent:TimerEvent) : void
      {
         try
         {
            if(mLoader != null || !YGOMLogin.IsLogguedIn() || StarlingModuleManager.MainModuleDefinition == EStarlingModuleDefinition.CARD_GAME)
            {
               return;
            }
            mLoader = new URLLoader();
            mLoader.addEventListener(flash.events.Event.COMPLETE,OnLoaded);
            mLoader.addEventListener(IOErrorEvent.IO_ERROR,OnLoaded);
            mLoader.addEventListener(SecurityErrorEvent.SECURITY_ERROR,OnLoaded);
            mLoader.load(new URLRequest(FacebookURLDefaults.GRAPH_URL + "/me/revival_requests?access_token=" + encodeURIComponent((FacebookProxy as FacebookManagerMobile).AccessToken) + "&t=" + new Date().time));
         }
         catch(error:Error)
         {
            mLoader = null;
         }
      }

      private static function OnLoaded(aEvent:flash.events.Event) : void
      {
         var loader:URLLoader = mLoader;
         var waiting:Object = {};
         var next:Object = null;
         mLoader = null;
         try
         {
            loader.removeEventListener(flash.events.Event.COMPLETE,OnLoaded);
            loader.removeEventListener(IOErrorEvent.IO_ERROR,OnLoaded);
            loader.removeEventListener(SecurityErrorEvent.SECURITY_ERROR,OnLoaded);
            if(aEvent.type != flash.events.Event.COMPLETE)
            {
               return;
            }
            for each(var challenger:Object in JSON.parse(String(loader.data)).challengers as Array)
            {
               waiting[String(challenger.uid)] = true;
               if(next == null && mShown[String(challenger.uid)] != true)
               {
                  next = challenger;
               }
            }
            mShown = waiting;
            if(next != null && StarlingModuleManager.MainModuleDefinition != EStarlingModuleDefinition.CARD_GAME)
            {
               Show(String(next.uid),String(next.name));
            }
         }
         catch(error:Error)
         {
         }
      }

      private static function Show(aUid:String, aName:String) : void
      {
         var width:Number = NaN;
         var text:TextField = null;
         Hide();
         mUid = aUid;
         width = Math.min(Starling.current.stage.stageWidth - 40,980);
         mToast = new Sprite();
         var back:Quad = new Quad(width,120,2839);
         back.alpha = 0.94;
         mToast.addChild(back);
         var line:Quad = new Quad(width,4,5287936);
         line.y = 116;
         mToast.addChild(line);
         text = new TextField(width - 400,120,aName + " challenges you to a live duel!",EFonts.HANZEL_BOLD,28,16777215);
         text.hAlign = HAlign.LEFT;
         text.autoScale = true;
         text.x = 24;
         text.touchable = false;
         mToast.addChild(text);
         mAccept = AssetManagerWrapper.GetButton(ECommonButton.GREEN_BUTTON,new Point(190,80),"ACCEPT",EFonts.HANZEL_BOLD,28,16777215);
         mAccept.x = width - 370;
         mAccept.y = 20;
         mAccept.addEventListener(Event.TRIGGERED,OnAccept);
         mToast.addChild(mAccept);
         mLater = AssetManagerWrapper.GetButton(ECommonButton.LIGHT_BLUE_BUTTON,new Point(160,80),"LATER",EFonts.HANZEL_BOLD,28,16777215);
         mLater.x = width - 170;
         mLater.y = 20;
         mLater.addEventListener(Event.TRIGGERED,OnLater);
         mToast.addChild(mLater);
         mToast.x = (Starling.current.stage.stageWidth - width) * 0.5;
         mToast.y = 12;
         Starling.current.stage.addChild(mToast);
         mHideTimer = new Timer(SHOW_MS,1);
         mHideTimer.addEventListener(TimerEvent.TIMER_COMPLETE,OnHideTimer);
         mHideTimer.start();
      }

      private static function OnAccept(aEvent:Event) : void
      {
         var uid:String = mUid;
         Hide();
         if(StarlingModuleManager.MainModuleDefinition != EStarlingModuleDefinition.CARD_GAME)
         {
            LiveChallenge.Start(uid);
         }
      }

      private static function OnLater(aEvent:Event) : void
      {
         Hide();
      }

      private static function OnHideTimer(aEvent:TimerEvent) : void
      {
         Hide();
      }

      private static function Hide() : void
      {
         try
         {
            if(mHideTimer != null)
            {
               mHideTimer.stop();
               mHideTimer.removeEventListener(TimerEvent.TIMER_COMPLETE,OnHideTimer);
               mHideTimer = null;
            }
            if(mAccept != null)
            {
               mAccept.removeEventListener(Event.TRIGGERED,OnAccept);
               mAccept = null;
            }
            if(mLater != null)
            {
               mLater.removeEventListener(Event.TRIGGERED,OnLater);
               mLater = null;
            }
            if(mToast != null)
            {
               mToast.removeFromParent(true);
               mToast = null;
            }
         }
         catch(error:Error)
         {
         }
      }
   }
}
