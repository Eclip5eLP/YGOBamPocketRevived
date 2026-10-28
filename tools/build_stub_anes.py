#!/usr/bin/env python3
"""
Build no-op stub ANEs for the 4 extension IDs the game SWF uses, packaged by the
official ADT (-target ane, platform Android-ARM64). Java only, no native code.

Each stub registers every function name its AS3 wrapper calls (taken from the
wrapper sources in work/as3) and returns null for all of them, so
ExtensionContext.createExtensionContext() is non-null and call() never throws.

AS3 side: the original catalog.xml + library.swf from the input APK, zipped as
the SWC (a SWC is a zip of exactly those two files). The wrapper code is unchanged.

Output: work/stub_anes/out/<extension id>.ane
Usage: python tools/build_stub_anes.py [--ns 33.1]
"""

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_APK = PROJECT_ROOT / "input" / "ygo.apk"
SDK = PROJECT_ROOT / "work" / "airsdk"
ADT_BAT = SDK / "bin" / "adt.bat"
FRE_JAR = SDK / "lib" / "android" / "FlashRuntimeExtensions.jar"
KEYSTORE = PROJECT_ROOT / "work" / "debug.keystore"
WORK = PROJECT_ROOT / "work" / "stub_anes"

# Function names from `grep -o 'call("..."'` on each wrapper in work/as3/scripts, plus
# ffiLoadInventory (called via setTimeout(extContext.call, ...), AndroidIAB.as:406-409)
EXTENSIONS = {
    "com.frimastudio.FlurryAnalytics": ("flurry", [
        "EndSession", "EndTimedEvent", "LogError", "LogEvent", "LogPageView", "PauseBackgroundSession",
        "SetAge", "SetAppVersion", "SetBackgroundSessionEnabled", "SetCaptureUncaughtExceptions",
        "SetCrashReportingEnabled", "SetDebugLogEnabled", "SetEventLoggingEnabled", "SetGender",
        "SetLogLevel", "SetPushToken", "SetReportLocationEnabled", "SetSecureTransportEnabled",
        "SetSessionContinueSeconds", "SetSessionReportsOnCloseEnabled", "SetSessionReportsOnPauseEnabled",
        "SetShowErrorInLogEnabled", "SetUserID", "StartSession"]),
    "com.pushwoosh.PushNotification": ("pushwoosh", [
        "clearLocalNotification", "clearLocalNotifications", "getPushToken", "getPushwooshHWID",
        "onDeviceReady", "pause", "registerPush", "resume", "scheduleLocalNotification", "setBadgeNumber",
        "setBeaconBackgroundMode", "setEnableLed", "setIntTag", "setMultiNotificationMode",
        "setSimpleNotificationMode", "setSoundType", "setStringTag", "setVibrateType", "startBeaconPushes",
        "startGeoPushes", "stopBeaconPushes", "stopGeoPushes", "unregisterPush"]),
    "com.milkmangames.extensions.AndroidIAB": ("androidiab", [
        "ffiAreSubscriptionsSupported", "ffiConsumeItem", "ffiInitIAB", "ffiLoadInventory", "ffiPurchaseItem",
        "ffiShutdown", "ffiStartBillingService"]),
    "com.milkmangames.extensions.RateBox": ("ratebox", [
        "ffiAreRatingConditionsMet", "ffiDidRateCurrentVersion", "ffiIncrementEventCount", "ffiInitRateBox",
        "ffiOnLaunch", "ffiResetConditions", "ffiSetAutoPrompt", "ffiShowPrompt", "ffiUseTestMode"]),
}

JAVA_TEMPLATE = """package revival.anestub.{pkg};

import com.adobe.fre.FREContext;
import com.adobe.fre.FREExtension;
import com.adobe.fre.FREFunction;
import com.adobe.fre.FREObject;
import java.util.HashMap;
import java.util.Map;

/**
 * No-op stub for {ext_id}: every function logs its name (System.out -> logcat tag System.out)
 * and returns null. Static nested classes only: javac 21 writes nameless MethodParameters
 * entries for capturing anonymous classes, which crashes ADT's d8.
 */
public class StubExtension implements FREExtension {{
    static final String[] NAMES = {{ {names} }};

    static void log(String m) {{ System.out.println("ANESTUB " + m); }}

    static final class StubFunction implements FREFunction {{
        private final String name;
        StubFunction(String name) {{ this.name = name; }}
        public FREObject call(FREContext ctx, FREObject[] args) {{
            log("{ext_id}." + name);
            return null;
        }}
    }}

    static final class StubContext extends FREContext {{
        public Map<String, FREFunction> getFunctions() {{
            Map<String, FREFunction> m = new HashMap<String, FREFunction>();
            for (String n : NAMES) {{
                m.put(n, new StubFunction(n));
            }}
            return m;
        }}
        public void dispose() {{ }}
    }}

    public void initialize() {{ log("{ext_id} initialize"); }}

    public FREContext createContext(String type) {{
        log("{ext_id} createContext");
        return new StubContext();
    }}

    public void dispose() {{ }}
}}
"""

