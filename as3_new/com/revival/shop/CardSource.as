package com.revival.shop
{
   import flash.filesystem.File;
   import flash.filesystem.FileMode;
   import flash.filesystem.FileStream;
   import flash.utils.getDefinitionByName;

   // "How to get this card" for the card popup (BuyCardPopup, patched) where the game itself only knows the card
   // shop, crafting, its booster packs and tournament themes and says "Coming soon!" otherwise. Texts come from
   // config/cardsources.json (tools/content_mods.py card_sources: story rewards by chapter, objectives, shop bundles,
   // Arena and tournament rewards), read like config/boosterpacks.json (downloaded game data when active, else the
   // APK's). A card shop card that is still locked (ShopUnlocks) names its chapter. null = no text (Coming soon).
   public class CardSource
   {
      private static var mTexts:Object;

      public function CardSource()
      {
         super();
      }

      public static function Describe(aTemplateId:int) : String
      {
         var chapter:* = ShopUnlocks.CHAPTERS[aTemplateId];
         var text:String = null;
         try
         {
            text = Texts()[String(aTemplateId)];
         }
         catch(error:Error)
         {
         }
         if(chapter != undefined && !ShopUnlocks.IsUnlocked(aTemplateId))
         {
            return "Clear chapter " + chapter + " in Story mode to buy it in the card shop." + (text ? " " + text : "");
         }
         return text ? text : null;
      }

      private static function Texts() : Object
      {
         var file:File = null;
         var stream:FileStream = null;
         if(mTexts != null)
         {
            return mTexts;
         }
         mTexts = {};
         try
         {
            file = File.applicationStorageDirectory.resolvePath("asset/gamedata/config/cardsources.json");
            // Loader.GameDataActive is added by tools/as3_patches.py (after this class is compiled): look it up
            if(!getDefinitionByName("com.frimastudio.as3ToolKit.net.Loader")["GameDataActive"] || !file.exists)
            {
               file = File.applicationDirectory.resolvePath("config/cardsources.json");
            }
            if(file.exists)
            {
               stream = new FileStream();
               stream.open(file,FileMode.READ);
               mTexts = JSON.parse(stream.readUTFBytes(stream.bytesAvailable));
               stream.close();
            }
         }
         catch(error:Error)
         {
         }
         return mTexts;
      }
   }
}
