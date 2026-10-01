# Dark Souls II: Scholar of the First Sin - Stuttering Fixes (Proton / Linux / Steam Deck)

A lightweight `dinput8.dll` proxy that eliminates the frametime stutter upon death in *Dark Souls II: Scholar of the First Sin* on Linux, including Steam Deck.

---

### TL;DR (Quick Install)

1. Download `dinput8.dll` from the Releases tab.
2. Copy it into your game directory: `.../Dark Souls II Scholar of the First Sin/Game/`
3. Set Launch Options in Steam (Steam Deck default): `MANGOHUD_CONFIG=fps_limit=60 DXVK_FRAME_RATE=60 WINEDLLOVERRIDES="dinput8=n,b" %command%`

_(For Linux Desktop or Seamless Co-op, see the full Installation section below)._

---

### The bug

My assumption is that when a player dies, the game synchronously invokes `ISteamUserStats::StoreStats` on the main rendering thread.

And on Linux / Proton this call must cross the Wine-to-native Steam IPC socket bridge, which introduces a delay. Because the local cache does not update immediately, the game engine panics and aggressively re-triggers `StoreStats`, completely stalling the render thread. And each time you die, the re-triggers increase.

To test yourself, run the game with `MANGOHUD=1 WINEDEBUG=-all,warn+steam,err+steam,+steamclient PROTON_LOG=1 MANGOHUD_CONFIG=fps_limit=60 DXVK_FRAME_RATE=60 %command%` and compare the log output in `$HOME/steam-335300.log` when the player die online and offline (or with the fix).

### How the fix works

Intercepts `StoreStats`, return `true` to unblock the game render loop, offload the original `StoreStats` to be a datached background thread and use an atomic lock to discard any recursive panic calls.

---

### Download

The simplest way to install the fix is to download the pre-compiled `dinput8.dll` file directly from the releases.

---

### Compilation (If you prefer to build from source)

To compile the code yourself, you will need the MinGW-w64 cross-compiler installed on your Linux distribution.

#### Installing MinGW-w64:

* **Arch Linux / Manjaro:** `sudo pacman -S mingw-w64-gcc`
* **Ubuntu / Debian / Mint:** `sudo apt install g++-mingw-w64-x86-64 gcc-mingw-w64-x86-64`
* **Fedora:** `sudo dnf install mingw64-gcc-c++`

#### Build Command:

```bash
 x86_64-w64-mingw32-g++ -shared -static -O2 ./src/ds2_fix.cpp -o ./output/dinput8.dll
```

or just

```bash
make
``` 

---

### Installation & Launch Options

#### Linux / Steam Deck

1. Copy the compiled `dinput8.dll` to the game's executable folder:
`.../steamapps/common/Dark Souls II Scholar of the First Sin/Game/`
2. Set your Steam launch options for the game.

*(Note: If you want the visual overlay, prepend `MANGOHUD=1` to any of the launch options below).*

**Steam Deck:**

```bash
MANGOHUD_CONFIG=fps_limit=60 DXVK_FRAME_RATE=60 WINEDLLOVERRIDES="dinput8=n,b" %command%

```

**Linux Desktop (e.g., CachyOS):**
If your distribution provides the `game-performance` wrapper (like CachyOS), you can include it to further optimize your setup:

```bash
MANGOHUD_CONFIG=fps_limit=60 DXVK_FRAME_RATE=60 WINEDLLOVERRIDES="dinput8=n,b" game-performance %command%

```

**Seamless Co-op Mod:**
If you are playing with the Seamless Co-op mod, use this command string instead to route the launcher correctly while maintaining the FPS limits and fixes.

*Linux (with game-performance):*

```bash
MANGOHUD_CONFIG=fps_limit=60 DXVK_FRAME_RATE=60 WINEDLLOVERRIDES="dinput8=n,b" bash -c 'exec "${@/DarkSoulsII.exe/ds2sc_launcher.exe}"' -- game-performance %command%

```

#### Windows (Untested)

*Note: This bug is primarily a Proton/Linux translation issue. This fix has not been actively tested on native Windows, but if the game lags while playing  (and dying), give it a try.*

1. Place `dinput8.dll` directly inside the `Game` folder next to `DarkSoulsII.exe`.

---

### Comparisons

The comparison is after dying in the game 10 times.

#### CachyOS

|           | After Fix                                                       | Before Fix                                                        |
| --------- | --------------------------------------------------------------- | ----------------------------------------------------------------- |
| Frametime | ![Fixed CachyOS Frametime][/images/fixed_cachyos_frametime.png] | ![Unfixed CachyOS Frametime][/images/fixed_cachyos_frametime.png] |
| Log       | ![Fixed CachyOS Log][/images/fixed_cachyos_log.png]             | ![Unfixed CachyOS Log][/images/fixed_cachyos_log.png]             |

#### Steam Deck

| After Fix                                                            | Before Fix                                                               |
| -------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| ![Fixed Steam Deck Frametime][/images/fixed_steamdeck_framerate.jpg] | ![Unfixed Steam Deck Frametime][/images/unfixed_steamdeck_framerate.jpg] |

### Alternative Option: Achievements Disabled

If you experience unexpected behavior or memory issues with the `ds2_fix.cpp`, an alternative version of the code `ds2_fix_achievements_disabled.cpp` is available.

This version simply forces `StoreStats` and `RequestCurrentStats` to return `false`. This tricks the game into thinking you are offline, which provides a more stable frametime. **Achievements will not unlock during gameplay** (Except `This is Dark Souls` for some reason).

Commands:
```bash
x86_64-w64-mingw32-g++ -shared -static -O2 ./src/ds2_fix_achievements_disabled.cpp -o ./output/dinput8.dll
```

or
```bash
make no_achievements
```

---

### Ban Disclaimer

> **Use at your own risk.**
>
> This mod hooks the Steamworks API purely to offload a performance-blocking call. It does **not** modify save data, game files, or player stats. While it doesn't trigger standard FromSoftware softbans, modifying game memory online always carries an inherent, non-zero risk.
