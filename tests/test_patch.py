"""Tests of the executable patch scripts and that they, the DLL's source and
the docs all have the same bytes. Run: python3 -m unittest discover tests

The PowerShell script is only run if `pwsh` (or `powershell`) is installed.
"""

import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "patch" / "patch_achievement_loop.py"
POWERSHELL_SCRIPT = ROOT / "patch" / "patch_achievement_loop.ps1"
C_SOURCE = ROOT / "src" / "ds2_fix_achievement_loop.c"

spec = importlib.util.spec_from_file_location("patch_achievement_loop", SCRIPT)
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)

POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


def executable_with(code: bytes) -> bytes:
    return b"\x11" * patch.OFFSET + code + b"\x22" * 100


def c_array(name: str) -> bytes:
    text = C_SOURCE.read_text()
    body = re.search(name + r"\[PATCH_SIZE\] = \{(.*?)\};", text, re.S).group(1)
    return bytes(int(x, 16) for x in re.findall(r"0x([0-9a-f]{2})", body))


def powershell_hex(name: str) -> bytes:
    text = POWERSHELL_SCRIPT.read_text()
    line = re.search(r"\$" + name + r" = ConvertFrom-Hex \((.*)\)", text).group(1)
    return bytes.fromhex("".join(re.findall(r"'([0-9a-f]+)'", line)))


class SameBytesEverywhere(unittest.TestCase):
    def test_the_two_versions(self):
        self.assertEqual(len(patch.ORIGINAL_CODE), 45)
        self.assertEqual(len(patch.FIXED_CODE), 45)
        self.assertNotEqual(patch.ORIGINAL_CODE, patch.FIXED_CODE)

    def test_the_dll_source_has_them(self):
        self.assertEqual(c_array("ORIGINAL_CODE"), patch.ORIGINAL_CODE)
        self.assertEqual(c_array("FIXED_CODE"), patch.FIXED_CODE)

    def test_the_powershell_script_has_them(self):
        self.assertEqual(powershell_hex("OriginalCode"), patch.ORIGINAL_CODE)
        self.assertEqual(powershell_hex("FixedCode"), patch.FIXED_CODE)

    def test_the_offsets_are_the_same_place(self):
        rva = int(re.search(r"PATCH_RVA (0x[0-9A-F]+)UL", C_SOURCE.read_text()).group(1), 16)
        # Virtual address 0x140b5e82c, in the section at 0x140001000 whose
        # data starts at file offset 0x400.
        self.assertEqual(0x140000000 + rva, 0x140B5E82C)
        self.assertEqual(rva - 0x1000 + 0x400, patch.OFFSET)
        text = POWERSHELL_SCRIPT.read_text()
        self.assertIn("$Offset = 0xB5DC2C", text)

    def test_every_jump_ends_the_same_handler(self):
        # Each conditional near jump (0f 8x and a 32 bit displacement) of both
        # versions goes to the end of the handler, 0x140b5e8ee.
        for code, jumps in ((patch.ORIGINAL_CODE, (4, 13, 35)), (patch.FIXED_CODE, (4, 21, 39))):
            for at in jumps:
                self.assertEqual(code[at], 0x0F)
                self.assertTrue(0x80 <= code[at + 1] <= 0x8F)
                target = 0x140B5E82C + at + 6 + int.from_bytes(code[at + 2:at + 6], "little")
                self.assertEqual(target, 0x140B5E8EE)


class Script(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "DarkSoulsII.exe"

    def run_script(self, *arguments):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(self.path), *arguments],
            capture_output=True,
            text=True,
        )

    def test_patch_then_revert_changes_only_the_45_bytes(self):
        self.path.write_bytes(executable_with(patch.ORIGINAL_CODE))
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(self.path.read_bytes(), executable_with(patch.FIXED_CODE))
        backup = self.path.with_name("DarkSoulsII.exe.orig")
        self.assertEqual(backup.read_bytes(), executable_with(patch.ORIGINAL_CODE))
        self.assertEqual(self.run_script("--revert").returncode, 0)
        self.assertEqual(self.path.read_bytes(), executable_with(patch.ORIGINAL_CODE))

    def test_no_backup(self):
        self.path.write_bytes(executable_with(patch.ORIGINAL_CODE))
        self.assertEqual(self.run_script("--no-backup").returncode, 0)
        self.assertEqual([p.name for p in self.path.parent.iterdir()], ["DarkSoulsII.exe"])

    def test_check_and_already_so_change_nothing(self):
        self.path.write_bytes(executable_with(patch.FIXED_CODE))
        self.assertIn("fixed", self.run_script("--check").stdout)
        self.assertIn("Already so", self.run_script().stdout)
        self.assertEqual(self.path.read_bytes(), executable_with(patch.FIXED_CODE))
        self.assertEqual([p.name for p in self.path.parent.iterdir()], ["DarkSoulsII.exe"])

    def test_another_version_is_never_written(self):
        other = executable_with(b"\0" * 45)
        self.path.write_bytes(other)
        self.assertNotEqual(self.run_script().returncode, 0)
        self.assertNotEqual(self.run_script("--revert").returncode, 0)
        self.assertEqual(self.run_script("--check").returncode, 0)
        self.assertEqual(self.path.read_bytes(), other)
        self.path.write_bytes(b"short")
        self.assertNotEqual(self.run_script().returncode, 0)

    def test_a_missing_file(self):
        self.assertNotEqual(self.run_script().returncode, 0)


@unittest.skipUnless(POWERSHELL, "PowerShell is not installed")
class PowerShellScript(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "DarkSoulsII.exe"

    def run_script(self, *arguments):
        return subprocess.run(
            [POWERSHELL, "-NoProfile", "-File", str(POWERSHELL_SCRIPT), str(self.path), *arguments],
            capture_output=True,
            text=True,
        )

    def test_patch_then_revert(self):
        self.path.write_bytes(executable_with(patch.ORIGINAL_CODE))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.path.read_bytes(), executable_with(patch.FIXED_CODE))
        backup = self.path.with_name("DarkSoulsII.exe.orig")
        self.assertEqual(backup.read_bytes(), executable_with(patch.ORIGINAL_CODE))
        self.assertIn("Already so", self.run_script().stdout)
        result = self.run_script("-Revert")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.path.read_bytes(), executable_with(patch.ORIGINAL_CODE))

    def test_check_no_backup_and_another_version(self):
        self.path.write_bytes(executable_with(patch.ORIGINAL_CODE))
        self.assertIn("original", self.run_script("-Check").stdout)
        self.assertEqual(self.run_script("-NoBackup").returncode, 0)
        self.assertEqual([p.name for p in self.path.parent.iterdir()], ["DarkSoulsII.exe"])
        other = executable_with(b"\0" * 45)
        self.path.write_bytes(other)
        self.assertNotEqual(self.run_script().returncode, 0)
        self.assertEqual(self.run_script("-Check").returncode, 0)
        self.assertEqual(self.path.read_bytes(), other)


if __name__ == "__main__":
    unittest.main()
