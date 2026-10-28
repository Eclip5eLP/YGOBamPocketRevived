import os
import re
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ADT_BAT = PROJECT_ROOT / "work" / "airsdk" / "bin" / "adt.bat"
KEYSTORE = PROJECT_ROOT / "work" / "debug.keystore"
CONTROL_SWF = PROJECT_ROOT / "work" / "ControlApp.swf"
DESC_IN = PROJECT_ROOT / "input" / "application.xml"
DESC_OUT = PROJECT_ROOT / "work" / "hello_air" / "application_ygo.xml"
OUT_APK = PROJECT_ROOT / "work" / "hello_air" / "ygo_control_adt.apk"

def main():
    import zipfile
    with zipfile.ZipFile(PROJECT_ROOT / "input" / "ygo.apk", "r") as z:
        xml = z.read("assets/META-INF/AIR/application.xml").decode("utf-8")
        for item in z.infolist():
            if item.filename.startswith("assets/icons/"):
                rel_name = item.filename[len("assets/"):]
                out_file = PROJECT_ROOT / "work" / "hello_air" / rel_name
                out_file.parent.mkdir(parents=True, exist_ok=True)
                out_file.write_bytes(z.read(item.filename))

    # Strip extensions for clean baseline test
    xml_mod = re.sub(r"<extensions>.*?</extensions>", "", xml, flags=re.DOTALL)
    # Update targetSdkVersion to 28
    xml_mod = re.sub(r'android:targetSdkVersion="\d+"', 'android:targetSdkVersion="28"', xml_mod)
    # Update namespace to 51.5
    xml_mod = re.sub(r'xmlns="http://ns\.adobe\.com/air/application/[0-9\.]+"',
                     'xmlns="http://ns.adobe.com/air/application/51.5"', xml_mod)
    # Replace content with ControlApp.swf
    xml_mod = re.sub(r"<content>.*?</content>", "<content>ControlApp.swf</content>", xml_mod)

    with open(DESC_OUT, "w", encoding="utf-8") as f:
        f.write(xml_mod)

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
        str(DESC_OUT),
        "-C", str(PROJECT_ROOT / "work"),
        "ControlApp.swf",
        "-C", str(PROJECT_ROOT / "work" / "hello_air"),
        "icons"
    ]
    print("Running ADT command for ygo_control_adt.apk...")
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    print("ADT stdout:", res.stdout)
    print("ADT stderr:", res.stderr)
    print("Returncode:", res.returncode)

    if res.returncode == 0:
        print(f"\nInstalling {OUT_APK} on device...")
        inst = subprocess.run(["adb", "install", "-r", "-d", str(OUT_APK)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print("Install:", inst.stdout, inst.stderr)

        pkg_name = "air.com.konami.ygo"
        subprocess.run(["adb", "shell", "am", "force-stop", pkg_name])
        subprocess.run(["adb", "logcat", "-b", "all", "-c"])

        print(f"Launching {pkg_name}/.AppEntry...")
        subprocess.run(["adb", "shell", "am", "start", "-n", f"{pkg_name}/.AppEntry"])

        import time
        time.sleep(5)

        ps_res = subprocess.run(["adb", "shell", f"ps -A | grep {pkg_name}"], shell=True, stdout=subprocess.PIPE, text=True)
        is_alive = pkg_name in ps_res.stdout
        print(f"App alive after 5s: {is_alive}")

        screen_bytes = subprocess.check_output(["adb", "exec-out", "screencap", "-p"])
        png_out = PROJECT_ROOT / "work" / "logs" / "ygo_control_adt.png"
        png_out.write_bytes(screen_bytes)
        print(f"Screenshot saved to {png_out}")

        from PIL import Image
        import io
        img = Image.open(io.BytesIO(screen_bytes))
        extrema = img.convert("L").getextrema()
        print(f"Extrema (min, max): {extrema}")

if __name__ == "__main__":
    main()
