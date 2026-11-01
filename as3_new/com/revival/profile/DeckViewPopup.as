package com.revival.profile
{
   import com.frimastudio.mobile.util.MobileUtils;
   import com.frimastudio.snowstorm.module.deckbuilder.popup.data.FullCardPopupData;
   import com.frimastudio.snowstorm.project.popup.PopupManager;
   import com.frimastudio.snowstorm.project.fonts.EFonts;
   import com.frimastudio.snowstorm.project.popup.popups.InfoPopup;
   import com.frimastudio.utils.cardloading.QueuedCardLoader;
   import com.frimastudio.utils.cardloading.event.QueuedCardLoaderEvent;
   import com.frimastudio.utils.rendering.card.CardVisual;
   import com.frimastudio.utils.rendering.card.CardVisualUtil;
   import com.frimastudio.utils.rendering.card.SmallCard;
   import com.frimastudio.utils.rendering.card.enum.ECardVisualType;
   import starling.display.Quad;
   import starling.events.EventDispatcher;
   import starling.events.Touch;
   import starling.events.TouchEvent;
   import starling.events.TouchPhase;
   import starling.text.TextField;
   import starling.utils.HAlign;
   import starling.utils.VAlign;

   // Read-only deck view: the deck's cards in a 5x3 grid (like the deck builder) and a preview on the right.
   // Tap a card to preview it, tap the preview for the full card popup. Cards load through QueuedCardLoader.
   public class DeckViewPopup extends InfoPopup
   {
      private static const COLUMNS:int = 5;

      private static const SCALE:Number = 0.8;

      private static const CELL:int = 106;

      private static const GRID_X:int = 30;

      private static const GRID_Y:int = 88;

      private static const PREVIEW_SCALE:Number = 0.4;

      private var mCards:Vector.<SmallCard> = new Vector.<SmallCard>();

      private var mIds:Vector.<int> = new Vector.<int>();

      private var mPreview:CardVisual;

      private var mPreviewId:int = -1;

      private var mPendingPreviewId:int = -1;

      public function DeckViewPopup()
      {
         super();
      }

      override public function Dispose() : void
      {
         var card:SmallCard = null;
         (QueuedCardLoader as EventDispatcher).removeEventListener(QueuedCardLoaderEvent.ON_CARD_LOADED,this.OnCardLoaded);
         this.ClearPreview();
         for each(card in this.mCards)
         {
            card.removeEventListener(TouchEvent.TOUCH,this.OnCardTouch);
         }
         this.mCards.length = 0;
         for each(var id:int in this.mIds)
         {
            QueuedCardLoader.RemoveCardByTemplateId(id);
         }
         this.mIds.length = 0;
         super.Dispose();
      }

      override protected function AddButtons() : void
      {
         CreateBaseButton("popup_close_btn",722,3);
      }

      override public function Draw() : void
      {
         var i:int = 0;
         var id:int = 0;
         var card:SmallCard = null;
         var slot:Quad = null;
         super.Draw();
         var cards:Array = (mPopupData as DeckViewPopupData).Cards || [];
         var message:String = (mPopupData as DeckViewPopupData).Message;
         var text:TextField = null;
         (QueuedCardLoader as EventDispatcher).addEventListener(QueuedCardLoaderEvent.ON_CARD_LOADED,this.OnCardLoaded);
         if(message)
         {
            text = new TextField(COLUMNS * CELL,cards.length > 2 * COLUMNS ? CELL - 10 : 2 * CELL - 20,message,EFonts.HANZEL_BOLD,26,7223);
            text.hAlign = HAlign.LEFT;
            text.vAlign = VAlign.TOP;
            text.autoScale = true;
            text.x = GRID_X;
            text.y = GRID_Y + Math.max(1,Math.ceil(Math.min(cards.length,15) / COLUMNS)) * CELL + 16;  // below the cards (rewards: up to 15)
            text.touchable = false;
            mUiContainer.addChild(text);
         }
         for(i = 0; i < (message ? COLUMNS : 15); i++)
         {
            slot = new Quad(CELL - 6,CELL - 6,7223);
            slot.alpha = 0.25;
            slot.x = GRID_X + i % COLUMNS * CELL;
            slot.y = GRID_Y + int(i / COLUMNS) * CELL;
            slot.touchable = false;
            mUiContainer.addChild(slot);
         }
         for(i = 0; i < cards.length && i < 30; i++)
         {
            id = int(cards[i]);
            card = new SmallCard(id,false);
            card.scaleX = card.scaleY = SCALE;
            card.x = GRID_X + i % COLUMNS * CELL;
            card.y = GRID_Y + int(i / COLUMNS) * CELL;
            card.addEventListener(TouchEvent.TOUCH,this.OnCardTouch);
            mUiContainer.addChild(card);
            this.mCards.push(card);
            if(this.mIds.indexOf(id) == -1)
            {
               this.mIds.push(id);
            }
         }
         QueuedCardLoader.QueueCardByTemplateIdList(this.mIds);
         for(i = 0; i < this.mCards.length; i++)
         {
            if(!QueuedCardLoader.IsQueued(int(cards[i])))
            {
               this.ShowCard(i);
            }
         }
         if(cards.length > 0)
         {
            this.ShowPreview(int(cards[0]));
         }
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

      private function OnCardLoaded(aEvent:QueuedCardLoaderEvent) : void
      {
         var cards:Array = (mPopupData as DeckViewPopupData).Cards;
         for(var i:int = 0; i < this.mCards.length; i++)
         {
            if(int(cards[i]) == aEvent.CardId)
            {
               this.ShowCard(i);
            }
         }
         if(aEvent.CardId == this.mPendingPreviewId)
         {
            this.ShowPreview(this.mPendingPreviewId);
         }
      }

      private function OnCardTouch(aEvent:TouchEvent) : void
      {
         var touch:Touch = aEvent.getTouch(aEvent.currentTarget as SmallCard,TouchPhase.ENDED);
         var index:int = this.mCards.indexOf(aEvent.currentTarget as SmallCard);
         if(touch != null && index != -1)
         {
            this.ShowPreview(int((mPopupData as DeckViewPopupData).Cards[index]));
         }
      }

      private function ShowPreview(aTemplateId:int) : void
      {
         this.ClearPreview();
         if(QueuedCardLoader.IsQueued(aTemplateId))
         {
            this.mPendingPreviewId = aTemplateId;
            return;
         }
         try
         {
            this.mPreviewId = aTemplateId;
            this.mPreview = CardVisualUtil.CreateCardVisual(aTemplateId,ECardVisualType.FULL_CARD_PREVIEW);
            this.mPreview.scaleX = this.mPreview.scaleY = PREVIEW_SCALE;
            this.mPreview.x = GRID_X + COLUMNS * CELL + 22;
            this.mPreview.y = GRID_Y + 20;
            this.mPreview.addEventListener(TouchEvent.TOUCH,this.OnPreviewTouched);
            mUiContainer.addChild(this.mPreview);
            this.mPreview.DisplayCardVisual();
         }
         catch(error:Error)
         {
            this.ClearPreview();
         }
      }

      private function ClearPreview() : void
      {
         this.mPendingPreviewId = -1;
         this.mPreviewId = -1;
         if(this.mPreview != null)
         {
            this.mPreview.removeEventListener(TouchEvent.TOUCH,this.OnPreviewTouched);
            this.mPreview.removeFromParent(true);
            this.mPreview = null;
         }
      }

      private function OnPreviewTouched(aEvent:TouchEvent) : void
      {
         if(!MobileUtils.TouchIsValid(aEvent) || this.mPreviewId == -1)
         {
            return;
         }
         var popupData:FullCardPopupData = new FullCardPopupData((mPopupData as DeckViewPopupData).ShowOwnedQuantity);
         popupData.CardTemplateId = this.mPreviewId;
         PopupManager.Show(popupData,false);
      }
   }
}
