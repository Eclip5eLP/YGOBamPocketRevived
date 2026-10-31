package com.revival.profile
{
   import com.frimastudio.common.core.manager.ManagerA;
   import com.frimastudio.snowstorm.module.deckbuilder.util.DeckBuilderUtil;
   import com.frimastudio.snowstorm.project.engine.data.YGOMData;
   import com.frimastudio.snowstorm.project.inventory.IInventoryManagerGame;
   import com.frimastudio.snowstorm.project.inventory.InventoryManagerEventGame;
   import flash.events.EventDispatcher;
   import com.frimastudio.snowstorm.project.inventory.amf.Card;
   import com.frimastudio.snowstorm.project.inventory.amf.FullDeck;
   import com.frimastudio.snowstorm.project.manager.EManagerDefinitionProject;
   import com.frimastudio.utils.object.ObjectGenerator;

   // Copy another player's deck (profile > COPY DECK) into a new deck of your own, built from cards in your
   // collection with the game's own BuildDeck (the cards move from the collection into the deck, like in the deck
   // builder). Nothing is built when a card is missing.
   public class DeckCopier
   {
      public function DeckCopier()
      {
         super();
      }

      // Number of deck cards you don't have free in your collection (0 = the deck can be copied).
      public static function MissingCount(aCards:Array) : int
      {
         var needed:Object = Count(aCards);
         var owned:Object = OwnedStacks();
         var missing:int = 0;
         for(var id:String in needed)
         {
            missing += Math.max(0,int(needed[id]) - (owned[id] != null ? int((owned[id] as Card).quantity) : 0));
         }
         return missing;
      }

      // Builds the deck and saves; returns false (and builds nothing) if a card is missing. Same steps as the deck
      // builder: an empty deck (BuildDeck), then its cards one entry per slot (UpdateFullDeck, which takes each card
      // out of the collection).
      public static function Copy(aCards:Array, aDeckName:String) : Boolean
      {
         var card:Card = null;
         var built:FullDeck = null;
         var onBuilt:Function = null;
         var inventory:IInventoryManagerGame = ManagerA.GetManager(EManagerDefinitionProject.INVENTORY_MANAGER) as IInventoryManagerGame;
         var owned:Object = OwnedStacks();
         if(MissingCount(aCards) > 0)
         {
            return false;
         }
         onBuilt = function(aEvent:InventoryManagerEventGame):void
         {
            built = aEvent.EventItem as FullDeck;
         };
         (inventory as EventDispatcher).addEventListener(InventoryManagerEventGame.ON_BUILD_DECK,onBuilt);
         try
         {
            inventory.BuildDeck(DeckBuilderUtil.GenerateEmptyDeck(aDeckName.substr(0,25)));
         }
         finally
         {
            (inventory as EventDispatcher).removeEventListener(InventoryManagerEventGame.ON_BUILD_DECK,onBuilt);
         }
         if(built == null)
         {
            return false;
         }
         built.amfCards = [];
         for each(var id:* in aCards)
         {
            card = ObjectGenerator.CopyItem(owned[String(int(id))] as Card) as Card;
            card.quantity = 1;
            built.amfCards.push(card);
         }
         inventory.UpdateFullDeck(built);
         YGOMData.Save();
         return true;
      }

      private static function Count(aCards:Array) : Object
      {
         var counts:Object = {};
         for each(var id:* in aCards)
         {
            counts[String(int(id))] = int(counts[String(int(id))]) + 1;
         }
         return counts;
      }

      // template id -> the collection stack of that card (cards not in a deck)
      private static function OwnedStacks() : Object
      {
         var stacks:Object = {};
         var inventory:IInventoryManagerGame = ManagerA.GetManager(EManagerDefinitionProject.INVENTORY_MANAGER) as IInventoryManagerGame;
         for each(var card:Card in inventory.GetCompleteDifferentFloatingCardList())
         {
            stacks[String(card.itemTemplateId)] = card;
         }
         return stacks;
      }
   }
}
