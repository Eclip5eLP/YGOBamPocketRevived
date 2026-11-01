package com.revival.summon
{
   import com.frimastudio.snowstorm.project.popup.data.InfoPopupData;

   // SummonPickerPopup: the possible results of a pair and what to do with the pick (Summon.OnLocalPair).
   public class SummonPickerPopupData extends InfoPopupData
   {
      public var ResultIds:Array;

      public var OnPick:Function;

      public function SummonPickerPopupData(aResultIds:Array, aOnPick:Function)
      {
         super("Summon");
         this.ResultIds = aResultIds;
         this.OnPick = aOnPick;
      }

      override public function get PopupClass() : Class
      {
         return SummonPickerPopup;
      }
   }
}
