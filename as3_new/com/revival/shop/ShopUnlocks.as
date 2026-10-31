package com.revival.shop
{
   import com.frimastudio.common.core.manager.ManagerA;
   import com.frimastudio.snowstorm.project.manager.EManagerDefinitionProject;
   import com.frimastudio.snowstorm.project.worldmap.IWorldmapManagerYGO;
   import com.frimastudio.snowstorm.project.worldmap.WorldmapCacheLogic;
   import com.frimastudio.snowstorm.project.worldmap.amf.WorldMap;
   import com.frimastudio.snowstorm.project.worldmap.amf.WorldNode;

   // Card shop entries that appear only after a story chapter is cleared (ShopCardView.UpdateCardList, patched).
   // These are the former Arena reward cards plus two cards that had no source (Arena weekly rewards too,
   // server/rewards.py) and the series 2 cards whose original shop entries never went on sale
   // (notes/pack_split_proposal.md). Chapter N = world 1
   // node with xmlNodeName N, cleared = WorldNode.completed. tools/content_mods.py (revival_rewards) reads this
   // table to add the shop entries, so it is the only place to edit. Any error: the card stays hidden.
   public class ShopUnlocks
   {
      // card template id : chapter
      public static const CHAPTERS:Object = {
         502:5, 515:10, 855:15, 861:15, 863:15,
         1056:20, 1057:20, 1058:20, 1006:25, 1280:25,
         1281:25, 1282:25, 1301:30, 1302:30, 1303:30,
         1151:35,
         1386:6,
         1009:12, 1010:12, 1011:12, 1053:12, 1054:12, 1180:12, 1292:12, 1293:12, 1294:12, 1299:12,
         1300:12, 1388:12, 1401:12,
         975:18, 1137:18, 1139:18, 1181:18, 1351:18, 1352:18, 1353:18, 1390:18, 1392:18,
         970:24, 1055:24, 1138:24, 1148:24, 1182:24
      };

      public function ShopUnlocks()
      {
         super();
      }

      public static function IsUnlocked(aTemplateId:int) : Boolean
      {
         var chapter:* = CHAPTERS[aTemplateId];
         if(chapter == undefined)
         {
            return true;
         }
         try
         {
            return IsChapterCleared(int(chapter));
         }
         catch(error:Error)
         {
         }
         return false;
      }

      public static function IsChapterCleared(aChapter:int) : Boolean
      {
         var cache:WorldmapCacheLogic = (ManagerA.GetManager(EManagerDefinitionProject.WORLDMAP_MANAGER) as IWorldmapManagerYGO).CacheLogic;
         var world:WorldMap = cache.GetWorldMapByTemplateId(1);
         var node:WorldNode = world != null ? cache.GetWorldNodeByXmlNodeName(world.id,aChapter) : null;
         return node != null && node.completed;
      }
   }
}
