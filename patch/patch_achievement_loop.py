#!/usr/bin/env python3
"""Fixes Dark Souls II: Scholar of the First Sin slowing down with every death
by patching 45 bytes of DarkSoulsII.exe in place.

    python3 patch_achievement_loop.py "/path/to/Game/DarkSoulsII.exe"
    python3 patch_achievement_loop.py "/path/to/Game/DarkSoulsII.exe" --revert
    python3 patch_achievement_loop.py "/path/to/Game/DarkSoulsII.exe" --check

Close the game first. It only changes the executable if the 45 bytes in it are
exactly the ones the game ships (or the fixed ones, to revert), so another game
version is never touched. A copy of the file is kept next to it as
DarkSoulsII.exe.orig, unless --no-backup is given; Steam's "Verify integrity of
game files" restores the original too. Needs only Python 3.6 or later.

What the change is, and why, is in docs/ACHIEVEMENT_LOOP.md. The same bytes are
in patch_achievement_loop.ps1 and ../src/ds2_fix_achievement_loop.c.
"""

from __future__ import annotations

import argparse
import shutil
import sys

# The file offset of virtual address 0x140b5e82c, in the executable's first
# code section (raw pointer 0x400 for virtual address 0x140001000).
OFFSET = 0xB5DC2C

ORIGINAL_CODE = bytes.fromhex(
    "44387b7c0f85b80000004084ff0f84af000000488b4368c6437c01488b7808"
    "44387b740f849900000044887b7c"
)

FIXED_CODE = bytes.fromhex(
    "403a7b7c0f86b8000000488b43684438b8900100000f85a7000000488b7808"
    "44387b740f94437c0f8495000000"
)

assert len(ORIGINAL_CODE) == len(FIXED_CODE) == 45


def state_of(code: bytes) -> str:
    """'original', 'fixed' or 'unknown' for the 45 bytes found in the file."""
    if code == ORIGINAL_CODE:
        return "original"
    if code == FIXED_CODE:
        return "fixed"
    return "unknown"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Patch DarkSoulsII.exe so deaths no longer slow the game"
        " down (see docs/ACHIEVEMENT_LOOP.md)."
    )
    parser.add_argument("executable", help="path to DarkSoulsII.exe")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--revert", action="store_true", help="put the game's own code back"
    )
    mode.add_argument(
        "--check", action="store_true", help="only say which it has"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="don't keep a copy as DarkSoulsII.exe.orig first",
    )
    args = parser.parse_args(argv)

    try:
        with open(args.executable, "rb") as file:
            file.seek(OFFSET)
            found = file.read(len(ORIGINAL_CODE))
    except OSError as error:
        print(f"Could not read {args.executable}: {error}", file=sys.stderr)
        return 1
    state = state_of(found)
    print(f"{args.executable}: {state}")
    if state == "unknown":
        print(
            "These are not the bytes of a game version this is made for, so"
            " the file is left alone. After a game update, verify the game"
            " files in Steam.",
            file=sys.stderr,
        )
        return 0 if args.check else 1
    if args.check:
        return 0
    want = "original" if args.revert else "fixed"
    if state == want:
        print("Already so; nothing to do.")
        return 0
    try:
        if not args.no_backup and not args.revert:
            backup = args.executable + ".orig"
            shutil.copy2(args.executable, backup)
            print(f"Copied the game's file to {backup}.")
        with open(args.executable, "r+b") as file:
            file.seek(OFFSET)
            file.write(ORIGINAL_CODE if args.revert else FIXED_CODE)
    except OSError as error:
        print(
            f"Could not write {args.executable}: {error}\n"
            "Is the game closed?",
            file=sys.stderr,
        )
        return 1
    print(f"Done: {want}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
