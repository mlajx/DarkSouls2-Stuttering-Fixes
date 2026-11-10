# The achievement loop: what it is, and the 45-byte fix

Dark Souls II: Scholar of the First Sin gets slower with every death until the
game is restarted. On an account that has all of the game's achievements, the
cause is a loop in the game's own Steam stats code that never ends, and that
every death makes one copy bigger. This document is what we found, what the
fix changes, and how that was checked. Three ways to apply the same fix are in
this repository:

| | what | where |
|---|---|---|
| DLL | a 3.5 KB `dinput8.dll` that changes the game's code in memory when the game starts | `src/ds2_fix_achievement_loop.c`, `make achievement_loop` |
| Python | changes the same bytes in `DarkSoulsII.exe` itself (Linux, Windows, macOS) | `patch/patch_achievement_loop.py` |
| PowerShell | the same, for Windows | `patch/patch_achievement_loop.ps1` |

All of them make the same 45-byte change, which is explained below. None of
them hooks the Steam API, starts a thread, or touches anything else.

## Who this is for

The loop below only runs on an account that has **every achievement except the
first one**, "The Dark Soul" (the one for earning all the others), or that has
that one too. That is how the game's code is written (see "Why only some
accounts"). If your account is missing any of the others, this fix changes
nothing for you, and a stutter you see has a different cause that we have not
investigated.

To check on Linux/Proton, run the game with
`WINEDEBUG=-all,+steamclient PROTON_LOG=1 %command%` and look in
`~/steam-335300.log`: on an affected account `RequestCurrentStats` appears in
it about every 300 ms for as long as the game runs, and each death adds a
second, third, ... series of them.

## What the game does

The game registers three Steam callbacks when it starts:

| id | Steam's name | the game's handler |
|---|---|---|
| 1101 | `UserStatsReceived` | `0x140b5e6a0`: reads all of the achievements, described below |
| 1102 | `UserStatsStored` | `0x140b5e920`: if still logged on, calls `RequestCurrentStats()` |
| 1103 | `UserAchievementStored` | `0x140b5e690`: does nothing |

The 1101 handler goes through every achievement, one `GetAchievement` and two
`GetAchievementDisplayAttribute` calls (name and description) each, and
remembers which are unlocked. It keeps one flag, "all the others are unlocked",
that **ignores the first achievement**. When that flag is set, it awards the
first achievement, with `SetAchievement`, and then calls `StoreStats`. It
never checks whether the first achievement is already unlocked.

So, on an account that has all the others (and so, after the first time, the
first one too):

1. Steam sends 1101 (stats received).
2. The handler walks every achievement, sees all the others unlocked, and
   awards the first one again, then calls `StoreStats`.
3. Steam answers with 1102 (stats stored).
4. That handler calls `RequestCurrentStats`.
5. Steam answers with 1101. Go to 2.

That is one pass every 300 ms, about 120 round trips to Steam each, for as long
as the game runs. It costs a skipped frame every 18 or so, even in a fresh
game, but it is a loop with a delay in it, so it is not noticed.

