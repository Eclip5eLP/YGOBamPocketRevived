#!/usr/bin/env python3
"""
Install (optional), cold-launch air.com.konami.ygo, capture N seconds of full logcat,
a screenshot, PID liveness, and the app-PID-only log lines.

Usage: python tools/device_run.py --tag NAME [--apk work/x.apk] [--seconds 15]
Outputs: work/logs/<tag>_logcat.txt, <tag>_pid.txt, <tag>.png
"""

import argparse
import subprocess
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS = PROJECT_ROOT / "work" / "logs"
PKG = "air.com.konami.ygo"


def adb(serial, *args, check=False, capture=True):
    return subprocess.run(["adb", *(["-s", serial] if serial else []), *args], capture_output=capture, check=check)


def pidof(serial, pkg=PKG):
    return adb(serial, "shell", "pidof", pkg).stdout.decode().strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--apk")
    ap.add_argument("--seconds", type=int, default=15)
    ap.add_argument("--serial", default="", help="adb device serial (default: the only connected device)")
    ap.add_argument("--pkg", default=PKG)
    args = ap.parse_args()
    s = args.serial
    pkg = args.pkg

    if args.apk:
        r = adb(s, "install", "-r", "-d", args.apk)
        print("install:", r.stdout.decode().strip(), r.stderr.decode().strip())
        if r.returncode != 0:
            return
    adb(s, "shell", "am", "force-stop", pkg)
    adb(s, "logcat", "-b", "all", "-c")
    t0 = time.time()
    r = adb(s, "shell", "am", "start", "-W", "-n", f"{pkg}/.AppEntry")
    print("am start:", r.stdout.decode().strip())

    pids = []
    while time.time() - t0 < args.seconds:
        p = pidof(s, pkg)
        pids.append((round(time.time() - t0, 1), p))
        time.sleep(1)
    print("pid samples (t, pid):", pids)

    shot = adb(s, "exec-out", "screencap", "-p").stdout
    (LOGS / f"{args.tag}.png").write_bytes(shot)
    log = adb(s, "logcat", "-b", "all", "-d", "-v", "threadtime").stdout
    (LOGS / f"{args.tag}_logcat.txt").write_bytes(log)

    app_pids = {p for _, p in pids if p}
    text = log.decode("utf-8", errors="replace")
    mine = [ln for ln in text.splitlines() if len(ln.split()) > 3 and ln.split()[2] in app_pids
            or "AIR RUNTIME" in ln or pkg in ln]
    (LOGS / f"{args.tag}_pid.txt").write_text("\n".join(mine), encoding="utf-8")
    print(f"alive at end: {bool(pidof(s, pkg))}; app pids seen: {sorted(app_pids)}; "
          f"logcat lines total {len(text.splitlines())}, app-related {len(mine)}")


if __name__ == "__main__":
    main()
