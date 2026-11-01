#!/usr/bin/env python3
"""Take one Airtest ADBCAP snapshot of an explicitly selected existing device.

This is a bounded child of android_cloud_qa.py, not a guest/emulator launcher.
Imports are lazy so --help and syntax validation never contact ADB.
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from airtest.core.android.android import Android
    from PIL import Image

    device = Android(serialno=args.serial, adb_path=args.adb,
                     cap_method="ADBCAP", touch_method="ADBTOUCH", ori_method="ADBORI")
    # ScreenProxy.auto_setup may silently choose MINICAP/JAVACAP if ADBCAP
    # fails. Never label that capture as ADBCAP: fail this helper and let the
    # parent record its explicit raw-ADB fallback instead.
    backend = device.screen_proxy.method_name
    print(json.dumps({"observed_airtest_backend": backend}), flush=True)
    if backend != "ADBCAP":
        raise RuntimeError("Airtest selected unexpected capture backend: " + str(backend))
    device.snapshot(filename=str(args.output), ensure_orientation=False, quality=99)
    if device.screen_proxy.method_name != "ADBCAP":
        raise RuntimeError("Airtest capture backend changed during snapshot")
    with Image.open(args.output) as screenshot:
        if screenshot.format != "PNG" or min(screenshot.size) <= 0:
            raise ValueError("Airtest did not produce a nonempty PNG")
        size = screenshot.size
        screenshot.verify()
    print(json.dumps({"backend": "airtest-adbcap", "observed_airtest_backend": backend,
                      "path": str(args.output), "size": size}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
