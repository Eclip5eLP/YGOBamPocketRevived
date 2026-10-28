#!/usr/bin/env python3
"""
Build work/game_adt_noext.apk from the REAL game using the official HARMAN ADT
(-target apk-captive-runtime -arch armv8). No DEX/lib grafting.

Inputs (read-only): input/ygo.apk
  - assets/MobileGame.swf (original, not work/MobileGame.swf which differs)
  - assets/config/**, assets/asset/**, assets/icons/** -> staged, passed to ADT so
    they land under assets/ in the output APK
  - assets/config/mmog.xml patched with tools/patch_apk.patch_mmog_xml()
  - assets/META-INF/AIR/application.xml -> descriptor, with:
      * <extensions> removed
      * the 7 ANE-dependent manifest components removed
      * android:usesCleartextTraffic="true" added on <application>
      * namespace / targetSdkVersion overridable from the CLI

Usage: python tools/build_game_adt.py [--ns 20.0] [--target-sdk N] [--extdir DIR] [--out work/game_adt_noext.apk]
"""

import argparse
import re
import shutil
import subprocess
import sys
import zipfile
import zlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))
from patch_apk import patch_mmog_xml  # noqa: E402

INPUT_APK = PROJECT_ROOT / "input" / "ygo.apk"
ADT_BAT = PROJECT_ROOT / "work" / "airsdk" / "bin" / "adt.bat"
KEYSTORE = PROJECT_ROOT / "work" / "debug.keystore"
BUILD_DIR = PROJECT_ROOT / "work" / "game_adt"
STAGE = BUILD_DIR / "stage"

STAGED_PREFIXES = ("assets/config/", "assets/asset/", "assets/icons/")
PUBLIC_KEY_XML = PROJECT_ROOT / "server" / "data" / "publickey.xml"

# Localization (.ace = zlib-compressed, strings length-prefixed): same-length text replacements
# for the BAM Pro popup price line (key bam_pro_price, EBamProLoc.as:18, BamProPopup.as:109).
LOCALIZATION_PATCHES = {
    "config/ace/resource/en/bam_pro.ace": [(b"ONLY $ 4.99 USD", b"FREE OF CHARGE!")],
    "config/ace/resource/en/localization_section.ace": [(b"ONLY $ 4.99 USD", b"FREE OF CHARGE!")],
    "config/ace/resource/fr/localization_section.ace": [(b"SEULEMENT $ 4.99 USD", b"TOTALEMENT GRATUIT !")],
}


def patch_ace(data: bytes, replacements) -> bytes:
    text = zlib.decompress(data)
    for old, new in replacements:
        assert len(old) == len(new) and text.count(old) == 1, (old, text.count(old))
        text = text.replace(old, new)
    return zlib.compress(text, 9)

# Components whose classes only exist in the ANE Java code (application.xml:40-61)
ANE_COMPONENT_PATTERNS = [
    r'<receiver\s+android:name="com\.google\.android\.gcm\.GCMBroadcastReceiver".*?</receiver>',
    r'<activity\s+android:name="com\.arellomobile\.android\.push\.PushWebview"\s*/>',
    r'<activity\s+android:name="com\.arellomobile\.android\.push\.MessageActivity"\s*/>',
    r'<activity\s+android:name="com\.arellomobile\.android\.push\.PushHandlerActivity"\s*/>',
    r'<activity\s+android:name="com\.pushwoosh\.nativeExtensions\.PushActivity">.*?</activity>',
    r'<service\s+android:name="com\.arellomobile\.android\.push\.PushGCMIntentService"\s*/>',
    r'<receiver\s+android:name="com\.arellomobile\.android\.push\.AlarmReceiver">\s*</receiver>',
]


