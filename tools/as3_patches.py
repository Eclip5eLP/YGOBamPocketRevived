"""
Source edits applied by tools/patch_as3.py: {class: [(old, new), ...]}. Each `old` is a snippet of the
FFDec-decompiled class and must occur exactly once. Keep edits small and anchored on stable lines.
"""

# --- Game data override (notes/findings.md 6.33) ---------------------------------------------------------
# Data files under config/ and the texture atlas lists under asset/list/ normally come from the APK. A downloaded "gamedata" package (asset/gamedata/ in
# app storage, marker asset/gamedata/gamedata_version) overrides them when its version is newer than the
# APK's own config/gamedata_version. Decided once per launch, so one session never mixes data versions.
LOADER = "com.frimastudio.as3ToolKit.net.Loader"
LOADER_EDITS = [
    ("""   import flash.utils.getTimer;
""", """   import flash.utils.getTimer;
   import flash.filesystem.File;
   import flash.filesystem.FileMode;
   import flash.filesystem.FileStream;
"""),
    ("""      private static const MAXIMUM_RETRY_LOADING:int = 5;
""", """      private static const MAXIMUM_RETRY_LOADING:int = 5;

      private static var sGameDataChecked:Boolean = false;

      private static var sGameDataActive:Boolean = false;

      private static var sSessionGameDataVersion:String = "";

      public static function ReadGameDataVersion(aFile:File) : String
      {
         var stream:FileStream = null;
         var text:String = "";
         if(aFile != null && aFile.exists)
         {
            stream = new FileStream();
            stream.open(aFile,FileMode.READ);
            text = stream.readUTFBytes(stream.bytesAvailable);
            stream.close();
         }
         return text.replace(/\\s/g,"");
      }

      public static function CompareGameDataVersion(aLeft:String, aRight:String) : int
      {
         var left:Array = aLeft.split(".");
         var right:Array = aRight.split(".");
         var length:int = Math.max(left.length,right.length);
         var a:int = 0;
         var b:int = 0;
         for(var i:int = 0; i < length; i++)
         {
            a = i < left.length ? int(parseInt(left[i])) : 0;
            b = i < right.length ? int(parseInt(right[i])) : 0;
            if(a != b)
            {
               return a > b ? 1 : -1;
            }
         }
         return 0;
      }

      public static function get BundledGameDataVersion() : String
      {
         return ReadGameDataVersion(File.applicationDirectory.resolvePath("config/gamedata_version"));
      }

      public static function get DownloadedGameDataVersion() : String
      {
         return ReadGameDataVersion(File.applicationStorageDirectory.resolvePath("asset/gamedata/gamedata_version"));
      }

      public static function get GameDataActive() : Boolean
      {
         var downloaded:String = null;
         if(!sGameDataChecked)
         {
            sGameDataChecked = true;
            try
            {
               downloaded = DownloadedGameDataVersion;
               sGameDataActive = downloaded != "" && CompareGameDataVersion(downloaded,BundledGameDataVersion) > 0;
               sSessionGameDataVersion = sGameDataActive ? downloaded : BundledGameDataVersion;
            }
            catch(error:Error)
            {
               sGameDataActive = false;
            }
         }
         return sGameDataActive;
      }

      public static function get ActiveGameDataVersion() : String
      {
         return GameDataActive ? sSessionGameDataVersion : BundledGameDataVersion;
      }

      public static function get GameDataChangedSinceStart() : Boolean
      {
         var downloaded:String = null;
         var bundled:String = null;
         if(!sGameDataChecked)
         {
            return false;
         }
         try
         {
            downloaded = DownloadedGameDataVersion;
            bundled = BundledGameDataVersion;
            return (downloaded != "" && CompareGameDataVersion(downloaded,bundled) > 0 ? downloaded : bundled) != sSessionGameDataVersion;
         }
         catch(error:Error)
         {
         }
         return false;
      }
"""),
    ("""      private function BuildURL(aWorker:Worker) : void
      {
""", """      private function BuildURL(aWorker:Worker) : void
      {
         var gameDataFile:File = null;
         if((aWorker.mUnversionnedURL.indexOf("config/") == 0 || aWorker.mUnversionnedURL.indexOf("asset/list/") == 0) && GameDataActive)
         {
            gameDataFile = File.applicationStorageDirectory.resolvePath("asset/gamedata/" + aWorker.mUnversionnedURL.split("?")[0]);
            if(gameDataFile.exists)
            {
               aWorker.mURLRequest.url = gameDataFile.url;
               return;
            }
         }
"""),
]

EXTERNAL_ASSET = "com.frimastudio.snowstorm.project.externalfile.enum.EExternalAsset"
EXTERNAL_ASSET_EDITS = [
    ("""      public static const FONT:EExternalAsset = new EExternalAsset(mId++,"font","asset/font/");
""", """      public static const FONT:EExternalAsset = new EExternalAsset(mId++,"font","asset/font/");

      public static const GAMEDATA:EExternalAsset = new EExternalAsset(mId++,"gamedata","asset/gamedata/");

      public static const SERIES3:EExternalAsset = new EExternalAsset(mId++,"series3","asset/cards/");
"""),
]

# New game data downloaded during this launch only applies from the next start: tell the player and close.
ENGINE = "com.frimastudio.mobile.MobileProjectEngine"
ENGINE_EDITS = [
    ("""   import flash.desktop.NativeApplication;
""", """   import flash.desktop.NativeApplication;
   import com.frimastudio.as3ToolKit.net.Loader;
   import com.frimastudio.snowstorm.project.popup.PopupManagerUtil;
"""),
    # popups during startup are drawn under the prelauncher visual, so ask after it is removed (last step)
    ("""         this.mPrelauncher = null;
         NativeApplication.nativeApplication.systemIdleMode = SystemIdleMode.NORMAL;
""", """         this.mPrelauncher = null;
         NativeApplication.nativeApplication.systemIdleMode = SystemIdleMode.NORMAL;
         if(Loader.GameDataChangedSinceStart)
         {
            PopupManagerUtil.ShowInfo("NEW CONTENT","New game content was downloaded. The game will now close. Start it again to play with the new content.").addEventListener(PopupManagerEvent.POPUP_CLOSED,this.OnGameDataUpdated);
         }
"""),
    ("""      private function LoadCommon() : void
      {
""", """      private function OnGameDataUpdated(aEvent:PopupManagerEvent) : void
      {
         NativeApplication.nativeApplication.exit();
      }

      private function LoadCommon() : void
      {
"""),
]

# --- Booster packs from data (notes/findings.md 6.33) ------------------------------------------------------
# The 9 original packs are code. Extra packs come from config/boosterpacks.json (game data: downloaded copy when
# active, else the APK's), read synchronously when the class initializes:
#   [{"shopItemId", "currency": "RMT"|"INGAME"|"CARD_PIECE", "cost", "id", "name", "description",
#     "guaranteed": [[rarityId, "5"], ...], "bonus": [[rarityId, "1:4"], ...], "cards": [templateId, ...],
#     "frame": cover frame in shop_booster_covers, "series": 1|2}]
BOOSTER_INFO = "com.frimastudio.snowstorm.module.shop.view.enum.EBoosterPackInfo"
BOOSTER_INFO_EDITS = [
    # Recompiling this class from FFDec's decompiled source broke this lookup: the decompiler turned the original
    # loop into "for each(...) {} continue loop0", which never returns a pack, so every booster card's popup said
    # "Coming soon!" (owner's test, findings 6.64). The same lookup, written plainly:
    ("""         var eBoosterPackInfo:EBoosterPackInfo = null;
         var cardTemplateId:int = 0;
         loop0:
         for each(eBoosterPackInfo in mList)
         {
            var _loc6_:int = 0;
            var _loc7_:* = eBoosterPackInfo.mBoosterPackCardTemplateIdList;
            do
            {
               for each(cardTemplateId in _loc7_)
               {
               }
               continue loop0;
            }
            while(cardTemplateId != aCardTemplateId);
            return eBoosterPackInfo;
         }
         return null;""", """         for each(var eBoosterPackInfo:EBoosterPackInfo in mList)
         {
            if(eBoosterPackInfo.mBoosterPackCardTemplateIdList.indexOf(aCardTemplateId) != -1)
            {
               return eBoosterPackInfo;
            }
         }
         return null;"""),
    ("""   import com.frimastudio.snowstorm.project.inventory.enumeration.CurrencyTypes;
""", """   import com.frimastudio.snowstorm.project.inventory.enumeration.CurrencyTypes;
   import com.frimastudio.as3ToolKit.net.Loader;
   import flash.filesystem.File;
   import flash.filesystem.FileMode;
   import flash.filesystem.FileStream;
"""),
    ("""BOOSTER_PACK_9_ID,8,2);
""", """BOOSTER_PACK_9_ID,8,2);

      private static const mExtraPacksLoaded:Boolean = LoadExtraPacks();

      private static function ExtraPackCurrency(aName:String) : int
      {
         if(aName == "INGAME")
         {
            return CurrencyTypes.INGAME.Id;
         }
         if(aName == "CARD_PIECE")
         {
            return CurrencyTypes.CARD_PIECE.Id;
         }
         return CurrencyTypes.RMT.Id;
      }

      private static function LoadExtraPacks() : Boolean
      {
         var file:File = null;
         var stream:FileStream = null;
         var list:Array = null;
         var pack:Object = null;
         var pair:Array = null;
         var cardId:int = 0;
         var guaranteed:Vector.<RarityBoosterPackInfo> = null;
         var bonus:Vector.<RarityBoosterPackInfo> = null;
         var cards:Vector.<int> = null;
         try
         {
            file = File.applicationStorageDirectory.resolvePath("asset/gamedata/config/boosterpacks.json");
            if(!Loader.GameDataActive || !file.exists)
            {
               file = File.applicationDirectory.resolvePath("config/boosterpacks.json");
            }
            if(!file.exists)
            {
               return false;
            }
            stream = new FileStream();
            stream.open(file,FileMode.READ);
            list = JSON.parse(stream.readUTFBytes(stream.bytesAvailable)) as Array;
            stream.close();
            for each(pack in list)
            {
               if(GetBoosterByShopItemId(int(pack.shopItemId)) == null)
               {
                  guaranteed = new Vector.<RarityBoosterPackInfo>();
                  for each(pair in pack.guaranteed)
                  {
                     guaranteed.push(new RarityBoosterPackInfo(int(pair[0]),String(pair[1])));
                  }
                  bonus = new Vector.<RarityBoosterPackInfo>();
                  for each(pair in pack.bonus)
                  {
                     bonus.push(new RarityBoosterPackInfo(int(pair[0]),String(pair[1])));
                  }
                  cards = new Vector.<int>();
                  for each(cardId in pack.cards)
                  {
                     cards.push(cardId);
                     (int(pack.series) == 1 ? mCardTemplateIdSerie1List : mCardTemplateIdSerie2List).push(cardId);
                  }
                  new EBoosterPackInfo(int(pack.shopItemId),ExtraPackCurrency(String(pack.currency)),int(pack.cost),int(pack.id),String(pack.name),String(pack.description),guaranteed,bonus,cards,int(pack.frame),int(pack.series));
               }
            }
         }
         catch(error:Error)
         {
            return false;
         }
         return true;
      }
"""),
]

# --- Delete decks (the original game had no way to remove a deck) ------------------------------------------
# InventoryManagerGame.DestroyDeck only sent a server request the mobile DAL ignores ("Shouldn't be called
# anymore"). Now it works locally: every card stack of the deck goes back into the collection (merged into the
# existing stack of that card), then the deck's card items and the deck are deleted, and the save is written.
INVENTORY = "com.frimastudio.snowstorm.project.inventory.InventoryManagerGame"
INVENTORY_EDITS = [
    ("""      public function DestroyDeck(aDeck:Deck) : void
      {
         var request:DestroyDeckRequest = new DestroyDeckRequest();
         request.deckId = aDeck.id;
         (mDAL as InventoryManagerDalMobile).DoDestroyDeckRequest(request);
      }
""", """      public function DestroyDeck(aDeck:Deck) : void
      {
         var deckCard:Item = null;
         var target:Item = null;
         var pending:Item = null;
         var stacks:Vector.<Item> = null;
         var inventory:Item = mCacheLogic.GetFloatingContainer(mAvatarManager.GetSelectedAvatarId(),ContainerTypes.INVENTORY.Id);
         var change:InventoryChange = new InventoryChange();
         change.addedItems = [];
         change.updatedItems = [];
         change.deletedItems = [];
         for each(deckCard in mCacheLogic.GetItemListByContainerId(aDeck.id))
         {
            change.deletedItems.push(deckCard);
            target = null;
            for each(pending in change.updatedItems.concat(change.addedItems))
            {
               if(pending.itemTemplateId == deckCard.itemTemplateId)
               {
                  target = pending;
               }
            }
            if(target == null)
            {
               stacks = mCacheLogic.GetItemListByItemTemplateId(inventory.id,deckCard.itemTemplateId);
               if(Boolean(stacks) && stacks.length > 0)
               {
                  target = ObjectGenerator.CopyItem(stacks[0]);
                  change.updatedItems.push(target);
               }
               else
               {
                  target = ObjectGenerator.CreateItemFromTemplateId(deckCard.itemTemplateId,YGOMData.GetNextId());
                  target.containerId = inventory.id;
                  target.quantity = 0;
                  change.addedItems.push(target);
               }
            }
            target.quantity += deckCard.quantity;
         }
         change.deletedItems.push(aDeck);
         this.ParseInventoryChange(change);
         YGOMData.Save(true);
         DispatchInventoryEvent(InventoryManagerEventGame.ON_DESTROY_DECK,InventoryManagerEvent.CODE_SUCCESS);
      }
"""),
]

CHOOSE_DECK_UI = "com.frimastudio.snowstorm.module.deckbuilder.screens.ui.ChooseDeckScreenUI"
CHOOSE_DECK_UI_EDITS = [
    ("""      private var mEditButton:Scale9Button;
""", """      private var mEditButton:Scale9Button;

      private var mDeleteButton:Scale9Button;

      public function get DeleteButton() : Scale9Button
      {
         return this.mDeleteButton;
      }
"""),
    ("""         this.mEditButton.removeFromParent(true);
         this.mEditButton = null;
""", """         this.mEditButton.removeFromParent(true);
         this.mEditButton = null;
         this.mDeleteButton.removeFromParent(true);
         this.mDeleteButton = null;
"""),
    ("""         container.addChild(this.mEditButton);
""", """         container.addChild(this.mEditButton);
         this.mDeleteButton = AssetManagerWrapper.GetButton(ECommonButton.PINK_BUTTON,new Point(132,70),"DELETE",EFonts.HANZEL_BOLD,28,Color.WHITE,true,HAlign.CENTER,VAlign.CENTER);
         this.mDeleteButton.x = 541;
         this.mDeleteButton.y = 10;
         container.addChild(this.mDeleteButton);
"""),
]

