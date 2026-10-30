#!/usr/bin/env python3
"""
Drive the headless Android emulator for testing (see README, Development).

  python tools/emu.py start            boot AVD "ygo" headless, adb root, reverse tcp:80 -> 8087
  python tools/emu.py install APK      install (keeps app data)
  python tools/emu.py launch           cold start the game
  python tools/emu.py shot NAME        screenshot to work/logs/NAME.png
  python tools/emu.py tap X Y [...]    tap at screen coordinates (2400x1080), several pairs allowed
  python tools/emu.py back             Android back key
  python tools/emu.py log [PATTERN]    app log lines (logcat), optionally filtered
  python tools/emu.py stop             shut the emulator down

SDK location: env ANDROID_SDK_ROOT, default C:/Users/ultim/dev/android-sdk.
"""

import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SDK = Path(os.environ.get("ANDROID_SDK_ROOT", "C:/Users/ultim/dev/android-sdk"))
ADB = str(SDK / "platform-tools" / "adb")
SERIAL = os.environ.get("YGO_EMU_SERIAL", "emulator-5560")
PKG = "air.com.konami.ygo"


def adb(*args, capture=True, check=False):
    return subprocess.run([ADB, "-s", SERIAL, *args], capture_output=capture, check=check)


def wait_boot(timeout=180):
    adb("wait-for-device")
    end = time.time() + timeout
    while time.time() < end:
        if adb("shell", "getprop", "sys.boot_completed").stdout.strip() == b"1":
            return
        time.sleep(2)
    sys.exit("emulator did not finish booting")


def start():
    port = SERIAL.split("-")[-1]
    subprocess.Popen([str(SDK / "emulator" / "emulator"), "-avd", "ygo", "-no-window", "-no-audio", "-no-boot-anim",
                      "-gpu", "swiftshader_indirect", "-memory", "4096", "-port", port],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    wait_boot()
    adb("root")
    time.sleep(2)
    wait_boot()
    # the game only talks to port 80; binding it on the device needs root adbd
    print(adb("reverse", "tcp:80", "tcp:8087").stdout.decode().strip() or "reverse ok")
    # no "Viewing full screen" hint over the game
    adb("shell", "settings", "put", "secure", "immersive_mode_confirmations", "confirmed")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "start":
        start()
    elif cmd == "install":
        r = adb("install", "-r", "-d", args[0])
        print(r.stdout.decode().strip(), r.stderr.decode().strip())
    elif cmd == "launch":
        adb("shell", "am", "force-stop", PKG)
        adb("logcat", "-c")
        print(adb("shell", "am", "start", "-W", "-n", f"{PKG}/.AppEntry").stdout.decode().strip().splitlines()[-1])
    elif cmd == "shot":
        out = ROOT / "work" / "logs" / f"{args[0]}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(adb("exec-out", "screencap", "-p").stdout)
        print(out)
    elif cmd == "tap":
        for x, y in zip(args[0::2], args[1::2]):
            adb("shell", "input", "tap", x, y)
            time.sleep(0.6)
    elif cmd == "back":
        adb("shell", "input", "keyevent", "4")
    elif cmd == "log":
        pid = adb("shell", "pidof", PKG).stdout.decode().strip()
        lines = adb("logcat", "-d", "-v", "time", *(["--pid", pid] if pid else [])).stdout.decode("utf-8", "replace")
        for line in lines.splitlines():
            if not args or re.search(args[0], line, re.I):
                print(line)
    elif cmd == "stop":
        adb("emu", "kill")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
