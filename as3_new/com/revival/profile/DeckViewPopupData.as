package com.revival.profile
{
   import com.frimastudio.snowstorm.project.popup.data.InfoPopupData;

   // Read-only deck view (profile > VIEW DECK): the deck's card template ids, shown 5x3 like the deck builder.
   // With a Message (card rewards, as3_new/com/revival/rewards): one row of cards and the message below it.
   public class DeckViewPopupData extends InfoPopupData
   {
      public var Cards:Array;

      public var ShowOwnedQuantity:Boolean;

      public var Message:String;

      public function DeckViewPopupData(aTitle:String, aCards:Array, aShowOwnedQuantity:Boolean, aMessage:String = null)
      {
         super(aTitle);
         this.Cards = aCards;
         this.ShowOwnedQuantity = aShowOwnedQuantity;
         this.Message = aMessage;
      }

      override public function get PopupClass() : Class
      {
         return DeckViewPopup;
      }
   }
}