CHOOSE_DECK = "com.frimastudio.snowstorm.module.deckbuilder.screens.ChooseDeckScreen"
CHOOSE_DECK_EDITS = [
    ("""   import com.frimastudio.snowstorm.project.popup.PopupManagerUtil;
""", """   import com.frimastudio.snowstorm.project.popup.PopupManagerUtil;
   import com.frimastudio.snowstorm.project.popup.data.EPopupCloseData;
   import com.frimastudio.snowstorm.project.popup.data.TwoChoicePopupData;
"""),
    ("""         this.mUI.EditButton.addEventListener(Event.TRIGGERED,this.OnButtonTapped);
""", """         this.mUI.EditButton.addEventListener(Event.TRIGGERED,this.OnButtonTapped);
         (this.mUI as ChooseDeckScreenUI).DeleteButton.addEventListener(Event.TRIGGERED,this.OnDeleteTapped);
"""),
    ("""         this.mUI.EditButton.removeEventListener(Event.TRIGGERED,this.OnButtonTapped);
""", """         this.mUI.EditButton.removeEventListener(Event.TRIGGERED,this.OnButtonTapped);
         (this.mUI as ChooseDeckScreenUI).DeleteButton.removeEventListener(Event.TRIGGERED,this.OnDeleteTapped);
"""),
    ("""      private function GoBack() : void
""", """      private function OnDeleteTapped(aEvent:Event) : void
      {
         var popup:Popup = null;
         if(this.mSelectedDeck == null || this.mDeckIsLoaded == false)
         {
            return;
         }
         if(this.mDeckList.length <= 1)
         {
            PopupManagerUtil.ShowWarning("DELETE DECK","You need to keep at least one deck.");
            return;
         }
         popup = PopupManager.Show(new TwoChoicePopupData("DELETE DECK",'Delete the deck "' + this.mSelectedDeck.deckName + '"? Its cards go back to your collection.',"DELETE",EPopupCloseData.YES,null,null,"CANCEL",EPopupCloseData.NO,null,null),false);
         popup.addEventListener(PopupManagerEvent.POPUP_CLOSED,this.OnDeleteConfirmed);
      }

      private function OnDeleteConfirmed(aEvent:PopupManagerEvent) : void
      {
         var deck:Deck = this.mSelectedDeck;
         aEvent.currentTarget.removeEventListener(PopupManagerEvent.POPUP_CLOSED,this.OnDeleteConfirmed);
         if(aEvent.PopupCloseData != EPopupCloseData.YES || deck == null || this.mDeckList.indexOf(deck) == -1)
         {
            return;
         }
         if(deck.isDefaultDeck)
         {
            this.SetAsDefaultDeck(null);
         }
         this.mDeckList.splice(this.mDeckList.indexOf(deck),1);
         this.mInventoryManager.DestroyDeck(deck);
         this.mUI.DeckDisplay.ClearDeckDisplayed();
         this.mSelectedDeck = null;
         this.PopulateComboBox();
         this.SelectDeck(this.GetDefaultDeck());
         this.PopulateComboBox();
      }

      private function GoBack() : void
"""),
]

# --- Version gate (notes/findings.md 6.34) ------------------------------------------------------------------
# Every game request carries the APK version (mmog.xml client/version) and the game data version in effect, so
# the server can refuse online play to outdated clients (server/game.py version gate). APKs without these
# parameters (1.0.0) are refused too; they also get the original "NEW UPDATE AVAILABLE" popup, because the
# server's GetVersionResponse names a newer version, and continue offline.
SERVERCOM = "com.frimastudio.common.core.servercom.ServerComHTTP"
SERVERCOM_EDITS = [
    ("""   import flash.utils.ByteArray;
""", """   import flash.utils.ByteArray;
   import com.frimastudio.as3ToolKit.net.Loader;
"""),
    ("""         this.mServerUrl = param1.replace(_loc4_,_loc4_ + ":" + param2);
""", """         this.mServerUrl = param1.replace(_loc4_,_loc4_ + ":" + param2);
         this.mServerUrl += (this.mServerUrl.indexOf("?") == -1 ? "?" : "&") + "v=" + (ManagerA.Util as IUtil).GetVar("client","version") + "&d=" + Loader.ActiveGameDataVersion;
"""),
]

# Do not recompile LoginModule: with an edit there (closepopupconfig.xml?v=) the upgraded app hung at the end of
# startup in the emulator; without it, it starts normally. The server picks the startup popup text from the version
# the client IP last sent with GetVersionRequest instead (server/server.py).
# "UPDATE NOW" opens the project's releases page instead of the closed Google Play listing.
RELEASES_URL = "https://github.com/Eclip5eLP/YGOBamPocketRevived/releases/latest"
NEW_APP_UPDATE = "com.frimastudio.snowstorm.project.popup.popups.versionupdate.NewAppUpdate"
NEW_APP_UPDATE_EDITS = [
    ("""private const ANDROID_APP_URL:String = "https://play.google.com/store/apps/details?id=air." + "com.konami.ygo";""",
     f"""private const ANDROID_APP_URL:String = "{RELEASES_URL}";"""),
]
VERSION_UNAVAILABLE = "com.frimastudio.snowstorm.project.popup.popups.versionupdate.VersionUnavailable"
VERSION_UNAVAILABLE_EDITS = [
    ("""private const ANDROID_APP_URL:String = "https://play.google.com/store/apps/details?id=" + "com.konami.ygo";""",
     f"""private const ANDROID_APP_URL:String = "{RELEASES_URL}";"""),
]

# --- Several main (world) maps (notes/findings.md 6.35) -------------------------------------------------------
# World map template N > 1 is defined by worldnodetemplate rows with worldMapTemplateId N (game data) and its layout
# asset/world/worldmap<N>.xml (world package). Saves get the missing world maps when they load (ValidateWorld runs
# on every load), the world map shows a switch button when the save has more than one, and the helpers that
# assumed world map 1 look across all world maps.
DEFAULT_DATA = "com.frimastudio.snowstorm.project.engine.data.YGOMDefaultDataUtil"
DEFAULT_DATA_EDITS = [
    ("""      private static function ValidateWorld() : void
      {
""", """      private static function ValidateMissingWorldMaps() : void
      {
         var templateId:int = 0;
         var map:WorldMap = null;
         var found:Boolean = false;
         var templateList:Vector.<WorldNodeTemplate> = null;
         var template:WorldNodeTemplate = null;
         var node:WorldNode = null;
         var mapManager:IWorldmapManagerYGO = ManagerA.GetManager(EManagerDefinitionProject.WORLDMAP_MANAGER) as IWorldmapManagerYGO;
         for(templateId = 2; templateId <= 20; templateId++)
         {
            templateList = mapManager.CacheLogic.GetWorldNodeTemplateListByWorldMapTemplateId(templateId);
            if(templateList == null || templateList.length == 0)
            {
               continue;
            }
            found = false;
            for each(map in mJSONSave.worldMapArray)
            {
               if(map.worldMapTemplateId == templateId)
               {
                  found = true;
               }
            }
            if(found)
            {
               continue;
            }
            map = new WorldMap();
            map.id = mJSONSave.currentIndex--;
            map.avatarPlayerId = mJSONSave.worldMapArray[0].avatarPlayerId;
            map.totalStarCompleted = 0;
            map.worldMapTemplateId = templateId;
            map.worldNodes = new Array();
            for each(template in templateList)
            {
               node = new WorldNode();
               node.id = mJSONSave.currentIndex--;
               node.worldMapId = map.id;
               node.worldNodeTemplateId = template.id;
               node.completed = false;
               node.locked = template.locked;
               node.starTotal = 0;
               node.fullyCompletedTotal = 0;
               map.worldNodes.push(node);
            }
            mJSONSave.worldMapArray.push(map);
         }
      }

      private static function ValidateWorld() : void
      {
         ValidateMissingWorldMaps();
"""),
]

WORLDMAP_CACHE = "com.frimastudio.snowstorm.project.worldmap.WorldmapCacheLogic"
WORLDMAP_CACHE_EDITS = [
    ("""         var worldMap:WorldMap = this.GetWorldMapByTemplateId(1);
         var templateId:int = int.MAX_VALUE;
         for(var i:int = 0; i < worldMap.worldNodes.length; i++)
         {
            worldTemplate = this.GetWorldNodeTemplateById(worldMap.worldNodes[i].worldNodeTemplateId);
            if(worldTemplate != null && worldTemplate.storyMapTemplateId == aStoryMapTemplateId)
            {
               if(worldTemplate.id < templateId)
               {
                  worldXMLName = worldTemplate.xmlNodeName;
                  templateId = worldTemplate.id;
               }
            }
         }
         return this.GetWorldNodeByXmlNodeName(worldMap.id,worldXMLName);""",
     """         var worldMap:WorldMap = null;
         var foundMap:WorldMap = null;
         var templateId:int = int.MAX_VALUE;
         for each(worldMap in this.mCache.GetWorldMapList())
         {
            for(var i:int = 0; i < worldMap.worldNodes.length; i++)
            {
               worldTemplate = this.GetWorldNodeTemplateById(worldMap.worldNodes[i].worldNodeTemplateId);
               if(worldTemplate != null && worldTemplate.storyMapTemplateId == aStoryMapTemplateId)
               {
                  if(worldTemplate.id < templateId)
                  {
                     worldXMLName = worldTemplate.xmlNodeName;
                     templateId = worldTemplate.id;
                     foundMap = worldMap;
                  }
               }
            }
         }
         if(foundMap == null)
         {
            return null;
         }
         return this.GetWorldNodeByXmlNodeName(foundMap.id,worldXMLName);"""),
]

WORLDMAP_DAL = "com.frimastudio.snowstorm.project.worldmap.dal.WorldmapManagerDalMobile"
WORLDMAP_DAL_EDITS = [
    ("""            template = (mManager as IWorldmapManagerYGO).CacheLogic.GetWorldNodeTemplateById(aRequest.worldNodeTemplatesId[i]);
            node = (mManager as IWorldmapManagerYGO).CacheLogic.GetWorldNodeByXmlNodeName(worldMap.id,template.xmlNodeName);""",
     """            template = (mManager as IWorldmapManagerYGO).CacheLogic.GetWorldNodeTemplateById(aRequest.worldNodeTemplatesId[i]);
            worldMap = (mManager as IWorldmapManagerYGO).CacheLogic.GetWorldMapByTemplateId(template.worldMapTemplateId);
            node = (mManager as IWorldmapManagerYGO).CacheLogic.GetWorldNodeByXmlNodeName(worldMap.id,template.xmlNodeName);"""),
]

# Chapters missing from the hard-coded chapter list (maptoload "60" -> id 59) get an entry on first use
WORLD_NODE_ENUM = "com.frimastudio.snowstorm.module.map.enum.WorldNodeEnum"
WORLD_NODE_ENUM_EDITS = [
    ("""            if(enum.MapToLoad == aMapToLoad)
            {
               return enum;
            }
         }
         return null;""", """            if(enum.MapToLoad == aMapToLoad)
            {
               return enum;
            }
         }
         if(int(aMapToLoad) > 1)
         {
            return new WorldNodeEnum(int(aMapToLoad) - 1,aMapToLoad,false);
         }
         return null;"""),
]

WORLD_MAP_VIEW = "com.frimastudio.snowstorm.module.map.map.WorldMap"
WORLD_MAP_VIEW_EDITS = [
    ("""   import com.frimastudio.snowstorm.project.worldmap.amf.WorldNodeTemplate;
""", """   import com.frimastudio.snowstorm.project.worldmap.amf.WorldNodeTemplate;
   import flash.filesystem.File;
"""),
    # fail safe: an unknown world map id or a missing layout file (e.g. content not downloaded) falls back to map 1
    ("""         LoadWorldXML(EMapModuleLibrary.WORLD_MAP_ASSET);""",
     """         var worldMapUrl:String = EMapModuleLibrary.WORLD_MAP_ASSET;
         var currentWorldMap:Object = mWorldmapManager.CacheLogic.GetWorldMapById(mMapProgression.worldMapId);
         var layoutFile:File = null;
         if(currentWorldMap != null && currentWorldMap.worldMapTemplateId != 1)
         {
            layoutFile = File.applicationStorageDirectory.resolvePath("asset/world/worldmap" + currentWorldMap.worldMapTemplateId + ".xml");
            if(layoutFile.exists)
            {
               worldMapUrl = layoutFile.url;
            }
            else
            {
               currentWorldMap = null;
            }
         }
         if(currentWorldMap == null && mWorldmapManager.CacheLogic.GetWorldMapByTemplateId(1) != null)
         {
            mMapProgression.worldMapId = mWorldmapManager.CacheLogic.GetWorldMapByTemplateId(1).id;
            mMapProgression.worldMapNodeId = 1;
         }
         LoadWorldXML(worldMapUrl);"""),
]

# World selection: a fifth button in the map's left action bar (only on a world map, only when the save has several
# world maps) opens a scrollable list of worlds (BigInfoPopup with Entries). Any failure leaves the bar as it was.
BIG_INFO_DATA = "com.frimastudio.snowstorm.project.popup.data.BigInfoPopupData"
BIG_INFO_DATA_EDITS = [
    ("""      public function BigInfoPopupData(aContentText:String = null)""",
     """      public var Entries:Array = null;

      public var SelectedEntry:int = -1;

      public function BigInfoPopupData(aContentText:String = null)"""),
]

BIG_INFO = "com.frimastudio.snowstorm.project.popup.popups.BigInfoPopup"
BIG_INFO_EDITS = [
    ("""   import starling.utils.HAlign;
""", """   import starling.utils.HAlign;
   import com.frimastudio.snowstorm.project.popup.data.BigInfoPopupData;
   import com.frimastudio.snowstorm.project.ui.ECommonButton;
   import starling.display.DisplayObject;
   import starling.text.TextField;
   import flash.geom.Point;
"""),
    ("""      private function SetupScrollerText() : void
      {
""", """      private function SetupEntries(aEntries:Array) : void
      {
         var i:int = 0;
         var button:DisplayObject = null;
         var title:TextField = new TextField(this.mPopupSize.width - 80,80,(mPopupData as InfoPopupData).ContentText,EFonts.HANZEL_BOLD,40,7223);
         this.mScrollerElement.addChild(title);
         for(i = 0; i < aEntries.length; i++)
         {
            button = AssetManagerWrapper.GetButton(i == (mPopupData as BigInfoPopupData).SelectedEntry ? ECommonButton.GREEN_BUTTON : ECommonButton.LIGHT_BLUE_BUTTON,new Point(this.mPopupSize.width - 120,90),String(aEntries[i]),EFonts.HANZEL_BOLD,34,16777215,true,HAlign.CENTER,VAlign.CENTER);
            button.name = String(i);
            button.addEventListener(Event.TRIGGERED,this.OnEntryTouch);
            this.mScrollerElement.addChild(button);
         }
      }

      private function OnEntryTouch(aEvent:Event) : void
      {
         if(this.mScrollerElement.HasMoved)
         {
            return;
         }
         mPopupData.CustomData = int((aEvent.currentTarget as DisplayObject).name);
         DispatchPopupClosedEvent();
      }

      private function SetupScrollerText() : void
      {
         if(mPopupData is BigInfoPopupData && (mPopupData as BigInfoPopupData).Entries != null)
         {
            this.SetupEntries((mPopupData as BigInfoPopupData).Entries);
            return;
         }
"""),
]

