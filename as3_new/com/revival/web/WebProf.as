package com.revival.web
{
   import flash.external.ExternalInterface;
   import flash.utils.getTimer;

   // Browser build profiling only (YGO_WEB_PROFILE=1, as3_patches.py WEB_PROFILE_EDITS): time spent per named part,
   // handed to the page's __prof(json) every 2 s (then reset). Never in a normal build.
   public class WebProf
   {
      private static var mTotals:Object = {};

      private static var mCounts:Object = {};

      private static var mLastFlush:int;

      public function WebProf()
      {
         super();
      }

      public static function Add(aName:String, aMs:int) : void
      {
         mTotals[aName] = int(mTotals[aName]) + aMs;
         mCounts[aName] = int(mCounts[aName]) + 1;
         var now:int = getTimer();
         if(now - mLastFlush >= 2000)
         {
            var report:Object = {"ms":now - mLastFlush};
            for(var k:String in mTotals)
            {
               report[k] = mTotals[k] + "ms/" + mCounts[k];
            }
            mTotals = {};
            mCounts = {};
            mLastFlush = now;
            try
            {
               ExternalInterface.call("__prof",JSON.stringify(report));
            }
            catch(error:Error)
            {
            }
         }
      }
   }
}
