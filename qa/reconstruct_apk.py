#!/usr/bin/env python3
"""Restore one exact, already signed APK from official data and a data-free template.

No Android compilation or signing takes place.  Both output modes consume the
same bytes; --verify-only hashes them without writing the APK.  Python 3.9+ and
the standard library are sufficient.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile
import time
import zlib


SCHEMA = "kam-exact-apk-reconstruction-v1"
APK_SIZE = 856629249
APK_SHA256 = "c7df4b880984b9a475b57ee00b41fa5ba6140f4c21e5f688a9188ab1622169c4"
ASSET_COUNT = 8885
CHUNK_SIZE = 1024 * 1024


class ReconstructionError(Exception):
    """A failed integrity or input check; no completed APK is published."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReconstructionError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for data in iter(lambda: source.read(CHUNK_SIZE), b""):
            digest.update(data)
    return digest.hexdigest()


def relative_path(value: object, label: str) -> PurePosixPath:
    require(isinstance(value, str) and bool(value), f"Invalid {label}")
    require("\\" not in value and "\x00" not in value, f"Invalid {label}: {value!r}")
    path = PurePosixPath(value)
    require(not path.is_absolute(), f"Absolute {label} is forbidden: {value!r}")
    require(all(part not in ("", ".", "..") for part in value.split("/")),
            f"Non-canonical {label}: {value!r}")
    require(":" not in path.parts[0], f"Drive-qualified {label}: {value!r}")
    return path


def nonnegative_integer(value: object, label: str) -> int:
    require(type(value) is int and value >= 0, f"Invalid {label}")
    return value


def valid_sha256(value: object, label: str) -> str:
    require(isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value), f"Invalid {label}")
    return value


def load_recipe(path: Path) -> dict:
    recipe = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(recipe, dict) and recipe.get("schema") == SCHEMA,
            "Unsupported reconstruction recipe")
    apk = recipe["apk"]
    require(apk["size"] == APK_SIZE and apk["sha256"] == APK_SHA256,
            "Recipe does not describe the fixed c7df4b88 APK")
    template = recipe["template"]
    require(template["compression"] == "gzip", "Unsupported template compression")
    relative_path(template["file"], "template filename")
    nonnegative_integer(template["size"], "template size")
    valid_sha256(template["sha256"], "template SHA-256")
    raw_template_size = nonnegative_integer(template["raw_size"], "raw template size")
    valid_sha256(template["raw_sha256"], "raw template SHA-256")
    require(recipe["asset_compression"] == {
        "method": "raw-deflate", "level": 1, "window_bits": -15,
        "mem_level": 8, "strategy": 0,
    }, "Unsupported asset compression settings")

    assets = recipe["assets"]
    require(isinstance(assets, list) and len(assets) == ASSET_COUNT,
            f"Expected exactly {ASSET_COUNT} asset ranges")
    previous_end = 0
    total_payload = 0
    archive_paths = set()
    for asset in assets:
        path_name = str(relative_path(asset["apk_path"], "APK asset path"))
        require(path_name.startswith("assets/kamdata/"),
                f"Non-game range in asset recipe: {path_name}")
        require(path_name not in archive_paths, f"Duplicate APK path: {path_name}")
        archive_paths.add(path_name)
        relative_path(asset["source_path"], "source path")
        start = nonnegative_integer(asset["offset"], "asset offset")
        size = nonnegative_integer(asset["compressed_size"], "compressed asset size")
        raw_size = nonnegative_integer(asset["size"], "source asset size")
        require(type(asset["zip_method"]) is int and asset["zip_method"] in (0, 8),
                f"Unsupported ZIP method: {path_name}")
        require(asset["zip_method"] != 0 or size == raw_size,
                f"Invalid stored asset size: {path_name}")
        require(start >= previous_end and start + size <= APK_SIZE,
                f"Overlapping or out-of-bounds asset range: {path_name}")
        valid_sha256(asset["source_sha256"], "source SHA-256")
        valid_sha256(asset["payload_sha256"], "payload SHA-256")
        previous_end = start + size
        total_payload += size
    require(raw_template_size + total_payload == APK_SIZE,
            "Template and payload sizes do not cover the whole APK")
    return recipe