MAP_ACTION_BAR = "com.frimastudio.snowstorm.module.hud.bar.MapActionBar"
MAP_ACTION_BAR_EDITS = [
    ("""   import com.frimastudio.snowstorm.module.map.popup.data.StoryPopupData;
""", """   import com.frimastudio.snowstorm.module.map.popup.data.StoryPopupData;
   import com.frimastudio.snowstorm.project.popup.data.BigInfoPopupData;
"""),
    ("""      private var mMenuButton:Button;
""", """      private var mMenuButton:Button;

      private var mWorldButton:Button;

      private var mWorldPopup:Popup;

      private var mWorldList:Array;

      private function GetSortedWorldMaps() : Array
      {
         var map:Object = null;
         var list:Array = [];
         for each(map in this.mWorldMapManager.CacheLogic.GetWorldMapList())
         {
            list.push(map);
         }
         list.sortOn("worldMapTemplateId",Array.NUMERIC);
         return list;
      }

      private function AddWorldButton() : void
      {
         var progression:MapProgression = null;
         try
         {
            progression = this.mWorldMapManager.CacheLogic.GetMapProgression();
            if(this.IsOpenedOutsideMapModule || progression == null || progression.storyNodeId != 0 || this.GetSortedWorldMaps().length < 2)
            {
               return;
            }
            this.mWorldButton = AssetManagerWrapper.GetBaseButton("hud_worldbutton");
            this.mWorldButton.addChildAt(AssetManagerWrapper.GetButton(ECommonButton.DARK_BLUE_BUTTON,new Point(98.5,98.5)),0);
            this.mWorldButton.x = 10;
            this.mWorldButton.y = BUTTON_POSITION_Y[0] - 108;
            this.mWorldButton.addEventListener(Event.TRIGGERED,this.OnWorldButton);
            this.mContainer.addChild(this.mWorldButton);
            this.mContainer.y -= 108;
            this.mBackground.y -= 108;
            this.mBackground.height += 108;
         }
         catch(error:Error)
         {
            if(this.mWorldButton != null)
            {
               this.mWorldButton.removeFromParent(true);
               this.mWorldButton = null;
            }
         }
      }

      private function OnWorldButton(aEvent:Event) : void
      {
         var i:int = 0;
         var labels:Array = [];
         var data:BigInfoPopupData = null;
         var current:int = this.mWorldMapManager.CacheLogic.GetMapProgression().worldMapId;
         if(PopupManager.IsPopupDisplayed())
         {
            return;
         }
         this.mWorldList = this.GetSortedWorldMaps();
         data = new BigInfoPopupData("SELECT A WORLD");
         data.Entries = labels;
         for(i = 0; i < this.mWorldList.length; i++)
         {
            labels.push(this.WorldName(this.mWorldList[i].worldMapTemplateId));
            if(this.mWorldList[i].id == current)
            {
               data.SelectedEntry = i;
            }
         }
         this.mWorldPopup = PopupManager.Show(data);
         this.mWorldPopup.addEventListener(PopupManagerEvent.POPUP_CLOSED,this.OnWorldSelected);
      }

      private function WorldName(aTemplateId:int) : String
      {
         var key:String = "WORLD_NAME_" + aTemplateId;
         var name:String = this.mLocalizer.GetString(EMapStringId.WORLD_MAP_LOCALIZER_SECTION,key);
         return name == null || name == "" || name == key ? "World " + aTemplateId : name;
      }

      private function OnWorldSelected(aEvent:PopupManagerEvent) : void
      {
         var progression:MapProgression = null;
         var map:Object = null;
         this.mWorldPopup.removeEventListener(PopupManagerEvent.POPUP_CLOSED,this.OnWorldSelected);
         this.mWorldPopup = null;
         if(!(aEvent.CustomData is int) || int(aEvent.CustomData) < 0 || int(aEvent.CustomData) >= this.mWorldList.length)
         {
            return;
         }
         map = this.mWorldList[int(aEvent.CustomData)];
         progression = this.mWorldMapManager.CacheLogic.GetMapProgression();
         if(map.id == progression.worldMapId)
         {
            return;
         }
         progression.worldMapId = map.id;
         progression.worldMapNodeId = 1;
         progression.storyMapId = 0;
         progression.storyNodeId = 0;
         this.mWorldMapManager.SaveTravelProgression(progression);
         this.ChangeModule(EStarlingModuleDefinition.MAP);
      }
"""),
    ("""         for(var i:int = 0; i < 4; i++)
         {
            this.AddButton(i);
         }
""", """         for(var i:int = 0; i < 4; i++)
         {
            this.AddButton(i);
         }
         this.AddWorldButton();
"""),
    ("""         if(Boolean(this.mMenuButton))
         {""", """         if(Boolean(this.mWorldButton))
         {
            this.mWorldButton.removeEventListener(Event.TRIGGERED,this.OnWorldButton);
            this.mWorldButton.removeFromParent(true);
            this.mWorldButton = null;
         }
         if(Boolean(this.mMenuButton))
         {"""),
]

# --- In-app login (notes/findings.md 6.35) --------------------------------------------------------------------
# Login opened the system browser (navigateToURL) and came back through the fb<appId>://authorize link. Now the
# login page opens in a StageWebView over the game, like the invite dialog; the authorize redirect is caught in
# the web view and handed to the existing ProcessLogin. Android Back or the page's Cancel link closes it.
FB_MANAGER = "com.frimastudio.snowstorm.project.facebook.FacebookManagerMobile"
FB_MANAGER_EDITS = [
    ("""   import flash.media.StageWebView;
""", """   import flash.media.StageWebView;
   import flash.events.LocationChangeEvent;
   import flash.events.KeyboardEvent;
   import flash.ui.Keyboard;
"""),
    ("""         navigateToURL(req);
""", """         this.OpenLoginWebView(url + "?" + ops.toString());
"""),
    ("""      protected function OnLoginFailed(aResetDiskCache:Boolean = false) : void
""", """      private var mLoginWebView:StageWebView;

      private function OpenLoginWebView(aUrl:String) : void
      {
         this.CloseLoginWebView();
         var stage:Object = Starling.current.nativeStage;
         this.mLoginWebView = new StageWebView();
         this.mLoginWebView.stage = Starling.current.nativeStage;
         this.mLoginWebView.viewPort = new Rectangle(stage.stageWidth * 0.15,stage.stageHeight * 0.04,stage.stageWidth * 0.7,stage.stageHeight * 0.92);
         this.mLoginWebView.addEventListener(LocationChangeEvent.LOCATION_CHANGING,this.OnLoginWebViewLocation);
         this.mLoginWebView.addEventListener(LocationChangeEvent.LOCATION_CHANGE,this.OnLoginWebViewLocation);
         Starling.current.nativeStage.addEventListener(KeyboardEvent.KEY_DOWN,this.OnLoginWebViewKey,false,1000);
         this.mLoginWebView.loadURL(aUrl);
      }

      private function CloseLoginWebView() : void
      {
         if(this.mLoginWebView == null)
         {
            return;
         }
         Starling.current.nativeStage.removeEventListener(KeyboardEvent.KEY_DOWN,this.OnLoginWebViewKey);
         this.mLoginWebView.removeEventListener(LocationChangeEvent.LOCATION_CHANGING,this.OnLoginWebViewLocation);
         this.mLoginWebView.removeEventListener(LocationChangeEvent.LOCATION_CHANGE,this.OnLoginWebViewLocation);
         this.mLoginWebView.stage = null;
         this.mLoginWebView.dispose();
         this.mLoginWebView = null;
      }

      private function OnLoginWebViewLocation(aEvent:LocationChangeEvent) : void
      {
         var location:String = aEvent.location;
         if(location == null || location.indexOf("fb" + this.mAppId + "://") != 0)
         {
            return;
         }
         aEvent.preventDefault();
         this.CloseLoginWebView();
         this.mListenForLoginInvoke = false;
         this.ProcessLogin(location);
      }

      private function OnLoginWebViewKey(aEvent:KeyboardEvent) : void
      {
         if(aEvent.keyCode != Keyboard.BACK || this.mLoginWebView == null)
         {
            return;
         }
         aEvent.preventDefault();
         aEvent.stopImmediatePropagation();
         this.CloseLoginWebView();
         this.mListenForLoginInvoke = false;
         this.ProcessLogin(null);
      }

      protected function OnLoginFailed(aResetDiskCache:Boolean = false) : void
"""),
]

# --- No Facebook logo on the login buttons ----------------------------------------------------------------------
def _no_icon(button, icon):
    return (f"""         this.{button}.AddIcon({icon});
         this.{button}.textBounds = new Rectangle({icon}.width,0,this.{button}.textBounds.width - {icon}.width - 10,this.{button}.textBounds.height);
""", "")


MAIN_MENU_VIEW = "com.frimastudio.snowstorm.module.mainmenu.view.MainMenuView"
LOGIN_VIEW = "com.frimastudio.snowstorm.module.login.view.LoginView"
ADVANTAGE_POPUP = "com.frimastudio.snowstorm.module.login.popup.AdvantageLoginPopup"

# --- Quick fixes (notes/todo.md priority 1) ---------------------------------------------------------------------
# The server info popup (ShowApplicationClosePopup) only at startup (LoginModule), not every time the currency
# shop opens.
POPUP_UTIL = "com.frimastudio.snowstorm.project.popup.PopupManagerUtil"
POPUP_UTIL_EDITS = [
    ("""         PopupManager.Show(popup,aQueuePopup) as CurrencyPopup;
         ShowApplicationClosePopup();
""", """         PopupManager.Show(popup,aQueuePopup) as CurrencyPopup;
"""),
]

# Leaderboard opens on all players, "friends only" unticked.
LEADERBOARD_UI = "com.frimastudio.snowstorm.module.arena.popup.ui.LeaderboardPopupUI"
LEADERBOARD_UI_EDITS = [
    ("""         this.mFriendOnlyCheckbox.IsChecked = true;""", """         this.mFriendOnlyCheckbox.IsChecked = false;"""),
]

# Settings: the support button opens the project's GitHub; no BAM Pro "restore purchases" (Pro is always on).
OPTION_POPUP = "com.frimastudio.snowstorm.module.option.popup.OptionPopup"
OPTION_POPUP_EDITS = [
    ('''      private static const FORUM_URL:String = "http://yugioh-bam.com/mobile";''',
     '''      private static const FORUM_URL:String = "https://github.com/Eclip5eLP/YGOBamPocketRevived";'''),
    ("""         mUiContainer.addChild(this.mRestoreTransactionBtn);
""", """         mUiContainer.addChild(this.mRestoreTransactionBtn);
         this.mRestoreTransactionBtn.visible = false;
         bamProText.visible = false;
"""),
    # the support block alone, centred in the right column
    ("""         forSupportText.y = 422;""", """         forSupportText.y = 280;"""),
    ("""         this.mVisitForumButton.y = 470;""", """         this.mVisitForumButton.y = 328;"""),
]

# BAM Pro is always unlocked: every Pro check reads this getter (chapters, series 2 packs and cards, arena, the
# upgrade banners); GateBamPro read the field directly. Saves store isPremium = true from then on.
BAM_PRO = "com.frimastudio.snowstorm.project.bampro.BamProHandlerImpl"
BAM_PRO_EDITS = [
    ("""      public function get IsBamPro() : Boolean
      {
         return this.mIsBamPro;""", """      public function get IsBamPro() : Boolean
      {
         return true;"""),
    ("""         if(this.mIsBamPro)
         {
            dispatchEvent(new BamProHandlerEvent(BamProHandlerEvent.BAM_PRO_GATE,true));""",
     """         if(this.IsBamPro)
         {
            dispatchEvent(new BamProHandlerEvent(BamProHandlerEvent.BAM_PRO_GATE,true));"""),
]

# Energy never runs out: every reader (duel start, try again, consume requests, the widget) sees at least the
# maximum, so consumption has no effect. The HUD energy bar is not shown (the widget still exists, unchanged).
ENERGY_MANAGER = "com.frimastudio.snowstorm.project.energy.EnergyManager"
ENERGY_MANAGER_EDITS = [
    ("""      public function get CurrentEnergy() : Energy
      {
         return this.mCurrentEnergy;""", """      public function get CurrentEnergy() : Energy
      {
         if(this.mCurrentEnergy != null && this.mCurrentEnergy.energy < this.mCurrentEnergy.maximumEnergy)
         {
            this.mCurrentEnergy.energy = this.mCurrentEnergy.maximumEnergy;
         }
         return this.mCurrentEnergy;"""),
]

# No energy costs on screen: the duel popups lose the energy icon + number (the button label is centred instead),
# the "try again" button loses its energy icon, and a node's "-N" energy animation is skipped (the flow continues
# exactly like for a node without cost). Node hover tooltips (web only) are left as they are.
DUEL_INFO_POPUP = "com.frimastudio.snowstorm.module.map.popup.DuelInfoPopup"
DUEL_INFO_POPUP_EDITS = [
    ("""         mUiContainer.addChild(energyIcon);
""", ""),
    ("""         mUiContainer.addChild(energyCost);
""", ""),
    ("""         var duelText:TextField = new TextField(175,56,data.BtnText,EFonts.HANZEL_BOLD,43,16777215);
         duelText.vAlign = VAlign.CENTER;
         duelText.hAlign = HAlign.LEFT;
         duelText.touchable = false;
         duelText.autoScale = true;
         duelText.x = 400;""", """         var duelText:TextField = new TextField(280,56,data.BtnText,EFonts.HANZEL_BOLD,43,16777215);
         duelText.vAlign = VAlign.CENTER;
         duelText.hAlign = HAlign.CENTER;
         duelText.touchable = false;
         duelText.autoScale = true;
         duelText.x = 312;"""),
]

DUEL_STAR_POPUP = "com.frimastudio.snowstorm.module.map.popup.DuelStarPopup"
DUEL_STAR_POPUP_EDITS = [
    ("""         var buttonText:TextField = new TextField(47,33,aBtnText,EFonts.HANZEL_BOLD,26,16777215);
         buttonText.touchable = false;
         buttonText.autoScale = true;
         buttonText.x = 15;""", """         var buttonText:TextField = new TextField(150,33,aBtnText,EFonts.HANZEL_BOLD,26,16777215);
         buttonText.touchable = false;
         buttonText.autoScale = true;
         buttonText.x = 21;"""),
    ("""         container.addChild(energyIcon);
""", ""),
    ("""         container.addChild(energyCost);
""", ""),
]

TRY_AGAIN_POPUP = "com.frimastudio.snowstorm.module.cardgame.popup.TryAgainPopup"
TRY_AGAIN_POPUP_EDITS = [
    ("""         this.mTryAgainButton.AddIcon(AssetManagerWrapper.GetImage("popup_energy_buton"));
         this.mTryAgainButton.textBounds = new Rectangle(140,22,204,52);""",
     """         this.mTryAgainButton.textBounds = new Rectangle(20,22,315,52);"""),
    ("""         mUiContainer.addChild(energyText);
""", ""),
]

STORY_MAP = "com.frimastudio.snowstorm.module.map.map.StoryMap"
STORY_MAP_EDITS = [
    ("""            StarlingListener.Add(AnimationHandlerEvent.ENERGY_COST_ANIM_PLAYED,mAnimationHandler as EventDispatcher,this.OnEnergyCostDone);
            mAnimationHandler.PlayEnergyCostAnim(aXmlNode.EnergyCost);""",
     """            this.OnEnergyCostDone(null);"""),
]

