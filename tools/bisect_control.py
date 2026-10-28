#!/usr/bin/env python3
"""
Yu-Gi-Oh! BAM Pocket - Control APK Bisection Test Tool
Tests hypotheses (a) through (e) on the control APK to find the cause of early runtime termination.
"""

import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Import helpers from tools/patch_apk.py
sys.path.insert(0, str(PROJECT_ROOT / "tools"))
import patch_apk

def run_adb_test(apk_path: str, log_output_path: str, screenshot_path: str):
    """Installs APK, launches it, waits 5s, captures logcat and screenshot, returns survival time in ms."""
    print(f"Installing {os.path.basename(apk_path)} on device...")
    res = subprocess.run(["adb", "install", "-r", "-d", apk_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print(f"Install failed: {res.stderr}")
        return -1, "INSTALL_FAILED"

    subprocess.run(["adb", "shell", "am", "force-stop", "air.com.konami.ygo"])
    subprocess.run(["adb", "logcat", "-b", "all", "-c"])

    print("Launching air.com.konami.ygo/.AppEntry...")
    subprocess.run(["adb", "shell", "am", "start", "-n", "air.com.konami.ygo/.AppEntry"])

    time.sleep(5)

    log_bytes = subprocess.check_output(["adb", "logcat", "-b", "all", "-d", "-v", "threadtime"])
    Path(log_output_path).write_bytes(log_bytes)

    screen_bytes = subprocess.check_output(["adb", "exec-out", "screencap", "-p"])
    Path(screenshot_path).write_bytes(screen_bytes)

    # Check process status
    ps_res = subprocess.run(["adb", "shell", "ps -A | grep air.com.konami.ygo"], stdout=subprocess.PIPE, text=True)
    is_alive = "air.com.konami.ygo" in ps_res.stdout

    # Parse logcat for start and finish timestamps
    log_text = log_bytes.decode("utf-8", errors="ignore")
    start_ts = None
    finish_ts = None
    app_pid = None
    control_lines = []

    for line in log_text.splitlines():
        if "Starting in synchronous mode" in line:
            parts = line.split()
            if len(parts) >= 3:
                start_ts = parts[1]
                app_pid = parts[2]
        if "AIR RUNTIME: finish" in line:
            parts = line.split()
            if len(parts) >= 3:
                finish_ts = parts[1]
        if "[CONTROL]" in line or "=== AIR CONTROL TEST" in line:
            control_lines.append(line.strip())

    delta_ms = None
    if start_ts and finish_ts:
        def to_ms(ts):
            h, m, rest = ts.split(":")
            s, ms = rest.split(".")
            return (int(h)*3600 + int(m)*60 + int(s))*1000 + int(ms)
        delta_ms = to_ms(finish_ts) - to_ms(start_ts)

    # Check if screenshot is non-black
    import struct
    # PNG check: if PNG data contains non-black pixels
    non_black = False
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(screen_bytes))
        extrema = img.convert("L").getextrema()
        if extrema[1] > 10:
            non_black = True
    except Exception:
        # Simple heuristic on raw bytes
        if len(set(screen_bytes[100:1000])) > 20:
            non_black = True

    status_str = f"Alive: {is_alive}, Delta: {delta_ms} ms, Renders: {non_black}, Control Lines: {len(control_lines)}"
    return delta_ms, status_str


def build_custom_apk(out_apk: str, *,
                     no_extensions: bool = False,
                     root_desc_only: bool = False,
                     assets_desc_only: bool = False,
                     no_arm64_dup: bool = False,
                     mobile_profile_only: bool = False,
                     target_namespace: str = None):
    """Builds a modified control APK with specific bisection flags."""
    input_apk = str(PROJECT_ROOT / "input" / "ygo.apk")
    air_runtime = str(PROJECT_ROOT / "work" / "air_runtime")
    custom_swf = str(PROJECT_ROOT / "work" / "ControlApp.swf")
    unaligned_apk = out_apk + ".unaligned.apk"
    temp_signed = out_apk + ".signed_tmp.apk"

    with zipfile.ZipFile(input_apk, "r") as in_zip, zipfile.ZipFile(unaligned_apk, "w") as out_zip:
        copied_count = 0
        patched_count = 0

        for item in in_zip.infolist():
            fname = item.filename
            if fname in ["META-INF/MANIFEST.MF", "META-INF/CERT.SF", "META-INF/CERT.RSA"] or (fname.startswith("META-INF/") and fname.endswith((".SF", ".RSA", ".DSA"))):
                continue
            if fname.startswith("lib/"):
                continue

            # (a) If no_extensions, skip all ANE entries
            if no_extensions and ("extensions/" in fname or "META-INF/ANE" in fname):
                continue

            data = in_zip.read(fname)

            # SWF replacement
            if fname == "assets/MobileGame.swf":
                data = Path(custom_swf).read_bytes()
                patched_count += 1

            # AXML
            elif fname == "AndroidManifest.xml":
                data = patch_apk.patch_axml_target_sdk(data, 28)
                patched_count += 1

            # application.xml
            elif fname == "assets/META-INF/AIR/application.xml":
                xml_str = data.decode("utf-8")
                xml_str = patch_apk.patch_application_xml_target_sdk(data, 28).decode("utf-8")

                if no_extensions:
                    xml_str = re.sub(r'<extensions>.*?</extensions>', '', xml_str, flags=re.DOTALL)

                if mobile_profile_only:
                    xml_str = xml_str.replace("<supportedProfiles>desktop mobileDevice</supportedProfiles>",
                                              "<supportedProfiles>mobileDevice</supportedProfiles>")

                if target_namespace:
                    xml_str = re.sub(r'xmlns="http://ns\.adobe\.com/air/application/[0-9\.]+"',
                                     f'xmlns="{target_namespace}"', xml_str)

                data = xml_str.encode("utf-8")
                patched_count += 1

                # (b) Descriptor injection logic
                if not assets_desc_only:
                    root_item = zipfile.ZipInfo("META-INF/AIR/application.xml", item.date_time)
                    root_item.compress_type = item.compress_type
                    out_zip.writestr(root_item, data)
                    copied_count += 1

                if root_desc_only:
                    # Skip writing assets/META-INF/AIR/application.xml
                    continue

            elif "extensions/" in fname and fname.endswith("extension.xml"):
                if not no_arm64_dup:
                    data = patch_apk.patch_ane_extension_xml(data)
                patched_count += 1

            out_zip.writestr(item, data, compress_type=item.compress_type)
            copied_count += 1

            # Mirror assets to root
            if fname.startswith("assets/"):
                root_name = fname[len("assets/"):]
                if root_name and root_name != "META-INF/AIR/application.xml":
                    if not (no_extensions and ("extensions/" in root_name or "META-INF/ANE" in root_name)):
                        root_item = zipfile.ZipInfo(root_name, item.date_time)
                        root_item.compress_type = item.compress_type
                        out_zip.writestr(root_item, data)
                        copied_count += 1

            # ANE ARM64 duplication
            if not no_arm64_dup and not no_extensions:
                if "extensions/" in fname and "/META-INF/ANE/Android-ARM/" in fname:
                    arm64_fname = fname.replace("/META-INF/ANE/Android-ARM/", "/META-INF/ANE/Android-ARM64/")
                    new_item = zipfile.ZipInfo(arm64_fname, item.date_time)
                    new_item.compress_type = item.compress_type
                    out_zip.writestr(new_item, data)
                    copied_count += 1
                    root_arm64 = arm64_fname[len("assets/"):]
                    root_item64 = zipfile.ZipInfo(root_arm64, item.date_time)
                    root_item64.compress_type = item.compress_type
                    out_zip.writestr(root_item64, data)
                    copied_count += 1

        # Bundle captive runtime
        patch_apk.bundle_air_runtime(out_zip, air_runtime, exit_hook=False)

    # Sign & zipalign
    jarsigner_bin = patch_apk.find_tool("jarsigner")
    keystore = str(PROJECT_ROOT / "work" / "debug.keystore")
    shutil.copy(unaligned_apk, temp_signed)

    sign_cmd = [jarsigner_bin, "-sigalg", "SHA256withRSA", "-digestalg", "SHA-256",
                "-keystore", keystore, "-storepass", "android", "-keypass", "android",
                temp_signed, "androiddebugkey"]
    subprocess.run(sign_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    patch_apk.zipalign_apk(temp_signed, out_apk, 4)

    for tmp in [unaligned_apk, temp_signed]:
        if os.path.exists(tmp): os.remove(tmp)

    print(f"Successfully built: {out_apk}")


def main():
    variants = [
        ("variant_a_no_ext", {"no_extensions": True}, "Remove all <extensions> and delete META-INF/ANE"),
        ("variant_b1_assets_desc_only", {"assets_desc_only": True}, "Only assets/META-INF/AIR/application.xml (no root desc)"),
        ("variant_b2_root_desc_only", {"root_desc_only": True}, "Only root META-INF/AIR/application.xml (no assets desc)"),
        ("variant_c_no_arm64_dup", {"no_arm64_dup": True}, "Restore Android-ARM only (undo ARM64 duplication)"),
        ("variant_d_mobile_only", {"mobile_profile_only": True}, "supportedProfiles = mobileDevice"),
        ("variant_e_ns_50_2", {"target_namespace": "http://ns.adobe.com/air/application/50.2"}, "Namespace 50.2 (latest supported)"),
    ]

    results = []
    for var_name, flags, desc in variants:
        print("\n" + "="*70)
        print(f"RUNNING BISECTION: {var_name}")
        print(f"Description: {desc}")
        print("="*70)
        apk_path = str(PROJECT_ROOT / "work" / f"ygo_control_{var_name}.apk")
        log_path = str(PROJECT_ROOT / "work" / "logs" / f"control_{var_name}.txt")
        png_path = str(PROJECT_ROOT / "work" / "logs" / f"control_{var_name}.png")

        build_custom_apk(apk_path, **flags)
        delta_ms, status = run_adb_test(apk_path, log_path, png_path)
        results.append((var_name, desc, delta_ms, status))

    print("\n" + "="*70)
    print("BISECTION SUMMARY RESULTS:")
    print("="*70)
    for var_name, desc, delta_ms, status in results:
        print(f"{var_name:30} | {delta_ms} ms | {status} | {desc}")

if __name__ == "__main__":
    main()
