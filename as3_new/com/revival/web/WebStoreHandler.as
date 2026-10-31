package com.revival.web
{
   import com.frimastudio.mobile.apppurchase.data.ProductDetail;
   import com.frimastudio.mobile.apppurchase.enum.EAppPurchaseProduct;
   import com.frimastudio.mobile.apppurchase.event.StoreHandlerEvent;
   import com.frimastudio.mobile.apppurchase.handler.StoreHandler;
   import flash.utils.setTimeout;

   // Browser build only (as3_patches.py WEB_EDITS): the store without the Android billing extension. Same behaviour
   // as the APK's billing stub (tools/build_stub_anes.py): every product costs "Free" and every purchase succeeds at
   // once. No payment path exists.
   public class WebStoreHandler extends StoreHandler
   {
      public function WebStoreHandler()
      {
         super();
      }

      override public function Init() : void
      {
         setTimeout(OnInitcomplete,1);
      }

      override public function get IsSupported() : Boolean
      {
         return true;
      }

      override public function LoadProductDetail() : void
      {
         var product:ProductDetail = null;
         mProductDetailList = new Vector.<ProductDetail>();
         for each(var id:String in EAppPurchaseProduct.GetPurchaseIdList())
         {
            product = new ProductDetail();
            product.ProductId = id;
            product.Name = id;
            product.Description = "Free (private server)";
            product.Price = "Free";
            mProductDetailList.push(product);
         }
         setTimeout(dispatchEvent,1,new StoreHandlerEvent(StoreHandlerEvent.ITEM_DETAIL_RECEIVED));
      }

      override public function BuyProduct(aProductId:String) : void
      {
         var event:StoreHandlerEvent = new StoreHandlerEvent(StoreHandlerEvent.PURCHASE_COMPLETE);
         var product:ProductDetail = new ProductDetail();
         product.ProductId = aProductId;
         event.ProductList = new Vector.<ProductDetail>();
         event.ProductList.push(product);
         setTimeout(dispatchEvent,1,event);
      }
   }
}
