import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AIR_SDK = PROJECT_ROOT / "work" / "airsdk"
ADT_BAT = AIR_SDK / "bin" / "adt.bat"
HELLO_DIR = PROJECT_ROOT / "work" / "hello_air"
OUT_APK = HELLO_DIR / "hello.apk"
KEYSTORE = PROJECT_ROOT / "work" / "debug.keystore"
CONTROL_SWF = PROJECT_ROOT / "work" / "ControlApp.swf"

def package_app():
    if not ADT_BAT.exists():
        print(f"Error: ADT not found at {ADT_BAT}")
        return False

    shutil.copy(CONTROL_SWF, HELLO_DIR / "ControlApp.swf")

    cmd = [
        str(ADT_BAT),
        "-package",
        "-target", "apk-captive-runtime",
        "-arch", "armv8",
        "-storetype", "pkcs12",
        "-keystore", str(KEYSTORE),
        "-storepass", "android",
        "-keypass", "android",
        str(OUT_APK),
        str(HELLO_DIR / "application.xml"),
        "-C", str(HELLO_DIR),
        "ControlApp.swf"
    ]
    print("Running ADT command:")
    print(" ".join(cmd))
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    print("ADT stdout:", res.stdout)
    print("ADT stderr:", res.stderr)
    return res.returncode == 0

def test_on_device():
    print(f"\nInstalling {OUT_APK} on device...")
    res = subprocess.run(["adb", "install", "-r", "-d", str(OUT_APK)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    print("ADB install:", res.stdout, res.stderr)
    if res.returncode != 0:
        return False

    pkg_name = "air.com.test.helloair"
    subprocess.run(["adb", "shell", "am", "force-stop", pkg_name])
    subprocess.run(["adb", "logcat", "-b", "all", "-c"])

    print(f"Launching {pkg_name}/.AppEntry...")
    subprocess.run(["adb", "shell", "am", "start", "-n", f"{pkg_name}/.AppEntry"])

    time.sleep(5)

    log_bytes = subprocess.check_output(["adb", "logcat", "-b", "all", "-d", "-v", "threadtime"])
    (PROJECT_ROOT / "work" / "logs" / "official_hello_air.txt").write_bytes(log_bytes)

    screen_bytes = subprocess.check_output(["adb", "exec-out", "screencap", "-p"])
    (PROJECT_ROOT / "work" / "logs" / "official_hello_air.png").write_bytes(screen_bytes)

    ps_res = subprocess.run([f"adb shell ps -A | grep {pkg_name}"], shell=True, stdout=subprocess.PIPE, text=True)
    is_alive = pkg_name in ps_res.stdout
    print(f"App alive after 5s: {is_alive}")

    # Check timestamps
    log_text = log_bytes.decode("utf-8", errors="ignore")
    start_ts = None
    finish_ts = None
    for line in log_text.splitlines():
        if "Starting in synchronous mode" in line:
            start_ts = line.split()[1]
        if "AIR RUNTIME: finish" in line:
            finish_ts = line.split()[1]
        if "[CONTROL]" in line or "=== AIR CONTROL TEST" in line:
            print("LOG LINE:", line.strip())

    print(f"Start: {start_ts}, Finish: {finish_ts}")
    return is_alive

if __name__ == "__main__":
    if package_app():
        test_on_device()
    else:
        print("Packaging failed.")
