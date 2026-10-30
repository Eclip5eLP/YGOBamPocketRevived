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
    MAIN_MENU_VIEW: [_no_icon("mLoginButton", "facebookIcon")],
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
    ENGINE: ENGINE_EDITS,
    BOOSTER_INFO: BOOSTER_INFO_EDITS,
    INVENTORY: INVENTORY_EDITS,
    CHOOSE_DECK_UI: CHOOSE_DECK_UI_EDITS,
    CHOOSE_DECK: CHOOSE_DECK_EDITS,
    SERVERCOM: SERVERCOM_EDITS,
    NEW_APP_UPDATE: NEW_APP_UPDATE_EDITS,
    VERSION_UNAVAILABLE: VERSION_UNAVAILABLE_EDITS,
}