def locate_sources(recipe: dict, data_root: Path) -> list[Path]:
    require(data_root.is_dir(), f"Data root is not a directory: {data_root}")
    sources = []
    for asset in recipe["assets"]:
        source = (data_root / asset["source_path"]).resolve(strict=True)
        require(data_root in source.parents,
                f"Asset escapes the data root: {asset['source_path']}")
        require(source.is_file(), f"Asset is not a file: {asset['source_path']}")
        require(source.stat().st_size == asset["size"],
                f"Wrong source size: {asset['source_path']}")
        sources.append(source)
    return sources


def verify_corresponding_source_files(recipe: dict, directory: Path) -> None:
    provenance = recipe["corresponding_source"]
    records = provenance["patches"] + [provenance["license_file"]]
    require(len(provenance["patches"]) == 3, "Expected main patches and the dirty submodule patch")
    for record in records:
        relative_path(record["path"], "corresponding source file")
        path = (directory / record["path"]).resolve(strict=True)
        require(directory in path.parents, "Corresponding source file escapes recipe directory")
        require(path.is_file() and path.stat().st_size == record["size"],
                f"Corresponding source size mismatch: {record['path']}")
        require(sha256_file(path) == record["sha256"],
                f"Corresponding source SHA-256 mismatch: {record['path']}")


