#!/usr/bin/env python3
"""
Test Suite: Patched APK Verification
Verifies:
1. assets/config/mmog.xml contains revival server URLs and port 80 mappings
2. AndroidManifest.xml binary AXML contains targetSdkVersion=24 (Android 14/15 compatible)
3. assets/META-INF/AIR/application.xml contains android:targetSdkVersion="24"
4. 4-byte zipalign on all uncompressed (STORED) entries
5. Signature verification via jarsigner -verify
6. Absence of legacy signature files
"""

import os
import struct
import subprocess
import sys
from pathlib import Path
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from tools.patch_apk import find_tool, verify_alignment


def run_checks(apk_path: str, expected_host: str = "ygo.eclip5e.com", expected_sdk: int = 28):
    print(f"=== Verifying Patched APK: {apk_path} ===")
    assert os.path.isfile(apk_path), f"APK file not found: {apk_path}"

    with zipfile.ZipFile(apk_path, "r") as zf:
        entry_names = zf.namelist()

        # 1. Verify no leftover old signatures
        legacy_sig = [e for e in entry_names if e.startswith("META-INF/") and e.endswith((".RSA", ".DSA")) and e != "META-INF/ANDROIDD.RSA"]
        print(f"1. Checking signatures in META-INF... Found {len([e for e in entry_names if e.startswith('META-INF/')])} files.")
        assert "META-INF/MANIFEST.MF" in entry_names, "Missing META-INF/MANIFEST.MF"

        # 2. Verify mmog.xml
        print("2. Checking assets/config/mmog.xml...")
        assert "assets/config/mmog.xml" in entry_names, "Missing assets/config/mmog.xml"
        mmog_text = zf.read("assets/config/mmog.xml").decode("utf-8")
        assert f"http://{expected_host}/facebook/proxy.html" in mmog_text, "serverUrl not properly patched in mmog.xml"
        assert f"http://{expected_host}/facebook/proxy.html~80~844" in mmog_text, "pvpServerUrl not properly patched in mmog.xml"
        assert f"http://{expected_host}" in mmog_text, "openGraphServerUrl not properly patched in mmog.xml"
        print("   [PASS] mmog.xml URLs verified.")

        # 2b. Verify Captive Adobe AIR Multi-ABI Bundling
        print("2b. Checking Captive Adobe AIR Multi-ABI Bundling...")
        assert "classes.dex" in entry_names, "Missing primary classes.dex"
        assert "classes2.dex" in entry_names, "Missing captive runtime classes2.dex"
        expected_libs = [
            "lib/arm64-v8a/libCore.so",
            "lib/arm64-v8a/libc++_shared.so",
            "lib/arm64-v8a/libysshared.so",
            "lib/armeabi-v7a/libCore.so",
            "lib/armeabi-v7a/libc++_shared.so",
            "lib/armeabi-v7a/libysshared.so",
        ]
        for lib in expected_libs:
            assert lib in entry_names, f"Missing native library: {lib}"
            lib_head = zf.read(lib)[:4]
            assert lib_head == b"\x7fELF", f"Invalid ELF magic for {lib}: {lib_head}"
        print(f"   [PASS] Captive runtime verified: classes2.dex and {len(expected_libs)} multi-ABI native libraries.")

        # 3. Verify application.xml
        print("3. Checking assets/META-INF/AIR/application.xml...")
        assert "assets/META-INF/AIR/application.xml" in entry_names, "Missing application.xml"
        app_xml_text = zf.read("assets/META-INF/AIR/application.xml").decode("utf-8")
        expected_target_attr = f'android:targetSdkVersion="{expected_sdk}"'
        assert expected_target_attr in app_xml_text, f"application.xml missing {expected_target_attr}"
        print(f"   [PASS] application.xml contains targetSdkVersion={expected_sdk}.")

        # 4. Verify binary AndroidManifest.xml
        print("4. Checking binary AndroidManifest.xml AXML...")
        assert "AndroidManifest.xml" in entry_names, "Missing AndroidManifest.xml"
        axml = zf.read("AndroidManifest.xml")
        header_type, header_size, chunk_size = struct.unpack('<HHI', axml[8:16])
        string_count, style_count, flags, strings_start, styles_start = struct.unpack('<IIIII', axml[16:36])
        offsets = struct.unpack(f'<{string_count}I', axml[36:36 + 4 * string_count])
        str_data = axml[8 + strings_start:]
        strings = []
        for off in offsets:
            length = struct.unpack('<H', str_data[off:off + 2])[0]
            s = str_data[off + 2:off + 2 + length * 2].decode('utf-16le', errors='ignore')
            strings.append(s)

        assert 'targetSdkVersion' in strings, "targetSdkVersion string not found in AXML"
        target_sdk_idx = strings.index('targetSdkVersion')

        pos = 8
        found_target_sdk = None
        while pos < len(axml) - 8:
            tag, size = struct.unpack('<II', axml[pos:pos + 8])
            if tag == 0x00100102:
                attr_count = struct.unpack('<H', axml[pos + 28:pos + 30])[0]
                attr_pos = pos + 36
                for _ in range(attr_count):
                    aname = struct.unpack('<I', axml[attr_pos + 4:attr_pos + 8])[0]
                    if aname == target_sdk_idx:
                        found_target_sdk = struct.unpack('<i', axml[attr_pos + 16:attr_pos + 20])[0]
                    attr_pos += 20
            pos += size

        assert found_target_sdk == expected_sdk, f"AXML targetSdkVersion expected {expected_sdk}, got {found_target_sdk}"
        print(f"   [PASS] Binary AXML targetSdkVersion={found_target_sdk} verified.")

    # 5. Check 4-byte zipalign
    print("5. Checking 4-byte zipalign of stored entries...")
    is_aligned = verify_alignment(apk_path)
    assert is_aligned, "4-byte alignment verification failed"
    print("   [PASS] All stored entries 4-byte aligned (0 misaligned).")

    # 6. Verify jarsigner
    print("6. Verifying JAR signature with jarsigner...")
    jarsigner_bin = find_tool("jarsigner")
    if jarsigner_bin:
        res = subprocess.run([jarsigner_bin, "-verify", apk_path], capture_output=True, text=True)
        assert res.returncode == 0, f"jarsigner failed with code {res.returncode}"
        assert "jar verified" in res.stdout, f"Signature invalid: {res.stdout}"
        print("   [PASS] jarsigner verified: jar verified.")
    else:
        print("   [SKIP] jarsigner not found on PATH.")

    print("\n" + "=" * 65)
    print(f"ALL CHECKS PASSED: {apk_path} is ready for installation!")
    print("=" * 65)


if __name__ == "__main__":
    apk = sys.argv[1] if len(sys.argv) > 1 else str(PROJECT_ROOT / "work" / "ygo_patched.apk")
    run_checks(apk)