# Pack guard: a booster pack whose shop item opens no loot table (or an empty one) is refused before any currency
# is taken (the original flow charges first, then rolls the pack). The build already validates this
# (content_mods.write_boosterpacks); this is the runtime safety net. If the check itself fails, the purchase
# proceeds as before.
SHOP_MANAGER = "com.frimastudio.snowstorm.project.shop.ShopManagerProject"
SHOP_MANAGER_EDITS = [
    ("""   import com.frimastudio.common.core.manager.ManagerA;
""", """   import com.frimastudio.common.core.manager.ManagerA;
   import com.frimastudio.snowstorm.project.shop.enumeration.ShopItemTypes;
   import com.frimastudio.snowstorm.project.popup.PopupManagerUtil;
"""),
    ("""         var purchaseCost:int = shopItemConversion.cost * Math.max(aShopItem.quantity,1);""",
     """         if(aShopItem.shopItemTypeId == ShopItemTypes.LOOT.Id && !this.HasLootTable(aShopItem.id))
         {
            PopupManagerUtil.ShowWarning("PACK UNAVAILABLE","This booster pack cannot be opened right now.");
            return PASS_DATE;
         }
         var purchaseCost:int = shopItemConversion.cost * Math.max(aShopItem.quantity,1);"""),
    ("""      private function SendBuyQuestInformation(aShopItem:ShopItem) : void""",
     """      private function HasLootTable(aShopItemId:int) : Boolean
      {
         var loot:LootShopItemTemplate = null;
         var group:Object = null;
         try
         {
            loot = (ManagerA.GetManager(EManagerDefinitionProject.LOOT_MANAGER) as ILootManagerYGO).CacheLogic.GetLootShopItemTemplateById(aShopItemId);
            if(loot == null || loot.lootGroups == null)
            {
               return false;
            }
            for each(group in loot.lootGroups)
            {
               if(group.lootItemTemplates != null && group.lootItemTemplates.length > 0)
               {
                  return true;
               }
            }
            return false;
         }
         catch(error:Error)
         {
         }
         return true;
      }

      private function SendBuyQuestInformation(aShopItem:ShopItem) : void"""),
]

# Collection: a main menu button opens the shop's card view in collection mode (ShopCardView.CollectionMode):
# every card of the game with the owned quantity (CardTemplateListUtil, like the deck builder), unowned cards
# dimmed, no prices, the filter screen with its "my cards only" box, "owned / shown" count; back returns to the main
# menu. The flag is cleared when the shop module closes. The button is only added if its icon and label can be
# built (new main menu atlas page, content_mods.mainmenu_icons); otherwise the menu stays as it was.
MAIN_MENU_VIEW_EDITS = [
    ("""   import com.frimastudio.mobile.adaptativeui.Element;
""", """   import com.frimastudio.mobile.adaptativeui.Element;
   import com.revival.friends.RequestBadge;
"""),
    ("""         bottomButtonBar.addChild(this.mTournamentButton);
""", """         bottomButtonBar.addChild(this.mTournamentButton);
         this.AddProfileButton(bottomButtonBar);
         RequestBadge.Attach(this.mFriendsButton);
"""),
    ("""         this.mTournamentButton.filter = tournamentColor;""", """         this.mTournamentButton.filter = tournamentColor;
         if(this.mProfileButton != null)
         {
            this.mProfileButton.filter = gameColor;
         }"""),
    ("""      private var mCraftingButton:Scale9Button;
""", """      private var mCraftingButton:Scale9Button;

      private var mCollectionButton:Scale9Button;

      private var mProfileButton:Scale9Button;

      public function get ProfileButton() : Scale9Button
      {
         return this.mProfileButton;
      }

      private function AddProfileButton(aBar:Element) : void
      {
         try
         {
            this.mProfileButton = this.CreateMainMenuButton("mainmenu_profile");
            aBar.addChild(this.mProfileButton);
         }
         catch(error:Error)
         {
            if(this.mProfileButton != null)
            {
               this.mProfileButton.removeFromParent(true);
               this.mProfileButton = null;
            }
         }
      }

      public function get CollectionButton() : Scale9Button
      {
         return this.mCollectionButton;
      }

      private function AddCollectionButton(aBar:Element) : void
      {
         try
         {
            this.mCollectionButton = this.CreateMainMenuButton("mainmenu_collection");
            aBar.addChild(this.mCollectionButton);
         }
         catch(error:Error)
         {
            if(this.mCollectionButton != null)
            {
               this.mCollectionButton.removeFromParent(true);
               this.mCollectionButton = null;
            }
         }
      }
"""),
    ("""         topButtonBar.addChild(this.mEditDeckButton);
""", """         topButtonBar.addChild(this.mEditDeckButton);
         this.AddCollectionButton(topButtonBar);
"""),
    ("""         this.mCraftingButton = null;
""", """         this.mCraftingButton = null;
         if(this.mCollectionButton != null)
         {
            this.mCollectionButton.removeFromParent(true);
            this.mCollectionButton = null;
         }
         if(this.mProfileButton != null)
         {
            this.mProfileButton.removeFromParent(true);
            this.mProfileButton = null;
         }
"""),
]

MAIN_MENU_MODULE = "com.frimastudio.snowstorm.module.mainmenu.MainMenuModule"
MAIN_MENU_MODULE_EDITS = [
    ("""   import com.frimastudio.mobile.module.EStarlingModuleDefinition;
""", """   import com.frimastudio.mobile.module.EStarlingModuleDefinition;
   import com.frimastudio.snowstorm.module.shop.view.ShopCardView;
   import com.revival.profile.ProfilePopupData;
   import com.frimastudio.snowstorm.project.facebook.FacebookProxy;
"""),
    ("""         this.mUi.CraftingButton.addEventListener(Event.TRIGGERED,this.OnTouchHandler);
""", """         this.mUi.CraftingButton.addEventListener(Event.TRIGGERED,this.OnTouchHandler);
         if(this.mUi.CollectionButton != null)
         {
            this.mUi.CollectionButton.addEventListener(Event.TRIGGERED,this.OnTouchHandler);
         }
         if(this.mUi.ProfileButton != null)
         {
            this.mUi.ProfileButton.addEventListener(Event.TRIGGERED,this.OnTouchHandler);
         }
"""),
    ("""         this.mUi.CraftingButton.removeEventListener(Event.TRIGGERED,this.OnTouchHandler);
""", """         this.mUi.CraftingButton.removeEventListener(Event.TRIGGERED,this.OnTouchHandler);
         if(this.mUi.CollectionButton != null)
         {
            this.mUi.CollectionButton.removeEventListener(Event.TRIGGERED,this.OnTouchHandler);
         }
         if(this.mUi.ProfileButton != null)
         {
            this.mUi.ProfileButton.removeEventListener(Event.TRIGGERED,this.OnTouchHandler);
         }
"""),
    ("""            case this.mUi.ShopButton:
               this.ChangeModule(EStarlingModuleDefinition.SHOP);
               break;""", """            case this.mUi.ShopButton:
               this.ChangeModule(EStarlingModuleDefinition.SHOP);
               break;
            case this.mUi.CollectionButton:
               ShopCardView.CollectionMode = true;
               this.ChangeModule(EStarlingModuleDefinition.SHOP);
               break;
            case this.mUi.ProfileButton:
               if(!YGOMLogin.IsLogguedIn())
               {
                  PopupManagerUtil.ShowLoginRequiredPopup();
               }
               else
               {
                  try
                  {
                     PopupManager.Show(new ProfilePopupData(FacebookProxy.OwnUser.uid,true));
                  }
                  catch(error:Error)
                  {
                  }
               }
               break;"""),
]

SHOP_MODULE = "com.frimastudio.snowstorm.module.shop.ShopModule"
SHOP_MODULE_EDITS = [
    ("""   import com.frimastudio.snowstorm.module.shop.view.AbstractShopView;
""", """   import com.frimastudio.snowstorm.module.shop.view.AbstractShopView;
   import com.frimastudio.snowstorm.module.shop.view.ShopCardView;
"""),
    ("""         this.ChangeView(EShopView.MENU);""",
     """         this.ChangeView(ShopCardView.CollectionMode ? EShopView.CARD : EShopView.MENU);"""),
    ("""      override public function Dispose() : void
      {
         super.Dispose();""", """      override public function Dispose() : void
      {
         ShopCardView.CollectionMode = false;
         super.Dispose();"""),
]

# Original content in the APK (findings 6.63): the APK carries the content packages under
# assets/externalpackage/<name>-<version>.zip plus the version list (externalpackage/versionning.xml), so a fresh
# install plays at once, even offline. A bundled package is used only when it is exactly the version the version
# list asks for (newer packages, e.g. new cards, still download). The game already had a debug path that installs
# externalpackage/<name>.zip without a version check (LoadPackage); it now uses the versioned name. Without a saved
# version list and without the server (first start offline), the bundled list is used instead of failing; when every
# missing package is bundled, installing starts without the download popup and without the server check.
EXTERNAL_FILES = "com.frimastudio.snowstorm.project.externalfile.ExternalFileControllerImpl"
EXTERNAL_FILES_EDITS = [
    ("""         var debugFastPackage:File = File.applicationDirectory.resolvePath("externalpackage/" + aAssetToLoad.Name + this.PACKAGE_END);""",
     """         var debugFastPackage:File = this.BundledPackage(aAssetToLoad);"""),
    ("""            if(isDebugLoading == true)
            {
               this.DisplayLoadingPopup(-1);
            }""", """            if(this.AllMissingBundled())
            {
               this.OnStartLoading(null);
            }
            else if(isDebugLoading == true)
            {
               this.DisplayLoadingPopup(-1);
            }"""),
    # the download popup counts only what really downloads
    ("""               loadingSpace += assetData.CompressedSize;""", """               if(!this.BundledPackage(this.mMissingPackageList[i]).exists)
               {
                  loadingSpace += assetData.CompressedSize;
               }"""),
    ("""      private function ValidateVersionAvailableOnServer() : void""", """      private function BundledPackage(aAsset:EExternalAsset) : File
      {
         var version:String = VersionController.GetAssetVersion(VersionController.CurrentGameVersion,aAsset.Name);
         return File.applicationDirectory.resolvePath("externalpackage/" + aAsset.Name + "-" + version + this.PACKAGE_END);
      }

      private function AllMissingBundled() : Boolean
      {
         try
         {
            for each(var asset:EExternalAsset in this.mMissingPackageList)
            {
               if(!this.BundledPackage(asset).exists)
               {
                  return false;
               }
            }
            return this.mMissingPackageList.length > 0;
         }
         catch(error:Error)
         {
         }
         return false;
      }

      private function ValidateVersionAvailableOnServer() : void"""),
]
# Startup popup text before the server has ever been reached (fresh install, offline): ours instead of Konami's
# shutdown notice (the server sends the current text, server/server.py CLOSE_POPUP_CONFIG_XML, which the game keeps).
# The original literal stays in an unused constant (the edit only replaces the start of its line).
_POPUP_EN = ("Yugioh BAM Pocket Revived: a free, fan-run revival, not affiliated with Konami.<br><br>LOG IN to play online: "
             "online save, friends, Arena, Teams, tournaments and live duels against your friends.<br><br>All purchases "
             "are free, including BAM Pro.<br><br>github.com/Eclip5eLP/YGOBamPocketRevived<br>By Eclip5e")
_POPUP_FR = ("Yugioh BAM Pocket Revived : une renaissance gratuite gérée par des fans, non affiliée à Konami."
             "<br><br>Connectez-vous pour jouer en ligne : sauvegarde en ligne, amis, Arène, Équipes, tournois et "
             "duels en direct contre vos amis.<br><br>Tous les achats sont gratuits, BAM Pro compris.<br><br>"
             "github.com/Eclip5eLP/YGOBamPocketRevived<br>By Eclip5e")
GAME_SETTINGS_ENUM = "com.frimastudio.snowstorm.module.option.EGameSettings"
GAME_SETTINGS_ENUM_EDITS = [
    ('''      public static const CLOSE_POPUP_EN_CONTENT:EGameSettings = new EGameSettings("close_config_content_en",''',
     f'''      public static const CLOSE_POPUP_EN_CONTENT:EGameSettings = new EGameSettings("close_config_content_en","<![CDATA[{_POPUP_EN}]]>");

      private static const KONAMI_CLOSE_POPUP_EN:String = ('''),
    ('''      public static const CLOSE_POPUP_FR_CONTENT:EGameSettings = new EGameSettings("close_config_content_fr",''',
     f'''      public static const CLOSE_POPUP_FR_CONTENT:EGameSettings = new EGameSettings("close_config_content_fr","<![CDATA[{_POPUP_FR}]]>");

      private static const KONAMI_CLOSE_POPUP_FR:String = ('''),
]
VERSION_CONTROLLER = "com.frimastudio.snowstorm.project.externalfile.versionning.VersionControllerImpl"
VERSION_CONTROLLER_EDITS = [
    ("""               this.OnLocalVersionXmlLoaded(false,null);""", """               localVersionningFile = File.applicationDirectory.resolvePath("externalpackage/" + this.VERSIONNING_XML_NAME);
               if(localVersionningFile.exists)
               {
                  FrimaLoader.LoadXML(localVersionningFile.url,this.OnLocalVersionXmlLoaded,this);
               }
               else
               {
                  this.OnLocalVersionXmlLoaded(false,null);
               }"""),
]

# Fusion (never released by Konami, so these paths were never used; findings 6.62):
# - a pack with the player's first fusion card skipped the opening animation and went straight to the fusion
#   tutorial popup: the animation now always plays, the tutorial popup comes when it closes;
# - the tutorial popup's close button started the tutorial as well (one handler for both buttons): it only closes;
# - tutorial round 2 enabled BAM only after the player tapped the fusion icon (OnFusionZoom), which the text only
#   hints at, so players got stuck: BAM is enabled once the cards are placed, as in the other rounds.
BOOSTER_VIEW = "com.frimastudio.snowstorm.module.shop.view.ShopBoosterPackView"
BOOSTER_VIEW_EDITS = [
    ("""      private var mLootManager:ILootManagerYGO;
""", """      private var mLootManager:ILootManagerYGO;

      private var mRevivalFusionLoot:Array;
"""),
    ("""            if(FusionCardUtils.CheckForFusionTutorialFromLoot(aEvent.LootList))
            {
               return;
            }""", """            this.mRevivalFusionLoot = aEvent.LootList;"""),
    ("""         this.mCurrentBoosterPackDisplay.UpdateProgressBarValue();
      }""", """         this.mCurrentBoosterPackDisplay.UpdateProgressBarValue();
         if(this.mRevivalFusionLoot != null)
         {
            FusionCardUtils.CheckForFusionTutorialFromLoot(this.mRevivalFusionLoot);
            this.mRevivalFusionLoot = null;
         }
      }"""),
]
FUSION_TUTO_POPUP = "com.frimastudio.snowstorm.project.popup.popups.FusionTutorialPopup"
FUSION_TUTO_POPUP_EDITS = [
    ("""      private function OnTouch(aEvent:Event) : void
      {
""", """      private function OnTouch(aEvent:Event) : void
      {
         if(aEvent.currentTarget == this.mCloseBtn)
         {
            DispatchPopupClosedEvent();
            return;
         }
"""),
]
FUSION_TUTO = "com.frimastudio.snowstorm.module.cardgame.flowhandling.flowhandler.FusionTutorial"
FUSION_TUTO_EDITS = [
    ("""                  DisplayBubble(ECardGameStringId.FUSION_ROUND2_STEP4,null,false);
                  return;""", """                  DisplayBubble(ECardGameStringId.FUSION_ROUND2_STEP4,null,false);"""),
]

