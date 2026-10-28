#!/usr/bin/env python3
"""
Yu-Gi-Oh! BAM Pocket APK Patcher & Modern Android Compatibility Signer
Patches:
- assets/config/mmog.xml (custom server host/port for revival server)
- AndroidManifest.xml (targetSdkVersion patched to 28 to remove 'built for older devices' prompt)
- assets/META-INF/AIR/application.xml (targetSdkVersion=28, usesCleartextTraffic=true)
- Bundles Adobe AIR captive runtime (classes2.dex + libairruntime.so) if --air-runtime provided
- Removes legacy META-INF signatures
- Signs with jarsigner (or apksigner)
- 4-byte zipaligns all stored entries

Citations:
- EngineServerCom.as:255-256: Hardcodes HTTP port 80 for serverUrl (HTTP mode)
- EngineServerCom.as:409-413: Connects using ServerURLParser results
- ServerComHTTP.as:249-251: Appends port to server URL
- ServerURLParser.as:18-23: Splits pvpServerUrl by '~' into [ServerUrl, ServerPort, PolicyPort]
- YGOMPvPLoginImpl.as:266-267: Connects to pvpServerUrl using ServerURLParser
- Android 14 Policy: minInstallableTargetSdkVersion = 23
- Android 15 Policy: minInstallableTargetSdkVersion = 24
- Android DeprecatedTargetSdkVersionDialog: triggered when targetSdkVersion < ro.build.version.min_supported_target_sdk (28). Bypassed by setting targetSdkVersion to 28.
- AppEntry.as / AppEntry.java (classes.dex):
  - loadCaptiveRuntimeClasses(): Checks Class.forName("com.adobe.air.AndroidActivityWrapper"). Bypasses runtime check when bundled.
  - isRuntimeInstalled(): Checks PackageManager for "com.adobe.air".
"""

import argparse
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import zipfile

try:
    from tools.patch_exit_hook import apply_exit_hook_to_bytes
except ImportError:
    try:
        from patch_exit_hook import apply_exit_hook_to_bytes
    except ImportError:
        apply_exit_hook_to_bytes = None

# Python >= 3.8 check
if sys.version_info < (3, 8):
    sys.exit("Error: Python 3.8 or higher is required.")

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def find_tool(tool_name: str) -> str:
    """Finds an executable tool on PATH or common Android/Java directories."""
    found = shutil.which(tool_name)
    if found:
        return found

    if sys.platform == "win32":
        for ext in [".exe", ".bat", ".cmd"]:
            found = shutil.which(f"{tool_name}{ext}")
            if found:
                return found

    home = Path.home()
    sdk_candidates = [
        os.environ.get("ANDROID_HOME"),
        os.environ.get("ANDROID_SDK_ROOT"),
        str(home / "AppData" / "Local" / "Android" / "Sdk"),
        str(home / "Android" / "Sdk"),
        "/usr/lib/android-sdk",
    ]
    for sdk_path in sdk_candidates:
        if not sdk_path or not os.path.isdir(sdk_path):
            continue
        build_tools_dir = Path(sdk_path) / "build-tools"
        if build_tools_dir.is_dir():
            for version_dir in sorted(build_tools_dir.iterdir(), reverse=True):
                if version_dir.is_dir():
                    candidate = version_dir / tool_name
                    if candidate.is_file():
                        return str(candidate)
                    if sys.platform == "win32":
                        for ext in [".exe", ".bat", ".cmd"]:
                            cand_ext = version_dir / f"{tool_name}{ext}"
                            if cand_ext.is_file():
                                return str(cand_ext)

    # For keytool / jarsigner, check JAVA_HOME or Adoptium / JDK paths
    if tool_name in ("keytool", "jarsigner"):
        java_home = os.environ.get("JAVA_HOME")
        if java_home:
            cand = Path(java_home) / "bin" / (f"{tool_name}.exe" if sys.platform == "win32" else tool_name)
            if cand.is_file():
                return str(cand)
        if sys.platform == "win32":
            prog_files = Path("C:/Program Files")
            if prog_files.is_dir():
                for jdk_cand in prog_files.glob(f"**/{tool_name}.exe"):
                    return str(jdk_cand)

    return ""


