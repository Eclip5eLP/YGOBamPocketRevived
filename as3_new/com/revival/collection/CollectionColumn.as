package com.revival.collection
{
   import com.frimastudio.mobile.adaptativeui.scroller.display.Scrollable;
   import com.frimastudio.utils.cardloading.QueuedCardLoader;
   import com.frimastudio.utils.rendering.card.SmallCard;
   import com.frimastudio.utils.rendering.card.util.CardQuantityDisplay;
   import starling.events.Touch;
   import starling.events.TouchEvent;
   import starling.events.TouchPhase;

   // A column of small cards in the collection grid, each with its owned quantity; unowned cards are dimmed.
   // The scroller reports a tap on the column; TouchedTemplateId says which card of the column was touched.
   public class CollectionColumn extends Scrollable
   {
      public static const ROWS:int = 3;

      public static const SCALE:Number = 0.86;

      public static const CELL:int = 142;

      public static const WIDTH:int = 120;

      private var mCards:Vector.<SmallCard> = new Vector.<SmallCard>();

      private var mQuantities:Vector.<CardQuantityDisplay> = new Vector.<CardQuantityDisplay>();

      private var mTouchedIndex:int = -1;

      public function CollectionColumn()
      {
         super();
      }

      override public function dispose() : void
      {
         this.ClearCards();
         this.mCards = null;
         this.mQuantities = null;
         super.dispose();
      }

      override public function Reset() : void
      {
         this.ClearCards();
         super.Reset();
      }

      override public function RefreshRender() : void
      {
         var i:int = 0;
         var card:SmallCard = null;
         var quantity:CardQuantityDisplay = null;
         var data:CollectionColumnData = scrollerData as CollectionColumnData;
         this.ClearCards();
         for(i = 0; i < data.Templates.length; i++)
         {
            card = new SmallCard(data.Templates[i].id,false);
            card.scaleX = card.scaleY = SCALE;
            card.y = i * CELL;
            card.alpha = data.Quantities[i] > 0 ? 1 : 0.45;
            card.addEventListener(TouchEvent.TOUCH,this.OnCardTouch);
            addChild(card);
            this.mCards.push(card);
            quantity = new CardQuantityDisplay();
            quantity.scaleX = quantity.scaleY = SCALE;
            quantity.x = 10;
            quantity.y = card.y + 108;
            quantity.touchable = false;
            quantity.UpdateQuantity(data.Quantities[i]);
            addChild(quantity);
            this.mQuantities.push(quantity);
            if(!QueuedCardLoader.IsQueued(data.Templates[i].id))
            {
               this.ShowCard(i);
            }
         }
         super.RefreshRender();
      }

      override public function SoftRefresh() : void
      {
         var data:CollectionColumnData = scrollerData as CollectionColumnData;
         for(var i:int = 0; i < this.mQuantities.length && i < data.Quantities.length; i++)
         {
            this.mQuantities[i].UpdateQuantity(data.Quantities[i]);
            this.mCards[i].alpha = data.Quantities[i] > 0 ? 1 : 0.45;
         }
         super.SoftRefresh();
      }

      public function OnCardLoaded(aTemplateId:int) : void
      {
         var data:CollectionColumnData = scrollerData as CollectionColumnData;
         if(data == null)
         {
            return;
         }
         for(var i:int = 0; i < this.mCards.length && i < data.Templates.length; i++)
         {
            if(data.Templates[i].id == aTemplateId)
            {
               this.ShowCard(i);
            }
         }
      }

      public function get TouchedTemplateId() : int
      {
         var data:CollectionColumnData = scrollerData as CollectionColumnData;
         if(data == null || this.mTouchedIndex < 0 || this.mTouchedIndex >= data.Templates.length)
         {
            return -1;
         }
         return data.Templates[this.mTouchedIndex].id;
      }

      private function ShowCard(aIndex:int) : void
      {
         try
         {
            this.mCards[aIndex].DisplayCardVisual();
         }
         catch(error:Error)
         {
         }
      }

      private function OnCardTouch(aEvent:TouchEvent) : void
      {
         var touch:Touch = aEvent.getTouch(aEvent.currentTarget as SmallCard,TouchPhase.BEGAN);
         if(touch != null)
         {
            this.mTouchedIndex = this.mCards.indexOf(aEvent.currentTarget as SmallCard);
         }
      }

      private function ClearCards() : void
      {
         var card:SmallCard = null;
         var quantity:CardQuantityDisplay = null;
         if(this.mCards != null)
         {
            for each(card in this.mCards)
            {
               card.removeEventListener(TouchEvent.TOUCH,this.OnCardTouch);
               card.removeFromParent(true);
            }
            this.mCards.length = 0;
         }
         if(this.mQuantities != null)
         {
            for each(quantity in this.mQuantities)
            {
               quantity.removeFromParent(true);
            }
            this.mQuantities.length = 0;
         }
         this.mTouchedIndex = -1;
      }
   }
}
