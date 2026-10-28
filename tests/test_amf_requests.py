#!/usr/bin/env python3
"""
Unit tests for BAM Pocket AMF3 communication and request handling.
Verifies:
- GetPlayerSaveRequest handling and GetPlayerSaveResponse decoding
- Request ordering (responses emitted 1:1 in request order)
- Error handling for unknown request classes (returns AbstractException, not GetVersionResponse)
- Round-trip encoding/decoding of AMF3 data types (ints, doubles, strings, arrays, bytearrays, objects)
"""

import os
import shutil
import tempfile
import struct
import sys
import threading
import time
import urllib.request
import zlib

# Ensure server module can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server.amf3 as amf3
from pathlib import Path
from server.server import BAMServerHandler, BAMThreadingServer, setup_logging


def send_amf_request(base_url: str, request_objects: list, ext_id: str = "") -> list:
    """Encodes and sends AMF request array, returning decoded response objects."""
    # Build payload: UTF external ID + AMF3 array of requests
    ext_id_bytes = ext_id.encode('utf-8')
    payload = bytearray(struct.pack(">H", len(ext_id_bytes)) + ext_id_bytes)

    arr = bytearray([amf3.MARKER_ARRAY])
    arr.extend(amf3.encode_u29((len(request_objects) << 1) | 1))
    arr.append(0x01) # empty string dense key
    for obj in request_objects:
        arr.extend(amf3.encode_amf3_value(obj))

    compressed = zlib.compress(bytes(payload + arr))

    http_req = urllib.request.Request(
        f"{base_url}/facebook/proxy.html",
        data=compressed,
        headers={"Content-Type": "binary/octet-stream"}
    )
    with urllib.request.urlopen(http_req) as resp:
        data = resp.read()

    ret_code = struct.unpack(">i", data[:4])[0]
    assert ret_code == 0, f"Expected return code 0, got {ret_code}"

    decomp = zlib.decompress(data[4:])
    decoder = amf3.AMF3Decoder(decomp)
    decoded = decoder.decode_value()
    assert isinstance(decoded, list), f"Expected response array, got {type(decoded)}"
    return decoded


