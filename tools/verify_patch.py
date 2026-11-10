#!/usr/bin/env python3
"""Runs the game's code before and after the patch on an x86-64 emulator, over
every combination of the inputs it reads, and compares them.

    pip install unicorn
    python3 tools/verify_patch.py

The 45 bytes sit at virtual address 0x140b5e82c of DarkSoulsII.exe, in the
handler of Steam's "stats received" callback. Both versions end by either
falling through to 0x140b5e859 (go on to award the first achievement) or
branching to 0x140b5e8ee (the end of the handler). The inputs are what the code
reads: dil ("all the other achievements are unlocked"), this+0x7c (an "awarding"
flag), this+0x74 ("stats received") and the "unlocked" byte of the first
achievement's entry. See docs/ACHIEVEMENT_LOOP.md.
"""

import importlib.util
import itertools
import sys
from pathlib import Path

from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_64, Uc
from unicorn.x86_const import (
    UC_X86_REG_RAX,
    UC_X86_REG_RBX,
    UC_X86_REG_RDI,
    UC_X86_REG_R15,
)

script = Path(__file__).resolve().parent.parent / "patch" / "patch_achievement_loop.py"
spec = importlib.util.spec_from_file_location("patch_achievement_loop", script)
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)

BASE = 0x140B5E000
START = 0x140B5E82C
GO_ON = 0x140B5E859
SKIP = 0x140B5E8EE
OBJECT, ENTRIES = 0x200000, 0x300000
NAME = 0x1122334455667788


def run(code, dil, awarding, received, unlocked, junk):
    emulator = Uc(UC_ARCH_X86, UC_MODE_64)
    emulator.mem_map(BASE, 0x1000)
    emulator.mem_write(BASE, b"\x90" * 0x1000)
    emulator.mem_write(START, code)
    emulator.mem_map(OBJECT, 0x1000)
    emulator.mem_map(ENTRIES, 0x1000)
    emulator.mem_write(OBJECT + 0x7C, bytes([awarding]))
    emulator.mem_write(OBJECT + 0x74, bytes([received]))
    emulator.mem_write(OBJECT + 0x68, ENTRIES.to_bytes(8, "little"))
    emulator.mem_write(ENTRIES + 8, NAME.to_bytes(8, "little"))
    emulator.mem_write(ENTRIES + 0x190, bytes([unlocked]))
    emulator.reg_write(UC_X86_REG_RBX, OBJECT)
    emulator.reg_write(UC_X86_REG_R15, 0)
    emulator.reg_write(UC_X86_REG_RDI, (junk << 8) | dil)  # only dil matters
    emulator.reg_write(UC_X86_REG_RAX, 0xDEADBEEFDEADBEEF)
    result = {}

    def hook(emu, address, size, user):
        if address in (GO_ON, SKIP):
            result["exit"] = "go on" if address == GO_ON else "skip"
            emu.emu_stop()

    emulator.hook_add(UC_HOOK_CODE, hook)
    emulator.emu_start(START, 0, timeout=0, count=100)
    result["awarding"] = emulator.mem_read(OBJECT + 0x7C, 1)[0]
    # rdi only matters on the path that goes on to use it: the first
    # achievement's name.
    went_on = result.get("exit") == "go on"
    result["rdi"] = emulator.reg_read(UC_X86_REG_RDI) if went_on else None
    return result


def main():
    rows, bad = [], 0
    for dil, awarding, received, unlocked in itertools.product((0, 1), repeat=4):
        results = []
        for code in (patch.ORIGINAL_CODE, patch.FIXED_CODE):
            outcomes = {
                tuple(sorted(run(code, dil, awarding, received, unlocked, junk).items()))
                for junk in (0, 0xDEADBE, 0xFFFFFF)
            }
            assert len(outcomes) == 1, "the result depends on the upper bits of rdi"
            results.append(dict(next(iter(outcomes))))
        original, fixed = results
        # The only intended change: where the original goes on to award the
        # first achievement, skip when it is already unlocked.
        expect = "skip" if original["exit"] == "go on" and unlocked else original["exit"]
        only_new_skip = original["exit"] == "go on" and unlocked
        ok = fixed["exit"] == expect
        ok &= fixed["exit"] != "go on" or fixed["rdi"] == original["rdi"]
        # The awarding flag is left alone where only the new check skips.
        ok &= fixed["awarding"] == (awarding if only_new_skip else original["awarding"])
        # The handler sets this+0x74 to 1 itself before this code, so 0 cannot
        # occur here.
        reachable = received == 1
        bad += (not ok) and reachable
        verdict = "ok" if ok else ("BAD" if reachable else "differs (cannot happen: this+0x74 is 1 here)")
        rows.append((dil, awarding, received, unlocked, original["exit"], fixed["exit"], verdict))
    print("dil this+7c this+74 unlocked | original -> patched")
    for dil, awarding, received, unlocked, was, now, verdict in rows:
        note = "   <- the new check" if was == "go on" and now == "skip" else ""
        print(f"  {dil}     {awarding}      {received}       {unlocked}     | {was:5s} -> {now:5s}  {verdict}{note}")
    if bad:
        print(f"\n{bad} reachable case(s) differ.")
        return 1
    print("\nEvery reachable case is as intended (8 of the 16 are reachable).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
