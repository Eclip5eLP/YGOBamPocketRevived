package com.revival.profile
{
   import com.facebook.graph.core.FacebookURLDefaults;
   import com.frimastudio.mobile.device.DeviceManager;
   import com.frimastudio.snowstorm.project.facebook.FacebookManagerMobile;
   import com.frimastudio.snowstorm.project.facebook.FacebookMobile;
   import com.frimastudio.snowstorm.project.facebook.FacebookProxy;
   import com.frimastudio.snowstorm.project.fonts.EFonts;
   import com.frimastudio.snowstorm.project.popup.popups.InfoPopup;
   import com.frimastudio.snowstorm.project.popup.PopupManager;
   import com.frimastudio.snowstorm.project.ui.ECommonButton;
   import com.frimastudio.utils.button.Scale9Button;
   import flash.display.Bitmap;
   import flash.display.Loader;
   import flash.events.IOErrorEvent;
   import flash.events.SecurityErrorEvent;
   import flash.geom.Point;
   import flash.geom.Rectangle;
   import flash.media.StageWebView;
   import flash.net.URLLoader;
   import flash.net.URLRequest;
   import starling.core.Starling;
   import starling.display.Image;
   import starling.display.Quad;
   import starling.events.Event;
   import starling.text.TextField;
   import starling.textures.Texture;
   import starling.utils.HAlign;
   import starling.utils.VAlign;

   // Player profile (main menu > Profile): picture, name, league, stars, cards, play deck, loaded from the
   // revival server (server/profiles.py). EDIT PROFILE opens the server's edit page in the in-app web view
   // (picture, username, password); the profile reloads when it closes. Network errors only show a message.
   public class ProfilePopup extends InfoPopup
   {
      private static const APP_ID:String = "145583478967400";

      private static const PICTURE_SIZE:int = 170;

      private var mPicture:Image;

      private var mPictureTexture:Texture;

      private var mLines:TextField;

      private var mName:TextField;

      private var mEditButton:Scale9Button;

      private var mDeckButton:Scale9Button;

      private var mDeck:Array;

      private var mDeckName:String;

      private var mLoader:URLLoader;

      private var mPictureLoader:Loader;

      public function ProfilePopup()
      {
         super();
      }

      override public function Dispose() : void
      {
         this.StopLoading();
         this.ClearPicture();
         this.mLines = null;
         this.mName = null;
         this.mEditButton = null;
         this.mDeckButton = null;
         this.mDeck = null;
         super.Dispose();
      }

      override public function Draw() : void
      {
         super.Draw();
         var frame:Quad = new Quad(PICTURE_SIZE + 8,PICTURE_SIZE + 8,7223);
         frame.x = 46;
         frame.y = 96;
         mUiContainer.addChild(frame);
         this.mName = new TextField(500,50,"",EFonts.HANZEL_BOLD,38,7223);
         this.mName.hAlign = HAlign.LEFT;
         this.mName.autoScale = true;
         this.mName.x = 250;
         this.mName.y = 92;
         mUiContainer.addChild(this.mName);
         this.mLines = new TextField(510,240,"Loading...",EFonts.HANZEL_BOLD,26,7223);
         this.mLines.hAlign = HAlign.LEFT;
         this.mLines.vAlign = VAlign.TOP;
         this.mLines.autoScale = true;
         this.mLines.x = 250;
         this.mLines.y = 148;
         mUiContainer.addChild(this.mLines);
         this.Reload();
      }

      override protected function AddButtons() : void
      {
         var data:ProfilePopupData = mPopupData as ProfilePopupData;
         CreateBaseButton("popup_close_btn",722,3);
         this.mDeckButton = CreateButton(ECommonButton.LIGHT_BLUE_BUTTON,new Point(330,90),data.CanEdit ? 50 : 235,410,"VIEW DECK",EFonts.HANZEL_BOLD,36,16777215);
         this.mDeckButton.visible = false;
         if(data.CanEdit)
         {
            this.mEditButton = CreateButton(ECommonButton.GREEN_BUTTON,new Point(330,90),420,410,"EDIT PROFILE",EFonts.HANZEL_BOLD,36,16777215);
         }
      }

      override protected function OnButtonTouch(aEvent:Event) : void
      {
         if(aEvent.currentTarget == this.mEditButton)
         {
            this.OpenEditPage();
            return;
         }
         if(aEvent.currentTarget == this.mDeckButton)
         {
            if(this.mDeck != null && this.mDeck.length > 0)
            {
               PopupManager.Show(new DeckViewPopupData(this.mDeckName,this.mDeck,(mPopupData as ProfilePopupData).CanEdit),false);
            }
            return;
         }
         super.OnButtonTouch(aEvent);
      }

      private function get Uid() : String
      {
         return (mPopupData as ProfilePopupData).Uid;
      }

      private function Reload() : void
      {
         this.StopLoading();
         this.mLoader = new URLLoader();
         this.mLoader.addEventListener(flash.events.Event.COMPLETE,this.OnProfileLoaded);
         this.mLoader.addEventListener(IOErrorEvent.IO_ERROR,this.OnLoadError);
         this.mLoader.addEventListener(SecurityErrorEvent.SECURITY_ERROR,this.OnLoadError);
         this.mLoader.load(new URLRequest(FacebookURLDefaults.GRAPH_URL + "/" + this.Uid + "/revival_profile?t=" + new Date().time));
         this.mPictureLoader = new Loader();
         this.mPictureLoader.contentLoaderInfo.addEventListener(flash.events.Event.COMPLETE,this.OnPictureLoaded);
         this.mPictureLoader.contentLoaderInfo.addEventListener(IOErrorEvent.IO_ERROR,this.OnLoadError);
         this.mPictureLoader.load(new URLRequest(FacebookURLDefaults.GRAPH_URL + "/" + this.Uid + "/picture?t=" + new Date().time));
      }

      private function StopLoading() : void
      {
         if(this.mLoader != null)
         {
            this.mLoader.removeEventListener(flash.events.Event.COMPLETE,this.OnProfileLoaded);
            this.mLoader.removeEventListener(IOErrorEvent.IO_ERROR,this.OnLoadError);
            this.mLoader.removeEventListener(SecurityErrorEvent.SECURITY_ERROR,this.OnLoadError);
            try
            {
               this.mLoader.close();
            }
            catch(error:Error)
            {
            }
            this.mLoader = null;
         }
         if(this.mPictureLoader != null)
         {
            this.mPictureLoader.contentLoaderInfo.removeEventListener(flash.events.Event.COMPLETE,this.OnPictureLoaded);
            this.mPictureLoader.contentLoaderInfo.removeEventListener(IOErrorEvent.IO_ERROR,this.OnLoadError);
            this.mPictureLoader = null;
         }
      }

      private function OnLoadError(aEvent:flash.events.Event) : void
      {
         if(this.mLines != null && aEvent.currentTarget == this.mLoader)
         {
            this.mLines.text = "The profile could not be loaded. Check your connection.";
         }
      }

      private function OnProfileLoaded(aEvent:flash.events.Event) : void
      {
         var profile:Object = null;
         if(this.mLines == null)
         {
            return;
         }
         try
         {
            profile = JSON.parse(String(this.mLoader.data));
            this.mName.text = String(profile.name);
            this.mDeck = profile.deck as Array;
            this.mDeckName = profile.deck_name ? String(profile.deck_name) : "DECK";
            this.mDeckButton.visible = this.mDeck != null && this.mDeck.length > 0;
            this.mLines.text = "Level " + profile.league + "     Stars " + profile.stars + "\n" + "Cards: " + profile.cards_unique + " different, " + profile.cards_total + " in total\n" + "Deck: " + (profile.deck_name ? profile.deck_name + " (" + profile.deck.length + " cards)" : profile.deck.length + " cards") + (profile.created ? "\nPlaying since " + this.FormatDate(Number(profile.created)) : "");
         }
         catch(error:Error)
         {
            this.mLines.text = "The profile could not be loaded.";
         }
      }

      private function FormatDate(aSeconds:Number) : String
      {
         var date:Date = new Date(aSeconds * 1000);
         return date.getFullYear() + "-" + String(101 + date.getMonth()).substr(1) + "-" + String(100 + date.getDate()).substr(1);
      }

      private function OnPictureLoaded(aEvent:flash.events.Event) : void
      {
         var bitmap:Bitmap = null;
         if(this.mLines == null)
         {
            return;
         }
         try
         {
            bitmap = this.mPictureLoader.content as Bitmap;
            this.ClearPicture();
            this.mPictureTexture = Texture.fromBitmapData(bitmap.bitmapData,false);
            this.mPicture = new Image(this.mPictureTexture);
            this.mPicture.width = PICTURE_SIZE;
            this.mPicture.height = PICTURE_SIZE;
            this.mPicture.x = 50;
            this.mPicture.y = 100;
            mUiContainer.addChild(this.mPicture);
         }
         catch(error:Error)
         {
            this.ClearPicture();
         }
      }

      private function ClearPicture() : void
      {
         if(this.mPicture != null)
         {
            this.mPicture.removeFromParent(true);
            this.mPicture = null;
         }
         if(this.mPictureTexture != null)
         {
            this.mPictureTexture.dispose();
            this.mPictureTexture = null;
         }
      }

      private function OpenEditPage() : void
      {
         var webView:StageWebView = null;
         var width:Number = NaN;
         var height:Number = NaN;
         try
         {
            webView = new StageWebView();
            webView.stage = Starling.current.nativeStage;
            width = Math.min(webView.stage.stageWidth * 0.8,900);
            height = webView.stage.stageHeight * 0.85;
            webView.viewPort = new Rectangle((webView.stage.stageWidth - width) * 0.5,(webView.stage.stageHeight - height) * 0.5,width,height);
            FacebookMobile.dialog("/revival_profile",this.OnEditClosed,Starling.current.nativeStage,webView,APP_ID,DeviceManager.GetInstance().IsMobile,{"access_token":(FacebookProxy as FacebookManagerMobile).AccessToken});
         }
         catch(error:Error)
         {
            this.mLines.text = "The profile editor could not be opened.";
         }
      }

      private function OnEditClosed(aResult:Object, aFail:Object) : void
      {
         if(this.mLines != null)
         {
            this.Reload();
         }
      }
   }
}