def reconstruct(recipe: dict, template_path: Path, sources: list[Path], output) -> dict:
    """The only byte-producing implementation, shared by write and verify modes."""
    whole_digest = hashlib.sha256()
    template_digest = hashlib.sha256()
    total_output = 0
    total_template = 0
    payload_bytes = 0
    stored_count = 0
    deflated_count = 0

    def emit(data: bytes) -> None:
        nonlocal total_output
        total_output += len(data)
        require(total_output <= APK_SIZE, "Reconstruction exceeds fixed APK size")
        whole_digest.update(data)
        if output is not None:
            output.write(data)

    with gzip.open(template_path, "rb") as template:
        def preserve(length: int) -> None:
            nonlocal total_template
            require(length >= 0, "Internal range order error")
            while length:
                data = template.read(min(CHUNK_SIZE, length))
                require(bool(data), "Truncated template")
                length -= len(data)
                total_template += len(data)
                template_digest.update(data)
                emit(data)

        for asset, source in zip(recipe["assets"], sources):
            preserve(asset["offset"] - total_output)
            source_digest = hashlib.sha256()
            payload_digest = hashlib.sha256()
            raw_size = 0
            compressed_size = 0
            compressor = None
            if asset["zip_method"] == 8:
                compressor = zlib.compressobj(1, zlib.DEFLATED, -15, 8, zlib.Z_DEFAULT_STRATEGY)
                deflated_count += 1
            else:
                stored_count += 1

            def emit_payload(data: bytes) -> None:
                nonlocal compressed_size, payload_bytes
                compressed_size += len(data)
                payload_bytes += len(data)
                require(compressed_size <= asset["compressed_size"],
                        f"Payload too large: {asset['apk_path']}")
                payload_digest.update(data)
                emit(data)

            with source.open("rb") as original:
                for data in iter(lambda: original.read(CHUNK_SIZE), b""):
                    raw_size += len(data)
                    require(raw_size <= asset["size"],
                            f"Source grew while reading: {asset['source_path']}")
                    source_digest.update(data)
                    emit_payload(compressor.compress(data) if compressor else data)
            if compressor is not None:
                emit_payload(compressor.flush())
            require(raw_size == asset["size"]
                    and source_digest.hexdigest() == asset["source_sha256"],
                    f"Source SHA-256/size mismatch: {asset['source_path']}")
            require(compressed_size == asset["compressed_size"]
                    and payload_digest.hexdigest() == asset["payload_sha256"],
                    f"Payload mismatch: {asset['apk_path']}; zlib {zlib.ZLIB_RUNTIME_VERSION}")

        preserve(APK_SIZE - total_output)
        require(not template.read(1), "Unexpected trailing bytes in raw template")

    require(total_template == recipe["template"]["raw_size"]
            and template_digest.hexdigest() == recipe["template"]["raw_sha256"],
            "Raw template SHA-256/size mismatch")
    require(total_output == APK_SIZE and whole_digest.hexdigest() == APK_SHA256,
            "Final APK SHA-256/size mismatch")
    return {
        "status": "verified", "apk_size": total_output,
        "apk_sha256": whole_digest.hexdigest(),
        "source_assets_verified": len(sources), "stored_assets": stored_count,
        "deflated_assets": deflated_count, "asset_payload_bytes": payload_bytes,
        "raw_template_bytes": total_template,
        "raw_template_sha256": template_digest.hexdigest(),
        "zlib_compile_version": zlib.ZLIB_VERSION,
        "zlib_runtime_version": zlib.ZLIB_RUNTIME_VERSION,
        "android_runtime_tested": False, "signing_performed": False,
    }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True,
                        help="The installer extraction's app directory, with data/, Campaigns/, etc.")
    parser.add_argument("--recipe", type=Path,
                        default=Path(__file__).resolve().parent / "reconstruction" / "recipe.json")
    parser.add_argument("--template", type=Path,
                        help="Override the template path recorded relative to the recipe")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path, help="New APK path; existing files are never overwritten")
    mode.add_argument("--verify-only", action="store_true",
                      help="Produce and check exactly the same bytes without writing an APK")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started = time.monotonic()
    temporary_path = None
    try:
        recipe_path = args.recipe.resolve(strict=True)
        recipe = load_recipe(recipe_path)
        verify_corresponding_source_files(recipe, recipe_path.parent)
        template_path = (args.template or recipe_path.parent / recipe["template"]["file"]).resolve(strict=True)
        require(template_path.is_file(), "Template is not a regular file")
        require(template_path.stat().st_size == recipe["template"]["size"],
                "Compressed template size mismatch")
        require(sha256_file(template_path) == recipe["template"]["sha256"],
                "Compressed template SHA-256 mismatch")
        sources = locate_sources(recipe, args.data_root.resolve(strict=True))

        if args.verify_only:
            result = reconstruct(recipe, template_path, sources, None)
            result["mode"] = "verify-only"
        else:
            output_path = args.output.absolute()
            require(output_path.parent.is_dir(), "Output parent directory does not exist")
            require(not os.path.lexists(output_path), f"Output already exists: {output_path}")
            free_bytes = shutil.disk_usage(output_path.parent).free
            require(free_bytes >= APK_SIZE + 16 * CHUNK_SIZE,
                    f"Not enough free disk space: {free_bytes} bytes available")
            descriptor, name = tempfile.mkstemp(prefix=f".{output_path.name}.", suffix=".partial",
                                                dir=output_path.parent)
            temporary_path = Path(name)
            with os.fdopen(descriptor, "wb") as output:
                result = reconstruct(recipe, template_path, sources, output)
                output.flush()
                os.fsync(output.fileno())
            # Atomic no-clobber publication on the same filesystem.  A new file
            # appearing at the output path during reconstruction is preserved.
            os.link(temporary_path, output_path)
            temporary_path.unlink()
            temporary_path = None
            result["mode"] = "write"
            result["output"] = str(output_path)
        result["recipe_sha256"] = sha256_file(recipe_path)
        result["template_sha256"] = recipe["template"]["sha256"]
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        print(json.dumps(result, indent=2))
        return 0
    except (ReconstructionError, OSError, ValueError, KeyError, TypeError, zlib.error, EOFError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc),
                          "elapsed_seconds": round(time.monotonic() - started, 3)}), file=sys.stderr)
        return 1
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