# AndroidIAB: free billing emulator instead of a no-op. This APK contains no Google Play Billing
# code at all (the original IAB Java was never packaged), so nothing can ever be charged: every
# purchase simply "succeeds" here and the game grants the item itself (AppPurchaseHandlerImpl.as:124-160).
# Status codes / JSON shapes the AS3 wrapper parses: AndroidIAB.as:273-405 (onExtStatus) and
# :419-445 (decodePurchaseObject: itemType, orderId, sku, purchaseTime, developerPayload, token,
# signature, json; decodeAndroidItem: itemType, price, title, description). Request ids: 10 inventory,
# 20 item details (AndroidIAB.as:39-41). Placeholders: {ext_id}, {names}.
IAB_JAVA = """package revival.anestub.androidiab;

import com.adobe.fre.FREContext;
import com.adobe.fre.FREExtension;
import com.adobe.fre.FREFunction;
import com.adobe.fre.FREObject;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;

/** Free billing emulator for {ext_id}. No payment path exists. */
public class StubExtension implements FREExtension {
    static final String[] NAMES = { {names} };
    /** Purchased but not yet consumed (BAM Pro stays owned for the process lifetime). */
    static final Set<String> OWNED = Collections.synchronizedSet(new LinkedHashSet<String>());

    static void log(String m) { System.out.println("ANESTUB " + m); }

    static String q(String s) {
        if (s == null) return "\\"\\"";
        return "\\"" + s.replace("\\\\", "\\\\\\\\").replace("\\"", "\\\\\\"") + "\\"";
    }

    static String purchaseJson(String sku) {
        long t = System.currentTimeMillis();
        return "{\\"itemType\\":\\"inapp\\",\\"orderId\\":" + q("REVIVAL-FREE." + t) + ",\\"sku\\":" + q(sku)
            + ",\\"purchaseTime\\":" + t + ",\\"developerPayload\\":\\"\\",\\"token\\":" + q("revival-free-" + sku + "-" + t)
            + ",\\"signature\\":\\"\\",\\"json\\":\\"{}\\"}";
    }

    static String str(FREObject[] a, int i) {
        try { return a != null && a.length > i && a[i] != null ? a[i].getAsString() : null; } catch (Exception e) { return null; }
    }

    static boolean bool(FREObject[] a, int i) {
        try { return a != null && a.length > i && a[i] != null && a[i].getAsBool(); } catch (Exception e) { return false; }
    }

    static int integer(FREObject[] a, int i) {
        try { return a != null && a.length > i && a[i] != null ? a[i].getAsInt() : 0; } catch (Exception e) { return 0; }
    }

    static void send(FREContext ctx, String code, String level) {
        log("{ext_id} dispatch " + code + " " + level);
        ctx.dispatchStatusEventAsync(code, level);
    }

    static final class Fn implements FREFunction {
        private final String name;
        Fn(String name) { this.name = name; }

        public FREObject call(FREContext ctx, FREObject[] args) {
            log("{ext_id}." + name);
            if (name.equals("ffiStartBillingService")) {
                send(ctx, "BILLING_CONNECTION_READY", "{}");
            } else if (name.equals("ffiLoadInventory")) {
                boolean withDetails = bool(args, 0);
                String itemList = str(args, 1);
                int requestId = integer(args, 2);
                StringBuilder purchases = new StringBuilder();
                synchronized (OWNED) {
                    for (String sku : OWNED) {
                        if (purchases.length() > 0) purchases.append(',');
                        purchases.append(q(sku)).append(':').append(purchaseJson(sku));
                    }
                }
                StringBuilder skus = new StringBuilder();
                if (withDetails && itemList != null) {
                    for (String sku : itemList.split(",")) {
                        if (sku.length() == 0) continue;
                        if (skus.length() > 0) skus.append(',');
                        skus.append(q(sku)).append(":{\\"itemType\\":\\"inapp\\",\\"price\\":\\"Free\\",\\"title\\":")
                            .append(q(sku)).append(",\\"description\\":\\"Free (private server)\\"}");
                    }
                }
                send(ctx, "INVENTORY_LOADED", "{\\"requestId\\":" + requestId + ",\\"purchases\\":{" + purchases
                    + "},\\"skus\\":{" + skus + "}}");
            } else if (name.equals("ffiPurchaseItem")) {
                String sku = str(args, 0);
                OWNED.add(sku);
                send(ctx, "PURCHASE_SUCCEEDED", "{\\"requestId\\":0,\\"purchase\\":" + purchaseJson(sku) + "}");
            } else if (name.equals("ffiConsumeItem")) {
                String sku = str(args, 0);
                OWNED.remove(sku);
                send(ctx, "CONSUME_SUCCEEDED", "{\\"requestId\\":0,\\"sku\\":" + q(sku) + ",\\"purchase\\":"
                    + purchaseJson(sku) + "}");
            }
            return null;
        }
    }

    static final class Ctx extends FREContext {
        public Map<String, FREFunction> getFunctions() {
            Map<String, FREFunction> m = new HashMap<String, FREFunction>();
            for (String n : NAMES) {
                m.put(n, new Fn(n));
            }
            return m;
        }
        public void dispose() { }
    }

    public void initialize() { log("{ext_id} initialize (free billing emulator)"); }

    public FREContext createContext(String type) {
        log("{ext_id} createContext");
        return new Ctx();
    }

    public void dispose() { }
}
"""

