#!/usr/bin/env python3
"""Prepare an isolated Pascal Script source tree by applying the tracked FPC patch.

The submodule checkout remains pristine. The patch is deliberately applied only
to the Android/FPC build copy and is tested by the Android CI workflows.
"""
import pathlib
import shutil
import subprocess
import sys

source, output = map(pathlib.Path, sys.argv[1:])
patch_file = pathlib.Path(__file__).resolve().parent.parent / "patches" / "pascalscript-fpc-3.2.2.patch"
output.mkdir(parents=True, exist_ok=True)
for path in source.iterdir():
    if path.suffix.lower() in (".pas", ".inc"):
        shutil.copyfile(path, output / path.name)

subprocess.run(
    ["patch", "--batch", "--forward", "--binary", "-p1", "-d", str(output)],
    input=patch_file.read_bytes(),
    check=True,
)
print("Applied tracked Pascal Script FPC 3.2.2 patch to isolated build copy")