# Card popup (Edit Deck, collection, crafting): a card shop card still locked by its chapter is not for sale yet, and
# cards the game had no source for ("Coming soon!") say how to get them (com.revival.shop.CardSource, findings 6.62).
BUY_CARD_POPUP = "com.frimastudio.snowstorm.module.shop.view.popup.BuyCardPopup"
BUY_CARD_POPUP_EDITS = [
    ("""   import starling.utils.Color;
""", """   import starling.utils.Color;
   import com.revival.shop.CardSource;
   import com.revival.shop.ShopUnlocks;
"""),
    ("""         if(Boolean(shopItem) && !shopItem.backorder)""",
     """         if(Boolean(shopItem) && !shopItem.backorder && ShopUnlocks.IsUnlocked(mCardVisual.CardTemplateId))"""),
    ("""            case STATUS_INVALID:
            default:
               this.AddInfoText("popup_buycardpopup_comingsoon");""", """            case STATUS_INVALID:
            default:
               if(CardSource.Describe(mCardVisual.CardTemplateId) != null)
               {
                  this.AddSourceText(CardSource.Describe(mCardVisual.CardTemplateId));
               }
               else
               {
                  this.AddInfoText("popup_buycardpopup_comingsoon");
               }"""),
    ("""      private function AddInfoText(aLocalizationTag:String, ... args) : void""", """      private function AddSourceText(aText:String) : void
      {
         var infoText:TextField = new TextField(325,200,aText,EFonts.HANZEL_BOLD,26,Color.WHITE);
         infoText.touchable = false;
         infoText.autoScale = true;
         infoText.vAlign = VAlign.CENTER;
         infoText.hAlign = HAlign.CENTER;
         infoText.x = mCardVisual.x + mCardVisual.width + 25;
         infoText.y = mUiContainer.stage.stageHeight / 2 - infoText.height / 2;
         mUiContainer.addChild(infoText);
      }

      private function AddInfoText(aLocalizationTag:String, ... args) : void"""),
]

SHOP_CARD_VIEW = "com.frimastudio.snowstorm.module.shop.view.ShopCardView"
SHOP_CARD_VIEW_EDITS = [
    # collection: a tapped card opens the card popup with its buy button / how to get it (as in Edit Deck), not the
    # plain big card
    ("""      private function ShowFullCardDisplay() : void
      {
""", """      private function ShowFullCardDisplay() : void
      {
         if(CollectionMode)
         {
            PopupManager.Show(new BuyCardPopupData(this.mCurrentEventCardTemplate.id),false);
            return;
         }
"""),
    ("""         this.CreateCardCountDisplay(filterContainer);
         this.UpdateCardList();""", """         this.CreateCardCountDisplay(filterContainer);
         if(CollectionMode)
         {
            this.CreateCollectionPanel(cardListContainer);
         }
         this.UpdateCardList();"""),
    ("""         this.mCardCountText = null;
""", """         this.mCardCountText = null;
         if(this.mCollectionPanel != null)
         {
            this.mCollectionPanel.removeFromParent(true);
            this.mCollectionPanel = null;
         }
"""),
    ("""   import com.frimastudio.utils.cardfiltering.CardFiltering;
""", """   import com.frimastudio.utils.cardfiltering.CardFiltering;
   import com.frimastudio.snowstorm.project.inventory.util.CardTemplateListUtil;
   import com.frimastudio.snowstorm.project.inventory.util.CardTemplateListData;
   import com.revival.collection.CollectionPanel;
   import com.revival.shop.ShopUnlocks;
   import com.frimastudio.snowstorm.module.shop.view.popup.data.BuyCardPopupData;
   import starling.core.Starling;
"""),
    # chapter-locked card shop entries (as3_new/com/revival/shop/ShopUnlocks.as)
    ("""            cardTemplate = mInventoryManager.CacheLogic.GetTemplateById(shopItem.itemTemplateId) as CardTemplate;
            if(cardTemplate != null)""", """            cardTemplate = mInventoryManager.CacheLogic.GetTemplateById(shopItem.itemTemplateId) as CardTemplate;
            if(cardTemplate != null && ShopUnlocks.IsUnlocked(shopItem.itemTemplateId))"""),
    ("""      private var mCardScrollerDataList:Vector.<AbstractScrollerData>;
""", """      private var mCardScrollerDataList:Vector.<AbstractScrollerData>;

      public static var CollectionMode:Boolean = false;

      private var mCollectionPanel:CollectionPanel;

      // New layout (as3_new/com/revival/collection): grid + preview pane. On any error the shop list stays.
      private function CreateCollectionPanel(aShopList:Element) : void
      {
         try
         {
            this.mCollectionPanel = new CollectionPanel(width,Starling.current.stage.stageHeight * 0.17);
            addChild(this.mCollectionPanel);
            aShopList.visible = false;
         }
         catch(error:Error)
         {
            if(this.mCollectionPanel != null)
            {
               this.mCollectionPanel.removeFromParent(true);
               this.mCollectionPanel = null;
            }
            aShopList.visible = true;
         }
      }

      private function CollectionText(aKey:String, aFallback:String) : String
      {
         var text:String = mLocalizerManager.GetString(ELocalizationName.MAIN_MENU.SectionName,aKey);
         return text == null || text == "" || text == aKey ? aFallback : text;
      }

      private function UpdateCollectionList() : void
      {
         var i:int = 0;
         var owned:int = 0;
         var data:CardTemplateListData = CardTemplateListUtil.GenerateCardTemplateDataList(FilterModule.MyCardOnly,FilterModule.TournamentCardOnly,this.mSelectedFilterDisplay.ActiveFilterList,this.SortCardByName);
         var ownedTemplates:Vector.<CardTemplate> = new Vector.<CardTemplate>();
         var ownedQuantities:Vector.<int> = new Vector.<int>();
         var missingTemplates:Vector.<CardTemplate> = new Vector.<CardTemplate>();
         var missingQuantities:Vector.<int> = new Vector.<int>();
         for(i = 0; i < data.CardTemplateList.length; i++)
         {
            if(data.QuantityList[i] > 0)
            {
               ownedTemplates.push(data.CardTemplateList[i]);
               ownedQuantities.push(data.QuantityList[i]);
            }
            else
            {
               missingTemplates.push(data.CardTemplateList[i]);
               missingQuantities.push(data.QuantityList[i]);
            }
         }
         data = new CardTemplateListData(ownedTemplates.concat(missingTemplates),ownedQuantities.concat(missingQuantities));
         this.mCardTemplateList = data.CardTemplateList;
         this.mCardScrollerDataList.length = 0;
         for(i = 0; i < this.mCardTemplateList.length; i++)
         {
            this.mCardScrollerDataList.push(new CardScrollerData(BuyCardShopDisplay,291,this.mCardTemplateList[i],data.QuantityList[i]));
            if(data.QuantityList[i] > 0)
            {
               owned++;
            }
         }
         if(this.mCollectionPanel != null)
         {
            this.mShopCardScroller.dataProvider = new Vector.<AbstractScrollerData>();
            this.mCollectionPanel.SetCards(this.mCardTemplateList,data.QuantityList);
         }
         else
         {
            this.mShopCardScroller.dataProvider = this.mCardScrollerDataList.concat();
         }
         this.mCardCountText.text = owned + " / " + this.mCardTemplateList.length;
      }
"""),
    ("""         TitleText = Localize("shop_card_title");
         BackLabelText = Localize("shop_menu_back_btn");""", """         TitleText = Localize("shop_card_title");
         BackLabelText = Localize("shop_menu_back_btn");
         if(CollectionMode)
         {
            FilterModule.MyCardOnly = false;
            TitleText = this.CollectionText("mainmenu_collection_text","COLLECTION");
            BackLabelText = this.CollectionText("mainmenu_back_btn_text","BACK");
         }"""),
    ("""         var shopItemGroup:ShopItemGroup = mShopManager.GetShopItemGroupById(ShopItemGroupEnum.CARD.Id);""",
     """         if(CollectionMode)
         {
            this.UpdateCollectionList();
            return;
         }
         var shopItemGroup:ShopItemGroup = mShopManager.GetShopItemGroupById(ShopItemGroupEnum.CARD.Id);"""),
    ("""         this.mActiveShopDisplay = aEvent.currentTarget as BuyCardShopDisplay;
         if(this.mShopCardScroller.HasMoved)
         {
            this.mActiveShopDisplay.BuyButton.RemoveAnimation();
            return;
         }
         this.mCurrentEventCardTemplate = aEvent.RelatedCardTemplate;
         if(this.mCurrentEventCardTemplate.cardRarityId == CardRarities.BAM_LEGEND.Id""",
     """         this.mActiveShopDisplay = aEvent.currentTarget as BuyCardShopDisplay;
         if(this.mShopCardScroller.HasMoved)
         {
            if(this.mActiveShopDisplay.BuyButton != null)
            {
               this.mActiveShopDisplay.BuyButton.RemoveAnimation();
            }
            return;
         }
         this.mCurrentEventCardTemplate = aEvent.RelatedCardTemplate;
         if(this.mCurrentEventCardTemplate.cardRarityId == CardRarities.BAM_LEGEND.Id"""),
    ("""            mModuleManager.OpenSubModule(EStarlingModuleDefinition.FILTER,[false,false,false,false]);""",
     """            mModuleManager.OpenSubModule(EStarlingModuleDefinition.FILTER,CollectionMode ? [true,true,false,false] : [false,false,false,false]);"""),
    ("""      override protected function OnBackTapped() : void
      {
         DispatchChangeView(EShopView.MENU);""", """      override protected function OnBackTapped() : void
      {
         if(CollectionMode)
         {
            CloseShop();
            return;
         }
         DispatchChangeView(EShopView.MENU);"""),
]

BUY_CARD_DISPLAY = "com.frimastudio.snowstorm.module.shop.display.BuyCardShopDisplay"
BUY_CARD_DISPLAY_EDITS = [
    ("""   import com.frimastudio.snowstorm.module.shop.display.event.CardShopDisplayEvent;
""", """   import com.frimastudio.snowstorm.module.shop.display.event.CardShopDisplayEvent;
   import com.frimastudio.snowstorm.module.shop.view.ShopCardView;
"""),
    ("""      private function CreateBuyButton() : void
      {
         var shopItem:ShopItem = null;""", """      private function CreateBuyButton() : void
      {
         var shopItem:ShopItem = null;
         if(ShopCardView.CollectionMode)
         {
            this.DisposeButton();
            return;
         }"""),
    ("""         if(this.mBuyMovieClip != null)
         {
            this.CreateBuyButton();
         }
         this.mCardOwnedPanel.Quantity = (mScrollerData as CardScrollerData).Quantity;""",
     """         if(this.mBuyMovieClip != null)
         {
            this.CreateBuyButton();
         }
         this.mCardOwnedPanel.Quantity = (mScrollerData as CardScrollerData).Quantity;
         this.mFullCardVisual.alpha = ShopCardView.CollectionMode && (mScrollerData as CardScrollerData).Quantity <= 0 ? 0.45 : 1;"""),
]

# Friends manager: the Duel Ground's add-friend button opens the new friends page (as3_new/com/revival/friends)
# instead of the old invite list; if the web view cannot open, the old popup is shown.
DUEL_GROUND = "com.frimastudio.snowstorm.module.duelground.DuelGroundModule"
DUEL_GROUND_EDITS = [
    ("""   import com.frimastudio.mobile.module.EStarlingModuleDefinition;
""", """   import com.frimastudio.mobile.module.EStarlingModuleDefinition;
   import com.revival.friends.FriendsManager;
"""),
    ("""            PopupManagerUtil.ShowInviteFriendsPopup();""", """            if(!FriendsManager.Open())
            {
               PopupManagerUtil.ShowInviteFriendsPopup();
            }"""),
]

# Startup: skip push notification registration. The Pushwoosh service is gone and its ANE is a stub
# (tools/build_stub_anes.py) that never answers, so every cold start waited the full 15 s timeout
# (MobileProjectEngine.StartPushWooshTimeout). Findings 6.49.
# (added to ENGINE's list below; one PATCHES entry per class, a second key would replace the first)
MOBILE_ENGINE_EDITS = [
    ("""      private function InitPushNotification() : void
      {
         if(DeviceManager.GetInstance().IsMobile == false || true == false)""", """      private function InitPushNotification() : void
      {
         if(true)"""),
]

# PvP connection while idle: one ping per minute instead of every ping_frequency. It only carries live duel messages,
# which happen in PvP mode (search popup to duel end: 2 s pings, unchanged); duel results arrive together with the
# duel's last message. notes 6.50.
PVP_COM = "com.frimastudio.snowstorm.project.engine.MobileEngineServerComPvp"
PVP_COM_EDITS = [
    ("""      public function ForceStartPingCycle() : void
      {
         mPingTimer.start();""", """      public function ForceStartPingCycle() : void
      {
         mPingTimer.delay = 60000;
         mPingTimer.start();"""),
    ("""         var frequency:uint = uint(ManagerA.Util.GetVar("engine","ping_frequency"));
         mPingTimer.delay = frequency < 1000 ? DEFAULT_PING_FREQUENCY : frequency;""", """         mPingTimer.delay = 60000;"""),
]

# Game settings (tutorials done, selected deck type, sound, ...) survive APK updates: the original reset them to
# defaults whenever the app's install date changed, so every update showed the live duel tutorial prompt again.
GAME_SETTINGS = "com.frimastudio.snowstorm.module.option.GameSettings"
GAME_SETTINGS_EDITS = [
    # the app folder's date is AIR-only (File): a browser build (Ruffle) throws here and stopped startup
    ("""         var appDate:String = File.applicationDirectory.creationDate.toString();""",
     """         var appDate:String = "web";
         try
         {
            appDate = File.applicationDirectory.creationDate.toString();
         }
         catch(dateError:Error)
         {
         }"""),
    ("""            this.mSharedObject.SaveValue(SHARED_OBJECT_DATE_NAME,appDate);
            options = null;""", """            this.mSharedObject.SaveValue(SHARED_OBJECT_DATE_NAME,appDate);"""),
]

# Friend live duel: the Tournament screen starts the search of a pending challenge (as3_new/com/revival/friends/
# LiveChallenge.as; the tournament popups need this module's assets).
TOURNAMENT_VIEW = "com.frimastudio.snowstorm.module.tournament.view.TournamentView"
TOURNAMENT_VIEW_EDITS = [
    ("""   import com.frimastudio.common.core.manager.ManagerA;
""", """   import com.frimastudio.common.core.manager.ManagerA;
   import com.revival.friends.LiveChallenge;
"""),
    ("""      public function InitComplete() : void
      {
         this.CheckTeamPointEarned();
      }""", """      public function InitComplete() : void
      {
         this.CheckTeamPointEarned();
         LiveChallenge.OnTournamentScreenReady();
      }"""),
]

PLAYER_INFO_BAR = "com.frimastudio.snowstorm.module.hud.bar.PlayerInfoBar"
PLAYER_INFO_BAR_EDITS = [
    ("""         this.mHudElementList.push(this.mEnergyWidget);
""", ""),
]

# No "Energy" tile in the shop menu (buying energy is pointless now).
SHOP_MENU = "com.frimastudio.snowstorm.module.shop.view.ShopMenuView"
SHOP_MENU_EDITS = [
    ("""         bottomMenuContainer.addChild(this.mEnergyBtn);
""", ""),
]

# Map jump: dragging moves the scrolling engine by hand while the camera viewport stays on the pointer; selecting a
# node switched back to the camera, so the map snapped back to the pointer (in chapters often the top). The camera
# now takes over the dragged position, then keeps following the pointer from there.
ABSTRACT_MAP = "com.frimastudio.snowstorm.module.map.map.AbstractMap"
ABSTRACT_MAP_EDITS = [
    ("""         Log.Report("AbstractMap::OnNodeSelectedEvent","Node " + aEvent.nameId + " selected",Log.INFO);
         this.mIsMovedByDragging = false;""",
     """         Log.Report("AbstractMap::OnNodeSelectedEvent","Node " + aEvent.nameId + " selected",Log.INFO);
         try
         {
            if(this.mIsMovedByDragging && this.mScrollingEngine != null && this.mScrollingEngine.ScrollingCamera != null)
            {
               this.mScrollingEngine.ScrollingCamera.ViewPort.x = -this.mScrollingEngine.x;
               this.mScrollingEngine.ScrollingCamera.ViewPort.y = -this.mScrollingEngine.y;
            }
         }
         catch(error:Error)
         {
         }
         this.mIsMovedByDragging = false;"""),
]

