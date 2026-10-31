package com.revival.rewards
{
   import com.facebook.graph.core.FacebookURLDefaults;
   import com.frimastudio.common.core.manager.ManagerA;
   import com.frimastudio.snowstorm.core.inventory.amf.Item;
   import com.frimastudio.snowstorm.project.avatar.IAvatarManagerGT;
   import com.frimastudio.snowstorm.project.engine.data.YGOMData;
   import com.frimastudio.snowstorm.project.facebook.FacebookManagerMobile;
   import com.frimastudio.snowstorm.project.facebook.FacebookProxy;
   import com.frimastudio.snowstorm.project.inventory.IInventoryManagerGame;
   import com.frimastudio.snowstorm.project.inventory.amf.InventoryChange;
   import com.frimastudio.snowstorm.project.inventory.enumeration.ContainerTypes;
   import com.frimastudio.snowstorm.project.login.YGOMLogin;
   import com.frimastudio.snowstorm.project.manager.EManagerDefinitionProject;
   import com.frimastudio.snowstorm.project.popup.PopupManager;
   import com.frimastudio.utils.object.ObjectGenerator;
   import com.revival.profile.DeckViewPopupData;
   import flash.events.Event;
   import flash.events.IOErrorEvent;
   import flash.events.SecurityErrorEvent;
   import flash.net.SharedObject;
   import flash.net.URLLoader;
   import flash.net.URLRequest;
   import flash.net.URLRequestMethod;
   import flash.net.URLVariables;

   // Card rewards from the server (server/rewards.py: Arena weekly rewards, God card tournament milestones). Checked
   // when the main menu opens (MainMenuView, patched): each pending reward adds its cards to the inventory like a
   // tournament reward (InventoryManagerGame.ConsumeTournamentReward), saves, shows the cards, then tells the server
   // it was received. Received ids are also kept on the device (SharedObject), so a reward whose confirmation was
   // lost is confirmed again but never added twice. Errors leave the reward on the server for the next check.
   public class RewardInbox
   {
      private static var mBusy:Boolean;

      public function RewardInbox()
      {
         super();
      }

      public static function Check() : void
      {
         var loader:URLLoader = null;
         var onDone:Function = null;
         try
         {
            if(mBusy || !YGOMLogin.IsLogguedIn())
            {
               return;
            }
            mBusy = true;
            loader = new URLLoader();
            onDone = function(aEvent:Event):void
            {
               loader.removeEventListener(Event.COMPLETE,onDone);
               loader.removeEventListener(IOErrorEvent.IO_ERROR,onDone);
               loader.removeEventListener(SecurityErrorEvent.SECURITY_ERROR,onDone);
               try
               {
                  if(aEvent.type == Event.COMPLETE)
                  {
                     Receive(JSON.parse(String(loader.data)).rewards as Array);
                  }
               }
               catch(error:Error)
               {
               }
               mBusy = false;
            };
            loader.addEventListener(Event.COMPLETE,onDone);
            loader.addEventListener(IOErrorEvent.IO_ERROR,onDone);
            loader.addEventListener(SecurityErrorEvent.SECURITY_ERROR,onDone);
            loader.load(new URLRequest(FacebookURLDefaults.GRAPH_URL + "/me/revival_rewards?access_token=" + encodeURIComponent(Token()) + "&t=" + new Date().time));
         }
         catch(error:Error)
         {
            mBusy = false;
         }
      }

      private static function Token() : String
      {
         return (FacebookProxy as FacebookManagerMobile).AccessToken;
      }

      private static function Receive(aRewards:Array) : void
      {
         var received:Object = Received();
         var added:Boolean = false;
         var shown:Array = [];
         for each(var reward:Object in aRewards || [])
         {
            var key:String = String(FacebookProxy.OwnUser.uid) + "_" + reward.id;
            try
            {
               if(received.data[key] != true)
               {
                  for each(var card:* in reward.cards)
                  {
                     AddCard(int(card));
                  }
                  received.data[key] = true;
                  added = true;
                  shown.push(reward);
               }
               Consume(int(reward.id));
            }
            catch(error:Error)
            {
            }
         }
         if(added)
         {
            try
            {
               received.flush();
            }
            catch(error:Error)
            {
            }
            YGOMData.Save(true);
         }
         for each(reward in shown)
         {
            PopupManager.Show(new DeckViewPopupData(String(reward.title),reward.cards,false,String(reward.text) + "\n\nThe card" + (reward.cards.length == 1 ? " is" : "s are") + " now in your collection. Tap a card to see it."));
         }
      }

      private static function Received() : SharedObject
      {
         return SharedObject.getLocal("revival_rewards");
      }

      // Same steps as InventoryManagerGame.ConsumeTournamentReward for a card.
      private static function AddCard(aTemplateId:int) : void
      {
         var inventory:IInventoryManagerGame = ManagerA.GetManager(EManagerDefinitionProject.INVENTORY_MANAGER) as IInventoryManagerGame;
         var avatarId:int = int((ManagerA.GetManager(EManagerDefinitionProject.AVATAR_MANAGER) as IAvatarManagerGT).GetSelectedAvatarId());
         var container:Item = inventory.CacheLogic.GetFloatingContainer(avatarId,ContainerTypes.INVENTORY.Id);
         var existing:Vector.<Item> = inventory.CacheLogic.GetItemListByItemTemplateId(container.id,aTemplateId);
         var change:InventoryChange = new InventoryChange();
         var item:Item = null;
         change.addedItems = [];
         change.updatedItems = [];
         change.deletedItems = [];
         if(existing != null && existing.length > 0)
         {
            item = ObjectGenerator.CopyItem(existing[0]);
            item.quantity += 1;
            change.updatedItems.push(item);
         }
         else
         {
            item = ObjectGenerator.CreateItemFromTemplateId(aTemplateId,YGOMData.GetNextId());
            item.quantity = 1;
            change.addedItems.push(item);
         }
         inventory.ParseInventoryChange(change);
      }

      private static function Consume(aId:int) : void
      {
         var loader:URLLoader = new URLLoader();
         var request:URLRequest = new URLRequest(FacebookURLDefaults.GRAPH_URL + "/me/revival_rewards");
         var vars:URLVariables = new URLVariables();
         vars.access_token = Token();
         vars.consume = aId;
         request.method = URLRequestMethod.POST;
         request.data = vars;
         loader.addEventListener(IOErrorEvent.IO_ERROR,Ignore);
         loader.addEventListener(SecurityErrorEvent.SECURITY_ERROR,Ignore);
         loader.load(request);
      }

      private static function Ignore(aEvent:Event) : void
      {
      }
   }
}