def patch_mmog_xml(xml_bytes: bytes, host: str, port: int = 80) -> bytes:
    """
    Patches serverUrl, pvpServerUrl, and openGraphServerUrl in mmog.xml.
    Follows:
    - ServerURLParser.as:19-22: Splits pvpServerUrl by '~'
    - EngineServerCom.as:255-256: Hardcodes port 80 for HTTP serverUrl
    - ServerComHTTP.as:249-251: Replaces URL host with host:port
    """
    xml_text = xml_bytes.decode("utf-8")

    if port == 80:
        http_server_url = f"http://{host}/facebook/proxy.html"
        pvp_server_url = f"http://{host}/facebook/proxy.html~80~844"
        reporting_server_url = f"http://{host}/facebook/proxy.html"
        opengraph_server_url = f"http://{host}"
    else:
        http_server_url = f"http://{host}:{port}/facebook/proxy.html"
        pvp_server_url = f"http://{host}/facebook/proxy.html~{port}~844"
        reporting_server_url = f"http://{host}:{port}/facebook/proxy.html"
        opengraph_server_url = f"http://{host}:{port}"

    # 1. Update <http> section
    def replace_http(m):
        block = m.group(0)
        block = re.sub(
            r'(<var\s+name=["\']serverUrl["\']\s+value=["\'])[^"\']*(["\'])',
            rf'\g<1>{http_server_url}\g<2>',
            block,
            count=1
        )
        block = re.sub(
            r'(<var\s+name=["\']pvpServerUrl["\']\s+value=["\'])[^"\']*(["\'])',
            rf'\g<1>{pvp_server_url}\g<2>',
            block,
            count=1
        )
        return block

    xml_text = re.sub(r'<http>.*?</http>', replace_http, xml_text, flags=re.DOTALL)

    # 2. Update <reporting> section
    def replace_reporting(m):
        block = m.group(0)
        block = re.sub(
            r'(<var\s+name=["\']serverUrl["\']\s+value=["\'])[^"\']*(["\'])',
            rf'\g<1>{reporting_server_url}\g<2>',
            block,
            count=1
        )
        return block

    xml_text = re.sub(r'<reporting>.*?</reporting>', replace_reporting, xml_text, flags=re.DOTALL)

    # 3. Update <facebook> openGraphServerUrl
    xml_text = re.sub(
        r'(<var\s+name=["\']openGraphServerUrl["\']\s+value=["\'])[^"\']*(["\'])',
        rf'\g<1>{opengraph_server_url}\g<2>',
        xml_text,
        count=1
    )

    return xml_text.encode("utf-8")


