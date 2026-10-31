package com.revival.collection
{
   import com.frimastudio.mobile.adaptativeui.EElementAlign;
   import com.frimastudio.mobile.adaptativeui.scroller.AbstractScrollerData;
   import com.frimastudio.mobile.adaptativeui.scroller.event.ScrollerEvent;
   import com.frimastudio.mobile.asset.AssetManagerWrapper;
   import com.frimastudio.mobile.util.MobileUtils;
   import com.frimastudio.snowstorm.module.deckbuilder.popup.data.FullCardPopupData;
   import com.frimastudio.snowstorm.project.inventory.amf.CardTemplate;
   import com.frimastudio.snowstorm.project.popup.PopupManager;
   import com.frimastudio.snowstorm.project.ui.EScale9Definition;
   import com.frimastudio.utils.cardloading.QueuedCardLoader;
   import com.frimastudio.utils.rendering.card.CardVisual;
   import com.frimastudio.utils.rendering.card.CardVisualUtil;
   import com.frimastudio.utils.rendering.card.enum.ECardVisualType;
   import feathers.display.Scale9Image;
   import flash.geom.Rectangle;
   import starling.display.Image;
   import starling.display.Quad;
   import starling.display.Sprite;
   import starling.events.Event;
   import starling.events.TouchEvent;

   // Collection layout (main menu > Collection): a 3-row grid of small cards scrolling horizontally on the left,
   // a card preview pane on the right. Tapping a small card shows it in the preview; tapping the preview opens the
   // full card popup. Built by ShopCardView in collection mode; if building fails, ShopCardView keeps its own list.
   public class CollectionPanel extends Sprite
   {
      private static const PREVIEW_WIDTH:int = 291;

      private static const PREVIEW_HEIGHT:int = 427;

      private static const PREVIEW_SCALE:Number = 0.6;

      private var mScroller:CollectionScroller;

      private var mSlider:Image;

      private var mPreviewFrame:Scale9Image;

      private var mPreview:CardVisual;

      private var mPreviewId:int = -1;

      private var mPendingPreviewId:int = -1;

      public function CollectionPanel(aWidth:Number, aTop:Number)
      {
         super();
         var gridHeight:int = CollectionColumn.ROWS * CollectionColumn.CELL;
         var scrollerWidth:Number = aWidth - PREVIEW_WIDTH - 50;
         this.mSlider = AssetManagerWrapper.GetImage("shop_card_scroller_slider");
         var sliderContainer:Sprite = new Sprite();
         var sliderBG:Quad = new Quad(scrollerWidth,this.mSlider.height,0);
         sliderBG.touchable = false;
         sliderContainer.addChild(sliderBG);
         sliderContainer.addChild(this.mSlider);
         sliderContainer.x = 15;
         sliderContainer.y = aTop + gridHeight + 8;
         this.mScroller = new CollectionScroller(new Rectangle(0,0,scrollerWidth,gridHeight),this.mSlider,this.mSlider.x,scrollerWidth - this.mSlider.width);
         this.mScroller.Align = EElementAlign.LEFT;
         this.mScroller.Gap = 0;
         this.mScroller.x = 15;
         this.mScroller.y = aTop;
         this.mScroller.addEventListener(ScrollerEvent.CHILD_TAPPED,this.OnColumnTapped);
         this.mScroller.addEventListener("collectionCardLoaded",this.OnCardLoaded);
         addChild(this.mScroller);
         addChild(sliderContainer);
         this.mPreviewFrame = AssetManagerWrapper.GetScale9Image(EScale9Definition.SHOP_ITEM_BACKGROUND);
         this.mPreviewFrame.width = PREVIEW_WIDTH;
         this.mPreviewFrame.height = PREVIEW_HEIGHT;
         this.mPreviewFrame.x = aWidth - PREVIEW_WIDTH - 20;
         this.mPreviewFrame.y = aTop - 12;
         this.mPreviewFrame.touchable = false;
         addChild(this.mPreviewFrame);
      }

      override public function dispose() : void
      {
         this.ClearPreview();
         if(this.mScroller != null)
         {
            this.mScroller.removeEventListener(ScrollerEvent.CHILD_TAPPED,this.OnColumnTapped);
            this.mScroller.removeEventListener("collectionCardLoaded",this.OnCardLoaded);
            this.mScroller.removeFromParent(true);
            this.mScroller = null;
         }
         this.mSlider = null;
         this.mPreviewFrame = null;
         super.dispose();
      }

      // Fills the grid column by column; the first card goes into the preview.
      public function SetCards(aTemplates:Vector.<CardTemplate>, aQuantities:Vector.<int>) : void
      {
         var i:int = 0;
         var columns:Vector.<AbstractScrollerData> = new Vector.<AbstractScrollerData>();
         var templates:Vector.<CardTemplate> = null;
         var quantities:Vector.<int> = null;
         for(i = 0; i < aTemplates.length; i++)
         {
            if(i % CollectionColumn.ROWS == 0)
            {
               templates = new Vector.<CardTemplate>();
               quantities = new Vector.<int>();
               columns.push(new CollectionColumnData(templates,quantities));
            }
            templates.push(aTemplates[i]);
            quantities.push(aQuantities[i]);
         }
         this.mScroller.dataProvider = columns;
         this.ShowPreview(aTemplates.length > 0 ? aTemplates[0].id : -1);
      }

      private function OnColumnTapped(aEvent:ScrollerEvent) : void
      {
         var column:CollectionColumn = aEvent.ActiveChild as CollectionColumn;
         if(column != null && column.TouchedTemplateId != -1)
         {
            this.ShowPreview(column.TouchedTemplateId);
         }
      }

      private function OnCardLoaded(aEvent:Event) : void
      {
         if(this.mPendingPreviewId != -1 && int(aEvent.data) == this.mPendingPreviewId)
         {
            this.ShowPreview(this.mPendingPreviewId);
         }
      }

      private function ShowPreview(aTemplateId:int) : void
      {
         this.ClearPreview();
         if(aTemplateId == -1)
         {
            return;
         }
         if(QueuedCardLoader.IsQueued(aTemplateId))
         {
            this.mPendingPreviewId = aTemplateId;
            return;
         }
         try
         {
            this.mPreviewId = aTemplateId;
            QueuedCardLoader.LockFromRemoveByCardTemplateIdList(new <int>[aTemplateId]);
            this.mPreview = CardVisualUtil.CreateCardVisual(aTemplateId,ECardVisualType.FULL_CARD_PREVIEW);
            this.mPreview.scaleX = PREVIEW_SCALE;
            this.mPreview.scaleY = PREVIEW_SCALE;
            this.mPreview.x = this.mPreviewFrame.x + (PREVIEW_WIDTH - this.mPreview.width) / 2;
            this.mPreview.y = this.mPreviewFrame.y + (PREVIEW_HEIGHT - this.mPreview.height) / 2;
            this.mPreview.addEventListener(TouchEvent.TOUCH,this.OnPreviewTouched);
            addChild(this.mPreview);
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
         if(this.mPreviewId != -1)
         {
            QueuedCardLoader.UnlockFromRemoveByCardTemplateIdList(new <int>[this.mPreviewId]);
            this.mPreviewId = -1;
         }
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
         var popupData:FullCardPopupData = new FullCardPopupData();
         popupData.DisplayQuantity = true;
         popupData.CardTemplateId = this.mPreviewId;
         PopupManager.Show(popupData);
      }
   }
}