PATCHES = {
    ABSTRACT_MAP: ABSTRACT_MAP_EDITS,
    POPUP_UTIL: POPUP_UTIL_EDITS,
    LEADERBOARD_UI: LEADERBOARD_UI_EDITS,
    OPTION_POPUP: OPTION_POPUP_EDITS,
    BAM_PRO: BAM_PRO_EDITS,
    ENERGY_MANAGER: ENERGY_MANAGER_EDITS,
    PLAYER_INFO_BAR: PLAYER_INFO_BAR_EDITS,
    SHOP_MENU: SHOP_MENU_EDITS,
    DUEL_INFO_POPUP: DUEL_INFO_POPUP_EDITS,
    DUEL_STAR_POPUP: DUEL_STAR_POPUP_EDITS,
    TRY_AGAIN_POPUP: TRY_AGAIN_POPUP_EDITS,
    STORY_MAP: STORY_MAP_EDITS,
    SHOP_MANAGER: SHOP_MANAGER_EDITS,
    DUEL_GROUND: DUEL_GROUND_EDITS,
    TOURNAMENT_VIEW: TOURNAMENT_VIEW_EDITS,
    GAME_SETTINGS: GAME_SETTINGS_EDITS,
    PVP_COM: PVP_COM_EDITS,
    MAIN_MENU_MODULE: MAIN_MENU_MODULE_EDITS,
    SHOP_MODULE: SHOP_MODULE_EDITS,
    SHOP_CARD_VIEW: SHOP_CARD_VIEW_EDITS,
    BUY_CARD_POPUP: BUY_CARD_POPUP_EDITS,
    BOOSTER_VIEW: BOOSTER_VIEW_EDITS,
    EXTERNAL_FILES: EXTERNAL_FILES_EDITS,
    VERSION_CONTROLLER: VERSION_CONTROLLER_EDITS,
    GAME_SETTINGS_ENUM: GAME_SETTINGS_ENUM_EDITS,
    FUSION_TUTO_POPUP: FUSION_TUTO_POPUP_EDITS,
    FUSION_TUTO: FUSION_TUTO_EDITS,
    BUY_CARD_DISPLAY: BUY_CARD_DISPLAY_EDITS,
    MAIN_MENU_VIEW: [_no_icon("mLoginButton", "facebookIcon")] + MAIN_MENU_VIEW_EDITS,
    LOGIN_VIEW: [_no_icon("mLoginBtn", "facebookIcon"), _no_icon("mBtnLoginMini", "facebookIcon")],
    ADVANTAGE_POPUP: [_no_icon("mLoginBtn", "fbIcon")],
    FB_MANAGER: FB_MANAGER_EDITS,
    DEFAULT_DATA: DEFAULT_DATA_EDITS,
    WORLDMAP_CACHE: WORLDMAP_CACHE_EDITS,
    WORLDMAP_DAL: WORLDMAP_DAL_EDITS,
    WORLD_NODE_ENUM: WORLD_NODE_ENUM_EDITS,
    WORLD_MAP_VIEW: WORLD_MAP_VIEW_EDITS,
    BIG_INFO_DATA: BIG_INFO_DATA_EDITS,
    BIG_INFO: BIG_INFO_EDITS,
    MAP_ACTION_BAR: MAP_ACTION_BAR_EDITS,
    LOADER: LOADER_EDITS,
    EXTERNAL_ASSET: EXTERNAL_ASSET_EDITS,
    ENGINE: ENGINE_EDITS + MOBILE_ENGINE_EDITS,
    BOOSTER_INFO: BOOSTER_INFO_EDITS,
    INVENTORY: INVENTORY_EDITS,
    CHOOSE_DECK_UI: CHOOSE_DECK_UI_EDITS,
    CHOOSE_DECK: CHOOSE_DECK_EDITS,
    SERVERCOM: SERVERCOM_EDITS,
    NEW_APP_UPDATE: NEW_APP_UPDATE_EDITS,
    VERSION_UNAVAILABLE: VERSION_UNAVAILABLE_EDITS,
}

# Dev only (YGO_PERF=1, never in release builds): every startup step reports its time since launch (getTimer, ms)
# to the dev server as GET /perf?s=<step>&t=<ms>, so the server log shows how long each step takes; uncaught script
# errors (hidden in release builds) arrive the same way as "error <message> <stack>".
PERF_EDITS = [
    ("""   import com.frimastudio.as3ToolKit.display.Log;
""", """   import com.frimastudio.as3ToolKit.display.Log;
   import com.revival.dev.Perf;
"""),
    ("""            Log.Report("MobileProjectEngine/ProcessNextStep",message,Log.INFO);
            this.UpdateProgressBar();
            step.Execute();""", """            Log.Report("MobileProjectEngine/ProcessNextStep",message,Log.INFO);
            Perf.Mark(currentStep + " " + step);
            this.UpdateProgressBar();
            step.Execute();"""),
    ("""            message = "Initialization complete";""", """            message = "Initialization complete";
            Perf.Mark("init complete");"""),
    ("""            Perf.Mark(currentStep + " " + step);
""", """            Perf.Mark(currentStep + " " + step);
            if(currentStep == 1) { Perf.CatchErrors(); }
"""),
]
MODULE_MANAGER = "com.frimastudio.mobile.module.StarlingModuleManagerImpl"
PERF_MODULE_EDITS = [
    ("""   import com.frimastudio.as3ToolKit.display.Log;
""", """   import com.frimastudio.as3ToolKit.display.Log;
   import com.revival.dev.Perf;
"""),
    ("""         Log.Report("StarlingModuleManagerImpl/ChangeModule","Changing main module to :: " + aModuleDefinition.Name,Log.INFO);
""", """         Log.Report("StarlingModuleManagerImpl/ChangeModule","Changing main module to :: " + aModuleDefinition.Name,Log.INFO);
         Perf.Mark("open " + aModuleDefinition.Name);
"""),
    ("""         this.mCurrentMainModule.removeEventListener(StarlingModuleEvent.MODULE_READY,this.OnModuleReady);
""", """         this.mCurrentMainModule.removeEventListener(StarlingModuleEvent.MODULE_READY,this.OnModuleReady);
         Perf.Mark("ready " + this.mMainModuleDefinition.Name);
"""),
]
if __import__("os").environ.get("YGO_PERF") == "1":
    PATCHES[ENGINE] = PATCHES[ENGINE] + PERF_EDITS
    PATCHES[MODULE_MANAGER] = PERF_MODULE_EDITS


# --- Browser build only (YGO_WEB=1, tools/build_web.py; never in the APK, notes/browser_version.md) ------------
# Ruffle has no AIR file storage (flash.filesystem.File is a stub), so: no content package check or download (the
# content is served extracted under storage/, com.revival.web.Web.STORAGE), every app-storage path becomes that
# URL, and the local save is kept in a SharedObject. Edits are appended to the class's APK edits.
def _web_import(cls):
    pkg = cls.rsplit(".", 1)[0]
    return (f"package {pkg}\n{{\n", f"package {pkg}\n{{\n   import com.revival.web.Web;\n   import com.revival.web.WebLogin;\n")


def _storage_url(cls, *anchors):
    """Edits replacing File.applicationStorageDirectory.url in each anchor (a unique line part) with Web.STORAGE."""
    return [_web_import(cls)] + [(a, a.replace("File.applicationStorageDirectory.url", "Web.STORAGE"))
                                 for a in anchors]


WEB_EDITS = {
    # the game adds the hard-coded port 80 after the host (EngineServerCom): wrong for a dev origin with a port
    # ("host:8090:80") and for https (Ruffle upgrades http:// to https:// on an https page, upgradeToHttps, but keeps
    # the port). The web build's URLs are complete: use them as they are.
    SERVERCOM: [
        ("""         this.mServerUrl = param1.replace(_loc4_,_loc4_ + ":" + param2);""",
         """         this.mServerUrl = param1;"""),
    ],
    # game data version (sent as &d= on every request, version gate): the APK reads config/gamedata_version from
    # its files, which Ruffle can't; build_web.py passes the version it bundles. No downloaded game data on the web.
    LOADER: [
        ("""         return ReadGameDataVersion(File.applicationDirectory.resolvePath("config/gamedata_version"));""",
         f"""         return "{__import__("os").environ.get("YGO_WEB_GAMEDATA", "")}";"""),
        ("""         return ReadGameDataVersion(File.applicationStorageDirectory.resolvePath("asset/gamedata/gamedata_version"));""",
         """         return "";"""),
    ],
    # login: the login page in a frame on the web page instead of the Android web view (com.revival.web.WebLogin)
    FB_MANAGER: [
        _web_import(FB_MANAGER),
        ("""      private function OpenLoginWebView(aUrl:String) : void
      {
""", """      private function OpenLoginWebView(aUrl:String) : void
      {
         if(WebLogin.Open(aUrl,this.OnWebLoginDone))
         {
            return;
         }
"""),
        ("""      private function CloseLoginWebView() : void
""", """      private function OnWebLoginDone(aLocation:String) : void
      {
         this.mListenForLoginInvoke = false;
         this.ProcessLogin(aLocation);
      }

      private function CloseLoginWebView() : void
"""),
    ],
    # extra booster packs: config/boosterpacks.json is read from files at class start-up; the page fetches it and
    # passes it as the "boosterpacks" parameter
    BOOSTER_INFO: [
        _web_import(BOOSTER_INFO),
        ("""            file = File.applicationStorageDirectory.resolvePath("asset/gamedata/config/boosterpacks.json");
            if(!Loader.GameDataActive || !file.exists)
            {
               file = File.applicationDirectory.resolvePath("config/boosterpacks.json");
            }
            if(!file.exists)
            {
               return false;
            }
            stream = new FileStream();
            stream.open(file,FileMode.READ);
            list = JSON.parse(stream.readUTFBytes(stream.bytesAvailable)) as Array;
            stream.close();""", """            list = JSON.parse(Web.Param("boosterpacks") || "[]") as Array;"""),
    ],
    # editable text (deck name box in the deck chooser, ComboBox): StageText is AIR-only; Ruffle could not even load
    # the class (VerifyError StageTextInitOptions), so Edit Deck never finished loading. Same API on a TextField.
    "com.frimastudio.mobile.display.NativeText": [
        ("""   import flash.text.StageText;
   import flash.text.StageTextInitOptions;
""", """   import com.revival.web.WebStageText;
"""),
        ("""      private var st:StageText;""", """      private var st:WebStageText;"""),
        ("""         var stio:StageTextInitOptions = new StageTextInitOptions(this.numberOfLines > 1);
         this.st = new StageText(stio);""", """         this.st = new WebStageText(this.numberOfLines > 1);"""),
    ],
    # Stage.assignFocus / FocusDirection are AIR-only (not in Ruffle)
    "com.frimastudio.mobile.display.combobox.ComboBox": [
        ("""         this.mStageRef.assignFocus(null,FocusDirection.NONE);""", """         this.mStageRef.focus = null;"""),
        # Ruffle can't construct SoftKeyboardEvent (#1056 _triggerType): WebStageText sends plain Events of those types
        ("""      private function OnInputStart(aEvent:SoftKeyboardEvent) : void""",
         """      private function OnInputStart(aEvent:flash.events.Event) : void"""),
        ("""      private function OnInputFinished(aEvent:SoftKeyboardEvent) : void""",
         """      private function OnInputFinished(aEvent:flash.events.Event) : void"""),
    ],
    # drawing only when something can have changed (com.revival.web.WebRender, findings 6.60)
    "starling.animation.Juggler": [
        ("""      public function add(object:IAnimatable) : void""", """      public function get revivalBusy() : Boolean
      {
         for each(var o:IAnimatable in this.mObjects)
         {
            if(o != null)
            {
               return true;
            }
         }
         return false;
      }

      public function add(object:IAnimatable) : void"""),
    ],
    "starling.core.Starling": [
        ("""   import flash.display.Sprite;
""", """   import flash.display.Sprite;
   import com.revival.web.WebRender;
"""),
        ("""         this.advanceTime(passedTime);
         this.render();""", """         this.advanceTime(passedTime);
         if(WebRender.ShouldRender(this.mJuggler.revivalBusy))
         {
            this.render();
         }"""),
        ("""      private function onTouch(event:flash.events.Event) : void
      {""", """      private function onTouch(event:flash.events.Event) : void
      {
         WebRender.Input();"""),
        ("""      private function onKey(event:flash.events.KeyboardEvent) : void
      {""", """      private function onKey(event:flash.events.KeyboardEvent) : void
      {
         WebRender.Input();"""),
    ],
    # content host: the page's own origin (the game server's "cdn" may name another host or port)
    "com.frimastudio.snowstorm.project.player.PlayerManagerGT": [
        _web_import("com.frimastudio.snowstorm.project.player.PlayerManagerGT"),
        ("""         this.mPackageUrlServer = aResponse.cdn;""",
         """         this.mPackageUrlServer = Web.Host(aResponse.cdn);"""),
    ],
    # no Android billing extension in the browser: a store that behaves like the APK's free billing stub
    "com.frimastudio.mobile.apppurchase.AppPurchaseHandlerImpl": [
        ("""package com.frimastudio.mobile.apppurchase
{
""", """package com.frimastudio.mobile.apppurchase
{
   import com.revival.web.WebStoreHandler;
"""),
        ("""            this.mStoreHandler = new GooglePlayHandler();""",
         """            this.mStoreHandler = new WebStoreHandler();"""),
    ],
    "com.frimastudio.snowstorm.project.externalfile.ExternalFileControllerImpl": [
        ("""   import com.frimastudio.as3ToolKit.display.Log;
""", """   import com.frimastudio.as3ToolKit.display.Log;
   import flash.utils.setTimeout;
"""),
        # nothing to check or download: report the files as ready (next frame, after the caller's listeners)
        ("""      public function Init() : void
      {
""", """      public function Init() : void
      {
         setTimeout(dispatchEvent,1,new ExternalFileEvent(ExternalFileEvent.ON_FILE_READY));
         return;
"""),
    ],
    ENGINE: _storage_url(ENGINE, "var directory:String = File.applicationStorageDirectory.url;") + [
        # /bam/?stats=1: Starling's stats box (fps, memory, draw calls) for measuring the browser version
        ("""         this.mPrelauncher = null;
         NativeApplication.nativeApplication.systemIdleMode = SystemIdleMode.NORMAL;
""", """         this.mPrelauncher = null;
         NativeApplication.nativeApplication.systemIdleMode = SystemIdleMode.NORMAL;
         if(Web.Param("stats") == "1")
         {
            Starling.current.showStats = true;
         }
"""),
    ],
    "com.frimastudio.mobile.asset.AssetManagerWrapperImpl": [
        _web_import("com.frimastudio.mobile.asset.AssetManagerWrapperImpl"),
        ("""var prefix:String = File.applicationStorageDirectory.nativePath + "/";""",
         """var prefix:String = Web.STORAGE;"""),
        # downloaded assets are queued as File objects: URLs instead
        ("""\n                     file = new File(path);
                     pathList.push(file);""", """\n                     pathList.push(path);"""),
        ("""\n                        file = new File(path);
                        pathList.push(file);""", """\n                        pathList.push(path);"""),
    ],
    "com.frimastudio.mobile.asset.ExternalAssetManager": _storage_url(
        "com.frimastudio.mobile.asset.ExternalAssetManager",
        "aList[i] = File.applicationStorageDirectory.url + aList[i].toLowerCase();"),
    "com.frimastudio.scrollingengine2d.main.ScrollingEngine2D": _storage_url(
        "com.frimastudio.scrollingengine2d.main.ScrollingEngine2D",
        'resPath = File.applicationStorageDirectory.url + "asset/misc/maplibrary/maplibrary_all";',
        'bgPath = File.applicationStorageDirectory.url + "asset/misc/mapbackground/mapbackground_"'),
    "com.frimastudio.snowstorm.module.cardgame.hud.BackgroundChooser": _storage_url(
        "com.frimastudio.snowstorm.module.cardgame.hud.BackgroundChooser",
        'return File.applicationStorageDirectory.url + "asset/misc/cardgamebg/"'),
    "com.frimastudio.snowstorm.module.cardgame.player.OpponentPlayer": _storage_url(
        "com.frimastudio.snowstorm.module.cardgame.player.OpponentPlayer",
        "AI_CHARACTER_PATH:String = File.applicationStorageDirectory.url"),
    "com.frimastudio.snowstorm.module.map.enum.EMapModuleLibrary": _storage_url(
        "com.frimastudio.snowstorm.module.map.enum.EMapModuleLibrary",
        "PATH_ASSET_MAP_LIBRARY:String = File.applicationStorageDirectory.url",
        "WORLD_MAP_ASSET:String = File.applicationStorageDirectory.url"),
    "com.frimastudio.snowstorm.module.map.map.StoryMap": _storage_url(
        "com.frimastudio.snowstorm.module.map.map.StoryMap",
        'LoadWorldXML(File.applicationStorageDirectory.url + "asset/world/Map"'),
    "com.frimastudio.utils.backgroundUtil.BackgroundLoadingUtilImpl": [
        _web_import("com.frimastudio.utils.backgroundUtil.BackgroundLoadingUtilImpl"),
        ("""            file = File.applicationStorageDirectory.resolvePath(path);
            this.mAssetManager.enqueue(file);""", """            this.mAssetManager.enqueue(Web.STORAGE + path);"""),
    ],
    # card pictures: URLs instead of File objects (Starling's AssetManager takes both)
    "com.frimastudio.utils.cardloading.CardLoadingUtil": [
        _web_import("com.frimastudio.utils.cardloading.CardLoadingUtil"),
        ("""\n            file = File.applicationStorageDirectory.resolvePath(path);
            fileList.push(file);""", """\n            fileList.push(path);"""),
        ("""\n               file = File.applicationStorageDirectory.resolvePath(path);
               fileList.push(file);""", """\n               fileList.push(path);"""),
        ("""return File.applicationStorageDirectory.resolvePath(path).nativePath;""",
         """return Web.STORAGE + path;"""),
    ],
    # local save: SharedObject instead of Data/JSONSave_A|B.sav; the pre-JSON PlayerInfo.sav never exists here
    "com.frimastudio.snowstorm.project.engine.data.YGOMDataImpl": [
        _web_import("com.frimastudio.snowstorm.project.engine.data.YGOMDataImpl"),
        ("""         var file:File = File.applicationStorageDirectory;
         file = file.resolvePath(path);
         if(file != null && Boolean(file.exists))
         {
            ba = new ByteArray();
            fileStream = new FileStream();
            fileStream.open(file,FileMode.READ);
            fileStream.readBytes(ba);
            fileStream.close();
            ba.uncompress();""", """         ba = Web.ReadSave("JSONSave_" + aSaveId);
         if(ba != null)
         {
            ba.uncompress();"""),
        ("""      private function LoadFromLocalData() : void
      {
""", """      private function LoadFromLocalData() : void
      {
         if(true)
         {
            return;
         }
"""),
        ("""         file.preventBackup = true;
         this.mGameSaveStream.open(file,FileMode.WRITE);
         this.mGameSaveStream.writeBytes(ba);
         this.mGameSaveStream.close();
         file = File.applicationStorageDirectory;
         file = file.resolvePath("./Data/PlayerInfo.sav");
         if(file != null && Boolean(file.exists))
         {
            file.deleteFile();
         }""", """         Web.WriteSave(mLatestDeviceJSONData == mDeviceJSONData_B ? "JSONSave_B" : "JSONSave_A",ba);"""),
        ("""      public function ClearLocalData() : void
      {
""", """      public function ClearLocalData() : void
      {
         Web.DeleteSave("JSONSave_A");
         Web.DeleteSave("JSONSave_B");
         mDeviceJSONData_A = null;
         mDeviceJSONData_B = null;
"""),
    ],
}
if __import__("os").environ.get("YGO_WEB") == "1":
    for _cls, _edits in WEB_EDITS.items():
        PATCHES[_cls] = PATCHES.get(_cls, []) + _edits

