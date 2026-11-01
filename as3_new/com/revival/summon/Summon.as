package com.revival.summon
{
   import com.frimastudio.common.core.manager.ManagerA;
   import com.frimastudio.snowstorm.module.cardgame.card.CardBO;
   import com.frimastudio.snowstorm.module.cardgame.effect.effectlist.EffectBO;
   import com.frimastudio.snowstorm.module.cardgame.handler.CGHandlerManager;
   import com.frimastudio.snowstorm.module.cardgame.player.AwayPlayer;
   import com.frimastudio.snowstorm.module.cardgame.player.IAIPlayer;
   import com.frimastudio.snowstorm.module.cardgame.player.LocalPlayer;
   import com.frimastudio.snowstorm.module.cardgame.trigger.ICGTriggerDispatcher;
   import com.frimastudio.snowstorm.module.cardgame.util.FusionUtil;
   import com.frimastudio.snowstorm.project.inventory.IInventoryManagerGame;
   import com.frimastudio.snowstorm.project.inventory.amf.Card;
   import com.frimastudio.snowstorm.project.inventory.amf.CardTemplate;
   import com.frimastudio.snowstorm.project.inventory.enumeration.CardTypes;
   import com.frimastudio.snowstorm.project.inventory.util.CardTemplateListData;
   import com.frimastudio.snowstorm.project.manager.EManagerDefinitionProject;
   import flash.filesystem.File;
   import flash.filesystem.FileMode;
   import flash.filesystem.FileStream;
   import flash.utils.Dictionary;
   import flash.utils.getDefinitionByName;
   import flash.utils.getTimer;

   // Synchro and Xyz summons (notes/synchro_xyz.md). They reuse the fusion pairing: a card dropped on your monster
   // in the same channel (CardBO.CardToFuseWith), resolved by RoundHandler.DoFusionLaunch through
   // GameMatBO.CreateFusionCard, so the materials stay under the result (IngredientCardList).
   //
   // Rules: config/summons.json (content, tools/content_mods.py summons):
   //   {"synchro": {"<tuner id>": {"<level total>": [result ids]}},
   //    "xyz": [{"id": result id, "rank": n, "family": 0 or monster type, "element": 0 or attribute}]}
   // Synchro: a Tuner + a non-Tuner monster, levels added. Xyz: two monsters of the rank's level; a family/element
   // must be shared by both materials. Results keep their level (an Xyz's rank is its level), so they can be
   // material again.
   //
   // Who may make what: the local player only results they own (fusion results always); the live opponent anything
   // the rules allow (their pick travels with their move, PlayerHandBO / AwayPlayer patches); an AI Synchro yes,
   // Xyz only with the duel's AiXyz flag, or exactly the duel's AiExtra list (map node properties aixyz / aiextra,
   // DuelData patch). Several possible results: the local player picks (SummonPickerPopup), the AI takes the
   // strongest.
   public class Summon
   {
      public static const NONE:int = 0;

      public static const SYNCHRO:int = 2;

      public static const XYZ:int = 3;

      private static const OWNED_CACHE_MS:int = 3000;

      private static var sRules:Object;

      private static var sKind:Object;

      private static var sChoice:Dictionary = new Dictionary(true);

      private static var sOwned:Object;

      private static var sOwnedTime:int = -100000;

      public function Summon()
      {
         super();
      }

      private static function Rules() : Object
      {
         var file:File = null;
         var stream:FileStream = null;
         var id:String = null;
         var total:String = null;
         var entry:Object = null;
         if(sRules != null)
         {
            return sRules;
         }
         sRules = {"synchro":{},"xyz":[]};
         sKind = {};
         try
         {
            file = File.applicationStorageDirectory.resolvePath("asset/gamedata/config/summons.json");
            // Loader.GameDataActive is added by tools/as3_patches.py (after this class is compiled): look it up
            if(!getDefinitionByName("com.frimastudio.as3ToolKit.net.Loader")["GameDataActive"] || !file.exists)
            {
               file = File.applicationDirectory.resolvePath("config/summons.json");
            }
            if(file.exists)
            {
               stream = new FileStream();
               stream.open(file,FileMode.READ);
               sRules = JSON.parse(stream.readUTFBytes(stream.bytesAvailable));
               stream.close();
            }
         }
         catch(error:Error)
         {
         }
         sRules.synchro = sRules.synchro || {};
         sRules.xyz = sRules.xyz || [];
         for(id in sRules.synchro)
         {
            for(total in sRules.synchro[id])
            {
               for each(var result:* in sRules.synchro[id][total])
               {
                  sKind[String(result)] = SYNCHRO;
               }
            }
         }
         for each(entry in sRules.xyz)
         {
            sKind[String(entry.id)] = XYZ;
         }
         return sRules;
      }

      // SYNCHRO, XYZ or NONE (fusion results and normal cards)
      public static function Kind(aTemplateId:int) : int
      {
         Rules();
         return int(sKind[String(aTemplateId)]);
      }

      public static function IsTuner(aTemplateId:int) : Boolean
      {
         return Rules().synchro[String(aTemplateId)] != null;
      }

      // Synchro and Xyz results the rules allow for two cards (template data), Synchro first, in data order.
      public static function RuleResults(aId1:int, aLevel1:int, aType1:int, aElement1:int, aFamily1:int, aId2:int, aLevel2:int, aType2:int, aElement2:int, aFamily2:int) : Array
      {
         var results:Array = [];
         var rules:Object = Rules();
         var list:Array = null;
         var entry:Object = null;
         if(aType1 != CardTypes.MONSTER_TYPE.Id || aType2 != CardTypes.MONSTER_TYPE.Id)
         {
            return results;
         }
         if(IsTuner(aId1) != IsTuner(aId2))
         {
            list = (IsTuner(aId1) ? rules.synchro[String(aId1)] : rules.synchro[String(aId2)])[String(aLevel1 + aLevel2)] as Array;
            for each(var id:* in list)
            {
               results.push(int(id));
            }
         }
         if(aLevel1 == aLevel2 && aLevel1 > 0)
         {
            for each(entry in rules.xyz)
            {
               if(int(entry.rank) == aLevel1 && (!entry.family || int(entry.family) == aFamily1 && int(entry.family) == aFamily2) && (!entry.element || int(entry.element) == aElement1 && int(entry.element) == aElement2))
               {
                  results.push(int(entry.id));
               }
            }
         }
         return results;
      }

      private static function CardResults(aCard1:CardBO, aCard2:CardBO) : Array
      {
         return RuleResults(aCard1.CardTemplateId,aCard1.CardLevel,aCard1.CardType.Id,aCard1.CardElement.Id,aCard1.CardFamily.Id,aCard2.CardTemplateId,aCard2.CardLevel,aCard2.CardType.Id,aCard2.CardElement.Id,aCard2.CardFamily.Id);
      }

      private static function Inventory() : IInventoryManagerGame
      {
         return ManagerA.GetManager(EManagerDefinitionProject.INVENTORY_MANAGER) as IInventoryManagerGame;
      }

      private static function Template(aTemplateId:int) : CardTemplate
      {
         return Inventory().CacheLogic.GetTemplateById(aTemplateId) as CardTemplate;
      }

      public static function Owns(aTemplateId:int) : Boolean
      {
         var card:Card = null;
         if(sOwned == null || getTimer() - sOwnedTime > OWNED_CACHE_MS)
         {
            sOwned = {};
            sOwnedTime = getTimer();
            try
            {
               for each(card in Inventory().GetCompleteCardList())
               {
                  if(card.quantity > 0)
                  {
                     sOwned[String(card.itemTemplateId)] = true;
                  }
               }
            }
            catch(error:Error)
            {
            }
         }
         return sOwned[String(aTemplateId)] == true;
      }

      private static function DuelSetting(aName:String) : *
      {
         var test:Object = Rules().test;
         if(test != null && test.hasOwnProperty(aName))  // test content: same as the map node property (aixyz, aiextra)
         {
            return test[aName];
         }
         try
         {
            return Object(CGHandlerManager.MainModule.DuelInfo)[aName];
         }
         catch(error:Error)
         {
         }
         return null;
      }

      // An AI may make this Synchro/Xyz in the current duel.
      public static function AiAllows(aResultId:int) : Boolean
      {
         var extra:Array = DuelSetting("AiExtra") as Array;
         if(extra != null)
         {
            return extra.indexOf(aResultId) != -1;
         }
         return Kind(aResultId) != XYZ || DuelSetting("AiXyz") == true;
      }

      private static function IsAI(aCard:CardBO) : Boolean
      {
         return !(aCard.Owner is LocalPlayer) && (aCard.Owner is IAIPlayer || !(aCard.Owner is AwayPlayer));
      }

      // Everything this pair can become for its owner: the fusion result first, then Synchro/Xyz results.
      public static function Candidates(aCard1:CardBO, aCard2:CardBO) : Array
      {
         var results:Array = [];
         var base:CardBO = null;
         var id:int = 0;
         if(aCard1 == null || aCard2 == null || aCard1 == aCard2)
         {
            return results;
         }
         base = FusionUtil.FindBaseMonster(aCard1,aCard2);
         if(base != null)
         {
            results.push(base.FusionInfo.resultCardTemplateId);
         }
         for each(id in CardResults(aCard1,aCard2))
         {
            if(results.indexOf(id) != -1)
            {
               continue;
            }
            if(aCard1.Owner is LocalPlayer ? Owns(id) : (IsAI(aCard1) ? AiAllows(id) : true))
            {
               results.push(id);
            }
         }
         return results;
      }

      // FusionUtil.IsFusionPossible (patched to call this)
      public static function IsPossible(aCard1:CardBO, aCard2:CardBO) : Boolean
      {
         return aCard1 != aCard2 && aCard1.CardToFuseWith == null && aCard2.CardToFuseWith == null && Candidates(aCard1,aCard2).length > 0;
      }

      // FusionUtil.IsFusionPossibleFromTemplate (AI planning, patched): Synchro/Xyz the AI may make
      public static function AiCanPair(aTemplate1:CardTemplate, aTemplate2:CardTemplate) : Boolean
      {
         for each(var id:int in RuleResults(aTemplate1.id,aTemplate1.cardLevel,aTemplate1.cardTypeId,aTemplate1.cardElementId,aTemplate1.cardFamilyId,aTemplate2.id,aTemplate2.cardLevel,aTemplate2.cardTypeId,aTemplate2.cardElementId,aTemplate2.cardFamilyId))
         {
            if(AiAllows(id))
            {
               return true;
            }
         }
         return false;
      }

      public static function SetChoice(aCard1:CardBO, aCard2:CardBO, aResultId:int) : void
      {
         if(aCard1 != null)
         {
            sChoice[aCard1] = aResultId;
         }
         if(aCard2 != null)
         {
            sChoice[aCard2] = aResultId;
         }
      }

      // What the pair becomes now: the stored pick if it is still possible, else the AI's strongest result or the
      // first one (fusion first). 0: nothing.
      public static function Result(aCard1:CardBO, aCard2:CardBO) : int
      {
         var candidates:Array = Candidates(aCard1,aCard2);
         var choice:int = int(sChoice[aCard1] || sChoice[aCard2]);
         var best:int = 0;
         var bestAtk:int = -1;
         var template:CardTemplate = null;
         if(candidates.length == 0)
         {
            return 0;
         }
         if(choice != 0 && candidates.indexOf(choice) != -1)
         {
            return choice;
         }
         if(candidates.length > 1 && IsAI(aCard1))
         {
            for each(var id:int in candidates)
            {
               template = Template(id);
               if(template != null && template.atkStat > bestAtk)
               {
                  best = id;
                  bestAtk = template.atkStat;
               }
            }
            return best;
         }
         return candidates[0];
      }

      // CardLoadingUtil.CardFileListFromCardTemplateIdList (patched): a duel preloads the pictures of its decks' cards
      // and of their fusion results; a result card is created in the round without waiting for its picture. Also
      // load what a card can become: a Tuner's Synchros, the Xyz of its level, and the Xyz of those results' levels.
      public static function PreloadIds(aTemplateId:int) : Array
      {
         var ids:Array = [];
         var template:CardTemplate = null;
         var rules:Object = Rules();
         var levels:Array = [];
         var entry:Object = null;
         try
         {
            template = Template(aTemplateId);
         }
         catch(error:Error)
         {
         }
         if(template == null || template.cardTypeId != CardTypes.MONSTER_TYPE.Id)
         {
            return ids;
         }
         levels.push(template.cardLevel);
         if(IsTuner(aTemplateId))
         {
            for(var total:String in rules.synchro[String(aTemplateId)])
            {
               for each(var id:* in rules.synchro[String(aTemplateId)][total])
               {
                  ids.push(int(id));
                  levels.push(int(total));
               }
            }
         }
         for each(entry in rules.xyz)
         {
            if(levels.indexOf(int(entry.rank)) != -1 && ids.indexOf(int(entry.id)) == -1)
            {
               ids.push(int(entry.id));
            }
         }
         return ids;
      }

      // Type line of a card view (DetailedCardVisual patch): "Warrior / Tuner", "Dragon / Synchro", "Warrior / Xyz"
      public static function TypeSuffix(aTemplateId:int) : String
      {
         if(IsTuner(aTemplateId))
         {
            return " / Tuner";
         }
         return Kind(aTemplateId) == SYNCHRO ? " / Synchro" : (Kind(aTemplateId) == XYZ ? " / Xyz" : "");
      }

      // Material count on an Xyz in the duel (DuelCard.RevivalMaterials, added by tools/as3_patches.py after this
      // class is compiled). Called when the card is made, when a material effect changes it, and on undo.
      public static function ShowMaterials(aCard:CardBO) : void
      {
         if(aCard == null || Kind(aCard.CardTemplateId) != XYZ)
         {
            return;
         }
         try
         {
            Object(aCard.Skin.FaceUpSkin)["RevivalMaterials"](MaterialCount(aCard));
         }
         catch(error:Error)
         {
         }
      }

      // --- Test duels (summons.json "test", written only by tools/content_test_mods.py, never in a release) ---------
      //   "draw": [template ids]  the local player's deck is drawn in this order first (after each shuffle)
      //   "aiHp": n               an AI opponent starts with n life points (the duel lasts long enough to test)

      // GameMatBO.ShuffleDeck (patched)
      public static function TestDraw(aDeck:Vector.<CardBO>, aOwner:Object) : Vector.<CardBO>
      {
         var test:Object = Rules().test;
         var front:Vector.<CardBO> = new Vector.<CardBO>();
         var rest:Vector.<CardBO> = aDeck.concat();
         var i:int = 0;
         if(test == null || test.draw == null || !(aOwner is LocalPlayer))
         {
            return aDeck;
         }
         for each(var id:* in test.draw)
         {
            for(i = 0; i < rest.length; i++)
            {
               if(rest[i].CardTemplateId == int(id))
               {
                  front.push(rest.splice(i,1)[0]);
                  break;
               }
            }
         }
         return front.concat(rest);
      }

      // GameMatBO.CalculateDeckHP (patched)
      public static function TestHp(aOwner:Object, aHp:int) : int
      {
         var test:Object = Rules().test;
         if(test != null && int(test.aiHp) > 0 && aOwner != null && !(aOwner is LocalPlayer) && !(aOwner is AwayPlayer))
         {
            return int(test.aiHp);
         }
         return aHp;
      }

      // --- Material effects (summons.json "effects": {"<effect id>": rule}) ---------------------------------------
      // A rule turns an existing effect row of a Synchro/Xyz card into a material effect:
      //   "needs": n      the effect only works while the card has at least n materials
      //   "cost": n       ... and detaches n materials (to the graveyard) each time it works
      //   "perMaterial":1 its ATK/LP amount is multiplied by the number of materials
      //   "attach": n     after it works, the card takes up to n monsters from its owner's graveyard as materials
      //                   (not shown yet: the graveyard pile/count keeps them until its next visual update)
      // Materials are the cards under the result (CardBO.IngredientCardList, saved and reverted by the duel's undo
      // states, CardBO.SaveState / RevertToState), so the AI's trial rounds undo detaching too.

      private static function EffectRule(aEffect:EffectBO) : Object
      {
         var effects:Object = Rules().effects;
         var id:int = 0;
         if(effects == null)
         {
            return null;
         }
         try
         {
            id = int(Object(aEffect)["RevivalEffectId"]);  // EffectBO patch (added after this class is compiled)
         }
         catch(error:Error)
         {
         }
         return id != 0 ? effects[String(id)] : null;
      }

      private static function EffectCard(aEffect:EffectBO) : CardBO
      {
         return aEffect.EffectOwner as CardBO;
      }

      public static function MaterialCount(aCard:CardBO) : int
      {
         return aCard != null && aCard.IngredientCardList != null ? int(aCard.IngredientCardList.length) : 0;
      }

      // EffectHandler.ResolveEffect (patched): false = the effect does not happen (not enough materials, or an
      // ON ... SUMMON effect after a summon of another kind)
      public static function CanResolveEffect(aEffect:EffectBO) : Boolean
      {
         var rule:Object = EffectRule(aEffect);
         if(rule == null)
         {
            return true;
         }
         if(rule.summonKind && !KindFits(String(rule.summonKind),sLastSummon))
         {
            return false;
         }
         // perMaterial needs one: with none, a "x materials" amount would be 0 (a multiply would zero the ATK)
         return MaterialCount(EffectCard(aEffect)) >= Math.max(int(rule.needs),int(rule.cost),rule.perMaterial ? 1 : 0);
      }

      // EffectHandler.ResolveEffect (patched): the effect worked; pay its cost / take its materials
      public static function OnEffectResolved(aEffect:EffectBO) : void
      {
         var rule:Object = EffectRule(aEffect);
         var card:CardBO = EffectCard(aEffect);
         var list:Vector.<CardBO> = null;
         var detached:Vector.<CardBO> = null;
         var graveyard:Vector.<CardBO> = null;
         var i:int = 0;
         if(rule == null || card == null)
         {
            return;
         }
         list = card.IngredientCardList != null ? card.IngredientCardList : new Vector.<CardBO>();
         if(int(rule.cost) > 0)
         {
            // a new list each time: an undo state may hold the old one (CardBO.RevertToState keeps its reference)
            detached = list.slice(Math.max(0,list.length - int(rule.cost)));
            list = list.slice(0,Math.max(0,list.length - int(rule.cost)));
            card.IngredientCardList = list;
            for each(var material:CardBO in detached)
            {
               card.Owner.GameMat.PlaceCardInGraveyard(material,false);
               material.PlayCardGoesToGraveyard();  // queued animation; it also updates the graveyard count
            }
         }
         if(int(rule.attach) > 0)
         {
            graveyard = card.Owner.GameMat.Graveyard;
            list = list.concat();
            for(i = graveyard.length - 1; i >= 0 && list.length < MaterialCount(card) + int(rule.attach); i--)
            {
               if(graveyard[i] != card && !graveyard[i].IsRez && graveyard[i].CardType.Id == CardTypes.MONSTER_TYPE.Id)
               {
                  list.push(graveyard[i]);
                  card.Owner.GameMat.RemoveFromGraveyard(graveyard[i]);
               }
            }
            card.IngredientCardList = list;
         }
         ShowMaterials(card);
      }

      // EffectHandler.ResolveStatModifier / ResolveHealthEffect (patched): the amount, times the materials
      public static function ScaleByMaterials(aEffect:EffectBO, aValue:Number) : Number
      {
         var rule:Object = EffectRule(aEffect);
         return rule != null && rule.perMaterial ? aValue * MaterialCount(EffectCard(aEffect)) : aValue;
      }

      // --- New effects (notes/new_effects.md; summons.json "effects" rules on effect rows) --------------------------
      //   ON SYNCHRO / ON XYZ / ON FUSION: a row with trigger ON_FUSION (32) and dispatcher ACTIVE_CARD on the result
      //                    card: RoundHandler.DoFusionLaunch launches ON_FUSION for the new card (no rule needed)
      //   "summonKind": "synchro" | "xyz" | "fusion" | "any"   ON SYNCHRO SUMMON ...: a row with trigger ON_FUSION and
      //                    dispatcher PLAYER (DoFusionLaunch patch adds the owner to the dispatchers) that only works
      //                    after a summon of that kind
      //   "targetKind": same values   BOOST ALL SYNCHROS ...: the row's targets are only results of that kind
      //                    (TargetRetreiver.GetEffectTarget patch)
      //   "material": true  MATERIAL: X, a row on a material card without a trigger of its own (trigger 0): when the
      //                    card is used for a summon, the row is added to the new card and works with its ON_FUSION
      //   "level": n / "levelSet": n   LEVEL UP / DOWN / SET: a LevelEffect changes the targets' Level (Synchro totals,
      //                    Xyz ranks) while they stay on the field (CardBO.RevivalLevel, saved with the card's state)
      //   "rebirth": true  REBIRTH, a text row: when the card is destroyed it is shuffled back into the Deck (a result:
      //                    its materials) - RoundHandler.ClearDeadCards patch
      //   "guardian": true GUARDIAN, a text row: when another card of its owner would be destroyed (effect or battle),
      //                    this card is destroyed instead - EffectHandler patches

      private static var sLastSummon:CardBO;

      // "synchro", "xyz" or "fusion" for a result card, "" for others
      public static function KindName(aCard:CardBO) : String
      {
         if(aCard == null)
         {
            return "";
         }
         if(Kind(aCard.CardTemplateId) == SYNCHRO)
         {
            return "synchro";
         }
         if(Kind(aCard.CardTemplateId) == XYZ)
         {
            return "xyz";
         }
         return aCard.IsFusionResult ? "fusion" : "";
      }

      private static function KindFits(aKind:String, aCard:CardBO) : Boolean
      {
         var kind:String = KindName(aCard);
         return kind != "" && (aKind == "any" || aKind == kind);
      }

      private static function RowRule(aEffectId:int) : Object
      {
         var effects:Object = Rules().effects;
         return effects != null ? effects[String(aEffectId)] : null;
      }

      // A card's template has a row with this rule key (guardian, rebirth)
      private static function HasRule(aCard:CardBO, aKey:String) : Boolean
      {
         var template:CardTemplate = Template(aCard.CardTemplateId);
         var rule:Object = null;
         if(template == null || template.effects == null)
         {
            return false;
         }
         for each(var cardEffect:Object in template.effects)
         {
            rule = RowRule(int(cardEffect.effect.id));
            if(rule != null && rule[aKey])
            {
               return true;
            }
         }
         return false;
      }

      // RoundHandler.DoFusionLaunch (patched), right after GameMatBO.CreateFusionCard: remember the summon for
      // "summonKind" rules and give the new card its materials' MATERIAL rows
      public static function OnSummoned(aResult:CardBO, aMaterial1:CardBO, aMaterial2:CardBO) : void
      {
         var rows:Array = [];
         var template:CardTemplate = null;
         var rule:Object = null;
         sLastSummon = aResult;
         for each(var material:CardBO in [aMaterial1,aMaterial2])
         {
            template = material != null ? Template(material.CardTemplateId) : null;
            if(template == null || template.effects == null)
            {
               continue;
            }
            for each(var cardEffect:Object in template.effects)
            {
               rule = RowRule(int(cardEffect.effect.id));
               if(rule != null && rule.material)
               {
                  rows.push(cardEffect);
               }
            }
         }
         if(rows.length > 0)
         {
            Object(aResult)["RevivalAddEffects"](rows);  // CardBO patch (added after this class is compiled)
         }
      }

      // TargetRetreiver.GetEffectTarget (patched)
      public static function FilterTargets(aEffect:EffectBO, aTargets:Vector.<ICGTriggerDispatcher>) : Vector.<ICGTriggerDispatcher>
      {
         var rule:Object = EffectRule(aEffect);
         var kept:Vector.<ICGTriggerDispatcher> = null;
         if(rule == null || !rule.targetKind)
         {
            return aTargets;
         }
         kept = new Vector.<ICGTriggerDispatcher>();
         for each(var target:ICGTriggerDispatcher in aTargets)
         {
            if(target is CardBO && KindFits(String(rule.targetKind),target as CardBO))
            {
               kept.push(target);
            }
         }
         return kept;
      }

      // EffectCreater.CreateEffects (patched): this row gets a LevelEffect
      public static function IsLevelEffect(aEffectId:int) : Boolean
      {
         var rule:Object = RowRule(aEffectId);
         return rule != null && (rule.hasOwnProperty("level") || rule.hasOwnProperty("levelSet"));
      }

      // EffectHandler.ResolveEffect (patched) for a LevelEffect
      public static function ResolveLevel(aEffect:EffectBO, aTargets:Vector.<ICGTriggerDispatcher>) : Boolean
      {
         var rule:Object = EffectRule(aEffect);
         var card:CardBO = null;
         var resolved:Boolean = false;
         if(rule == null)
         {
            return false;
         }
         for each(var target:ICGTriggerDispatcher in aTargets)
         {
            card = target as CardBO;
            if(card == null || card.IsDead || card.CardType.Id != CardTypes.MONSTER_TYPE.Id)
            {
               continue;
            }
            if(!resolved)
            {
               aEffect.EffectOwner.OnEffectLaunched(aEffect);
               resolved = true;
            }
            Object(card)["RevivalLevel"] = rule.hasOwnProperty("levelSet") ? int(rule.levelSet) : Math.max(1,card.CardLevel + int(rule.level));
         }
         return resolved;
      }

      // EffectHandler.ResolveDestroyCard / ResolveNormalAttack (patched): the card that is destroyed when aTarget would
      // be: a living GUARDIAN of the same owner, else aTarget itself
      public static function Destroyed(aTarget:CardBO) : CardBO
      {
         if(aTarget == null || aTarget.IsDead || aTarget.Owner == null)
         {
            return aTarget;
         }
         for each(var card:CardBO in aTarget.Owner.GameMat.GetCardsOnMat())
         {
            if(card != aTarget && !card.IsDead && !card.IsInvincible && HasRule(card,"guardian"))
            {
               return card;
            }
         }
         return aTarget;
      }

      // RoundHandler.ClearDeadCards (patched), before the dead cards leave the field: the cards REBIRTH returns to the
      // Deck once they are in the graveyard (a result card: its materials)
      public static function RebirthCards(aPlayers:Array) : Vector.<CardBO>
      {
         var cards:Vector.<CardBO> = new Vector.<CardBO>();
         for each(var player:Object in aPlayers)
         {
            for each(var card:CardBO in player.GameMat.GetCardsOnMat())
            {
               if(card.IsDead && HasRule(card,"rebirth"))
               {
                  if(card.IsFusionResult)
                  {
                     if(card.IngredientCardList != null)
                     {
                        cards = cards.concat(card.IngredientCardList);
                     }
                  }
                  else
                  {
                     cards.push(card);
                  }
               }
            }
         }
         return cards;
      }

      // Card frame pictures: the fusion picture's name with "fusion" replaced by "synchro"/"xyz" (second common atlas
      // page, tools/content_mods.py summon_frames). Fusion results and fusion bases keep the fusion picture.
      public static function FrameName(aFusionName:String, aKind:int) : String
      {
         if(aKind == SYNCHRO)
         {
            return aFusionName.replace("fusion","synchro");
         }
         if(aKind == XYZ)
         {
            return aFusionName.replace("fusion","xyz");
         }
         return aFusionName;
      }

      // Deck builder card list (EditDeckScreen patch): no Fusion/Synchro/Xyz results, they are made in duels.
      public static function WithoutResults(aData:CardTemplateListData) : CardTemplateListData
      {
         var templates:Vector.<CardTemplate> = new Vector.<CardTemplate>();
         var quantities:Vector.<int> = new Vector.<int>();
         for(var i:int = 0; i < aData.CardTemplateList.length; i++)
         {
            if(!aData.CardTemplateList[i].fusionResult)
            {
               templates.push(aData.CardTemplateList[i]);
               quantities.push(aData.QuantityList[i]);
            }
         }
         return new CardTemplateListData(templates,quantities);
      }

      // LocalPlayerHand.SetAsPlaced (patched): the local player just paired two cards. Several results: ask.
      public static function OnLocalPair(aBase:CardBO, aDropped:CardBO) : void
      {
         var candidates:Array = Candidates(aBase,aDropped);
         delete sChoice[aBase];
         delete sChoice[aDropped];
         if(candidates.length > 1)
         {
            SummonPickerPopup.Ask(candidates,function(aResultId:int):void
            {
               SetChoice(aBase,aDropped,aResultId);
               try
               {
                  aDropped.Skin.FaceUpSkin.DisplayFusedAnim(aResultId);
               }
               catch(error:Error)
               {
               }
            });
         }
      }
   }
}