EXTENSION_XML = """<?xml version="1.0" encoding="utf-8"?>
<extension xmlns="http://ns.adobe.com/air/extension/{ns}">
  <id>{ext_id}</id>
  <versionNumber>1.0.0</versionNumber>
  <platforms>
    <platform name="Android-ARM64">
      <applicationDeployment>
        <nativeLibrary>stub.jar</nativeLibrary>
        <initializer>revival.anestub.{pkg}.StubExtension</initializer>
        <finalizer>revival.anestub.{pkg}.StubExtension</finalizer>
      </applicationDeployment>
    </platform>
  </platforms>
</extension>
"""


def run(cmd, **kw):
    print(">", " ".join(str(c) for c in cmd))
    res = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)
    print("  rc", res.returncode, res.stdout.strip(), res.stderr.strip())
    if res.returncode != 0:
        sys.exit(f"failed: {cmd[0]}")
    return res


def build_one(ext_id, pkg, names, ns, apk):
    d = WORK / pkg
    if d.exists():
        shutil.rmtree(d)
    src = d / "src" / "revival" / "anestub" / pkg
    src.mkdir(parents=True)
    classes = d / "classes"
    plat = d / "Android-ARM64"
    classes.mkdir()
    plat.mkdir()

    names_java = ", ".join(f'"{n}"' for n in names)
    if ext_id == "com.milkmangames.extensions.AndroidIAB":
        java = IAB_JAVA.replace("{ext_id}", ext_id).replace("{names}", names_java)
    else:
        java = JAVA_TEMPLATE.format(pkg=pkg, ext_id=ext_id, names=names_java)
    (src / "StubExtension.java").write_text(java, encoding="utf-8")
    run(["javac", "--release", "8", "-nowarn", "-cp", FRE_JAR, "-d", classes,
         src / "StubExtension.java"])
    with zipfile.ZipFile(plat / "stub.jar", "w", zipfile.ZIP_DEFLATED) as jar:
        for f in classes.rglob("*.class"):
            jar.write(f, f.relative_to(classes).as_posix())

    root = f"assets/META-INF/AIR/extensions/{ext_id}/"
    lib_swf = apk.read(root + "library.swf")
    (plat / "library.swf").write_bytes(lib_swf)
    with zipfile.ZipFile(d / "library.swc", "w", zipfile.ZIP_DEFLATED) as swc:
        swc.writestr("catalog.xml", apk.read(root + "catalog.xml"))
        swc.writestr("library.swf", lib_swf)

    (d / "extension.xml").write_text(EXTENSION_XML.format(ns=ns, ext_id=ext_id, pkg=pkg), encoding="utf-8")
    out = WORK / "out" / f"{ext_id}.ane"
    out.parent.mkdir(exist_ok=True)
    # unsigned: ADT rejects the self-signed debug key for ANEs ("not an X509 code-signing certificate")
    run([ADT_BAT, "-package", "-target", "ane", out, d / "extension.xml", "-swc", d / "library.swc",
         "-platform", "Android-ARM64", "-C", plat, "library.swf", "stub.jar"])
    print(f"built {out} ({out.stat().st_size} bytes)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ns", default="33.1", help="extension descriptor namespace version")
    args = ap.parse_args()
    with zipfile.ZipFile(INPUT_APK) as apk:
        for ext_id, (pkg, names) in EXTENSIONS.items():
            build_one(ext_id, pkg, names, args.ns, apk)


if __name__ == "__main__":
    main()
