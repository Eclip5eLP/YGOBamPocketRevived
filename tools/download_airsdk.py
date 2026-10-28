import os
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ZIP_PATH = PROJECT_ROOT / "work" / "AIRSDK_Windows.zip"
TARGET_DIR = PROJECT_ROOT / "work" / "airsdk"

URL = "https://assets.airsdk.dev/api/versions/51.5.1.1/sdks/AIRSDK_Windows.zip?license=accepted"

def download_file(url, target_path):
    print(f"Downloading AIR SDK from {url}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp, open(target_path, "wb") as out_file:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        last_pct = 0
        t0 = time.time()
        buf_size = 1024 * 1024 # 1MB chunks
        while True:
            chunk = resp.read(buf_size)
            if not chunk:
                break
            out_file.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                pct = int(downloaded * 100 / total)
                if pct >= last_pct + 10 or downloaded == total:
                    elapsed = time.time() - t0
                    speed_mb = (downloaded / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                    print(f"Downloaded {downloaded / (1024 * 1024):.1f} / {total / (1024 * 1024):.1f} MB ({pct}%) at {speed_mb:.2f} MB/s")
                    last_pct = pct

def main():
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    adt_bat = TARGET_DIR / "bin" / "adt.bat"
    if adt_bat.exists():
        print(f"AIR SDK already installed at {TARGET_DIR}")
        return

    if not ZIP_PATH.exists() or ZIP_PATH.stat().st_size < 500 * 1024 * 1024:
        download_file(URL, ZIP_PATH)

    print(f"Extracting {ZIP_PATH} to {TARGET_DIR}...")
    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        z.extractall(TARGET_DIR)

    print(f"AIR SDK successfully extracted to {TARGET_DIR}")

if __name__ == "__main__":
    main()
