package com.revival.friends
{
   import com.facebook.graph.core.FacebookURLDefaults;
   import com.frimastudio.common.core.manager.ManagerA;
   import com.frimastudio.snowstorm.livepvp.util.LivePvpUtil;
   import com.frimastudio.snowstorm.module.tournament.popup.data.TournamentTutorialPopupData;
   import com.frimastudio.snowstorm.module.tournament.popup.duel.data.TournamentDuelFoundPopupData;
   import com.frimastudio.snowstorm.module.tournament.popup.duel.data.TournamentDuelSearchPopupData;
   import com.frimastudio.snowstorm.project.facebook.FacebookManagerMobile;
   import com.frimastudio.snowstorm.project.facebook.FacebookProxy;
   import com.frimastudio.snowstorm.project.inventory.IInventoryManagerGame;
   import com.frimastudio.snowstorm.project.livepvp.amf.StartDuelNotification;
   import com.frimastudio.snowstorm.project.login.YGOMPvPLogin;
   import com.frimastudio.snowstorm.project.manager.EManagerDefinitionProject;
   import com.frimastudio.snowstorm.project.popup.PopupManager;
   import com.frimastudio.snowstorm.project.popup.PopupManagerUtil;
   import com.frimastudio.snowstorm.project.popup.event.PopupManagerEvent;
   import com.frimastudio.snowstorm.project.popup.popups.Popup;
   import com.frimastudio.snowstorm.project.tournament.TournamentManagerProxy;
   import flash.events.Event;
   import flash.events.IOErrorEvent;
   import flash.events.SecurityErrorEvent;
   import flash.net.URLLoader;
   import flash.net.URLRequest;
   import flash.net.URLRequestMethod;
   import flash.net.URLVariables;

   // Live duel with a friend (friends page "Live duel" / "Accept", profile LIVE DUEL). The server is told whom we
   // wait for (POST me/revival_challenge, server/livepvp.py challenges), then the Tournament screen opens (its
   // popups need the tournament assets) and shows the game's own search popup; the server pairs us only with that
   // friend once they challenge us back. The duel itself is the tournament's live duel, unranked. Cancel in the
   // search popup leaves the queue and drops the challenge. Errors only show a message.
   public class LiveChallenge
   {
      private static var mPending:String;

      public function LiveChallenge()
      {
         super();
      }

      public static function Start(aUid:String) : void
      {
         var loader:URLLoader = null;
         var request:URLRequest = null;
         var vars:URLVariables = null;
         var onDone:Function = null;
         try
         {
            if(!YGOMPvPLogin.IsLogguedIn())
            {
               PopupManagerUtil.ShowInfo("LIVE DUEL","Live duels need the connection to the server. Try again in a moment.",false);
               return;
            }
            if((ManagerA.GetManager(EManagerDefinitionProject.INVENTORY_MANAGER) as IInventoryManagerGame).GetDefaultDeck() == null)
            {
               PopupManagerUtil.ShowInfo("LIVE DUEL","Choose your play deck first: Edit Deck, then My Play Deck.",false);
               return;
            }
            loader = new URLLoader();
            onDone = function(aEvent:Event):void
            {
               var result:Object = null;
               loader.removeEventListener(Event.COMPLETE,onDone);
               loader.removeEventListener(IOErrorEvent.IO_ERROR,onDone);
               loader.removeEventListener(SecurityErrorEvent.SECURITY_ERROR,onDone);
               try
               {
                  result = aEvent.type == Event.COMPLETE ? JSON.parse(String(loader.data)) : null;
                  if(result == null || result.ok != true)
                  {
                     PopupManagerUtil.ShowInfo("LIVE DUEL",result != null && result.error ? String(result.error) : "The live duel could not be started. Check your connection.",false);
                     return;
                  }
                  mPending = aUid;
                  TournamentManagerProxy.OpenTournamentModule();
               }
               catch(error:Error)
               {
                  mPending = null;
               }
            };
            loader.addEventListener(Event.COMPLETE,onDone);
            loader.addEventListener(IOErrorEvent.IO_ERROR,onDone);
            loader.addEventListener(SecurityErrorEvent.SECURITY_ERROR,onDone);
            vars = new URLVariables();
            vars.access_token = (FacebookProxy as FacebookManagerMobile).AccessToken;
            vars.to = aUid;
            request = new URLRequest(FacebookURLDefaults.GRAPH_URL + "/me/revival_challenge");
            request.method = URLRequestMethod.POST;
            request.data = vars;
            loader.load(request);
         }
         catch(error:Error)
         {
         }
      }

      // TournamentView.InitComplete: start the search of a pending challenge (the tutorial first, like the
      // tournament's own LIVE DUEL button).
      public static function OnTournamentScreenReady() : void
      {
         var popup:Popup = null;
         if(mPending == null)
         {
            return;
         }
         mPending = null;
         try
         {
            if(LivePvpUtil.IsLivePvpTutoNeeded())
            {
               // first live duel of this account: the tutorial, then the search (dropping the challenge here
               // cancelled every first challenge of a new account)
               popup = PopupManager.Show(new TournamentTutorialPopupData());
               popup.addEventListener(PopupManagerEvent.POPUP_CLOSED,OnTutorialClosed);
               return;
            }
            ShowSearch();
         }
         catch(error:Error)
         {
            Clear();
         }
      }

      private static function OnTutorialClosed(aEvent:PopupManagerEvent) : void
      {
         (aEvent.currentTarget as Popup).removeEventListener(PopupManagerEvent.POPUP_CLOSED,OnTutorialClosed);
         try
         {
            ShowSearch();
         }
         catch(error:Error)
         {
            Clear();
         }
      }

      private static function ShowSearch() : void
      {
         var popup:Popup = PopupManager.Show(new TournamentDuelSearchPopupData());
         popup.addEventListener(PopupManagerEvent.POPUP_CLOSED,OnSearchClosed);
      }

      private static function Ignore(aEvent:Event) : void
      {
      }

      private static function Clear() : void
      {
         var loader:URLLoader = null;
         var request:URLRequest = null;
         var vars:URLVariables = null;
         try
         {
            vars = new URLVariables();
            vars.access_token = (FacebookProxy as FacebookManagerMobile).AccessToken;
            vars.to = "0";
            request = new URLRequest(FacebookURLDefaults.GRAPH_URL + "/me/revival_challenge");
            request.method = URLRequestMethod.POST;
            request.data = vars;
            loader = new URLLoader();
            loader.addEventListener(IOErrorEvent.IO_ERROR,Ignore);
            loader.addEventListener(SecurityErrorEvent.SECURITY_ERROR,Ignore);
            loader.load(request);
         }
         catch(error:Error)
         {
         }
      }

      private static function OnSearchClosed(aEvent:PopupManagerEvent) : void
      {
         var data:TournamentDuelFoundPopupData = null;
         (aEvent.currentTarget as Popup).removeEventListener(PopupManagerEvent.POPUP_CLOSED,OnSearchClosed);
         if(aEvent.CustomData != null)
         {
            data = new TournamentDuelFoundPopupData();
            data.DuelInfo = aEvent.CustomData as StartDuelNotification;
            PopupManager.Show(data);
         }
      }
   }
}
