package com.revival.collection
{
   import com.frimastudio.mobile.adaptativeui.scroller.AbstractScrollerData;
   import com.frimastudio.snowstorm.project.inventory.amf.CardTemplate;

   // One column of the collection grid: up to CollectionColumn.ROWS cards and how many of each the player owns.
   public class CollectionColumnData extends AbstractScrollerData
   {
      public var Templates:Vector.<CardTemplate>;

      public var Quantities:Vector.<int>;

      public function CollectionColumnData(aTemplates:Vector.<CardTemplate>, aQuantities:Vector.<int>)
      {
         super(CollectionColumn,CollectionColumn.WIDTH);
         this.Templates = aTemplates;
         this.Quantities = aQuantities;
      }

      override public function Dispose() : void
      {
         this.Templates = null;
         this.Quantities = null;
         super.Dispose();
      }

      public function get TemplateIds() : Vector.<int>
      {
         var ids:Vector.<int> = new Vector.<int>();
         for(var i:int = 0; i < this.Templates.length; i++)
         {
            ids.push(this.Templates[i].id);
         }
         return ids;
      }
   }
}
