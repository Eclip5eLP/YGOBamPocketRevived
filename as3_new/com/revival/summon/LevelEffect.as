package com.revival.summon
{
   import com.frimastudio.snowstorm.module.cardgame.effect.EEffectPriority;
   import com.frimastudio.snowstorm.module.cardgame.effect.effectlist.EffectBO;
   import com.frimastudio.snowstorm.module.cardgame.effect.memento.data.BreakImmunityEffectSaveState;
   import com.frimastudio.snowstorm.module.cardgame.player.PlayerBO;

   // LEVEL UP / DOWN / SET (notes/new_effects.md): made by EffectCreater.CreateEffects (patched) for a row with a
   // "level"/"levelSet" rule, resolved by Summon.ResolveLevel. It holds no state of its own (the Level is saved with the
   // card), so it saves an empty state like BreakImmunityEffect.
   public class LevelEffect extends EffectBO
   {
      public function LevelEffect()
      {
         super();
      }

      override public function PassData(aData:Array, aOwner:PlayerBO = null) : void
      {
         super.PassData(aData,aOwner);
         mPriority = EEffectPriority.BOOST_CARD_PRIORITY;
      }

      override public function SaveState() : int
      {
         return AddSaveState(new BreakImmunityEffectSaveState());
      }

      override public function RevertToState(aStateIndex:int) : void
      {
      }

      override public function IsEffectPositive() : Boolean
      {
         return true;
      }

      override public function toString() : String
      {
         return "Level effect";
      }
   }
}
