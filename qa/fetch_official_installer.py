#!/usr/bin/env python3
"""Fetch and verify the pinned public installer for this workflow only.

This does not execute the installer, start Android, or run KaM. The caller owns
the temporary directory and the short-lived cross-job artifact.
"""
import argparse
import json
from pathlib import Path
import shutil

from prepare_inputs import download, utc, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 600:
        parser.error("--timeout must be between 1 and 600 seconds")
    output, evidence = args.output.resolve(), args.evidence.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=True)
    record = {
        "started_utc": utc(), "status": "RUNNING",
        "scope": "Official installer transfer only; no Android or game execution",
        "android_started": False, "game_executed": False,
    }
    try:
        if shutil.disk_usage(output.parent).free < 2 * 1024**3:
            raise RuntimeError("At least 2 GiB free is required")
        record["installer"] = download(output, args.timeout, evidence, record)
        record["status"] = "INPUT_INSTALLER_VERIFIED"
    except Exception as exc:
        record.update(status="INPUT_FETCH_FAILED", error=type(exc).__name__ + ": " + str(exc))
    finally:
        record["finished_utc"] = utc()
        write_json(evidence / "installer-fetch.json", record)
        print(json.dumps(record), flush=True)
    return 0 if record["status"] == "INPUT_INSTALLER_VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
