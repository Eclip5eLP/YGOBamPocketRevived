package com.revival.web
{
   import flash.utils.getTimer;

   // Browser build only (as3_patches.py WEB_EDITS on starling.core.Starling): in Ruffle every GPU submission costs
   // about 1 ms (findings 6.60), and Starling 1.x redraws the whole screen every frame even when nothing changed.
   // Draw every frame while something can be changing (input in the last ACTIVE_MS, or the juggler has tweens /
   // delayed calls / animations), otherwise only every IDLE_MS. Game logic (advanceTime) still runs every frame.
   public class WebRender
   {
      private static const ACTIVE_MS:int = 1500;

      private static const IDLE_MS:int = 200;

      private static var mLastInput:int = -100000;

      private static var mLastRender:int = -100000;

      public function WebRender()
      {
         super();
      }

      public static function Input() : void
      {
         mLastInput = getTimer();
      }

      public static function ShouldRender(aAnimating:Boolean) : Boolean
      {
         var now:int = getTimer();
         if(aAnimating || now - mLastInput < ACTIVE_MS || now - mLastRender >= IDLE_MS)
         {
            mLastRender = now;
            return true;
         }
         return false;
      }
   }
}
