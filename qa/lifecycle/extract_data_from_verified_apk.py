#!/usr/bin/env python3
"""Extract the exactly pinned KaM APK's bundled data for a clean Android rebuild.

No binary/game files enter Git: source APK is previously hash-verified, and all
data remains on the ephemeral runner. The previous APK is not modified.
"""
import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import zipfile

PINNED_SHA = "c7df4b880984b9a475b57ee00b41fa5ba6140f4c21e5f688a9188ab1622169c4"
PINNED_BYTES = 856629249
EXPECTED_FILES = 9820
EXPECTED_UNIQUE = 8885
EXPECTED_BYTES = 1026516608

def check_path(raw):
    path = PurePosixPath(raw)
    if not raw or "\\" in raw or ":" in raw or raw.startswith("/") or len(raw) > 1024 or \
       any(part in (".", "..", "") for part in path.parts):
        raise ValueError("unsafe bundled data path")
    return path

def hash_file(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apk", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    if a.apk.stat().st_size != PINNED_BYTES or hash_file(a.apk) != PINNED_SHA:
        raise SystemExit("Input APK differs from previously tested signed APK")
    a.output.mkdir(parents=True, exist_ok=False)
    seen = {}
    count = 0
    total = 0
    with zipfile.ZipFile(a.apk) as z:
        manifest = z.read("assets/kamdata.lst").decode("utf-8")
        for line in manifest.splitlines():
            entry = line.split("\t")
            if len(entry) != 3:
                raise ValueError("Unexpected kamdata.lst entry")
            length, dest, asset = entry
            dest_path, asset_path = check_path(dest), check_path(asset)
            n = int(length)
            if not (0 <= n <= 128 * 1024 * 1024):
                raise ValueError("Unexpected asset byte size")
            filename = a.output.joinpath(*dest_path.parts)
            filename.parent.mkdir(parents=True, exist_ok=True)
            if filename.exists():
                raise ValueError("Duplicate destination")
            if asset in seen:
                original = seen[asset]
                if original.stat().st_size != n:
                    raise ValueError("Duplicate asset size mismatch")
                os.link(original, filename)
            else:
                archive_path = "assets/kamdata/" + str(asset_path)
                with z.open(archive_path) as source, filename.open("wb") as target:
                    shutil.copyfileobj(source, target, 1024 * 1024)
                if filename.stat().st_size != n:
                    raise ValueError("Asset size mismatch")
                seen[asset] = filename
            count += 1
            total += n
            if count % 2000 == 0:
                print(f"Extracted {count} game paths", flush=True)
    if (count, len(seen), total) != (EXPECTED_FILES, EXPECTED_UNIQUE, EXPECTED_BYTES):
        raise ValueError(f"Unexpected manifest totals: {(count, len(seen), total)}")
    print(f"RESTORED_PINNED_GAME_DATA: {count} files, {len(seen)} unique, {total} bytes")

if __name__ == "__main__":
    main()
