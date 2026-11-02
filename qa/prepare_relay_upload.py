#!/usr/bin/env python3
"""Prepare a confidential, hash-pinned APK upload for one GitHub QA run.

The handshake is public ciphertext. Private key and decoded capsule stay outside
the repository. This script never prints upload capabilities or encryption keys.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
import zipfile

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

APK_BYTES = 856629249
APK_SHA256 = "c7df4b880984b9a475b57ee00b41fa5ba6140f4c21e5f688a9188ab1622169c4"
AAD = b"kam-input-relay-transport-v1"


def b64(value, size=None):
    result = base64.b64decode(value, validate=True)
    if size is not None and len(result) != size:
        raise ValueError("Unexpected binary field size")
    return result


def private_json(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as target:
        json.dump(value, target, indent=2)
        target.write("\n")


def prepare(args):
    envelope = json.loads(args.handshake.read_text())
    if envelope.get("schema_version") != 1 or envelope.get("algorithm") != "RSA-OAEP-SHA256+A256GCM":
        raise ValueError("Unknown handshake protocol")
    private = serialization.load_pem_private_key(args.private_key.read_bytes(), password=None)
    public_der = private.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    if hashlib.sha256(public_der).hexdigest() != envelope.get("key_fingerprint_sha256"):
        raise ValueError("Handshake public key fingerprint mismatch")
    envelope_key = private.decrypt(b64(envelope["wrapped_key_b64"]), padding.OAEP(
        mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    decoded = AESGCM(envelope_key).decrypt(
        b64(envelope["iv_b64"], 12),
        b64(envelope["ciphertext_b64"]) + b64(envelope["tag_b64"], 16), AAD)
    capsule = json.loads(decoded)
    expected = {
        "schema_version": 1, "request_id": args.request_id,
        "github_run_id": args.run_id, "github_run_attempt": args.run_attempt,
        "artifact_name": f"kam-encrypted-apk-{args.run_id}-{args.run_attempt}",
        "expected_apk": {"bytes": APK_BYTES, "sha256": APK_SHA256},
    }
    for field, value in expected.items():
        if capsule.get(field) != value:
            raise ValueError("Handshake identity mismatch: " + field)
    parsed = urlsplit(capsule["signed_upload_url"])
    if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443)
            or not parsed.hostname or not parsed.hostname.endswith(".blob.core.windows.net")
            or not parsed.query or parsed.fragment):
        raise ValueError("Unexpected artifact upload endpoint")
    cipher_info = capsule["payload_cipher"]
    if cipher_info["algorithm"] != "AES-256-GCM":
        raise ValueError("Unexpected payload encryption")
    key, nonce = b64(cipher_info["key_b64"], 32), b64(cipher_info["nonce_b64"], 12)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    plain_hash, plain_bytes = hashlib.sha256(), 0
    with zipfile.ZipFile(args.output_zip, "x", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        with archive.open("app.apk.enc", "w", force_zip64=True) as target:
            for path in args.parts:
                with path.open("rb") as source:
                    while chunk := source.read(4 * 1024 * 1024):
                        plain_hash.update(chunk)
                        plain_bytes += len(chunk)
                        target.write(encryptor.update(chunk))
            target.write(encryptor.finalize())
            target.write(encryptor.tag)
    if plain_bytes != APK_BYTES or plain_hash.hexdigest() != APK_SHA256:
        args.output_zip.unlink(missing_ok=True)
        raise ValueError("Source APK identity mismatch; upload was not attempted")
    with args.output_zip.open("rb") as source:
        zip_sha256 = hashlib.file_digest(source, "sha256").hexdigest()
    zip_bytes = args.output_zip.stat().st_size
    if not APK_BYTES + 16 < zip_bytes < APK_BYTES + 1024 * 1024:
        raise ValueError("Unexpected encrypted ZIP size")
    receipt = {field: expected[field] for field in (
        "schema_version", "request_id", "github_run_id", "github_run_attempt", "artifact_name")}
    receipt.update(zip_bytes=zip_bytes, zip_sha256=zip_sha256)
    private_json(args.capsule_output, capsule)
    private_json(args.receipt_output, receipt)
    print(json.dumps({"status": "ENCRYPTED_UPLOAD_PREPARED", "run_id": args.run_id,
                      "apk_bytes": plain_bytes, "apk_sha256": plain_hash.hexdigest(),
                      "zip_bytes": zip_bytes, "zip_sha256": zip_sha256}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handshake", type=Path, required=True)
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", default="1")
    parser.add_argument("--output-zip", type=Path, required=True)
    parser.add_argument("--capsule-output", type=Path, required=True)
    parser.add_argument("--receipt-output", type=Path, required=True)
    parser.add_argument("parts", type=Path, nargs="+")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]+", args.run_id) or not re.fullmatch(r"[0-9]+", args.run_attempt):
        parser.error("Run identity must be decimal")
    try:
        prepare(args)
    except Exception as exc:
        # Crypto/HTTP exception text can contain capabilities; report only type.
        print("Relay upload preparation failed: " + type(exc).__name__, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
