import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from windows.install_windows import install, verify


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "source"
        self.root.mkdir()
        (self.root / "Start Viewer.cmd").write_text("@echo off")
        self.manifest = {"Start Viewer.cmd": hashlib.sha256(b"@echo off").hexdigest()}
        (self.root / "SHA256SUMS.json").write_text(json.dumps(self.manifest))

    def test_install_checks_manifest_and_creates_start_menu_launcher(self):
        local = Path(self.temp.name) / "local"
        roaming = Path(self.temp.name) / "roaming"
        destination = install(self.root, local, roaming)
        verify(destination)
        self.assertTrue(
            (
                roaming / "Microsoft/Windows/Start Menu/Programs/Cisco Phone Viewer.cmd"
            ).is_file()
        )
        with self.assertRaises(FileExistsError):
            install(self.root, local, roaming)

    def test_tampered_file_rejected(self):
        (self.root / "Start Viewer.cmd").write_text("modified")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            verify(self.root)

    def test_unexpected_file_rejected(self):
        (self.root / "extra.py").write_text("unexpected")
        with self.assertRaisesRegex(ValueError, "unexpected files"):
            verify(self.root)

    def test_missing_file_rejected(self):
        (self.root / "Start Viewer.cmd").unlink()
        with self.assertRaisesRegex(ValueError, "missing"):
            verify(self.root)

    def test_symbolic_link_directory_rejected(self):
        try:
            (self.root / "injected").symlink_to(
                Path(self.temp.name), target_is_directory=True
            )
        except OSError as exc:
            self.skipTest(f"Symlink privilege is unavailable: {exc}")
        with self.assertRaisesRegex(ValueError, "symbolic links"):
            verify(self.root)


if __name__ == "__main__":
    unittest.main()
