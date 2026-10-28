import os
import re
import struct
import subprocess
import zipfile
from pathlib import Path

APK1 = "work/ygo_control.apk"       # Failing patched control
APK2 = "work/hello_air/hello.apk"    # Working official SDK captive build

def get_zip_info(apk_path):
    with zipfile.ZipFile(apk_path, "r") as z:
        files = {item.filename: item for item in z.infolist()}
    return files

def check_alignment(apk_path):
    alignments = {}
    with open(apk_path, "rb") as f, zipfile.ZipFile(apk_path, "r") as z:
        for item in z.infolist():
            f.seek(item.header_offset)
            l_hdr = f.read(30)
            _, _, _, method, _, _, _, c_size, u_size, n_len, e_len = struct.unpack("<IHHHHHIIIHH", l_hdr)
            data_offset = item.header_offset + 30 + n_len + e_len
            alignments[item.filename] = {
                "method": method,
                "compressed": c_size,
                "uncompressed": u_size,
                "offset": data_offset,
                "align_4": (data_offset % 4 == 0),
                "align_16k": (data_offset % 16384 == 0),
            }
    return alignments

def check_elf_segments(so_data):
    # Check ELF PT_LOAD alignment
    if len(so_data) < 64 or so_data[:4] != b"\x7fELF":
        return "Not an ELF"
    ei_class = so_data[4] # 1=32bit, 2=64bit
    if ei_class == 2: # 64-bit ELF
        e_phoff = struct.unpack("<Q", so_data[32:40])[0]
        e_phentsize = struct.unpack("<H", so_data[54:56])[0]
        e_phnum = struct.unpack("<H", so_data[56:58])[0]
        pt_loads = []
        for i in range(e_phnum):
            ph_bytes = so_data[e_phoff + i*e_phentsize : e_phoff + (i+1)*e_phentsize]
            p_type, p_flags = struct.unpack("<II", ph_bytes[:8])
            if p_type == 1: # PT_LOAD
                p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align = struct.unpack("<QQQQQQ", ph_bytes[8:56])
                pt_loads.append({"offset": p_offset, "vaddr": p_vaddr, "align": p_align})
        return pt_loads
    return "32-bit ELF"

def main():
    print(f"=== COMPARING {APK1} (FAILING) VS {APK2} (WORKING) ===\n")
    files1 = get_zip_info(APK1)
    files2 = get_zip_info(APK2)
    align1 = check_alignment(APK1)
    align2 = check_alignment(APK2)

    # 1. High-level counts
    print(f"Total entries: Failing={len(files1)}, Working={len(files2)}")

    # 2. Manifest and Descriptor diff
    print("\n--- 1. DESCRIPTOR & MANIFEST ---")
    with zipfile.ZipFile(APK1, "r") as z1, zipfile.ZipFile(APK2, "r") as z2:
        desc1 = z1.read("assets/META-INF/AIR/application.xml").decode("utf-8", errors="ignore")
        desc2 = z2.read("assets/META-INF/AIR/application.xml").decode("utf-8", errors="ignore")
        print(f"Failing descriptor size: {len(desc1)} bytes, root META-INF present: {'META-INF/AIR/application.xml' in files1}")
        print(f"Working descriptor size: {len(desc2)} bytes, root META-INF present: {'META-INF/AIR/application.xml' in files2}")
        print(f"Failing namespace: {re.findall(r'xmlns=\"[^\"]+\"', desc1)}")
        print(f"Working namespace: {re.findall(r'xmlns=\"[^\"]+\"', desc2)}")

    # 3. DEX files
    print("\n--- 2. DEX FILES ---")
    dex1 = [f for f in files1 if f.endswith(".dex")]
    dex2 = [f for f in files2 if f.endswith(".dex")]
    print(f"Failing DEX: {dex1}")
    for d in dex1:
        print(f"  {d}: size={files1[d].file_size}, compress={files1[d].compress_type}")
    print(f"Working DEX: {dex2}")
    for d in dex2:
        print(f"  {d}: size={files2[d].file_size}, compress={files2[d].compress_type}")

    # 4. Lib layout
    print("\n--- 3. NATIVE LIBRARIES (lib/) ---")
    libs1 = [f for f in files1 if f.startswith("lib/")]
    libs2 = [f for f in files2 if f.startswith("lib/")]
    print("Failing libs:")
    for l in sorted(libs1):
        info = align1[l]
        print(f"  {l:40} method={info['method']} size={info['uncompressed']} 16KB_aligned={info['align_16k']}")
    print("Working libs:")
    for l in sorted(libs2):
        info = align2[l]
        print(f"  {l:40} method={info['method']} size={info['uncompressed']} 16KB_aligned={info['align_16k']}")

    # 5. ELF PT_LOAD alignment
    print("\n--- 4. ELF PT_LOAD SEGMENT ALIGNMENT (in libCore.so) ---")
    with zipfile.ZipFile(APK1, "r") as z1:
        so1_arm64 = z1.read("lib/arm64-v8a/libCore.so") if "lib/arm64-v8a/libCore.so" in files1 else None
    with zipfile.ZipFile(APK2, "r") as z2:
        so2_arm64 = z2.read("lib/arm64-v8a/libCore.so") if "lib/arm64-v8a/libCore.so" in files2 else None

    if so1_arm64:
        loads1 = check_elf_segments(so1_arm64)
        print("Failing libCore.so (arm64-v8a) PT_LOAD segments:")
        for seg in loads1:
            print(f"  offset={hex(seg['offset'])}, vaddr={hex(seg['vaddr'])}, align={hex(seg['align'])}")
    if so2_arm64:
        loads2 = check_elf_segments(so2_arm64)
        print("Working libCore.so (arm64-v8a) PT_LOAD segments:")
        for seg in loads2:
            print(f"  offset={hex(seg['offset'])}, vaddr={hex(seg['vaddr'])}, align={hex(seg['align'])}")

    # 6. AndroidManifest.xml comparison
    print("\n--- 5. ANDROIDMANIFEST.XML COMPARISON ---")
    with zipfile.ZipFile(APK1, "r") as z1, zipfile.ZipFile(APK2, "r") as z2:
        axml1 = z1.read("AndroidManifest.xml")
        axml2 = z2.read("AndroidManifest.xml")
    print(f"Failing AndroidManifest.xml size: {len(axml1)} bytes")
    print(f"Working AndroidManifest.xml size: {len(axml2)} bytes")

    # 7. Zip alignment summary
    print("\n--- 6. ZIP ALIGNMENT SUMMARY ---")
    mis1 = [k for k, v in align1.items() if v["method"] == 0 and not v["align_4"]]
    mis2 = [k for k, v in align2.items() if v["method"] == 0 and not v["align_4"]]
    print(f"Failing uncompressed misaligned (not 4-byte): {len(mis1)}")
    print(f"Working uncompressed misaligned (not 4-byte): {len(mis2)}")

if __name__ == "__main__":
    main()