# --- Synchro and Xyz (notes/synchro_xyz.md, rules and policy in as3_new/com/revival/summon/Summon.as) ------------
# They reuse the fusion pairing (drop a card on your monster in the same channel) and GameMatBO.CreateFusionCard, so
# the materials stay under the result. Changed: who can pair and what the pair becomes (FusionUtil, CardBO,
# RoundHandler), the local player's pick (LocalPlayerHand -> SummonPickerPopup), the pick in live-duel moves
# (PlayerHandBO sends it as a negative last entry, AwayPlayer reads it), per-duel AI settings (DuelData, XMLNode
# map node properties aixyz / aiextra), white/black frames (CardVisual, DuelCard, DetailedCardVisual,
# FullCardVisual), and no results in the deck builder (EditDeckScreen).
SUMMON_IMPORT = "   import com.revival.summon.Summon;\n"
SUMMON_EDITS = {
    "com.frimastudio.snowstorm.module.cardgame.util.FusionUtil": [
        ("""   import com.frimastudio.snowstorm.module.cardgame.card.CardBO;
""", """   import com.frimastudio.snowstorm.module.cardgame.card.CardBO;
""" + SUMMON_IMPORT),
        ("""            return FindBaseMonster(aCard1,aCard2) != null && aCard1.CardToFuseWith == null && aCard2.CardToFuseWith == null;""",
         """            return Summon.IsPossible(aCard1,aCard2);"""),
        ("""            return true;
         }
         return false;
      }""", """            return true;
         }
         return Summon.AiCanPair(aCardTemplate1,aCardTemplate2);
      }"""),
    ],
    "com.frimastudio.snowstorm.module.cardgame.card.CardBO": [
        ("""   import com.frimastudio.snowstorm.module.cardgame.duelstar.IDuelStarHandler;
""", """   import com.frimastudio.snowstorm.module.cardgame.duelstar.IDuelStarHandler;
""" + SUMMON_IMPORT),
        ("""            aCard.Skin.FaceUpSkin.DisplayFusedAnim(baseCard.FusionInfo.resultCardTemplateId);""",
         """            aCard.Skin.FaceUpSkin.DisplayFusedAnim(Summon.Result(this,aCard));"""),
        ("""            this.mIngredientCardList = savedState.IngredientCardList;
""", """            this.mIngredientCardList = savedState.IngredientCardList;
            Summon.ShowMaterials(this);
"""),
    ],
    "com.frimastudio.snowstorm.module.cardgame.round.RoundHandler": [
        ("""   import com.frimastudio.mobile.util.event.StarlingListener;
""", """   import com.frimastudio.mobile.util.event.StarlingListener;
""" + SUMMON_IMPORT),
        ("""                  fusionInfo = this.GetFusionData(card);
                  if(fusionInfo != null)
                  {
                     fusedCard = aPlayer.GameMat.CreateFusionCard(fusionInfo.resultCardTemplateId,card,cardToFuseWith);""",
         """                  var summonId:int = Summon.Result(card,cardToFuseWith);
                  if(summonId != 0)
                  {
                     fusedCard = aPlayer.GameMat.CreateFusionCard(summonId,card,cardToFuseWith);"""),
    ],
    "com.frimastudio.snowstorm.module.cardgame.player.hand.LocalPlayerHand": [
        ("""   import com.frimastudio.common.core.client.UpdateManager;
""", """   import com.frimastudio.common.core.client.UpdateManager;
""" + SUMMON_IMPORT),
        ("""               if(FusionUtil.IsFusionPossible(cardOnMat,aCurrentDraggedCard))
               {
                  cardOnMat.CardToFuseWith = aCurrentDraggedCard;
                  fused = true;""", """               if(FusionUtil.IsFusionPossible(cardOnMat,aCurrentDraggedCard))
               {
                  cardOnMat.CardToFuseWith = aCurrentDraggedCard;
                  Summon.OnLocalPair(cardOnMat,aCurrentDraggedCard);
                  fused = true;"""),
        ("""            else if(FusionUtil.IsFusionPossible(cardOnMat,aCurrentDraggedCard))
            {
               cardOnMat.CardToFuseWith = aCurrentDraggedCard;
               fused = true;""", """            else if(FusionUtil.IsFusionPossible(cardOnMat,aCurrentDraggedCard))
            {
               cardOnMat.CardToFuseWith = aCurrentDraggedCard;
               Summon.OnLocalPair(cardOnMat,aCurrentDraggedCard);
               fused = true;"""),
    ],
    # Live-duel move: [slot, card, (second card), (-result)]. The result is always sent, not only a pick: this phone
    # lists only owned results, the other phone every result the rules allow, so with one owned result of two they
    # would summon different cards. Also fixes the original sending the card already on the field instead of the
    # card dropped on it (the other phone then played the wrong card).
    "com.frimastudio.snowstorm.module.cardgame.player.hand.PlayerHandBO": [
        ("""   import com.frimastudio.as3ToolKit.display.IUpdatable;
""", """   import com.frimastudio.as3ToolKit.display.IUpdatable;
""" + SUMMON_IMPORT),
        ("""                  this.AddCardToPlacedLivePvP(slot,card.CardToFuseWith);
""", """                  this.AddCardToPlacedLivePvP(slot,card.CardToFuseWith);
                  this.AddSummonChoice(card);
"""),
        ("""               this.AddCardToPlacedLivePvP(card.CurrentCardSlot,card);
""", """               this.AddCardToPlacedLivePvP(card.CurrentCardSlot,card.CardToFuseWith);
               this.AddSummonChoice(card);
"""),
        ("""      private function AddCardToPlacedLivePvP(aCardSlot:CardSlot, aCard:CardBO) : void
""", """      private function AddSummonChoice(aCard:CardBO) : void
      {
         var choice:int = Summon.Result(aCard,aCard.CardToFuseWith);
         if(choice != 0 && this.mCardsPlacedArray.length > 0)
         {
            (this.mCardsPlacedArray[this.mCardsPlacedArray.length - 1] as Array).push(-choice);
         }
      }

      private function AddCardToPlacedLivePvP(aCardSlot:CardSlot, aCard:CardBO) : void
"""),
    ],
    "com.frimastudio.snowstorm.module.cardgame.player.AwayPlayer": [
        ("""   import com.frimastudio.as3ToolKit.display.Log;
""", """   import com.frimastudio.as3ToolKit.display.Log;
""" + SUMMON_IMPORT),
        ("""            placementData = cardPlacementData[i];
""", """            placementData = (cardPlacementData[i] as Array).concat();
            var summonChoice:int = 0;
            if(placementData.length > 2 && int(placementData[placementData.length - 1]) < 0)
            {
               summonChoice = -int(placementData.pop());
            }
"""),
        ("""            cardsBeingPlayed.push(cardToPlay);
            if(placementData.length > 2)
            {
               fusionCard = this.GetNextAvailableCardByTemplateId(placementData[2]);
               cardToPlay.CardToFuseWith = fusionCard;""", """            cardsBeingPlayed.push(cardToPlay);
            Summon.SetChoice(cardToPlay,null,summonChoice);
            if(placementData.length > 2)
            {
               fusionCard = this.GetNextAvailableCardByTemplateId(placementData[2]);
               Summon.SetChoice(cardToPlay,fusionCard,summonChoice);
               cardToPlay.CardToFuseWith = fusionCard;"""),
    ],
    "com.frimastudio.snowstorm.module.map.node.DuelData": [
        ("""      private var mOpponentExternalId:String;
""", """      private var mOpponentExternalId:String;

      public var AiXyz:Boolean = false;

      public var AiExtra:Array = null;
"""),
        ("""         this.mOpponentExternalId = "";
""", """         this.mOpponentExternalId = "";
         this.AiXyz = false;
         this.AiExtra = null;
"""),
        ("""         clone.OpponentExternalId = this.mOpponentExternalId;
""", """         clone.OpponentExternalId = this.mOpponentExternalId;
         clone.AiXyz = this.AiXyz;
         clone.AiExtra = this.AiExtra != null ? this.AiExtra.concat() : null;
"""),
    ],
    "com.frimastudio.snowstorm.module.map.node.XMLNode": [
        ("""         duel.NodeName = mName.concat();
""", """         duel.NodeName = mName.concat();
         duel.AiXyz = GetProperty("aixyz") == "1";
         if(GetProperty("aiextra"))
         {
            duel.AiExtra = [];
            for each(var extraId:String in GetProperty("aiextra").split(","))
            {
               duel.AiExtra.push(int(extraId));
            }
         }
"""),
    ],
    "com.frimastudio.utils.rendering.card.CardVisual": [
        ("""   import com.frimastudio.common.core.manager.ManagerA;
""", """   import com.frimastudio.common.core.manager.ManagerA;
""" + SUMMON_IMPORT),
        ("""      public function get IsFusionCard() : Boolean
""", """      public function get SummonKind() : int
      {
         return this.mCardTemplate != null ? Summon.Kind(this.mCardTemplate.id) : 0;
      }

      public function get IsFusionCard() : Boolean
"""),
    ],
    "com.frimastudio.utils.rendering.card.DuelCard": [
        ("""   import com.frimastudio.mobile.asset.AssetCreationUtil;
""", """   import com.frimastudio.mobile.asset.AssetCreationUtil;
""" + SUMMON_IMPORT),
        ("""         this.mMonsterMaskQuad.color = IsFusionCard ? 4865697 : 11216906;""",
         """         this.mMonsterMaskQuad.color = IsFusionCard ? (SummonKind == Summon.SYNCHRO ? 10526880 : (SummonKind == Summon.XYZ ? 2631720 : 4865697)) : 11216906;"""),
        ("""               return FUSION_CARD_BACKGROUND;""", """               return Summon.FrameName(FUSION_CARD_BACKGROUND,SummonKind);"""),
        # Xyz material count, top left of the card in the duel (Summon.ShowMaterials)
        ("""      private var mAttackTxt:TextField;
""", """      private var mAttackTxt:TextField;

      private var mMaterialBack:Quad;

      private var mMaterialTxt:TextField;

      public function RevivalMaterials(aCount:int) : void
      {
         if(this.mMaterialTxt == null)
         {
            this.mMaterialBack = new Quad(46,26,0);
            this.mMaterialBack.alpha = 0.7;
            this.mMaterialBack.x = 17;
            this.mMaterialBack.y = 17;
            this.mMaterialBack.touchable = false;
            this.mMaterialTxt = new TextField(46,26,"",EFonts.HANZEL_BOLD,20,16777215);
            this.mMaterialTxt.x = 17;
            this.mMaterialTxt.y = 17;
            this.mMaterialTxt.touchable = false;
         }
         this.mMaterialTxt.text = "x" + aCount;
         addChild(this.mMaterialBack);
         addChild(this.mMaterialTxt);
      }
"""),
        ("""         if(IsMonsterCard)
         {
            this.mAttackTxt.text = AssociatedCardData.Attack.toString();
         }
""", """         if(IsMonsterCard)
         {
            this.mAttackTxt.text = AssociatedCardData.Attack.toString();
         }
         if(this.mMaterialTxt != null)
         {
            addChild(this.mMaterialBack);
            addChild(this.mMaterialTxt);
         }
"""),
        ("""      override public function dispose() : void
      {
         if(this.mFusionIcon != null)""", """      override public function dispose() : void
      {
         if(this.mMaterialTxt != null)
         {
            this.mMaterialBack.removeFromParent(true);
            this.mMaterialTxt.removeFromParent(true);
            this.mMaterialBack = null;
            this.mMaterialTxt = null;
         }
         if(this.mFusionIcon != null)"""),
    ],
    "com.frimastudio.snowstorm.module.cardgame.player.gamemat.GameMatBO": [
        ("""   import com.frimastudio.as3ToolKit.display.Log;
""", """   import com.frimastudio.as3ToolKit.display.Log;
""" + SUMMON_IMPORT),
        ("""         this.AddCardToIngredientList(cardBO,aCard2);
""", """         this.AddCardToIngredientList(cardBO,aCard2);
         Summon.ShowMaterials(cardBO);
"""),
        # test duels only (summons.json "test", test content): fixed first draws, big AI life points
        ("""         this.mDeck = suffledDeck;
""", """         this.mDeck = Summon.TestDraw(suffledDeck,this.mOwner);
"""),
        ("""               totalHP += this.mDeck[i].DefenseValue;
            }
         }
         return totalHP;""", """               totalHP += this.mDeck[i].DefenseValue;
            }
         }
         return Summon.TestHp(this.mOwner,totalHP);"""),
    ],
    "com.frimastudio.utils.rendering.card.DetailedCardVisual": [
        ("""   import com.frimastudio.as3ToolKit.display.Log;
""", """   import com.frimastudio.as3ToolKit.display.Log;
""" + SUMMON_IMPORT),
        ("""      protected var mBackgroundFusion:Image;
""", """      protected var mBackgroundFusion:Image;

      private var mBackgroundSummon:Image;

      private var mBackgroundSummonName:String;
"""),
        ("""            ImagePool.ReuseImage(this.mBackgroundFusion);
            this.mBackgroundFusion = null;
         }
""", """            ImagePool.ReuseImage(this.mBackgroundFusion);
            this.mBackgroundFusion = null;
         }
         if(this.mBackgroundSummon != null)
         {
            this.mBackgroundSummon.removeFromParent();
            ImagePool.ReuseImage(this.mBackgroundSummon);
            this.mBackgroundSummon = null;
         }
"""),
        ("""         this.mCardTypeTxtField.text = cardTypeText;
""", """         this.mCardTypeTxtField.text = cardTypeText + Summon.TypeSuffix(mCardTemplate != null ? mCardTemplate.id : 0);
"""),
        ("""               mBackground = this.mBackgroundFusion;""",
         """               mBackground = SummonKind != 0 ? this.SummonBackground() : this.mBackgroundFusion;"""),
        ("""      override protected function DisplayBackground() : void
""", """      private function SummonBackground() : Image
      {
         var name:String = Summon.FrameName(this.mDisplayData.FusionBackgroundTextureName,SummonKind);
         if(this.mBackgroundSummon == null || this.mBackgroundSummonName != name)
         {
            if(this.mBackgroundSummon != null)
            {
               this.mBackgroundSummon.removeFromParent();
               ImagePool.ReuseImage(this.mBackgroundSummon);
            }
            this.mBackgroundSummon = AssetManagerWrapper.GetImage(name);
            this.mBackgroundSummonName = name;
         }
         if(this.mBackgroundFusion != null)  // views scale their frames (HalfFullCardVisual: sell menu)
         {
            this.mBackgroundSummon.scaleX = this.mBackgroundFusion.scaleX;
            this.mBackgroundSummon.scaleY = this.mBackgroundFusion.scaleY;
            this.mBackgroundSummon.x = this.mBackgroundFusion.x;
            this.mBackgroundSummon.y = this.mBackgroundFusion.y;
         }
         return this.mBackgroundSummon;
      }

      override protected function DisplayBackground() : void
"""),
    ],
    # Synchro: white frame, black name/type text; bar under the art: frames 2 (Synchro) / 3 (Xyz) of
    # common_card_template_bar_bottom (second common atlas page)
    "com.frimastudio.utils.rendering.card.FullCardVisual": [
        ("""   import com.frimastudio.mobile.asset.AssetManagerWrapper;
""", """   import com.frimastudio.mobile.asset.AssetManagerWrapper;
""" + SUMMON_IMPORT),
        ("""         mCardNameTxtField.color = IsFusionCard ? Color.WHITE : Color.BLACK;
         mCardTypeTxtField.color = IsFusionCard ? Color.WHITE : Color.BLACK;""",
         """         mCardNameTxtField.color = IsFusionCard && SummonKind != Summon.SYNCHRO ? Color.WHITE : Color.BLACK;
         mCardTypeTxtField.color = IsFusionCard && SummonKind != Summon.SYNCHRO ? Color.WHITE : Color.BLACK;"""),
        ("""            this.mBarBottom.currentFrame = IsFusionCard ? 1 : 0;""",
         """            this.mBarBottom.currentFrame = Math.min(IsFusionCard ? (SummonKind == Summon.SYNCHRO ? 2 : (SummonKind == Summon.XYZ ? 3 : 1)) : 0,this.mBarBottom.numFrames - 1);"""),
    ],
    # Material effects (Summon.CanResolveEffect / OnEffectResolved / ScaleByMaterials): the effect row's id is kept on
    # the effect so its rule can be looked up in summons.json "effects".
    "com.frimastudio.snowstorm.module.cardgame.effect.effectlist.EffectBO": [
        ("""      protected var mIsOncePerGameDispatched:Boolean;
""", """      protected var mIsOncePerGameDispatched:Boolean;

      public var RevivalEffectId:int = 0;
"""),
        ("""         this.mIsOncePerGame = (aData[0] as Effect).oncePerGame;
""", """         this.mIsOncePerGame = (aData[0] as Effect).oncePerGame;
         this.RevivalEffectId = (aData[0] as Effect).id;
"""),
    ],
    "com.frimastudio.snowstorm.module.cardgame.effect.EffectHandler": [
        ("""   import com.frimastudio.as3ToolKit.math.RandomSeed;
""", """   import com.frimastudio.as3ToolKit.math.RandomSeed;
""" + SUMMON_IMPORT),
        ("""         if(aEffect.IsOncePerGame && aEffect.IsOncePerGameDispatched)
         {
            aEffect.OnEffectFailedResolved();
            return;
         }
""", """         if(aEffect.IsOncePerGame && aEffect.IsOncePerGameDispatched)
         {
            aEffect.OnEffectFailedResolved();
            return;
         }
         if(!Summon.CanResolveEffect(aEffect))
         {
            aEffect.OnEffectFailedResolved();
            aEffect.DispatcherList.length = 0;
            return;
         }
"""),
        ("""         if(isResolved)
         {
            aEffect.OnEffectResolved();
""", """         if(isResolved)
         {
            Summon.OnEffectResolved(aEffect);
            aEffect.OnEffectResolved();
"""),
        ("""                  initialValue = currentTargetCard.AttackPower;
""", """                  attackModifier = Summon.ScaleByMaterials(aCardStatModifier,attackModifier);
                  initialValue = currentTargetCard.AttackPower;
"""),
        ("""         targetPlayer.HP = OperatorUtil.ApplyOperator(aHealthEffect.HealthOperator,targetPlayer.HP,healthModifier);
""", """         healthModifier = Summon.ScaleByMaterials(aHealthEffect,healthModifier);
         targetPlayer.HP = OperatorUtil.ApplyOperator(aHealthEffect.HealthOperator,targetPlayer.HP,healthModifier);
"""),
    ],
    # A duel preloads its cards' pictures plus their fusion results'; a result card is created mid-round and needs its
    # picture already loaded (without it the round never finished, seen in the emulator). Add the Synchro/Xyz results.
    "com.frimastudio.utils.cardloading.CardLoadingUtil": [
        ("""   import com.frimastudio.as3ToolKit.display.Log;
""", """   import com.frimastudio.as3ToolKit.display.Log;
""" + SUMMON_IMPORT),
        ("""               path = GetCardCompletePathFromCardTemplateId(cardTemplate.fusionData.resultCardTemplateId);
               file = File.applicationStorageDirectory.resolvePath(path);
               fileList.push(file);
            }
""", """               path = GetCardCompletePathFromCardTemplateId(cardTemplate.fusionData.resultCardTemplateId);
               file = File.applicationStorageDirectory.resolvePath(path);
               fileList.push(file);
            }
            for each(var summonId:int in Summon.PreloadIds(cardTemplateId))
            {
               fileList.push(File.applicationStorageDirectory.resolvePath(GetCardCompletePathFromCardTemplateId(summonId)));
            }
"""),
    ],
    # AI planning: two hand cards in one slot only when they can pair. The original looked the cards up as inventory
    # items by their duel id (CardBO.CardId, a per-duel counter), which never finds them: the AI could only fuse onto
    # monsters already on the field. Look them up in the AI's hand instead (also used for Synchro/Xyz, with the AI
    # rules of Summon.AiAllows).
    "com.frimastudio.snowstorm.module.cardgame.ai.CardGameAI": [
        ("""         var card1:Card = this.mInventoryManager.CacheLogic.GetItemById(aCardId1) as Card;
         var card2:Card = this.mInventoryManager.CacheLogic.GetItemById(aCardId2) as Card;
         if(!card1 || !card2)
         {
            return false;
         }""", """         var hand:PlayerHandBO = (this.mPlayer as PlayerBO).PlayerHand;
         var handCard1:CardBO = hand.GetCardByUniqueId(aCardId1);
         var handCard2:CardBO = hand.GetCardByUniqueId(aCardId2);
         if(handCard1 != null && handCard2 != null)
         {
            return FusionUtil.IsFusionPossible(handCard1,handCard2);
         }
         var card1:Card = this.mInventoryManager.CacheLogic.GetItemById(aCardId1) as Card;
         var card2:Card = this.mInventoryManager.CacheLogic.GetItemById(aCardId2) as Card;
         if(!card1 || !card2)
         {
            return false;
         }"""),
        ("""   import com.frimastudio.as3ToolKit.util.Cleaner;
""", """   import com.frimastudio.as3ToolKit.util.Cleaner;
   import com.frimastudio.snowstorm.module.cardgame.player.hand.PlayerHandBO;
"""),
    ],
    # Every card list (Collection, sell menu, deck builder, crafting) starts here; it dropped all fusion results.
    # Synchro/Xyz cards can be owned: let them through (the deck builder removes them again, EditDeckScreen below).
    "com.frimastudio.utils.cardfiltering.CardFiltering": [
        ("""   import com.frimastudio.common.core.manager.ManagerA;
""", """   import com.frimastudio.common.core.manager.ManagerA;
""" + SUMMON_IMPORT),
        ("""            if(Boolean(shopItem) && (Boolean(aIgnoreBackorder || !shopItem.backorder)) && cardTemplate.fusionResult == false)""",
         """            if(Boolean(shopItem) && (Boolean(aIgnoreBackorder || !shopItem.backorder)) && (cardTemplate.fusionResult == false || Summon.Kind(cardTemplate.id) != Summon.NONE))"""),
    ],
    "com.frimastudio.snowstorm.module.deckbuilder.screens.EditDeckScreen": [
        ("""   import com.frimastudio.as3ToolKit.display.Log;
""", """   import com.frimastudio.as3ToolKit.display.Log;
""" + SUMMON_IMPORT),
        ("""         var cardListData:CardTemplateListData = CardTemplateListUtil.GenerateCardTemplateDataList(FilterModule.MyCardOnly,FilterModule.TournamentCardOnly,this.mUI.FilterDisplay.ActiveFilterList,null,cardTemplateDisplayedOnMatList);
""", """         var cardListData:CardTemplateListData = Summon.WithoutResults(CardTemplateListUtil.GenerateCardTemplateDataList(FilterModule.MyCardOnly,FilterModule.TournamentCardOnly,this.mUI.FilterDisplay.ActiveFilterList,null,cardTemplateDisplayedOnMatList));
"""),
    ],
}
for _cls, _edits in SUMMON_EDITS.items():
    PATCHES[_cls] = PATCHES.get(_cls, []) + _edits

