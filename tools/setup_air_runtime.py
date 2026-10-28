#!/usr/bin/env python3
"""
Prepares the universal 32-bit & 64-bit captive Adobe AIR runtime bundle in work/air_runtime.
Extracts:
- classes.dex from 64-bit arm8 Runtime.apk (injected as classes2.dex)
- lib/arm64-v8a/*.so from Runtime_arm8.apk
- lib/armeabi-v7a/*.so from Runtime_arm.apk
- assets/ (fonts, html) from Runtime_arm8.apk
"""

import os
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORK_DIR = PROJECT_ROOT / "work"
AIR_RUNTIME_DIR = WORK_DIR / "air_runtime"

def setup_runtime():
    arm8_apk = AIR_RUNTIME_DIR / "Runtime_arm8.apk"
    arm_apk = AIR_RUNTIME_DIR / "Runtime_arm.apk"

    if not arm8_apk.exists():
        raise FileNotFoundError(f"Missing {arm8_apk}")
    if not arm_apk.exists():
        raise FileNotFoundError(f"Missing {arm_apk}")

    print("Extracting universal AIR captive runtime...")
    
    # 1. classes.dex from arm8
    with zipfile.ZipFile(arm8_apk, "r") as z:
        dex_data = z.read("classes.dex")
        (AIR_RUNTIME_DIR / "classes.dex").write_bytes(dex_data)
        print(f"  classes.dex: {len(dex_data)} bytes")

        # Assets
        assets_dir = AIR_RUNTIME_DIR / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        for name in ["assets/AdobeClean-Light.ttf", "assets/index.html"]:
            if name in z.namelist():
                out_path = AIR_RUNTIME_DIR / name
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(z.read(name))
                print(f"  {name}: {out_path.stat().st_size} bytes")

        # 64-bit native libs
        lib64_dir = AIR_RUNTIME_DIR / "lib" / "arm64-v8a"
        lib64_dir.mkdir(parents=True, exist_ok=True)
        for item in z.infolist():
            if item.filename.startswith("lib/arm64-v8a/") and item.filename.endswith(".so"):
                so_data = z.read(item.filename)
                # Verify ELF header
                if so_data.startswith(b"\x7fELF"):
                    out_path = AIR_RUNTIME_DIR / item.filename
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_bytes(so_data)
                    print(f"  {item.filename}: {len(so_data)} bytes [ELF valid]")
                else:
                    print(f"  Skipping non-ELF stub: {item.filename} ({len(so_data)} bytes)")

    # 2. 32-bit native libs from arm
    with zipfile.ZipFile(arm_apk, "r") as z:
        lib32_dir = AIR_RUNTIME_DIR / "lib" / "armeabi-v7a"
        lib32_dir.mkdir(parents=True, exist_ok=True)
        for item in z.infolist():
            if item.filename.startswith("lib/armeabi-v7a/") and item.filename.endswith(".so"):
                so_data = z.read(item.filename)
                # Verify ELF header
                if so_data.startswith(b"\x7fELF"):
                    out_path = AIR_RUNTIME_DIR / item.filename
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_bytes(so_data)
                    print(f"  {item.filename}: {len(so_data)} bytes [ELF valid]")
                else:
                    print(f"  Skipping non-ELF stub: {item.filename} ({len(so_data)} bytes)")

    print(f"\nAIR runtime bundle ready at: {AIR_RUNTIME_DIR}")

if __name__ == "__main__":
    setup_runtime()
