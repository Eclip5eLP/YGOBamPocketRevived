package com.revival.collection
{
   import com.frimastudio.mobile.adaptativeui.scroller.AbstractScrollerData;
   import com.frimastudio.mobile.adaptativeui.scroller.OptimizedScroller;
   import com.frimastudio.mobile.adaptativeui.scroller.display.IScrollable;
   import com.frimastudio.utils.cardloading.QueuedCardLoader;
   import com.frimastudio.utils.cardloading.event.QueuedCardLoaderEvent;
   import starling.events.EventDispatcher;
   import flash.geom.Rectangle;
   import starling.display.DisplayObject;

   // Horizontal scroller of CollectionColumns. Like CardScroller, it loads the card textures of the visible columns
   // through QueuedCardLoader and frees them when a column is recycled.
   public class CollectionScroller extends OptimizedScroller
   {
      public function CollectionScroller(aRenderZone:Rectangle, aScrollerSkin:DisplayObject, aStartScrollerPosition:Number, aMaxScrollerPosition:Number)
      {
         super(aRenderZone,aScrollerSkin,aStartScrollerPosition,aMaxScrollerPosition);
         (QueuedCardLoader as EventDispatcher).addEventListener(QueuedCardLoaderEvent.ON_CARD_LOADED,this.OnCardLoaded);
      }

      override public function dispose() : void
      {
         var scrollable:IScrollable = null;
         (QueuedCardLoader as EventDispatcher).removeEventListener(QueuedCardLoaderEvent.ON_CARD_LOADED,this.OnCardLoaded);
         QueuedCardLoader.ClearQueuedCards();
         if(mScrollerVisualList != null)
         {
            for each(scrollable in mScrollerVisualList)
            {
               this.Unload(scrollable.scrollerData);
            }
         }
         super.dispose();
      }

      override protected function CreateScrollabeItem(aData:AbstractScrollerData, aDepth:int) : IScrollable
      {
         var scrollable:IScrollable = super.CreateScrollabeItem(aData,aDepth);
         this.Load(aData);
         return scrollable;
      }

      override protected function ResetScrollable(aScrollable:IScrollable, aData:AbstractScrollerData, aDepth:int) : IScrollable
      {
         if(aScrollable.scrollerData != aData)
         {
            this.Unload(aScrollable.scrollerData);
         }
         var scrollable:IScrollable = super.ResetScrollable(aScrollable,aData,aDepth);
         this.Load(aData);
         return scrollable;
      }

      private function Load(aData:AbstractScrollerData) : void
      {
         var column:CollectionColumnData = aData as CollectionColumnData;
         if(column != null)
         {
            QueuedCardLoader.QueueCardByTemplateIdList(column.TemplateIds);
         }
      }

      private function Unload(aData:AbstractScrollerData) : void
      {
         var column:CollectionColumnData = aData as CollectionColumnData;
         if(column == null)
         {
            return;
         }
         for each(var id:int in column.TemplateIds)
         {
            QueuedCardLoader.RemoveCardByTemplateId(id);
         }
      }

      private function OnCardLoaded(aEvent:QueuedCardLoaderEvent) : void
      {
         var scrollable:IScrollable = null;
         for each(scrollable in mScrollerVisualList)
         {
            if(scrollable is CollectionColumn)
            {
               (scrollable as CollectionColumn).OnCardLoaded(aEvent.CardId);
            }
         }
         dispatchEventWith("collectionCardLoaded",false,aEvent.CardId);
      }
   }
}
