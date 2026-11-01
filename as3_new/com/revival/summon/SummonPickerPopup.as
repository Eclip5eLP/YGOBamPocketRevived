package com.revival.summon
{
   import com.frimastudio.mobile.util.MobileUtils;
   import com.frimastudio.snowstorm.project.fonts.EFonts;
   import com.frimastudio.snowstorm.project.popup.PopupManager;
   import com.frimastudio.snowstorm.project.popup.popups.InfoPopup;
   import com.frimastudio.utils.cardloading.QueuedCardLoader;
   import com.frimastudio.utils.cardloading.event.QueuedCardLoaderEvent;
   import com.frimastudio.utils.rendering.card.CardVisual;
   import com.frimastudio.utils.rendering.card.CardVisualUtil;
   import com.frimastudio.utils.rendering.card.enum.ECardVisualType;
   import starling.display.Quad;
   import starling.display.Sprite;
   import starling.events.EventDispatcher;
   import starling.events.TouchEvent;
   import starling.text.TextField;
   import starling.utils.HAlign;

   // In a duel: the pair you just made can become several cards (Fusion / Synchro / Xyz you own). Tap one; closing
   // without a pick keeps the first. Four cards per page, < > buttons for more; only the shown page's cards are
   // loaded, through QueuedCardLoader (like DeckViewPopup).
   public class SummonPickerPopup extends InfoPopup
   {
      private static const SCALE:Number = 0.36;

      private static const CARD_WIDTH:int = 166;

      private static const ROW_X:int = 40;

      private static const ROW_Y:int = 92;

      private static const MAX_CARDS:int = 4;

      private var mCards:Vector.<CardVisual> = new Vector.<CardVisual>();

      private var mIds:Vector.<int> = new Vector.<int>();

      private var mAllIds:Vector.<int> = new Vector.<int>();

      private var mPage:int = 0;

      private var mPageText:TextField;

      private var mPrev:Sprite;

      private var mNext:Sprite;

      public function SummonPickerPopup()
      {
         super();
      }

      public static function Ask(aResultIds:Array, aOnPick:Function) : void
      {
         PopupManager.Show(new SummonPickerPopupData(aResultIds,aOnPick),false);
      }

      override public function Dispose() : void
      {
         (QueuedCardLoader as EventDispatcher).removeEventListener(QueuedCardLoaderEvent.ON_CARD_LOADED,this.OnCardLoaded);
         this.ClearCards();
         // the pictures stay loaded: the duel creates the picked card right after (CardLoadingUtil patch preloads
         // them too; unloading here could take the duel's copy away)
         this.mIds.length = 0;
         this.mAllIds.length = 0;
         for each(var button:Sprite in [this.mPrev,this.mNext])
         {
            if(button != null)
            {
               button.removeEventListener(TouchEvent.TOUCH,this.OnPageTouch);
            }
         }
         super.Dispose();
      }

      override protected function AddButtons() : void
      {
         CreateBaseButton("popup_close_btn",722,3);
      }

      override public function Draw() : void
      {
         var text:TextField = null;
         super.Draw();
         var ids:Array = (mPopupData as SummonPickerPopupData).ResultIds;
         text = new TextField(700,40,"Tap the card to summon",EFonts.HANZEL_BOLD,26,7223);
         text.hAlign = HAlign.LEFT;
         text.x = ROW_X;
         text.y = ROW_Y - 40;
         text.touchable = false;
         mUiContainer.addChild(text);
         for(var i:int = 0; i < ids.length; i++)
         {
            this.mAllIds.push(int(ids[i]));
         }
         (QueuedCardLoader as EventDispatcher).addEventListener(QueuedCardLoaderEvent.ON_CARD_LOADED,this.OnCardLoaded);
         if(this.mAllIds.length > MAX_CARDS)
         {
            this.mPrev = this.PageButton("<",ROW_X + 120);
            this.mNext = this.PageButton(">",ROW_X + 4 * (CARD_WIDTH + 10) - 190);
            this.mPageText = new TextField(200,50,"",EFonts.HANZEL_BOLD,26,7223);
            this.mPageText.x = ROW_X + 2 * (CARD_WIDTH + 10) - 105;
            this.mPageText.y = PAGE_Y;
            this.mPageText.touchable = false;
            mUiContainer.addChild(this.mPageText);
         }
         this.ShowPage(0);
      }

      private static const PAGE_Y:int = 345;

      private function PageCount() : int
      {
         return Math.ceil(this.mAllIds.length / MAX_CARDS);
      }

      private function PageButton(aLabel:String, aX:int) : Sprite
      {
         var button:Sprite = new Sprite();
         var back:Quad = new Quad(70,50,7223);
         var label:TextField = new TextField(70,50,aLabel,EFonts.HANZEL_BOLD,34,16777215);
         button.addChild(back);
         button.addChild(label);
         button.x = aX;
         button.y = PAGE_Y;
         button.addEventListener(TouchEvent.TOUCH,this.OnPageTouch);
         mUiContainer.addChild(button);
         return button;
      }

      private function ShowPage(aPage:int) : void
      {
         this.mPage = Math.max(0,Math.min(aPage,this.PageCount() - 1));
         this.mIds.length = 0;
         for(var i:int = this.mPage * MAX_CARDS; i < this.mAllIds.length && i < (this.mPage + 1) * MAX_CARDS; i++)
         {
            this.mIds.push(this.mAllIds[i]);
         }
         if(this.mPageText != null)
         {
            this.mPageText.text = (this.mPage + 1) + " / " + this.PageCount();
            this.mPrev.alpha = this.mPage > 0 ? 1 : 0.35;
            this.mNext.alpha = this.mPage < this.PageCount() - 1 ? 1 : 0.35;
         }
         QueuedCardLoader.QueueCardByTemplateIdList(this.mIds);
         this.ShowCards();
      }

      private function OnPageTouch(aEvent:TouchEvent) : void
      {
         if(!MobileUtils.TouchIsValid(aEvent))
         {
            return;
         }
         this.ShowPage(this.mPage + (aEvent.currentTarget == this.mNext ? 1 : -1));
      }

      private function ShowCards() : void
      {
         var card:CardVisual = null;
         this.ClearCards();
         for(var i:int = 0; i < this.mIds.length; i++)
         {
            if(QueuedCardLoader.IsQueued(this.mIds[i]))
            {
               continue;
            }
            try
            {
               card = CardVisualUtil.CreateCardVisual(this.mIds[i],ECardVisualType.FULL_CARD_PREVIEW);
               card.scaleX = card.scaleY = SCALE;
               card.x = ROW_X + i * (CARD_WIDTH + 10) + (MAX_CARDS - this.mIds.length) * (CARD_WIDTH + 10) / 2;
               card.y = ROW_Y;
               card.name = String(this.mIds[i]);
               card.addEventListener(TouchEvent.TOUCH,this.OnCardTouch);
               mUiContainer.addChild(card);
               card.DisplayCardVisual();
               this.mCards.push(card);
            }
            catch(error:Error)
            {
            }
         }
      }

      private function ClearCards() : void
      {
         for each(var card:CardVisual in this.mCards)
         {
            card.removeEventListener(TouchEvent.TOUCH,this.OnCardTouch);
            card.removeFromParent(true);
         }
         this.mCards.length = 0;
      }

      private function OnCardLoaded(aEvent:QueuedCardLoaderEvent) : void
      {
         if(this.mIds.indexOf(aEvent.CardId) != -1)
         {
            this.ShowCards();
         }
      }

      private function OnCardTouch(aEvent:TouchEvent) : void
      {
         var card:CardVisual = aEvent.currentTarget as CardVisual;
         var onPick:Function = (mPopupData as SummonPickerPopupData).OnPick;
         if(!MobileUtils.TouchIsValid(aEvent) || card == null)
         {
            return;
         }
         if(onPick != null)
         {
            onPick(int(card.name));
         }
         DispatchPopupClosedEvent();
      }
   }
}
