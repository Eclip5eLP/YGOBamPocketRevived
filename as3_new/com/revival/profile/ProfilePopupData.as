package com.revival.profile
{
   import com.frimastudio.snowstorm.project.popup.data.InfoPopupData;

   // Opens ProfilePopup for a player (uid). CanEdit adds the EDIT PROFILE button (own profile only).
   public class ProfilePopupData extends InfoPopupData
   {
      public var Uid:String;

      public var CanEdit:Boolean;

      public function ProfilePopupData(aUid:String, aCanEdit:Boolean)
      {
         super("PROFILE");
         this.Uid = aUid;
         this.CanEdit = aCanEdit;
      }

      override public function get PopupClass() : Class
      {
         return ProfilePopup;
      }
   }
}
