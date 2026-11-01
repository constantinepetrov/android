#!/usr/bin/env python3
"""Prepare a data-free APK template after comparing every source asset to the APK.

This preparation tool needs the original APK and its existing bundle symlinks.
The runner needs only reconstruct_apk.py, recipe.json, template.gz and the
official installer data.  This tool never reads a signing key.
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import time
import zipfile
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reconstruct_apk import APK_SHA256, APK_SIZE, ASSET_COUNT, CHUNK_SIZE, SCHEMA, require


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--source-provenance", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    data_root = args.data_root.resolve(strict=True)
    output_dir = args.output_dir.resolve(strict=True)
    template_path = output_dir / "template.gz"
    recipe_path = output_dir / "recipe.json"
    require(not template_path.exists() and not recipe_path.exists(), "Template/recipe already exists")
    require(args.apk.stat().st_size == APK_SIZE, "Unexpected input APK size")
    source_provenance = json.loads(args.source_provenance.read_text(encoding="utf-8"))
    template_compressed_digest = hashlib.sha256()
    template_raw_digest = hashlib.sha256()
    whole_digest = hashlib.sha256()
    template_raw_size = 0
    template_size = 0
    compressor = zlib.compressobj(9, zlib.DEFLATED, 31)
    assets = []
    position = 0

    with zipfile.ZipFile(args.apk) as archive, args.apk.open("rb") as apk, template_path.open("xb") as template:
        ranges = []
        other_assets = []
        for entry in archive.infolist():
            if not entry.filename.startswith("assets/kamdata/"):
                if entry.filename.startswith("assets/"):
                    other_assets.append(entry.filename)
                continue
            require(entry.compress_type in (0, 8), f"Unsupported method: {entry.filename}")
            require(not entry.flag_bits & 1, f"Encrypted entry: {entry.filename}")
            apk.seek(entry.header_offset)
            header = apk.read(30)
            require(header[:4] == b"PK\x03\x04", "Invalid local ZIP header")
            name_size, extra_size = struct.unpack_from("<HH", header, 26)
            ranges.append((entry.header_offset + 30 + name_size + extra_size, entry))
        ranges.sort(key=lambda item: item[0])
        require(len(ranges) == ASSET_COUNT, "Unexpected game asset count")
        require(sorted(other_assets) == sorted([
            "assets/kamdata.lst", "assets/licenses/AGPL-3.0.txt", "assets/licenses/SOURCE.txt",
        ]), f"Unreviewed non-game assets: {other_assets}")

        def save_template(data):
            nonlocal template_raw_size, template_size
            template_raw_size += len(data)
            template_raw_digest.update(data)
            whole_digest.update(data)
            compressed = compressor.compress(data)
            template.write(compressed)
            template_compressed_digest.update(compressed)
            template_size += len(compressed)

        def preserve_until(end):
            nonlocal position
            require(end >= position, "Overlapping asset ranges")
            apk.seek(position)
            while position < end:
                data = apk.read(min(CHUNK_SIZE, end - position))
                require(bool(data), "Unexpected APK EOF")
                save_template(data)
                position += len(data)

        for offset, entry in ranges:
            preserve_until(offset)
            source = (args.bundle_root / entry.filename.removeprefix("assets/")).resolve(strict=True)
            require(data_root in source.parents, f"Source outside official data root: {source}")
            require(source.is_file() and source.stat().st_size == entry.file_size,
                    f"Source size mismatch: {entry.filename}")
            source_digest = hashlib.sha256()
            payload_digest = hashlib.sha256()
            payload_size = 0
            raw_size = 0
            asset_compressor = zlib.compressobj(1, zlib.DEFLATED, -15, 8, zlib.Z_DEFAULT_STRATEGY) if entry.compress_type == 8 else None

            def compare_payload(data):
                nonlocal payload_size
                require(apk.read(len(data)) == data, f"Original payload mismatch: {entry.filename}")
                payload_digest.update(data)
                whole_digest.update(data)
                payload_size += len(data)

            with source.open("rb") as original:
                for data in iter(lambda: original.read(CHUNK_SIZE), b""):
                    source_digest.update(data)
                    raw_size += len(data)
                    compare_payload(asset_compressor.compress(data) if asset_compressor else data)
            if asset_compressor is not None:
                compare_payload(asset_compressor.flush())
            require(payload_size == entry.compress_size and raw_size == entry.file_size,
                    f"Payload/source size mismatch: {entry.filename}")
            assets.append({
                "apk_path": entry.filename, "offset": offset,
                "compressed_size": entry.compress_size, "zip_method": entry.compress_type,
                "size": entry.file_size, "source_path": source.relative_to(data_root).as_posix(),
                "source_sha256": source_digest.hexdigest(),
                "payload_sha256": payload_digest.hexdigest(),
            })
            position = offset + entry.compress_size
        preserve_until(APK_SIZE)
        require(not apk.read(1), "Unexpected APK trailing bytes")
        compressed = compressor.flush()
        template.write(compressed)
        template_compressed_digest.update(compressed)
        template_size += len(compressed)

    require(whole_digest.hexdigest() == APK_SHA256, "Input/reconstructed APK SHA-256 mismatch")
    recipe = {
        "schema": SCHEMA,
        "apk": {
            "filename": "KaM_Remake_r16397_ARM64_debug.apk", "size": APK_SIZE,
            "sha256": APK_SHA256,
            "source_commit": "c9214fd1451ac264d9bfc1b851b7b9360ab9eb52",
            "application_id": "org.kamremake.android", "abi": "arm64-v8a",
        },
        "installer": {
            "filename": "KaM-Remake-Beta-r16397.exe", "size": 711493971,
            "sha256": "9980a414f4adbe3806c322de5a74068861857968b3b5ddd4ec1d84987208cd9e",
            "landing_page": "https://www.kamremake.com/download/",
            "observed_download_url": "https://www.kamremake.com/files/kam-remake-r16397/?tmstv=1793532124",
            "extraction_tool": "innoextract", "verified_extraction_version": "1.9",
            "extraction_command": "innoextract -s -d EXTRACT_DIR KaM-Remake-Beta-r16397.exe",
            "data_root_after_extraction": "EXTRACT_DIR/app",
            "installer_executed": False,
        },
        "template": {
            "file": "template.gz", "compression": "gzip", "size": template_size,
            "sha256": template_compressed_digest.hexdigest(), "raw_size": template_raw_size,
            "raw_sha256": template_raw_digest.hexdigest(),
            "definition": "Concatenated original APK ranges outside all assets/kamdata/ payloads; original offsets are recorded in assets.",
            "remaining_asset_paths": other_assets,
        },
        "asset_compression": {
            "method": "raw-deflate", "level": 1, "window_bits": -15,
            "mem_level": 8, "strategy": 0,
        },
        "corresponding_source": source_provenance,
        "preparation": {
            "all_source_payloads_compared_with_original_apk": True,
            "asset_count": len(assets), "zlib_version": zlib.ZLIB_RUNTIME_VERSION,
            "input_and_reconstructed_sha256": whole_digest.hexdigest(),
            "android_runtime_tested": False, "private_signing_key_used": False,
        },
        "assets": assets,
    }
    with recipe_path.open("x", encoding="utf-8") as output:
        json.dump(recipe, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(json.dumps({
        "status": "prepared", "template": recipe["template"],
        "recipe_bytes": recipe_path.stat().st_size,
        "recipe_sha256": hashlib.sha256(recipe_path.read_bytes()).hexdigest(),
        "asset_count": len(assets), "apk_sha256": whole_digest.hexdigest(),
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }, indent=2))


if __name__ == "__main__":
    main()
