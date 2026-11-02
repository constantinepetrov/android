#!/usr/bin/env python3
"""Prepare the exact signed KaM APK using official data and a code-only template.

Downloads the public installer (never executes it), extracts files with
innoextract, and invokes the hash-checked reconstruction. No Android is started.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.parse import urlsplit

# This exact alternate is linked by the authors at https://www.kamremake.com/download/.
# GitHub-hosted runners timed out connecting to the primary www.kamremake.com host.
# Keep the installer and reconstructed APK identities pinned across the route change.
INSTALLER_URL = "https://release.knightsprovince.com/index.php/s/9xdF69oCWmJXW59/download/KaM%20Remake%20Beta%20r16397.exe"
INSTALLER_BYTES = 711493971
INSTALLER_SHA256 = "9980a414f4adbe3806c322de5a74068861857968b3b5ddd4ec1d84987208cd9e"
APK_BYTES = 856629249
APK_SHA256 = "c7df4b880984b9a475b57ee00b41fa5ba6140f4c21e5f688a9188ab1622169c4"
TEMPLATE_BYTES = 30104246
TEMPLATE_SHA256 = "3f9a8ab6628dc28ad959a912d40c7504a9b81aa3902a351ca023031a0732e0a4"
HERE = Path(__file__).resolve().parent


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def require_file(path, size, sha):
    if not path.is_file() or path.stat().st_size != size or digest(path) != sha:
        raise RuntimeError("File identity mismatch: " + str(path))


def write_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


def assemble_template(output):
    manifest_path = HERE / "reconstruction/template-parts.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("sha256") != TEMPLATE_SHA256 or manifest.get("bytes") != TEMPLATE_BYTES:
        raise RuntimeError("Unexpected template manifest identity")
    records = manifest.get("parts", [])
    if not records:
        raise RuntimeError("No template parts")
    seen = set()
    with output.open("xb") as target:
        for record in records:
            name = record["name"]
            if Path(name).name != name or name in seen or not name.startswith("template.gz.part"):
                raise RuntimeError("Invalid or duplicate template part")
            seen.add(name)
            part = manifest_path.parent / "parts" / name
            require_file(part, record["bytes"], record["sha256"])
            with part.open("rb") as source:
                shutil.copyfileobj(source, target, length=1024 * 1024)
    require_file(output, TEMPLATE_BYTES, TEMPLATE_SHA256)
    return len(records)


def download(output, timeout, evidence, record):
    if output.exists():
        raise RuntimeError("Refusing to replace an existing installer download")
    curl = shutil.which("curl")
    if not curl:
        raise RuntimeError("curl is required for the bounded IPv4 installer download")
    if shutil.which("getent"):
        try:
            command("installer-dns", ["getent", "ahosts", urlsplit(INSTALLER_URL).hostname],
                    evidence, 20, record)
        except RuntimeError as exc:
            record["dns_probe_warning"] = str(exc)
    # The first real GitHub run timed out before receiving response headers.
    # Use the authors' official alternate URL with TLS verification and IPv4, and
    # preserve DNS/HTTP diagnostics. The outer process deadline bounds retries.
    argv = [curl, "--ipv4", "--location", "--fail", "--show-error", "--silent",
            "--connect-timeout", "20", "--max-time", str(timeout),
            "--retry", "2", "--retry-delay", "3", "--retry-max-time", str(timeout),
            "--remove-on-error", "--user-agent", "Mozilla/5.0 (compatible; KaMCloudQA/1.0)",
            "--output", str(output), "--write-out",
            "http_code=%{http_code}\\nremote_ip=%{remote_ip}\\nurl_effective=%{url_effective}\\nsize_download=%{size_download}\\n",
            INSTALLER_URL]
    command("download-installer", argv, evidence, timeout + 30, record)
    require_file(output, INSTALLER_BYTES, INSTALLER_SHA256)
    return {"url": INSTALLER_URL, "source_page": "https://www.kamremake.com/download/",
            "backend": "curl-ipv4", "retry_limit": 2,
            "http_metadata_log": "download-installer.stdout",
            "bytes": output.stat().st_size, "sha256": INSTALLER_SHA256}


def command(name, argv, evidence, timeout, record):
    started = time.monotonic()
    out_file, err_file = evidence / (name + ".stdout"), evidence / (name + ".stderr")
    with out_file.open("wb") as out, err_file.open("wb") as err:
        try:
            result = subprocess.run(argv, stdout=out, stderr=err, timeout=timeout)
            code = result.returncode
        except subprocess.TimeoutExpired:
            code = 124
    record.setdefault("commands", []).append({
        "name": name, "argv": argv, "returncode": code, "timeout_seconds": timeout,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "stdout": out_file.name, "stderr": err_file.name,
    })
    if code:
        raise RuntimeError(name + " failed, exit " + str(code))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--output-apk", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--installer", type=Path, help="Existing pinned official installer, for an offline repeat")
    parser.add_argument("--innoextract", default="innoextract")
    parser.add_argument("--download-timeout", type=int, default=600)
    args = parser.parse_args()
    if not 1 <= args.download_timeout <= 900:
        parser.error("--download-timeout must be between 1 and 900 seconds")
    work, evidence = args.work_dir.resolve(), args.evidence.resolve()
    work.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=True)
    owned = work / "prepare-inputs"
    apk_output = args.output_apk.resolve()
    if apk_output == owned or owned in apk_output.parents:
        parser.error("--output-apk must be outside the temporary prepare-inputs directory")
    if args.installer and (args.installer.resolve() == owned or owned in args.installer.resolve().parents):
        parser.error("--installer must be outside the newly created preparation directory")
    record = {"started_utc": utc(), "status": "RUNNING", "scope": "Input preparation only",
              "apk_sha256_expected": APK_SHA256, "android_started": False,
              "game_executed": False}
    result_path = evidence / "input-preparation.json"
    try:
        if args.output_apk.exists():
            raise RuntimeError("Output APK already exists; use a fresh work directory")
        owned.mkdir(exist_ok=False)
        if shutil.disk_usage(work).free < 4 * 1024**3:
            raise RuntimeError("At least 4 GiB free is required for input preparation")
        template = owned / "template.gz"
        record["template_parts"] = assemble_template(template)
        record["template_sha256"] = digest(template)
        installer = args.installer.resolve() if args.installer else owned / "official-installer.exe"
        if args.installer:
            require_file(installer, INSTALLER_BYTES, INSTALLER_SHA256)
            record["installer"] = {"source": "existing pinned installer", "path": str(installer),
                                   "bytes": INSTALLER_BYTES, "sha256": INSTALLER_SHA256}
        else:
            record["installer"] = download(installer, args.download_timeout, evidence, record)
        write_json(result_path, record)
        extract_dir = owned / "extracted"
        extract_dir.mkdir()
        executable = shutil.which(args.innoextract) or args.innoextract
        command("extract-installer", [executable, "--silent", "--output-dir", str(extract_dir),
                                      str(installer)], evidence, 180, record)
        data_root = extract_dir / "app"
        for folder in ("data", "Campaigns", "Maps", "MapsMP", "Music", "Sounds", "Tutorials"):
            if not (data_root / folder).is_dir():
                raise RuntimeError("Official installer is missing expected directory " + folder)
        command("reconstruct-apk", [sys.executable, str(HERE / "reconstruct_apk.py"),
                                    "--data-root", str(data_root), "--template", str(template),
                                    "--output", str(args.output_apk.resolve())], evidence, 180, record)
        require_file(args.output_apk, APK_BYTES, APK_SHA256)
        record.update(status="INPUT_APK_VERIFIED", apk_path=str(args.output_apk.resolve()),
                      apk_bytes=APK_BYTES, apk_sha256=APK_SHA256)
        # Only this newly created preparation directory is removed. A caller's
        # supplied installer and the completed APK remain outside it.
        shutil.rmtree(owned)
        record["temporary_installer_and_extracted_data_removed"] = True
    except Exception as exc:
        record.update(status="INPUT_PREPARATION_FAILED",
                      error=type(exc).__name__ + ": " + str(exc))
    finally:
        record["finished_utc"] = utc()
        record["host_free_bytes"] = shutil.disk_usage(work).free
        write_json(result_path, record)
        print(json.dumps({key: record.get(key) for key in (
            "status", "error", "apk_bytes", "apk_sha256", "host_free_bytes")}), flush=True)
    return 0 if record["status"] == "INPUT_APK_VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())

