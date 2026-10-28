#!/usr/bin/env python3
"""
Generate the RSA key pair used for the game-server login (stdlib only).

The client encrypts LoginRequest.name/password with the public key from
assets/config/publickey.xml (Engine.as:395-420, RSAEncryption.as:31-35, PKCS#1 v1.5
type-2 padding, RSAKey.as:204-250). We ship our own public key in the APK and keep
the private key on the server, so Konami's private key is never needed.

Writes:
  server/data/rsa_private.json   (n, e, d as hex; SECRET, copy to the server's data dir)
  server/data/publickey.xml      (same format as the original config/publickey.xml)
Usage: python tools/gen_rsa_key.py [--bits 1024] [--force]
"""

import argparse
import json
import secrets
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA = PROJECT_ROOT / "server" / "data"


def is_probable_prime(n, rounds=40):
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for _ in range(rounds):
        a = secrets.randbelow(n - 3) + 2
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def gen_prime(bits):
    while True:
        c = secrets.randbits(bits) | (1 << (bits - 1)) | (1 << (bits - 2)) | 1
        if is_probable_prime(c):
            return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bits", type=int, default=1024)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    priv = DATA / "rsa_private.json"
    if priv.exists() and not args.force:
        raise SystemExit(f"{priv} exists; use --force to replace (clients built with the old key stop working)")
    e = 65537
    while True:
        p, q = gen_prime(args.bits // 2), gen_prime(args.bits // 2)
        phi = (p - 1) * (q - 1)
        if p != q and phi % e:
            break
    n = p * q
    d = pow(e, -1, phi)
    DATA.mkdir(parents=True, exist_ok=True)
    priv.write_text(json.dumps({"n": format(n, "x"), "e": format(e, "x"), "d": format(d, "x")}, indent=1))
    (DATA / "publickey.xml").write_text(
        "<RSAKeyValue>\n  <Modulus>%s</Modulus>\n  <Exponent>%s</Exponent>\n</RSAKeyValue>\n"
        % (format(n, "x"), format(e, "06x")))
    print(f"wrote {priv} and {DATA / 'publickey.xml'} ({n.bit_length()} bit modulus)")


if __name__ == "__main__":
    main()