Every death makes the game award an achievement of its own ("This is Dark
Souls") and store it. Steam's answer to that is a 1102, whose handler calls
`RequestCurrentStats`, which starts a **second** 1101 and with it a second copy
of the loop. Nothing ever ends a copy. We measured it on the main thread
(offline, Proton, with `strace` counting the calls it sends to Steam):

| deaths | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|---|
| Steam calls per second | 850 | 1,690 | 2,500 | 3,300 | 4,150 | 4,980 | 5,800 | 6,500 | 7,400 |

Each death adds about 830 calls per second, permanently (a fast travel adds
none). The frame rate stays at 60 until the main thread has no time left
between frames, which was at about 12 deaths (10,700 calls per second) here,
where it fell to 54.

What it is not: Steam answered every one of those calls in under a tenth of a
millisecond, so no single `StoreStats` was slow. The problem is how many times
the game makes them.

## Why only some accounts

The loop needs the award in step 2 to happen again and again, which it does
when "all the others are unlocked" is true. On an account that lacks one of
the others the flag stays clear, the handler does nothing, and the chain ends
at step 2. A death still stores an achievement, and so causes one extra pass of
steps 1 to 5, but that ends by itself. We confirmed the difference on the
account we tested (38 of 38 unlocked) by making the game's `GetAchievement`
answer "locked" for one of the others with a test proxy: with that, a death
caused one burst and nothing after it; without it, a permanent loop.

## The fix

The handler must not award the first achievement when it is already unlocked.
The first achievement's "unlocked" byte is in the handler's data already (at
`[entry + 0x190]`, one `0x198`-byte entry per achievement, the first entry
being the one `[rbx+0x68]` points to), so it is one more test, which is the
fix: the loop then ends at its first pass, a death costs one extra pass and not
a permanent one, and awarding the achievement for the first time still works.

The code that does it is the first 45 bytes of the handler's tail, at virtual
address `0x140b5e82c` (file offset `0xB5DC2C`). `dil` is "all the others are
unlocked", `[rbx+0x7c]` is a flag the handler keeps while it is awarding, and
`[rbx+0x74]` is "stats were received". Before:

```
140b5e82c  cmp  BYTE PTR [rbx+0x7c], r15b      ; r15b is 0: already awarding?
140b5e830  jne  0x140b5e8ee                    ;   yes: skip
140b5e836  test dil, dil                       ; all the others unlocked?
140b5e839  je   0x140b5e8ee                    ;   no: skip
140b5e83f  mov  rax, [rbx+0x68]                ; rax = the first achievement's entry
140b5e843  mov  BYTE PTR [rbx+0x7c], 1         ; awarding = 1
140b5e847  mov  rdi, [rax+0x8]                 ; rdi = its name, for SetAchievement
140b5e84b  cmp  BYTE PTR [rbx+0x74], r15b      ; stats received?
140b5e84f  je   0x140b5e8ee                    ;   no: skip
140b5e855  mov  BYTE PTR [rbx+0x7c], r15b      ; awarding = 0
140b5e859  ...                                 ; go on: SetAchievement, StoreStats
```

After:

```
140b5e82c  cmp  dil, BYTE PTR [rbx+0x7c]       ; one test for the first two:
140b5e830  jbe  0x140b5e8ee                    ;   skip unless dil > [rbx+0x7c]
140b5e836  mov  rax, [rbx+0x68]                ; rax = the first achievement's entry
140b5e83a  cmp  BYTE PTR [rax+0x190], r15b     ; is it already unlocked?
140b5e841  jne  0x140b5e8ee                    ;   yes: skip   <- the new check
140b5e847  mov  rdi, [rax+0x8]                 ; rdi = its name, for SetAchievement
140b5e84b  cmp  BYTE PTR [rbx+0x74], r15b      ; stats received?
140b5e84f  sete BYTE PTR [rbx+0x7c]            ; awarding = 1 if not (see below)
140b5e853  je   0x140b5e8ee                    ;   no: skip
140b5e859  ...                                 ; go on: SetAchievement, StoreStats
```

Both versions are 45 bytes and end at `0x140b5e859`, so nothing after them
moves, and every jump of both goes to the same place, the end of the handler
(`0x140b5e8ee`). The two flags `dil` and `[rbx+0x7c]` are only ever 0 or 1,
which is what lets the first two tests become one (`dil` and "not awarding" is
`dil > [rbx+0x7c]`) and make room for the new one. The `sete` keeps what the
original's last two instructions do: `[rbx+0x7c]` ends up 0 when the code goes
on, and is left at 1 on the one path that skips there, as before.

Written as bytes, with `X` for those that change and `.` for those that are
the same in both (29 of the 45 change, 16 are the same; the 45 are the smallest
range that holds every change):

```
before  44 38 7b 7c 0f 85 b8 00 00 00 40 84 ff 0f 84 af 00 00 00 48 8b 43 68 c6 43 7c 01
after   40 3a 7b 7c 0f 86 b8 00 00 00 48 8b 43 68 44 38 b8 90 01 00 00 0f 85 a7 00 00 00
        X  X  .  .  .  X  .  .  .  .  X  X  X  X  X  X  X  X  X  X  X  X  X  X  X  X  X
before  48 8b 78 08 44 38 7b 74 0f 84 99 00 00 00 44 88 7b 7c
after   48 8b 78 08 44 38 7b 74 0f 94 43 7c 0f 84 95 00 00 00
        .  .  .  .  .  .  .  .  .  X  X  X  X  .  X  .  .  .
```

(The jump displacements differ where the jump moved, since the target did not.)

## How it was checked

* **Disassembly.** The listings above are the real bytes, disassembled, and the
  fixed ones were also assembled from source with GNU `as` and compared.
* **Emulation.** `tools/verify_patch.py` runs both versions on an x86-64
  emulator ([Unicorn](https://www.unicorn-engine.org/)) for all 16 combinations
  of what the code reads, and checks that they exit the same way, with the same
  registers where it goes on, except for the one case that is meant to differ:
  the code would go on to award, and the first achievement is already unlocked.
  Eight of the 16 can happen (the handler sets `[rbx+0x74]` before it gets
  here); all eight are as intended.
* **The game.** On the real game (Proton, offline, an account with all 38
  achievements), with either the executable patch or the DLL the frame rate
  stayed at 60 through a dozen or more deaths in a row, where without it it
  fell to 54 by about 12.
* **Tests.** `tests/test_patch.py` (`make test`) checks that the three places
  that have the bytes (the DLL source and both scripts) have the same ones, the
  same place, and that patching and reverting change only those 45 bytes.

Not tested by us: Windows itself, including Windows PowerShell 5.1 (the
PowerShell script was run with PowerShell 7 on Linux, on stand-in files and on a
copy of the real executable's bytes in the tests; the Python script and the
DLL's loading were run on Linux with Wine and Proton).

## The DLL

`src/ds2_fix_achievement_loop.c` is a `dinput8.dll`. The game imports
`DirectInput8Create` from `dinput8.dll`, so one in the game's folder is loaded
in its place, and this one:

1. when it is loaded, looks at the 45 bytes in the running game, and if (and
   only if) they are exactly the ones the game ships, makes them the fixed ones;
2. forwards `DirectInput8Create` to the system's `dinput8.dll`, so controllers
   work as before.

That is all it does. It starts no thread and hooks nothing, and the executable
file is not changed. It is built with no C runtime, which is what keeps it at
3.5 KB (`make achievement_loop`). Wine and Proton load a DLL a program imports
from the program's own folder before their own, so no `WINEDLLOVERRIDES` is
needed (it does no harm if it is set). It has a relocation table, so it still
loads if something else holds the address it is built for.

## The patch scripts

```sh
python3 patch/patch_achievement_loop.py "…/Dark Souls II Scholar of the First Sin/Game/DarkSoulsII.exe"
python3 patch/patch_achievement_loop.py "…/Game/DarkSoulsII.exe" --check    # only say which it has
python3 patch/patch_achievement_loop.py "…/Game/DarkSoulsII.exe" --revert
```

```powershell
.\patch\patch_achievement_loop.ps1 "C:\Program Files (x86)\Steam\steamapps\common\Dark Souls II Scholar of the First Sin\Game\DarkSoulsII.exe"
.\patch\patch_achievement_loop.ps1 -Path .\DarkSoulsII.exe -Check     # or -Revert, -NoBackup
```

Close the game first. They write only the 45 bytes, in place, and only if the
file has exactly the bytes above at that offset, so another game version is
never touched (the script says so and stops). They keep the original as
`DarkSoulsII.exe.orig` unless told not to, and Steam's "Verify integrity of
game files" restores it too. A game update restores the original code, so run
the script again.

Use only one of the DLL and the patch (either way works on its own; the DLL
does nothing to an executable that is already patched).

## Use offline

Like the other fixes here, this changes how the game runs. The patch changes a
game file, and the DLL changes the game's memory. We use it offline only, and
do not know how the game's online protection would see either.