def patch_axml_target_sdk(axml_bytes: bytes, new_target_sdk: int = 28) -> bytes:
    """
    Patches targetSdkVersion in Android binary XML (AXML).
    Bypasses Android 14+ and Android 15+ minimum installable target SDK block (API 24+ required).
    Removes 'built for older devices' prompt (requires API 28+).
    """
    axml = bytearray(axml_bytes)
    if len(axml) < 36:
        return axml_bytes

    # Parse AXML String Pool
    header_type, header_size, chunk_size = struct.unpack('<HHI', axml[8:16])
    string_count, style_count, flags, strings_start, styles_start = struct.unpack('<IIIII', axml[16:36])
    offsets = struct.unpack(f'<{string_count}I', axml[36:36 + 4 * string_count])
    str_data = axml[8 + strings_start:]
    strings = []
    for off in offsets:
        length = struct.unpack('<H', str_data[off:off + 2])[0]
        s = str_data[off + 2:off + 2 + length * 2].decode('utf-16le', errors='ignore')
        strings.append(s)

    if 'targetSdkVersion' not in strings:
        print("Warning: targetSdkVersion not found in AXML string pool.")
        return axml_bytes

    target_sdk_idx = strings.index('targetSdkVersion') if 'targetSdkVersion' in strings else -1
    debuggable_idx = strings.index('debuggable') if 'debuggable' in strings else -1

    # Traverse AXML chunks for START_TAG containing targetSdkVersion / debuggable attributes
    pos = 8
    patched = False
    while pos < len(axml) - 8:
        tag, size = struct.unpack('<II', axml[pos:pos + 8])
        if tag == 0x00100102:  # START_TAG
            attr_count = struct.unpack('<H', axml[pos + 28:pos + 30])[0]
            attr_pos = pos + 36
            for _ in range(attr_count):
                aname = struct.unpack('<I', axml[attr_pos + 4:attr_pos + 8])[0]
                if aname == target_sdk_idx:
                    old_val = struct.unpack('<i', axml[attr_pos + 16:attr_pos + 20])[0]
                    struct.pack_into('<i', axml, attr_pos + 16, new_target_sdk)
                    patched = True
                    print(f"Patched AndroidManifest.xml targetSdkVersion: {old_val} -> {new_target_sdk}")
                elif aname == debuggable_idx:
                    old_val = struct.unpack('<i', axml[attr_pos + 16:attr_pos + 20])[0]
                    struct.pack_into('<i', axml, attr_pos + 16, 0)  # 0 = false (avoids 16KB PageSizeMismatchDialog)
                    print(f"Patched AndroidManifest.xml debuggable: {old_val} -> 0 (false)")
                attr_pos += 20
        pos += size

    if not patched:
        print("Warning: targetSdkVersion attribute not found in uses-sdk tag.")
    return bytes(axml)


def patch_application_xml_target_sdk(app_xml_bytes: bytes, new_target_sdk: int = 28) -> bytes:
    """Patches targetSdkVersion and usesCleartextTraffic in Adobe AIR application.xml."""
    text = app_xml_bytes.decode("utf-8")
    new_text = re.sub(
        r'android:targetSdkVersion=["\']\d+["\']',
        f'android:targetSdkVersion="{new_target_sdk}"',
        text
    )
    if 'android:usesCleartextTraffic' not in new_text:
        # Must patch the inner <application android:debuggable="..."> tag inside <manifestAdditions>,
        # NOT the root <application xmlns="..."> tag which lacks the android: namespace declaration!
        new_text = re.sub(
            r'<application\s+(android:debuggable)',
            r'<application android:usesCleartextTraffic="true" \1',
            new_text,
            count=1
        )
    if new_text != text:
        print(f"Patched assets/META-INF/AIR/application.xml (targetSdkVersion={new_target_sdk}, usesCleartextTraffic=true)")
    return new_text.encode("utf-8")


def patch_ane_extension_xml(xml_bytes: bytes) -> bytes:
    """
    Patches ANE extension.xml files to add Android-ARM64 platform support.
    Duplicates the Android-ARM platform block for Android-ARM64.
    """
    xml_text = xml_bytes.decode("utf-8")
    if 'name="Android-ARM64"' in xml_text or "name='Android-ARM64'" in xml_text:
        return xml_bytes
    pattern = r'(<platform\s+name=["\']Android-ARM["\']>.*?</platform>)'
    def repl(m):
        arm_block = m.group(1)
        arm64_block = arm_block.replace('name="Android-ARM"', 'name="Android-ARM64"').replace("name='Android-ARM'", "name='Android-ARM64'")
        return f"{arm_block}\n    {arm64_block}"
    new_text = re.sub(pattern, repl, xml_text, flags=re.DOTALL)
    return new_text.encode("utf-8")


