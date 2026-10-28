"""Install the verified offline bundle for the current Windows user."""

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

APP_NAME = "CiscoPhoneViewer-1.0.0"


def verify(root):
    manifest = json.loads((root / "SHA256SUMS.json").read_text(encoding="utf-8"))
    if any(path.is_symlink() for path in root.rglob("*")):
        raise ValueError("Package must not contain symbolic links")
    expected = set(manifest) | {"SHA256SUMS.json"}
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if actual != expected:
        raise ValueError("Package contains missing or unexpected files")
    for relative, digest in manifest.items():
        verify_file(root, relative, digest)


def verify_file(root, relative, digest):
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Invalid package path")
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError(f"Package checksum mismatch: {relative}")


def install(root, local_appdata, roaming_appdata):
    verify(root)
    destination = local_appdata / "Programs" / APP_NAME
    if destination.exists():
        raise FileExistsError(
            f"Already installed at {destination}. Remove the old copy first."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="cisco-viewer-", dir=destination.parent))
    try:
        shutil.copytree(root, staging, dirs_exist_ok=True)
        verify(staging)
        staging.rename(destination)
    except Exception:
        shutil.rmtree(staging)
        raise
    start_menu = roaming_appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    start_menu.mkdir(parents=True, exist_ok=True)
    # Escape percent signs because this file is interpreted by cmd.exe.
    launcher = str(destination / "Start Viewer.cmd").replace("%", "%%")
    (start_menu / "Cisco Phone Viewer.cmd").write_text(
        '@echo off\r\nchcp 65001 >nul\r\ncall "' + launcher + '"\r\n',
        encoding="utf-8",
    )
    print(f"Installed to {destination}")
    print("Open Cisco Phone Viewer from Start, or double-click Start Viewer.cmd there.")
    return destination


def main():
    if sys.platform != "win32":
        raise SystemExit("This installer is for Windows 11 x64 only.")
    root = Path(__file__).resolve().parent
    install(root, Path(os.environ["LOCALAPPDATA"]), Path(os.environ["APPDATA"]))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as exc:
        print(f"Installation failed: {exc}")
        raise SystemExit(1) from exc
