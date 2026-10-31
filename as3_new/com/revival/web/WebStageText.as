package com.revival.web
{
   import flash.display.BitmapData;
   import flash.display.Stage;
   import flash.events.Event;
   import flash.events.EventDispatcher;
   import flash.events.FocusEvent;
   import flash.events.KeyboardEvent;
   import flash.events.MouseEvent;
   import flash.events.SoftKeyboardEvent;
   import flash.ui.Keyboard;
   import flash.geom.Rectangle;
   import flash.text.TextField;
   import flash.text.TextFieldType;
   import flash.text.TextFormat;
   import flash.text.TextFormatAlign;

   // Browser build only (as3_patches.py WEB_EDITS on NativeText): flash.text.StageText is AIR-only (Ruffle has no
   // StageText/StageTextInitOptions, so the deck chooser crashed while building its deck-name box). This has the
   // part of StageText's API that NativeText uses, on an ordinary input TextField placed on the native stage.
   // A browser has no soft keyboard, but the game waits for its events: ComboBox puts a full-screen blocker up while
   // the keyboard is "open" and removes it on SOFT_KEYBOARD_DEACTIVATE (without that, nothing else in Edit Deck
   // reacted). Focus in = keyboard open; a click outside the field, Enter or focus out = keyboard closed. Plain Events
   // of the SoftKeyboardEvent types: Ruffle can't construct SoftKeyboardEvent (Error #1056 on _triggerType).
   public class WebStageText extends EventDispatcher
   {
      private var mField:TextField = new TextField();

      private var mEditing:Boolean;

      private var mFormat:TextFormat = new TextFormat("_sans",16,0);

      public var autoCapitalize:String = "none";

      public var autoCorrect:Boolean = false;

      public var locale:String = "en";

      public var returnKeyLabel:String = "default";

      public var softKeyboardType:String = "default";

      public var fontPosture:String = "normal";

      public var fontWeight:String = "normal";

      public function WebStageText(aMultiline:Boolean = false)
      {
         super();
         this.mField.type = TextFieldType.INPUT;
         this.mField.multiline = aMultiline;
         this.mField.wordWrap = aMultiline;
         this.mField.defaultTextFormat = this.mFormat;
         this.mField.addEventListener(FocusEvent.FOCUS_IN,this.OnFocusIn);
         this.mField.addEventListener(FocusEvent.FOCUS_OUT,this.OnFocusOut);
         this.mField.addEventListener(KeyboardEvent.KEY_DOWN,this.OnKey);
      }

      // (the game may ask for focus before the field is on the stage: editing starts anyway, the click watch when the
      // field gets there, see set stage)
      private function OnFocusIn(aEvent:FocusEvent) : void
      {
         if(this.mEditing)
         {
            return;
         }
         this.mEditing = true;
         this.WatchClicks();
         this.mField.dispatchEvent(new Event(SoftKeyboardEvent.SOFT_KEYBOARD_ACTIVATING));
         this.mField.dispatchEvent(new Event(SoftKeyboardEvent.SOFT_KEYBOARD_ACTIVATE));
      }

      private function WatchClicks() : void
      {
         if(this.mField.stage != null)
         {
            this.mField.stage.addEventListener(MouseEvent.MOUSE_DOWN,this.OnStageMouseDown,true,1000);
         }
      }

      private function OnFocusOut(aEvent:FocusEvent) : void
      {
         this.EndEditing();
      }

      private function OnKey(aEvent:KeyboardEvent) : void
      {
         if(aEvent.keyCode == Keyboard.ENTER && !this.mField.multiline)
         {
            this.EndEditing();
         }
      }

      private function OnStageMouseDown(aEvent:MouseEvent) : void
      {
         if(aEvent.target != this.mField)
         {
            this.EndEditing();
         }
      }

      private function EndEditing() : void
      {
         if(!this.mEditing)
         {
            return;
         }
         this.mEditing = false;
         if(this.mField.stage != null)
         {
            this.mField.stage.removeEventListener(MouseEvent.MOUSE_DOWN,this.OnStageMouseDown,true);
            if(this.mField.stage.focus == this.mField)
            {
               this.mField.stage.focus = null;
            }
         }
         this.mField.dispatchEvent(new Event(SoftKeyboardEvent.SOFT_KEYBOARD_DEACTIVATE));
      }

      // events (change, focus, keys) come from the text field itself
      override public function addEventListener(type:String, listener:Function, useCapture:Boolean = false, priority:int = 0, useWeakReference:Boolean = false) : void
      {
         this.mField.addEventListener(type,listener,useCapture,priority,useWeakReference);
      }

      override public function removeEventListener(type:String, listener:Function, useCapture:Boolean = false) : void
      {
         this.mField.removeEventListener(type,listener,useCapture);
      }

      public function set stage(aStage:Stage) : void
      {
         if(aStage != null)
         {
            aStage.addChild(this.mField);
            if(this.mEditing)
            {
               this.WatchClicks();
               aStage.focus = this.mField;
            }
         }
         else if(this.mField.parent != null)
         {
            if(this.mField.stage != null)
            {
               this.mField.stage.removeEventListener(MouseEvent.MOUSE_DOWN,this.OnStageMouseDown,true);
            }
            this.mField.parent.removeChild(this.mField);
         }
      }

      public function get stage() : Stage
      {
         return this.mField.stage;
      }

      public function dispose() : void
      {
         this.EndEditing();
         this.stage = null;
      }

      public function set viewPort(aRect:Rectangle) : void
      {
         this.mField.x = aRect.x;
         this.mField.y = aRect.y;
         this.mField.width = Math.max(1,aRect.width);
         this.mField.height = Math.max(1,aRect.height);
      }

      public function get viewPort() : Rectangle
      {
         return new Rectangle(this.mField.x,this.mField.y,this.mField.width,this.mField.height);
      }

      public function set color(aColor:uint) : void
      {
         this.mFormat.color = aColor;
         this.ApplyFormat();
      }

      public function get color() : uint
      {
         return uint(this.mFormat.color);
      }

      public function set fontFamily(aFont:String) : void
      {
         this.mFormat.font = aFont;
         this.ApplyFormat();
      }

      public function get fontFamily() : String
      {
         return this.mFormat.font;
      }

      public function set fontSize(aSize:Number) : void
      {
         this.mFormat.size = aSize;
         this.ApplyFormat();
      }

      public function get fontSize() : Number
      {
         return Number(this.mFormat.size);
      }

      public function set textAlign(aAlign:String) : void
      {
         this.mFormat.align = aAlign == "center" ? TextFormatAlign.CENTER : (aAlign == "right" || aAlign == "end" ? TextFormatAlign.RIGHT : TextFormatAlign.LEFT);
         this.ApplyFormat();
      }

      public function set displayAsPassword(aValue:Boolean) : void
      {
         this.mField.displayAsPassword = aValue;
      }

      public function set editable(aValue:Boolean) : void
      {
         this.mField.type = aValue ? TextFieldType.INPUT : TextFieldType.DYNAMIC;
      }

      public function set maxChars(aValue:int) : void
      {
         this.mField.maxChars = aValue;
      }

      public function set restrict(aValue:String) : void
      {
         this.mField.restrict = aValue;
      }

      public function set text(aText:String) : void
      {
         this.mField.text = aText == null ? "" : aText;
      }

      public function get text() : String
      {
         return this.mField.text;
      }

      public function set visible(aValue:Boolean) : void
      {
         this.mField.visible = aValue;
      }

      public function get visible() : Boolean
      {
         return this.mField.visible;
      }

      public function get multiline() : Boolean
      {
         return this.mField.multiline;
      }

      public function get selectionActiveIndex() : int
      {
         return this.mField.selectionEndIndex;
      }

      public function get selectionAnchorIndex() : int
      {
         return this.mField.selectionBeginIndex;
      }

      public function assignFocus() : void
      {
         if(this.mField.stage != null)
         {
            this.mField.stage.focus = this.mField;
         }
         this.OnFocusIn(null);
      }

      public function selectRange(anchorIndex:int, activeIndex:int) : void
      {
         this.mField.setSelection(anchorIndex,activeIndex);
      }

      public function drawViewPortToBitmapData(aBitmap:BitmapData) : void
      {
         aBitmap.draw(this.mField);
      }

      private function ApplyFormat() : void
      {
         this.mField.defaultTextFormat = this.mFormat;
         this.mField.setTextFormat(this.mFormat);
      }
   }
}