def bundle_air_runtime(out_zip: zipfile.ZipFile, air_runtime_path: str, exit_hook: bool = False) -> dict:
    """
    Bundles Adobe AIR runtime into the APK for captive runtime execution.
    Follows AppEntry.as / AppEntry.java (classes.dex):
    - loadCaptiveRuntimeClasses(): checks for com.adobe.air.AndroidActivityWrapper
    - Packages AIR classes as classes2.dex (Android Multidex)
    - Injects libairruntime.so native engine
    - Injects assets/Adobe AIR/ support files
    """
    bundled = {"dex": False, "libs": [], "assets": []}
    air_path = Path(air_runtime_path)
    if not air_path.exists():
        raise FileNotFoundError(f"Adobe AIR runtime not found: {air_runtime_path}")

    print(f"\nBundling Adobe AIR captive runtime from: {air_path}")
    if air_path.is_file() and air_path.suffix.lower() in (".apk", ".zip"):
        with zipfile.ZipFile(air_path, "r") as air_zip:
            for item in air_zip.infolist():
                name = item.filename
                # 1. Classes: Add classes.dex from runtime as classes2.dex
                if name == "classes.dex":
                    dex_data = air_zip.read(name)
                    new_item = zipfile.ZipInfo("classes2.dex", item.date_time)
                    new_item.compress_type = item.compress_type
                    out_zip.writestr(new_item, dex_data)
                    bundled["dex"] = True
                    print("  Injected classes2.dex (Adobe AIR runtime classes)")

                # 2. Native runtime libraries
                elif name.startswith("lib/") and name.endswith(".so"):
                    so_data = air_zip.read(name)
                    if exit_hook and name == "lib/arm64-v8a/libCore.so":
                        if apply_exit_hook_to_bytes is None:
                            raise RuntimeError("patch_exit_hook module not available to apply exit hook")
                        so_data = apply_exit_hook_to_bytes(so_data)
                        print("  Applied exit-suppression hook to lib/arm64-v8a/libCore.so")
                    new_item = zipfile.ZipInfo(name, item.date_time)
                    new_item.compress_type = zipfile.ZIP_STORED
                    out_zip.writestr(new_item, so_data)
                    bundled["libs"].append(name)
                    print(f"  Injected native library: {name}")

                # 3. Adobe AIR assets
                elif name.startswith("assets/Adobe AIR/"):
                    asset_data = air_zip.read(name)
                    new_item = zipfile.ZipInfo(name, item.date_time)
                    new_item.compress_type = item.compress_type
                    out_zip.writestr(new_item, asset_data)
                    bundled["assets"].append(name)
                    print(f"  Injected asset: {name}")

    elif air_path.is_dir():
        dex_file = air_path / "classes.dex"
        if dex_file.is_file():
            out_zip.writestr("classes2.dex", dex_file.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
            bundled["dex"] = True
            print("  Injected classes2.dex from directory")

        lib_dir = air_path / "lib"
        if lib_dir.is_dir():
            for so_path in lib_dir.rglob("*.so"):
                so_data = so_path.read_bytes()
                if not so_data.startswith(b"\x7fELF"):
                    print(f"  Skipping non-ELF stub: {so_path.name}")
                    continue
                rel_path = f"lib/{so_path.relative_to(lib_dir).as_posix()}"
                if exit_hook and rel_path == "lib/arm64-v8a/libCore.so":
                    if apply_exit_hook_to_bytes is None:
                        raise RuntimeError("patch_exit_hook module not available to apply exit hook")
                    so_data = apply_exit_hook_to_bytes(so_data)
                    print("  Applied exit-suppression hook to lib/arm64-v8a/libCore.so")
                out_zip.writestr(rel_path, so_data, compress_type=zipfile.ZIP_STORED)
                bundled["libs"].append(rel_path)
                print(f"  Injected native library: {rel_path} ({len(so_data)} bytes)")

        assets_dir = air_path / "assets"
        if assets_dir.is_dir():
            for a_path in assets_dir.rglob("*"):
                if a_path.is_file():
                    rel_path = f"assets/{a_path.relative_to(assets_dir).as_posix()}"
                    out_zip.writestr(rel_path, a_path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
                    bundled["assets"].append(rel_path)
                    print(f"  Injected asset: {rel_path}")

    return bundled


def repack_apk(input_apk: str, output_unaligned: str, host: str, port: int, target_sdk: int = 28, air_runtime: str = None, exit_hook: bool = False, custom_swf: str = None) -> bool:
    """
    Rewrites the APK zip archive:
    - Retains exact compression method for every entry
    - Strips old META-INF signature files (*.SF, *.RSA, *.DSA, MANIFEST.MF)
    - Strips legacy 32-bit placeholder libNativeABI.so if captive runtime not bundled
    - Bundles Adobe AIR runtime if air_runtime path provided
    - Patches assets/config/mmog.xml
    - Patches AndroidManifest.xml (targetSdkVersion)
    - Patches assets/META-INF/AIR/application.xml (targetSdkVersion, usesCleartextTraffic)
    """
    print(f"Reading input APK: {input_apk}")
    print(f"Repacking entries into: {output_unaligned}")

    stripped_signatures = []
    patched_count = 0
    copied_count = 0

    with zipfile.ZipFile(input_apk, "r") as in_zip:
        with zipfile.ZipFile(output_unaligned, "w") as out_zip:
            for item in in_zip.infolist():
                fname = item.filename

                # Strip old META-INF signature files
                if fname.startswith("META-INF/") and (
                    fname.endswith((".SF", ".RSA", ".DSA")) or fname == "META-INF/MANIFEST.MF"
                ):
                    stripped_signatures.append(fname)
                    continue

                # Strip legacy 32-bit placeholder stub (lib/armeabi-v7a/libNativeABI.so)
                # Prevents INSTALL_FAILED_NO_MATCHING_ABIS on modern 64-bit-only devices (Pixel 7/8/9/10).
                # libNativeABI.so is an obsolete store marker never loaded by classes.dex.
                if fname.startswith("lib/"):
                    print(f"Stripping legacy native ABI marker: {fname}")
                    continue

                # Read raw entry bytes
                data = in_zip.read(fname)

                # Custom SWF replacement (for diagnostics / control tests)
                if custom_swf and fname == "assets/MobileGame.swf":
                    print(f"Replacing {fname} with custom SWF: {custom_swf}...")
                    data = Path(custom_swf).read_bytes()
                    patched_count += 1

                # Patch mmog.xml
                if fname == "assets/config/mmog.xml":
                    print(f"Patching {fname} (host: {host}, port: {port})...")
                    data = patch_mmog_xml(data, host, port)
                    patched_count += 1

                # Patch binary AndroidManifest.xml
                elif fname == "AndroidManifest.xml":
                    print(f"Patching {fname} (targetSdkVersion: {target_sdk})...")
                    data = patch_axml_target_sdk(data, target_sdk)
                    patched_count += 1

                # Patch AIR application.xml
                elif fname == "assets/META-INF/AIR/application.xml":
                    print(f"Patching {fname} (targetSdkVersion: {target_sdk})...")
                    data = patch_application_xml_target_sdk(data, target_sdk)
                    patched_count += 1
                    # Also inject root descriptor META-INF/AIR/application.xml for captive runtime
                    root_item = zipfile.ZipInfo("META-INF/AIR/application.xml", item.date_time)
                    root_item.compress_type = item.compress_type
                    out_zip.writestr(root_item, data)
                    copied_count += 1
                    print("  Injected root descriptor: META-INF/AIR/application.xml")

                # Patch ANE extension.xml for Android-ARM64 compatibility
                elif "extensions/" in fname and fname.endswith("extension.xml"):
                    print(f"Patching ANE {fname} for Android-ARM64 support...")
                    data = patch_ane_extension_xml(data)
                    patched_count += 1

                # Write to output preserving entry name and compression method
                out_zip.writestr(item, data, compress_type=item.compress_type)
                copied_count += 1

                # If captive runtime is enabled, mirror assets/ entries to APK root
                # libCore.so inspects the APK ZIP directly and expects root paths (e.g. MobileGame.swf, META-INF/AIR/extensions/...)
                if air_runtime and fname.startswith("assets/"):
                    root_name = fname[len("assets/"):]
                    if root_name and root_name != "META-INF/AIR/application.xml":
                        root_item = zipfile.ZipInfo(root_name, item.date_time)
                        root_item.compress_type = item.compress_type
                        out_zip.writestr(root_item, data)
                        copied_count += 1

                # Duplicate ANE Android-ARM assets to Android-ARM64 for 64-bit devices
                if "extensions/" in fname and "/META-INF/ANE/Android-ARM/" in fname:
                    arm64_fname = fname.replace("/META-INF/ANE/Android-ARM/", "/META-INF/ANE/Android-ARM64/")
                    new_item = zipfile.ZipInfo(arm64_fname, item.date_time)
                    new_item.compress_type = item.compress_type
                    out_zip.writestr(new_item, data)
                    copied_count += 1
                    print(f"  Duplicated ANE platform entry: {arm64_fname}")
                    if air_runtime and arm64_fname.startswith("assets/"):
                        root_arm64 = arm64_fname[len("assets/"):]
                        root_item64 = zipfile.ZipInfo(root_arm64, item.date_time)
                        root_item64.compress_type = item.compress_type
                        out_zip.writestr(root_item64, data)
                        copied_count += 1

            # Bundle captive runtime if provided
            if air_runtime:
                bundle_air_runtime(out_zip, air_runtime, exit_hook=exit_hook)

    print(f"Repack complete: {copied_count} entries copied, {patched_count} files patched.")
    print(f"Stripped {len(stripped_signatures)} legacy signature files: {stripped_signatures}")
    return patched_count >= 1


def zipalign_apk(in_apk_path: str, out_apk_path: str, alignment: int = 4) -> int:
    """
    Natively 4-byte zipaligns stored (uncompressed) entries in an APK archive.
    Pads local header extra fields so stored file data starts on 4-byte boundaries.
    """
    stored_count = 0
    with zipfile.ZipFile(in_apk_path, "r") as in_zf, zipfile.ZipFile(out_apk_path, "w") as out_zf:
        for info in in_zf.infolist():
            data = in_zf.read(info)
            new_info = zipfile.ZipInfo(info.filename, info.date_time)
            new_info.compress_type = info.compress_type
            new_info.comment = info.comment
            new_info.extra = info.extra

            if new_info.compress_type == zipfile.ZIP_STORED:
                stored_count += 1
                curr_pos = out_zf.fp.tell()
                header_len = 30 + len(new_info.filename.encode("utf-8")) + len(new_info.extra)
                data_offset = curr_pos + header_len
                # Native shared libraries (.so) must be page-aligned (16384 bytes for 16KB/4KB kernel page size)
                align = 16384 if new_info.filename.endswith(".so") else alignment
                pad = (align - (data_offset % align)) % align
                if pad > 0:
                    new_info.extra = new_info.extra + (b"\x00" * pad)

            out_zf.writestr(new_info, data)
    return stored_count


def verify_alignment(apk_path: str, alignment: int = 4) -> bool:
    """Verifies that all stored entries in an APK are 4-byte aligned."""
    with open(apk_path, "rb") as f:
        data = f.read()

    pos = 0
    misaligned = 0
    total_stored = 0
    while pos < len(data) - 4:
        sig = struct.unpack("<I", data[pos:pos + 4])[0]
        if sig == 0x04034b50:
            ver, flag, method, time, date, crc, csize, usize, fn_len, extra_len = struct.unpack("<HHHHHIIIHH", data[pos + 4:pos + 30])
            fn = data[pos + 30:pos + 30 + fn_len].decode("utf-8", errors="ignore")
            data_offset = pos + 30 + fn_len + extra_len
            if method == 0:
                total_stored += 1
                if data_offset % alignment != 0:
                    misaligned += 1
            pos = data_offset + csize
        elif sig == 0x02014b50:
            break
        else:
            pos += 1

    return misaligned == 0 and total_stored > 0


def main():
    parser = argparse.ArgumentParser(description="Yu-Gi-Oh! BAM Pocket APK Patcher & Modern Android Compatibility Signer")
    parser.add_argument("--host", default="ygo.eclip5e.com", help="Target server hostname (default: ygo.eclip5e.com)")
    parser.add_argument("--port", type=int, default=80, help="Target server port (default: 80)")
    parser.add_argument("--target-sdk", type=int, default=28,
                        help="targetSdkVersion to set in AndroidManifest.xml (default: 28 to remove 'built for older devices' prompt)")
    parser.add_argument("--air-runtime", default=None,
                        help="Path to Adobe AIR APK or SDK directory to bundle captive runtime")
    parser.add_argument("--custom-swf", default=None,
                        help="Path to custom SWF to replace assets/MobileGame.swf")
    parser.add_argument("--exit-hook", action="store_true",
                        help="Inject NativeApplication.exit suppression hook into captive runtime libCore.so")
    parser.add_argument("--no-captive", action="store_true",
                        help="Force shared runtime (revert captive runtime bundling)")
    parser.add_argument("--input-apk", default=str(PROJECT_ROOT / "input" / "ygo.apk"),
                        help="Path to original input APK (default: input/ygo.apk)")
    parser.add_argument("--output-apk", default=str(PROJECT_ROOT / "work" / "ygo_patched.apk"),
                        help="Path to final patched and signed APK (default: work/ygo_patched.apk)")
    parser.add_argument("--keystore", default=str(PROJECT_ROOT / "work" / "debug.keystore"),
                        help="Path to keystore file (default: work/debug.keystore)")
    parser.add_argument("--key-alias", default="androiddebugkey", help="Keystore key alias (default: androiddebugkey)")
    parser.add_argument("--store-pass", default="android", help="Keystore password (default: android)")
    parser.add_argument("--key-pass", default="android", help="Key password (default: android)")

    args = parser.parse_args()

    input_apk = os.path.abspath(args.input_apk)
    if not os.path.isfile(input_apk):
        sys.exit(f"Error: Input APK not found: {input_apk}")

    output_apk = os.path.abspath(args.output_apk)
    os.makedirs(os.path.dirname(output_apk), exist_ok=True)

    unaligned_apk = output_apk + ".unaligned.apk"
    temp_signed = output_apk + ".signed_tmp.apk"

    # Step 1: Repack ZIP with patched mmog.xml, AndroidManifest.xml, and stripped legacy META-INF
    air_runtime = None if args.no_captive else args.air_runtime
    if not air_runtime and not args.no_captive:
        default_runtime = PROJECT_ROOT / "work" / "air_runtime"
        if (default_runtime / "classes.dex").is_file():
            air_runtime = str(default_runtime)
    success = repack_apk(input_apk, unaligned_apk, args.host, args.port, target_sdk=args.target_sdk, air_runtime=air_runtime, exit_hook=args.exit_hook, custom_swf=args.custom_swf)
    if not success:
        sys.exit("Error: Failed to patch APK files.")

    # Step 2: Locate tools
    keytool_bin = find_tool("keytool")
    jarsigner_bin = find_tool("jarsigner")
    zipalign_bin = find_tool("zipalign")
    apksigner_bin = find_tool("apksigner")

    # Step 3: Ensure debug keystore exists
    keystore_path = os.path.abspath(args.keystore)
    if not os.path.isfile(keystore_path):
        if not keytool_bin:
            sys.exit("Error: Keystore not found and keytool is missing to generate one.")
        print(f"\nGenerating debug keystore with keytool: {keystore_path}...")
        keytool_cmd = [
            keytool_bin,
            "-genkeypair",
            "-v",
            "-keystore", keystore_path,
            "-storepass", args.store_pass,
            "-alias", args.key_alias,
            "-keypass", args.key_pass,
            "-keyalg", "RSA",
            "-keysize", "2048",
            "-validity", "10000",
            "-dname", "CN=Android Debug,O=Android,C=US",
        ]
        res = subprocess.run(keytool_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            print(f"keytool stderr:\n{res.stderr}")
            sys.exit(f"Error: keytool failed with code {res.returncode}")
        print(f"[PASS] Keystore generated: {keystore_path}")

    # Step 4: Signing & Aligning
    if apksigner_bin:
        print(f"\nUsing apksigner: {apksigner_bin}")
        aligned_tmp = output_apk + ".aligned.apk"
        if zipalign_bin:
            print("Aligning with zipalign binary...")
            subprocess.run([zipalign_bin, "-p", "-f", "4", unaligned_apk, aligned_tmp], check=True)
        else:
            print("Aligning with native Python zipalign...")
            zipalign_apk(unaligned_apk, aligned_tmp, 4)

        print("Signing with apksigner...")
        apksigner_cmd = [
            apksigner_bin, "sign",
            "--ks", keystore_path,
            "--ks-pass", f"pass:{args.store_pass}",
            "--ks-key-alias", args.key_alias,
            "--key-pass", f"pass:{args.key_pass}",
            "--out", output_apk,
            aligned_tmp,
        ]
        subprocess.run(apksigner_cmd, check=True)

        print("\nVerifying with apksigner...")
        verify_res = subprocess.run([apksigner_bin, "verify", "--verbose", output_apk],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(verify_res.stdout)
        if os.path.exists(aligned_tmp):
            os.remove(aligned_tmp)
    elif jarsigner_bin:
        print(f"\nUsing jarsigner: {jarsigner_bin}")
        if os.path.exists(temp_signed):
            os.remove(temp_signed)
        if os.path.exists(temp_signed + ".orig"):
            os.remove(temp_signed + ".orig")
        shutil.copy(unaligned_apk, temp_signed)

        print("Signing APK with jarsigner (v1 JAR signature)...")
        sign_cmd = [
            jarsigner_bin,
            "-sigalg", "SHA256withRSA",
            "-digestalg", "SHA-256",
            "-keystore", keystore_path,
            "-storepass", args.store_pass,
            "-keypass", args.key_pass,
            temp_signed,
            args.key_alias,
        ]
        res = subprocess.run(sign_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            print(f"jarsigner stdout:\n{res.stdout}")
            print(f"jarsigner stderr:\n{res.stderr}")
            sys.exit(f"Error: jarsigner failed with code {res.returncode}")

        print("Aligning signed APK to 4-byte boundaries...")
        if zipalign_bin:
            subprocess.run([zipalign_bin, "-p", "-f", "4", temp_signed, output_apk], check=True)
        else:
            zipalign_apk(temp_signed, output_apk, 4)

        # Verify signature with jarsigner
        print("Verifying signed APK with jarsigner...")
        verify_cmd = [jarsigner_bin, "-verify", output_apk]
        res_ver = subprocess.run(verify_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(res_ver.stdout.strip())
        if "jar verified" not in res_ver.stdout:
            sys.exit("Error: jarsigner verification failed on final APK.")

        is_aligned = verify_alignment(output_apk)
        if not is_aligned:
            sys.exit("Error: Final APK has misaligned stored entries.")
        print("[PASS] 4-byte alignment verified on all stored entries (0 misaligned)!")
    else:
        sys.exit("Error: Neither apksigner nor jarsigner was found to sign the APK.")

    shared_backup = os.path.join(os.path.dirname(output_apk), "ygo_patched_shared.apk")
    if not air_runtime:
        shutil.copy2(output_apk, shared_backup)

    print("\n" + "=" * 65)
    print(f"SUCCESS: Generated verified, signed, and aligned APK:")
    print(f"  Target SDK: {args.target_sdk} (bypasses 'built for older devices' prompt)")
    print(f"  Output APK: {output_apk}")
    if air_runtime:
        print(f"  Captive Runtime: Bundled from {air_runtime}")
        print(f"  Shared Backup (Revert): {shared_backup}")
    else:
        print(f"  Runtime Mode: Shared (Backup saved to {shared_backup})")
    print("=" * 65)

    # Clean up intermediate unaligned files so user uses the final working APK
    for tmp in [unaligned_apk, temp_signed]:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


if __name__ == "__main__":
    main()
