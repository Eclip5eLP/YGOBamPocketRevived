#!/usr/bin/env python3
"""
Yu-Gi-Oh! BAM Pocket - libCore.so Exit-Suppression Hook Patcher

Purpose:
Intercepts and suppresses NativeApplication.exit() calls in the HARMAN AIR 50.2.4.4
arm64-v8a runtime (libCore.so), logging diagnostic messages to Android logcat
via __android_log_print while preventing the native runtime process from terminating.

Architecture & Hook Details [INFERRED from libCore.so disassembly]:
1. Exit Dispatch Stub:
   - Method table entry for NativeApplication.exit() is located at virtual address 0x72f004.
   - Original instruction at 0x72f004 calls 0x7469a0, which tail-calls vtable slot 4 (0x73ed18).
   - Patched to: 'b 0x77f1a0' (direct branch to diagnostic hook).

2. Diagnostic Hook Payload (installed at padding area 0x77f1a0):
   - Preserves frame and registers:
     stp x29, x30, [sp, #-32]!
     mov x29, sp
     stp x0, x1, [sp, #16]
   - Prepares logcat call arguments for __android_log_print (0x25f160):
     w0 = 4 (android_LogPriority: ANDROID_LOG_INFO)
     x1 = adr tag ("BAM_CORE") at 0x77f200
     x2 = adr fmt ("NativeApplication.exit() INTERCEPTED AND SUPPRESSED!\n") at 0x77f210
     bl 0x25f160 (__android_log_print)
   - Restores registers and returns safely:
     ldp x0, x1, [sp, #16]
     ldp x29, x30, [sp], #32
     mov w0, #4 (return integer 4)
     ret

3. Shutdown Wrapper Neutralization:
   - Native engine shutdown wrapper at 0x73ed18 delegates to 0x27136c (which invokes
     AndroidActivityWrapper.finish() and Utils.KillProcess()).
   - Patched to: 'ret' (0xd65f03c0) to prevent any indirect calls to shutdown from killing the process.
"""

import argparse
import os
from pathlib import Path
import struct
import sys

HOOK_ADDR = 0x77F1A0
TAG_ADDR = HOOK_ADDR + 0x60
FMT_ADDR = HOOK_ADDR + 0x70
BL_LOG_PRINT = 0x25F160  # __android_log_print in libCore.so PLT
METHOD_DISPATCH_ADDR = 0x72F004
SHUTDOWN_WRAPPER_ADDR = 0x73ED18


def encode_adr(target_addr: int, pc_addr: int, rd: int) -> int:
    """Encodes an ARM64 ADR instruction."""
    off = target_addr - pc_addr
    immlo = off & 3
    immhi = (off >> 2) & 0x7FFFF
    return 0x10000000 | (immlo << 29) | (immhi << 5) | rd


def encode_bl(target_addr: int, pc_addr: int) -> int:
    """Encodes an ARM64 BL instruction."""
    imm26 = (target_addr - pc_addr) // 4
    return 0x94000000 | (imm26 & 0x03FFFFFF)


def assemble_exit_hook() -> bytes:
    """Assembles the ARM64 diagnostic exit suppression hook payload."""
    insns = [
        # stp x29, x30, [sp, #-32]!
        0xA9BE7BFD,
        # mov x29, sp
        0x910003FD,
        # stp x0, x1, [sp, #16]
        0xA90107E0,
        # mov w0, #4 (ANDROID_LOG_INFO)
        0x52800080,
        # adr x1, TAG_ADDR
        encode_adr(TAG_ADDR, HOOK_ADDR + 16, 1),
        # adr x2, FMT_ADDR
        encode_adr(FMT_ADDR, HOOK_ADDR + 20, 2),
        # bl __android_log_print
        encode_bl(BL_LOG_PRINT, HOOK_ADDR + 24),
        # ldp x0, x1, [sp, #16]
        0xA94107E0,
        # ldp x29, x30, [sp], #32
        0xA8C27BFD,
        # mov w0, #4 (return 4)
        0x321E03E0,
        # ret
        0xD65F03C0,
    ]

    code = bytearray()
    for insn in insns:
        code.extend(struct.pack("<I", insn))

    # Pad to TAG_ADDR and append null-terminated tag
    code.extend(b"\x00" * (TAG_ADDR - (HOOK_ADDR + len(code))))
    code.extend(b"BAM_CORE\x00")

    # Pad to FMT_ADDR and append null-terminated format string
    code.extend(b"\x00" * (FMT_ADDR - (HOOK_ADDR + len(code))))
    code.extend(b"NativeApplication.exit() INTERCEPTED AND SUPPRESSED!\n\x00")

    return bytes(code)


def apply_exit_hook_to_bytes(so_bytes: bytes) -> bytes:
    """
    Applies the exit suppression hook to an arm64-v8a libCore.so binary buffer.
    Returns the modified binary bytes.
    """
    if len(so_bytes) < HOOK_ADDR + 0x100:
        raise ValueError(f"Binary too small ({len(so_bytes)} bytes) for libCore.so hook target.")

    so = bytearray(so_bytes)
    hook_payload = assemble_exit_hook()

    # 1. Install hook payload in padding space
    so[HOOK_ADDR : HOOK_ADDR + len(hook_payload)] = hook_payload

    # 2. Branch from NativeApplication.exit dispatch entry (0x72f004) to hook (0x77f1a0)
    branch_to_hook = 0x14000000 | (((HOOK_ADDR - METHOD_DISPATCH_ADDR) // 4) & 0x03FFFFFF)
    struct.pack_into("<I", so, METHOD_DISPATCH_ADDR, branch_to_hook)

    # 3. Patch shutdown wrapper at 0x73ed18 with 'ret' (0xd65f03c0)
    struct.pack_into("<I", so, SHUTDOWN_WRAPPER_ADDR, 0xD65F03C0)

    return bytes(so)


def main():
    parser = argparse.ArgumentParser(
        description="Patch arm64-v8a libCore.so to suppress and log NativeApplication.exit() calls."
    )
    parser.add_argument(
        "--input",
        default="work/air_runtime/lib/arm64-v8a/libCore.so.bak",
        help="Path to clean input libCore.so (default: work/air_runtime/lib/arm64-v8a/libCore.so.bak)",
    )
    parser.add_argument(
        "--output",
        default="work/air_runtime/lib/arm64-v8a/libCore.so",
        help="Path to write patched libCore.so (default: work/air_runtime/lib/arm64-v8a/libCore.so)",
    )
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.is_file():
        sys.exit(f"Error: Input libCore.so not found: {in_path}")

    print(f"Reading {in_path} ({in_path.stat().st_size} bytes)...")
    clean_bytes = in_path.read_bytes()

    patched_bytes = apply_exit_hook_to_bytes(clean_bytes)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(patched_bytes)
    print(f"Successfully patched {out_path} ({len(patched_bytes)} bytes) with exit-suppression hook.")


if __name__ == "__main__":
    main()
