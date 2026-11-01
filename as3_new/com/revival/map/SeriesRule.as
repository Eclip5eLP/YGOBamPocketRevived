package com.revival.map
{
   import com.frimastudio.common.core.manager.ManagerA;
   import com.frimastudio.snowstorm.common.deck.DeckUtil;
   import com.frimastudio.snowstorm.project.inventory.IInventoryManagerGame;
   import com.frimastudio.snowstorm.project.inventory.amf.Card;
   import com.frimastudio.snowstorm.project.inventory.amf.CardTemplate;
   import com.frimastudio.snowstorm.project.manager.EManagerDefinitionProject;
   import com.frimastudio.snowstorm.project.popup.PopupManagerUtil;

   // Chapters with a card series limit (layout property cardSerieLimit, e.g. 3 on World 2) only accept a play deck of
   // that series. The original game showed the limit ("Series 2 Cards Only") and limited instant decks to it, but never
   // checked a custom deck (DeckUtil.IsSeriesEnabledForDeck has no caller). StoryMap.EnergyCostNode (patched) asks
   // here before a duel costs energy.
   public class SeriesRule
   {
      public function SeriesRule()
      {
         super();
      }

      // True (and a popup is shown) when the play deck has a card of another series.
      public static function Blocks(aSeriesLimit:int) : Boolean
      {
         var inventory:IInventoryManagerGame = null;
         var template:CardTemplate = null;
         var wrong:int = 0;
         if(aSeriesLimit <= 0)
         {
            return false;
         }
         inventory = ManagerA.GetManager(EManagerDefinitionProject.INVENTORY_MANAGER) as IInventoryManagerGame;
         for each(var card:Card in DeckUtil.GetSelectedDeck(aSeriesLimit))
         {
            template = inventory.CacheLogic.GetTemplateById(card.itemTemplateId) as CardTemplate;
            if(template != null && template.cardSerieId != aSeriesLimit)
            {
               wrong++;
            }
         }
         if(wrong == 0)
         {
            return false;
         }
         PopupManagerUtil.ShowInfo("Series " + aSeriesLimit + " Cards Only","This chapter only allows Series " + aSeriesLimit + " cards. Your play deck has " + wrong + " card" + (wrong == 1 ? "" : "s") + " from other series.\n\nChoose or build a deck of Series " + aSeriesLimit + " cards in EDIT DECK.");
         return true;
      }
   }
}