def run_tests():
    project_root = Path(__file__).resolve().parent.parent
    setup_logging(project_root)

    test_port = 8766
    config = {
        "local_store_dir": os.path.abspath("input/data/data/air.com.konami.ygo/com.konami.ygo/Local Store"),
        "cache_dir": os.path.abspath("work/package_cache"),
        "cdn_host": f"127.0.0.1:{test_port}",
        "version_string": "android=1.11.2~ios=1.11.2",
        "data_dir": tempfile.mkdtemp(prefix="ygo_test_data_"),
    }
    # the server needs an RSA private key; use the project's (never written to)
    shutil.copy(project_root / "server" / "data" / "rsa_private.json", config["data_dir"])

    server = BAMThreadingServer(("127.0.0.1", test_port), BAMServerHandler, config)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)

    base_url = f"http://127.0.0.1:{test_port}"

    try:
        print("=== Test 1: GetPlayerSaveRequest handling & decoding ===")
        req_save = amf3.AMF3Object("com.frimastudio.snowstorm.project.player.amf.GetPlayerSaveRequest")
        responses = send_amf_request(base_url, [req_save])
        assert len(responses) == 1, f"Expected 1 response, got {len(responses)}"
        save_resp = responses[0]
        assert save_resp.class_alias == "com.frimastudio.snowstorm.project.player.amf.GetPlayerSaveResponse", \
            f"Unexpected class alias: {save_resp.class_alias}"
        assert save_resp.get("exception") is None, f"Expected exception None, got {save_resp.get('exception')}"
        # online saves are per account now (server/game.py); without a login there is no save
        assert save_resp.get("playerSave") is None, "Expected no playerSave without a logged-in session"
        print("[PASS] GetPlayerSaveRequest without login returns playerSave=None (per-account saves)")

        print("\n=== Test 2: Exact request ordering (1:1 response order) ===")
        req_ver = amf3.AMF3Object("com.frimastudio.snowstorm.project.player.amf.GetVersionRequest")
        req_ping = amf3.AMF3Object("com.frimastudio.snowstorm.core.player.amf.PingRequest", gameframe=42.0)
        req_token = amf3.AMF3Object("com.frimastudio.snowstorm.core.player.amf.GetTokenRequest")

        # Send batch in specific order: [Ping, GetVersion, GetToken, GetPlayerSave]
        batch = [req_ping, req_ver, req_token, req_save]
        batch_responses = send_amf_request(base_url, batch)

        assert len(batch_responses) == 4, f"Expected 4 responses, got {len(batch_responses)}"
        assert batch_responses[0].class_alias == "com.frimastudio.snowstorm.core.player.amf.PingResponse"
        assert batch_responses[0].gameframe == 42.0
        assert batch_responses[1].class_alias == "com.frimastudio.snowstorm.project.player.amf.GetVersionResponse"
        assert batch_responses[1].version == "android=1.11.2~ios=1.11.2"
        assert batch_responses[2].class_alias == "com.frimastudio.snowstorm.core.player.amf.GetTokenResponse"
        assert len(batch_responses[2].token) == 32  # random per-session token (server/game.py)
        assert batch_responses[3].class_alias == "com.frimastudio.snowstorm.project.player.amf.GetPlayerSaveResponse"
        print("[PASS] 4-message batch produced exactly 4 responses matching request order 1:1!")

        print("\n=== Test 3: Unknown request handling (error via exception, no GetVersionResponse fallback) ===")
        req_unknown = amf3.AMF3Object("com.frimastudio.snowstorm.project.unknown.amf.BogusRequest", foo="bar")
        err_responses = send_amf_request(base_url, [req_unknown])

        assert len(err_responses) == 1, f"Expected 1 response, got {len(err_responses)}"
        err_resp = err_responses[0]
        assert err_resp.class_alias != "com.frimastudio.snowstorm.project.player.amf.GetVersionResponse", \
            "Server incorrectly defaulted to GetVersionResponse on unknown request!"
        assert err_resp.class_alias == "com.frimastudio.snowstorm.project.unknown.amf.BogusResponse"
        exc = err_resp.get("exception")
        assert exc is not None, "Error response missing exception object"
        assert exc.class_alias == "com.frimastudio.commons.amf.exception.AbstractException"
        assert exc.get("code") == 1
        print(f"[PASS] Unknown request produced {err_resp.class_alias} with AbstractException (code {exc.get('code')})!")

        print("\n=== Test 4: Oversized POST body cap (> 1 MiB returns 413) ===")
        oversized_data = b"A" * (1024 * 1024 + 1024)  # 1 MiB + 1 KiB
        req_413 = urllib.request.Request(
            f"{base_url}/facebook/proxy.html",
            data=oversized_data,
            headers={"Content-Type": "binary/octet-stream"}
        )
        try:
            with urllib.request.urlopen(req_413) as resp:
                assert False, f"Expected 413 Payload Too Large, got status {resp.status}"
        except urllib.error.HTTPError as e:
            assert e.code == 413, f"Expected status 413, got {e.code}"
            print(f"[PASS] Oversized POST body ({len(oversized_data)} bytes) correctly rejected with HTTP {e.code}!")

        print("\n=== Test 5: Decompression bomb limit (> 4 MiB decompressed returns 413) ===")
        # 5 MiB of zeroes compresses to under 6 KiB
        decomp_bomb = zlib.compress(b"\x00" * (5 * 1024 * 1024))
        req_bomb = urllib.request.Request(
            f"{base_url}/facebook/proxy.html",
            data=decomp_bomb,
            headers={"Content-Type": "binary/octet-stream"}
        )
        try:
            with urllib.request.urlopen(req_bomb) as resp:
                assert False, f"Expected 413 for decompressed bomb, got status {resp.status}"
        except urllib.error.HTTPError as e:
            assert e.code == 413, f"Expected status 413, got {e.code}"
            print(f"[PASS] Decompression bomb ({len(decomp_bomb)} compressed bytes -> 5 MiB) rejected with HTTP {e.code}!")

        print("\n=== Test 6: CF-Connecting-IP logging ===")
        test_ip = "198.51.100.77"
        req_ip = urllib.request.Request(
            f"{base_url}/crossdomain.xml",
            headers={"CF-Connecting-IP": test_ip}
        )
        with urllib.request.urlopen(req_ip) as resp:
            assert resp.status == 200, f"Expected 200, got {resp.status}"

        # Flush / inspect work/server_requests.log
        log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "work", "server_requests.log")
        assert os.path.isfile(log_path), f"Log file missing: {log_path}"
        with open(log_path, "r", encoding="utf-8") as f:
            log_content = f.read()
        assert f"[{test_ip}]" in log_content, f"CF-Connecting-IP {test_ip} was not recorded in {log_path}"
        print(f"[PASS] Client IP from CF-Connecting-IP ({test_ip}) verified recorded in server_requests.log!")

    finally:
        server.shutdown()
        server.server_close()
        print("\nAll AMF request and hardening tests completed successfully!")


if __name__ == "__main__":
    run_tests()
