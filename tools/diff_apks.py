import os
import struct
import sys
import zipfile
from pathlib import Path

def inspect_apk(apk_path):
    print(f"\n{'='*70}\nINSPECTING: {apk_path}\n{'='*70}")
    with zipfile.ZipFile(apk_path, "r") as z:
        names = z.namelist()
        print(f"Total files: {len(names)}")

        # 1. Manifest
        print("\n--- Manifest & Descriptors ---")
        for n in names:
            if "application.xml" in n or "AndroidManifest.xml" in n:
                print(f"  {n}: size={z.getinfo(n).file_size}")

        # 2. Dex files
        print("\n--- DEX Files ---")
        for n in names:
            if n.endswith(".dex"):
                print(f"  {n}: size={z.getinfo(n).file_size}")

        # 3. Lib layout & 16KB alignment
        print("\n--- Native Libraries (lib/) & 16KB Alignment ---")
        with open(apk_path, "rb") as f:
            for item in z.infolist():
                if item.filename.startswith("lib/"):
                    f.seek(item.header_offset)
                    # Local file header: 30 bytes + name_len + extra_len
                    l_hdr = f.read(30)
                    sig, ver, flags, method, mtime, mdate, crc, c_size, u_size, n_len, e_len = struct.unpack("<IHHHHHIIIHH", l_hdr)
                    data_offset = item.header_offset + 30 + n_len + e_len
                    aligned_16k = (data_offset % 16384 == 0)
                    aligned_4k = (data_offset % 4096 == 0)
                    print(f"  {item.filename:40} | method={method} | offset={data_offset} (16KB: {aligned_16k}, 4KB: {aligned_4k})")

        # 4. Zip alignment overall
        uncompressed_misaligned = []
        with open(apk_path, "rb") as f:
            for item in z.infolist():
                if item.compress_type == 0 and not item.is_dir():
                    f.seek(item.header_offset)
                    l_hdr = f.read(30)
                    _, _, _, _, _, _, _, _, _, n_len, e_len = struct.unpack("<IHHHHHIIIHH", l_hdr)
                    data_offset = item.header_offset + 30 + n_len + e_len
                    if data_offset % 4 != 0:
                        uncompressed_misaligned.append((item.filename, data_offset))
        print(f"\n--- Zip alignment (4-byte for uncompressed) ---")
        if uncompressed_misaligned:
            print(f"  MISALIGNED files: {len(uncompressed_misaligned)}")
            for m in uncompressed_misaligned[:5]:
                print(f"    {m[0]} at offset {m[1]}")
        else:
            print("  All uncompressed entries are 4-byte aligned (OK)")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        for p in sys.argv[1:]:
            inspect_apk(p)
    else:
        inspect_apk("work/ygo_control.apk")
