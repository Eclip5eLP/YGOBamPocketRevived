package com.revival.dev
{
   import starling.core.Starling;
   import flash.events.Event;
   import flash.events.UncaughtErrorEvent;
   import flash.events.IOErrorEvent;
   import flash.net.URLLoader;
   import flash.net.URLRequest;
   import flash.utils.getTimer;

   // Dev only (builds with YGO_PERF=1, tools/as3_patches.py PERF_EDITS): reports a timing mark to the dev server as
   // GET /perf?s=<name>&t=<ms since launch>, which shows up in the server log.
   public class Perf
   {
      private static var mPending:Array = [];

      public function Perf()
      {
         super();
      }

      public static function Mark(aName:String) : void
      {
         var loader:URLLoader = null;
         try
         {
            loader = new URLLoader();
            loader.addEventListener(Event.COMPLETE,Done);
            loader.addEventListener(IOErrorEvent.IO_ERROR,Done);
            mPending.push(loader);
            loader.load(new URLRequest("http://127.0.0.1/perf?s=" + encodeURIComponent(aName) + "&t=" + getTimer()));
         }
         catch(error:Error)
         {
         }
      }

      // Uncaught script errors (hidden in release builds) go to the dev server log as "error <message> <stack>".
      public static function CatchErrors() : void
      {
         try
         {
            Starling.current.nativeStage.loaderInfo.uncaughtErrorEvents.addEventListener(UncaughtErrorEvent.UNCAUGHT_ERROR,OnUncaught);
         }
         catch(error:Error)
         {
         }
      }

      private static function OnUncaught(aEvent:UncaughtErrorEvent) : void
      {
         var e:Error = aEvent.error as Error;
         Mark("error " + (e != null ? e.message + " " + e.getStackTrace() : String(aEvent.error)));
      }

      private static function Done(aEvent:Event) : void
      {
         var index:int = mPending.indexOf(aEvent.currentTarget);
         if(index >= 0)
         {
            mPending.splice(index,1);
         }
      }
   }
}
