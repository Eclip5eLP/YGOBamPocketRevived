package com.revival.profile
{
   import com.frimastudio.snowstorm.project.popup.data.InfoPopupData;

   // Read-only deck view (profile > VIEW DECK): the deck's card template ids, shown 5x3 like the deck builder.
   public class DeckViewPopupData extends InfoPopupData
   {
      public var Cards:Array;

      public var ShowOwnedQuantity:Boolean;

      public function DeckViewPopupData(aTitle:String, aCards:Array, aShowOwnedQuantity:Boolean)
      {
         super(aTitle);
         this.Cards = aCards;
         this.ShowOwnedQuantity = aShowOwnedQuantity;
      }

      override public function get PopupClass() : Class
      {
         return DeckViewPopup;
      }
   }
}
