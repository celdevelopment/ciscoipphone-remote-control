"""Assemble the Windows x64 offline bundle from checksum-pinned official archives."""

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ARCHIVES = {
    "python-3.14.10-embed-amd64.zip": (
        "90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159",
        "https://www.python.org/ftp/python/3.14.10/python-3.14.10-embed-amd64.zip",
    ),
    "pillow-13.0.0-cp314-cp314-win_amd64.whl": (
        "f7cbb7a64e7ec664775195e4f81923bc8a93d9451b963f844e59118f63147a7a",
        "https://pypi.org/project/Pillow/13.0.0/",
    ),
    "defusedxml-0.7.1-py2.py3-none-any.whl": (
        "a352e7e428770286cc899e2542b6cdaedb2b4953ff269a210103ec58f6198a61",
        "https://pypi.org/project/defusedxml/0.7.1/",
    ),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unpack_verified(path, destination):
    expected, _ = ARCHIVES[path.name]
    if digest(path) != expected:
        raise ValueError(f"Upstream checksum mismatch: {path.name}")
    with ZipFile(path) as archive:
        for item in archive.infolist():
            if (
                not (destination / item.filename)
                .resolve()
                .is_relative_to(destination.resolve())
            ):
                raise ValueError("Unsafe archive path")
        archive.extractall(destination)


def copy_application(repo, bundle):
    for name in ("remote_viewer.py", "viewer.html", "viewer-requirements.txt"):
        shutil.copy2(repo / name, bundle / name)
    for name in (
        "Install.cmd",
        "Start Viewer.cmd",
        "Self Test.cmd",
        "install_windows.py",
        "README-WINDOWS.txt",
        "THIRD-PARTY-NOTICES.txt",
    ):
        shutil.copy2(repo / "windows" / name, bundle / name)
    (bundle / "tests").mkdir()
    shutil.copy2(
        repo / "tests/test_remote_viewer.py", bundle / "tests/test_remote_viewer.py"
    )
    # Native cmd.exe text files use CRLF, without PowerShell or policy bypasses.
    for path in bundle.glob("*.cmd"):
        path.write_bytes(
            path.read_text().replace("\r\n", "\n").replace("\n", "\r\n").encode()
        )


def assemble(args, bundle):
    repo = Path(__file__).resolve().parents[1]
    runtime = bundle / "runtime"
    runtime.mkdir()
    unpack_verified(args.runtime, runtime)
    packages = runtime / "site-packages"
    packages.mkdir()
    for name in ARCHIVES:
        if name.endswith(".whl"):
            unpack_verified(args.wheels / name, packages)
    # Explicit search path: no global Python, user site packages, or .pth startup code.
    (runtime / "python314._pth").write_text(
        "python314.zip\n.\nsite-packages\n..\n", encoding="ascii"
    )
    copy_application(repo, bundle)
    shutil.copytree(args.evidence, bundle / "security-evidence")
    shutil.copy2(args.report, bundle / "SECURITY-REVIEW.md")
    provenance = {
        name: {"sha256": values[0], "source": values[1]}
        for name, values in ARCHIVES.items()
    }
    (bundle / "COMPONENTS.json").write_text(json.dumps(provenance, indent=2) + "\n")
    manifest = {
        p.relative_to(bundle).as_posix(): digest(p)
        for p in sorted(bundle.rglob("*"))
        if p.is_file()
    }
    (bundle / "SHA256SUMS.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--wheels", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output ZIP already exists; choose a new path")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cisco-viewer-build-") as temp:
        bundle = Path(temp) / "CiscoPhoneViewer-1.0.0-Windows-x64"
        bundle.mkdir()
        assemble(args, bundle)
        with ZipFile(
            args.output, "w", compression=ZIP_DEFLATED, compresslevel=6
        ) as archive:
            for path in sorted(bundle.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(bundle.parent))
    checksum = digest(args.output)
    args.output.with_suffix(".zip.sha256").write_text(
        f"{checksum}  {args.output.name}\n"
    )
    print(
        f"Created {args.output} ({args.output.stat().st_size:,} bytes)\nSHA-256: {checksum}"
    )


if __name__ == "__main__":
    main()
