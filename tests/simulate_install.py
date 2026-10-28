#!/usr/bin/env python3
"""
Simulates client asset package downloading and installation.
Follows ExternalFileControllerImpl.as:388-393 and 509-587:
- Time-sliced installation loop [lines 521-553]
- Directory skipping ('/' ending entries) [line 525]
- Case normalization: resolvePath((Path + fileName).toLowerCase()) [line 392]
- Version file capture and final '{packageName}_version' marker creation [lines 527-547]

Verifies:
- All 26 packages download successfully from the running server
- Each zip contains exactly one file with 'version' in its name
- The version file content matches the manifest's 1.11.1 package version
- The extracted tree in temp_dir matches input/.../Local Store/asset/ (paths + sizes)
"""

import io
import os
import sys
import tempfile
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from typing import Dict, Tuple

# Ensure server module is imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from server.server import BAMServerHandler, BAMThreadingServer, PACKAGE_PATHS


def run_simulation():
    test_port = 8767
    base_store = os.path.abspath("input/data/data/air.com.konami.ygo/com.konami.ygo/Local Store")
    expected_asset_dir = os.path.join(base_store, "asset")
    cache_dir = os.path.abspath("work/package_cache")

    config = {
        "local_store_dir": base_store,
        "cache_dir": cache_dir,
        "cdn_host": f"127.0.0.1:{test_port}",
        "version_string": "android=1.11.2~ios=1.11.2",
    }

    # 1. Parse manifest versions for 1.11.1
    manifest_path = os.path.join(base_store, "versionning.xml")
    tree = ET.parse(manifest_path)
    root = tree.getroot()
    v111 = [v for v in root.findall("version") if v.attrib.get("value") == "1.11.1"][0]
    manifest_versions: Dict[str, str] = {
        pkg.attrib["name"]: pkg.attrib["version"] for pkg in v111.findall("package")
    }

    print(f"Loaded manifest versions for {len(manifest_versions)} packages from 1.11.1.")

    # 2. Start server in thread
    server = BAMThreadingServer(("127.0.0.1", test_port), BAMServerHandler, config)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)

    base_url = f"http://127.0.0.1:{test_port}"
    temp_dir_obj = tempfile.TemporaryDirectory()
    temp_install_dir = temp_dir_obj.name

    version_check_failures = []
    print("\n=== Phase 1: Downloading & Simulating AS3 Client Extraction ===")

    try:
        for idx, (pkg_name, pkg_rel_path) in enumerate(PACKAGE_PATHS.items(), 1):
            url = f"{base_url}/external_asset/android/1.11.1/{pkg_name}.zip"
            with urllib.request.urlopen(url) as resp:
                zip_bytes = resp.read()

            zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
            entries = zf.infolist()

            # Find version files in zip
            version_entries = [
                e for e in entries
                if "version" in e.filename.lower() and not e.filename.endswith("/")
            ]

            expected_version = manifest_versions.get(pkg_name, "")
            if len(version_entries) != 1:
                version_check_failures.append(
                    f"{pkg_name}: expected 1 version file, found {len(version_entries)}: {[e.filename for e in version_entries]}"
                )
            else:
                actual_version = zf.read(version_entries[0]).decode("utf-8", errors="replace").strip()
                if actual_version != expected_version:
                    version_check_failures.append(
                        f"{pkg_name}: version mismatch: got '{actual_version}', expected manifest '{expected_version}'"
                    )

            # Simulate client extraction [ExternalFileControllerImpl.as:509-587]
            current_package_version = None

            for entry in entries:
                # Line 525: directory check
                if entry.filename.endswith("/"):
                    continue

                entry_content = zf.read(entry)

                # Lines 527-535: version file capture vs normal file write
                if "version" in entry.filename:
                    current_package_version = entry_content
                else:
                    # Line 392: resolvePath((Path + fileName).toLowerCase())
                    dest_rel = (pkg_rel_path + entry.filename).lower()
                    dest_full = os.path.join(temp_install_dir, dest_rel)
                    os.makedirs(os.path.dirname(dest_full), exist_ok=True)
                    with open(dest_full, "wb") as f:
                        f.write(entry_content)

            # Lines 542-547: write final marker '{packageName}_version'
            if current_package_version is None:
                current_package_version = b"0.0.0"

            marker_rel = (pkg_rel_path + f"{pkg_name}_version").lower()
            marker_full = os.path.join(temp_install_dir, marker_rel)
            os.makedirs(os.path.dirname(marker_full), exist_ok=True)
            with open(marker_full, "wb") as f:
                f.write(current_package_version)

            ver_str = current_package_version.decode('utf-8', errors='replace').strip()
            print(f"[{idx:02d}/26] Extracted {pkg_name:16} ({len(zip_bytes):8d} bytes, {len(entries):4d} entries, ver: {ver_str})")

        # 3. Check version verification results
        print("\n=== Phase 2: Package Version Marker Verification ===")
        if version_check_failures:
            print("FAILED version marker checks:")
            for fail in version_check_failures:
                print(" -", fail)
            raise AssertionError(f"{len(version_check_failures)} packages failed version checks!")
        else:
            print("[PASS] All 26 packages contain exactly 1 version file matching 1.11.1 manifest version!")

        # 4. Diff installed tree against input/.../Local Store/asset/
        print("\n=== Phase 3: Diffing Extracted Tree Against input/.../Local Store/asset/ ===")
        installed_asset_dir = os.path.join(temp_install_dir, "asset")

        installed_files: Dict[str, int] = {}
        for root_dir, dirs, files in os.walk(installed_asset_dir):
            for fname in files:
                fpath = os.path.join(root_dir, fname)
                rel = os.path.relpath(fpath, installed_asset_dir).replace("\\", "/").lower()
                installed_files[rel] = os.path.getsize(fpath)

        expected_files: Dict[str, int] = {}
        for root_dir, dirs, files in os.walk(expected_asset_dir):
            for fname in files:
                fpath = os.path.join(root_dir, fname)
                rel = os.path.relpath(fpath, expected_asset_dir).replace("\\", "/").lower()
                expected_files[rel] = os.path.getsize(fpath)

        missing_in_installed = set(expected_files.keys()) - set(installed_files.keys())
        extra_in_installed = set(installed_files.keys()) - set(expected_files.keys())
        size_mismatches = {
            p: (installed_files[p], expected_files[p])
            for p in (set(installed_files.keys()) & set(expected_files.keys()))
            if installed_files[p] != expected_files[p]
        }

        print(f"Total expected asset files:  {len(expected_files)}")
        print(f"Total installed asset files: {len(installed_files)}")
        print(f"Missing in installed:        {len(missing_in_installed)}")
        print(f"Extra in installed:          {len(extra_in_installed)}")
        print(f"Size mismatches:             {len(size_mismatches)}")

        if missing_in_installed:
            print("Missing files (first 10):", sorted(list(missing_in_installed))[:10])
        if extra_in_installed:
            print("Extra files (first 10):", sorted(list(extra_in_installed))[:10])
        if size_mismatches:
            print("Size mismatches (first 10):", list(size_mismatches.items())[:10])

        assert len(missing_in_installed) == 0, f"Found {len(missing_in_installed)} missing files!"
        assert len(extra_in_installed) == 0, f"Found {len(extra_in_installed)} extra files!"
        assert len(size_mismatches) == 0, f"Found {len(size_mismatches)} size mismatches!"

        print("\n[PERFECT MATCH] 1627 files extracted, 0 missing, 0 extra, 0 size mismatches!")

    finally:
        server.shutdown()
        server.server_close()
        temp_dir_obj.cleanup()


if __name__ == "__main__":
    run_simulation()
