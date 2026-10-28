#!/usr/bin/env python3
"""
Yu-Gi-Oh! BAM Pocket Public Endpoint Live Check
Tests public deployment behind Cloudflare Tunnel:
- Sends Ping + GetVersion AMF3 batch to {base}/facebook/proxy.html
- Validates decoded response objects and properties
- Downloads arena.zip and validates archive integrity and version marker
"""

import argparse
import io
import os
from pathlib import Path
import struct
import sys
import urllib.request
import zipfile
import zlib

# Ensure server module is imported for AMF3 encoding/decoding
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import server.amf3 as amf3


def send_amf_batch(base_url: str, request_objects: list, ext_id: str = "") -> list:
    """Encodes and sends AMF request array, returning decoded response objects."""
    ext_id_bytes = ext_id.encode('utf-8')
    payload = bytearray(struct.pack(">H", len(ext_id_bytes)) + ext_id_bytes)

    arr = bytearray([amf3.MARKER_ARRAY])
    arr.extend(amf3.encode_u29((len(request_objects) << 1) | 1))
    arr.append(0x01)  # empty string dense key
    for obj in request_objects:
        arr.extend(amf3.encode_amf3_value(obj))

    compressed = zlib.compress(bytes(payload + arr))

    proxy_url = f"{base_url.rstrip('/')}/facebook/proxy.html"
    http_req = urllib.request.Request(
        proxy_url,
        data=compressed,
        headers={
            "Content-Type": "binary/octet-stream",
            "User-Agent": "Mozilla/5.0 (Android; Mobile) BAM-Pocket-Client"
        }
    )

    with urllib.request.urlopen(http_req, timeout=15) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP error {resp.status} from {proxy_url}")
        data = resp.read()

    if len(data) < 4:
        raise ValueError(f"Response too short: {len(data)} bytes")

    ret_code = struct.unpack(">i", data[:4])[0]
    if ret_code != 0:
        raise ValueError(f"Server returned non-zero return code: {ret_code}")

    decomp = zlib.decompress(data[4:])
    decoder = amf3.AMF3Decoder(decomp)
    decoded = decoder.decode_value()

    if not isinstance(decoded, list):
        raise TypeError(f"Expected response array, got {type(decoded)}")
    return decoded


def check_live_endpoint(base_url: str):
    base_url = base_url.rstrip("/")
    print("=" * 65)
    print(f"Yu-Gi-Oh! BAM Pocket Endpoint Check: {base_url}")
    print("=" * 65)

    # 1. AMF Batch Test (Ping + GetVersion)
    print("\n[Step 1] Sending AMF3 Ping + GetVersion batch to /facebook/proxy.html...")
    req_ping = amf3.AMF3Object("com.frimastudio.snowstorm.core.player.amf.PingRequest", gameframe=1.0)
    req_ver = amf3.AMF3Object("com.frimastudio.snowstorm.project.player.amf.GetVersionRequest")

    try:
        responses = send_amf_batch(base_url, [req_ping, req_ver])
    except Exception as e:
        sys.exit(f"[FAIL] AMF batch request failed: {e}")

    if len(responses) != 2:
        sys.exit(f"[FAIL] Expected 2 responses, received {len(responses)}")

    resp_ping, resp_ver = responses[0], responses[1]

    # Validate PingResponse
    if resp_ping.class_alias != "com.frimastudio.snowstorm.core.player.amf.PingResponse":
        sys.exit(f"[FAIL] Unexpected alias for response 0: {resp_ping.class_alias}")
    if resp_ping.get("gameframe") != 1.0:
        sys.exit(f"[FAIL] Unexpected gameframe: {resp_ping.get('gameframe')}")
    print(f"  [PASS] PingResponse verified (gameframe: {resp_ping.get('gameframe')})")

    # Validate GetVersionResponse
    if resp_ver.class_alias != "com.frimastudio.snowstorm.project.player.amf.GetVersionResponse":
        sys.exit(f"[FAIL] Unexpected alias for response 1: {resp_ver.class_alias}")
    version_val = resp_ver.get("version")
    cdn_host = resp_ver.get("cdn")
    print(f"  [PASS] GetVersionResponse verified (version: '{version_val}', cdn: '{cdn_host}')")

    # 2. Package Download & Validation Test (arena.zip)
    print("\n[Step 2] Downloading arena.zip from /external_asset/android/1.11.1/arena.zip...")
    arena_url = f"{base_url}/external_asset/android/1.11.1/arena.zip"
    try:
        req_pkg = urllib.request.Request(
            arena_url,
            headers={"User-Agent": "Mozilla/5.0 (Android; Mobile) BAM-Pocket-Client"}
        )
        with urllib.request.urlopen(req_pkg, timeout=30) as resp:
            if resp.status != 200:
                sys.exit(f"[FAIL] Failed to download {arena_url}: status {resp.status}")
            zip_bytes = resp.read()
    except Exception as e:
        sys.exit(f"[FAIL] Error downloading {arena_url}: {e}")

    print(f"  Downloaded {len(zip_bytes)} bytes. Validating PKZIP archive...")
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        entries = zf.namelist()
    except Exception as e:
        sys.exit(f"[FAIL] Invalid ZIP archive: {e}")

    version_files = [f for f in entries if "version" in f.lower()]
    if len(version_files) != 1:
        sys.exit(f"[FAIL] Expected 1 version file in arena.zip, found {len(version_files)}: {version_files}")

    ver_filename = version_files[0]
    ver_content = zf.read(ver_filename).decode("utf-8", errors="replace").strip()
    print(f"  Found marker file: {ver_filename} with version string: '{ver_content}'")

    if ver_content != "1.1.7":
        sys.exit(f"[FAIL] Version marker mismatch: expected '1.1.7', got '{ver_content}'")

    print(f"  [PASS] arena.zip archive and version marker ('1.1.7') fully verified ({len(entries)} entries)!")

    print("\n" + "=" * 65)
    print("ALL LIVE ENDPOINT CHECKS PASSED SUCCESSFULLY!")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description="Yu-Gi-Oh! BAM Pocket Endpoint Live Checker")
    parser.add_argument("--base", default="http://ygo.eclip5e.com",
                        help="Base server URL to check (default: http://ygo.eclip5e.com)")
    args = parser.parse_args()

    check_live_endpoint(args.base)


if __name__ == "__main__":
    main()