def patch_descriptor(xml: str, ns: str, target_sdk: int, keep_extensions: bool = False, cutout: str = "",
                     app_id: str = "") -> str:
    if not keep_extensions:
        xml, n = re.subn(r"<extensions>.*?</extensions>", "", xml, flags=re.DOTALL)
        assert n == 1, "expected exactly one <extensions> block"
    for pat in ANE_COMPONENT_PATTERNS:
        xml, n = re.subn(pat, "", xml, flags=re.DOTALL)
        assert n == 1, f"component not found exactly once: {pat}"
    xml, n = re.subn(r'<application android:debuggable="false">',
                     '<application android:debuggable="false" android:usesCleartextTraffic="true">', xml)
    assert n == 1
    xml, n = re.subn(r'xmlns="http://ns\.adobe\.com/air/application/[0-9.]+"',
                     f'xmlns="http://ns.adobe.com/air/application/{ns}"', xml)
    assert n == 1
    # No Google Play Billing in this build (AndroidIAB is the free emulator from tools/build_stub_anes.py)
    xml, n = re.subn(r'\s*<uses-permission android:name="com\.android\.vending\.BILLING" />', "", xml)
    assert n == 1
    if cutout:
        # Main.as:199-208 sizes the viewport from Capabilities.screenResolution (full panel); with the
        # default cutout mode the window excludes the camera-cutout side, so the frame is cut off.
        xml, n = re.subn(r"</manifestAdditions>",
                         f"</manifestAdditions>\n\t\t<displayCutoutMode>{cutout}</displayCutoutMode>", xml)
        assert n == 1
    if app_id:
        # Test copy with its own (empty) app storage; Android package becomes "air." + app_id.
        # Also renames the C2D permission names that embed the package (application.xml:30-31).
        xml, n = re.subn(r"<id>com\.konami\.ygo</id>", f"<id>{app_id}</id>", xml)
        assert n == 1
        xml = xml.replace("air.com.konami.ygo.", f"air.{app_id}.").replace(
            '<category android:name="air.com.konami.ygo"/>', f'<category android:name="air.{app_id}"/>')
    if target_sdk:
        xml, n = re.subn(r'android:targetSdkVersion="\d+"', f'android:targetSdkVersion="{target_sdk}"', xml)
        assert n == 1
    return xml


def stage_files(host: str, swf: str = "") -> str:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    with zipfile.ZipFile(INPUT_APK) as z:
        desc = z.read("assets/META-INF/AIR/application.xml").decode("utf-8")
        # --swf: patched SWF from tools/patch_swf.py; default is the untouched original
        (STAGE / "MobileGame.swf").write_bytes(Path(swf).read_bytes() if swf else z.read("assets/MobileGame.swf"))
        count = 0
        for info in z.infolist():
            if info.is_dir() or not info.filename.startswith(STAGED_PREFIXES):
                continue
            rel = info.filename[len("assets/"):]
            data = z.read(info)
            if rel == "config/mmog.xml":
                data = patch_mmog_xml(data, host, 80)
            if rel == "config/publickey.xml":
                # our own key pair (tools/gen_rsa_key.py); the server holds the private key
                data = PUBLIC_KEY_XML.read_bytes()
            if rel in LOCALIZATION_PATCHES:
                data = patch_ace(data, LOCALIZATION_PATCHES[rel])
            out = STAGE / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
            count += 1
    print(f"Staged MobileGame.swf + {count} files under {STAGE}")
    return desc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ns", default="20.0", help="AIR descriptor namespace version")
    ap.add_argument("--target-sdk", type=int, default=0, help="override android:targetSdkVersion (0 = keep)")
    ap.add_argument("--host", default="ygo.eclip5e.com")
    ap.add_argument("--extdir", help="keep <extensions> and package the ANEs in this dir (e.g. work/stub_anes/out)")
    ap.add_argument("--cutout", default="", help="android displayCutoutMode (default/always/never/shortEdges)")
    ap.add_argument("--app-id", default="", help="override <id> for a side-by-side test install")
    ap.add_argument("--swf", default="", help="use this MobileGame.swf instead of the original")
    ap.add_argument("--out", default=str(PROJECT_ROOT / "work" / "game_adt_noext.apk"))
    args = ap.parse_args()

    desc = stage_files(args.host, args.swf)
    desc_out = BUILD_DIR / "application_game.xml"
    desc_out.write_text(patch_descriptor(desc, args.ns, args.target_sdk, keep_extensions=bool(args.extdir), cutout=args.cutout, app_id=args.app_id), encoding="utf-8")
    print(f"Descriptor written: {desc_out} (ns {args.ns})")

    cmd = [str(ADT_BAT), "-package", "-target", "apk-captive-runtime", "-arch", "armv8",
           "-storetype", "pkcs12", "-keystore", str(KEYSTORE), "-storepass", "android", "-keypass", "android",
           args.out, str(desc_out), "-C", str(STAGE), "MobileGame.swf", "config", "asset", "icons"]
    if args.extdir:
        cmd += ["-extdir", args.extdir]
    print("Running:", " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    print("ADT stdout:", res.stdout)
    print("ADT stderr:", res.stderr)
    print("ADT returncode:", res.returncode)
    sys.exit(res.returncode)


if __name__ == "__main__":
    main()