# Browser profiling (YGO_WEB_PROFILE=1 on top of YGO_WEB, dev only): Starling's per-frame logic vs. drawing, and
# rendered (non-bitmap-font) text, reported to the page every 2 s (com.revival.web.WebProf).
WEB_PROFILE_EDITS = {
    "starling.core.Starling": [
        ("""   import flash.display.Sprite;
""", """   import flash.display.Sprite;
   import com.revival.web.WebProf;
"""),
        ("""         this.advanceTime(passedTime);
         if(WebRender.ShouldRender(this.mJuggler.revivalBusy))
         {
            this.render();
         }""", """         var profT0:int = getTimer();
         this.advanceTime(passedTime);
         var profT1:int = getTimer();
         if(WebRender.ShouldRender(this.mJuggler.revivalBusy))
         {
            this.render();
            WebProf.Add("drawcalls",this.mSupport.drawCount);
            WebProf.Add("render",getTimer() - profT1);
         }
         WebProf.Add("advance",profT1 - profT0);"""),
    ],
    # merged batches: vertex upload + state + drawTriangles (QuadBatch itself can't be recompiled: internal access)
    "starling.core.RenderSupport": [
        ("""   import com.adobe.utils.AGALMiniAssembler;
""", """   import com.adobe.utils.AGALMiniAssembler;
   import com.revival.web.WebProf;
   import flash.utils.getTimer;
"""),
        ("""         var currentBatch:QuadBatch = this.mQuadBatches[this.mCurrentQuadBatchID];
         if(currentBatch.numQuads != 0)
         {
            currentBatch.renderCustom(this.mProjectionMatrix);""", """         var currentBatch:QuadBatch = this.mQuadBatches[this.mCurrentQuadBatchID];
         if(currentBatch.numQuads != 0)
         {
            var profT0:int = getTimer();
            WebProf.Add("quads",currentBatch.numQuads);
            currentBatch.renderCustom(this.mProjectionMatrix);
            WebProf.Add("flush",getTimer() - profT0);"""),
    ],
    "starling.text.TextField": [
        ("""   import flash.display.BitmapData;
""", """   import flash.display.BitmapData;
   import com.revival.web.WebProf;
   import flash.utils.getTimer;
"""),
        ("""               this.createRenderedContents();""", """               var profT0:int = getTimer();
               this.createRenderedContents();
               WebProf.Add("text",getTimer() - profT0);"""),
    ],
}
if __import__("os").environ.get("YGO_WEB") == "1" and __import__("os").environ.get("YGO_WEB_PROFILE") == "1":
    for _cls, _edits in WEB_PROFILE_EDITS.items():
        PATCHES[_cls] = PATCHES.get(_cls, []) + _edits
