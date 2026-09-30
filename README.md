# Dark Souls II: Scholar of the First Sin - Stuttering Fixes (Proton / Linux / Steam Deck)

A lightweight `dinput8.dll` proxy that eliminates the severe frametime stutter upon character death in *Dark Souls II: Scholar of the First Sin* on Linux and Steam Deck.

---

### The Bug (Theory - Not Fully Confirmed)

When a player dies, *Dark Souls II* synchronously invokes `ISteamUserStats::StoreStats` on the main rendering thread.

* **On Linux / Proton:** This call must cross the Wine-to-native Steam IPC socket bridge, which introduces a 50–150ms delay. Because the local cache does not update immediately, the game engine panics and aggressively re-triggers `StoreStats` in a recursive loop, completely stalling the render thread.

By running your game with `WINEDEBUG=-all,warn+steam,err+steam,+steamclient PROTON_LOG=1` and comparing the log output when the player dies online versus offline.

**Test after dying 20 times:**

|                  | StoreStats Log Lines Generated | Frametime |
| ---------------- | ------------------------------ | --------- |
| Online (Unfixed) | todo                           | todo      |
| Offline          | todo                           | todo      |

### The Fix

Intercepts `StoreStats` (index 10 in the `ISteamUserStats` VTable):

1. Returns `true` instantly to unblock the render loop immediately.
2. Offloads the actual `StoreStats` call to a detached background thread.
3. Uses an atomic lock (`InterlockedCompareExchange`) with a 1.5-second cooldown to safely discard the engine's recursive panic calls during the IPC translation lag.

---

### Download

The simplest way to install the fix is to download the pre-compiled `dinput8.dll` file directly from the Releases/Files tab.

---

### Compilation (If you prefer to build from source)

To compile the code yourself, you will need the MinGW-w64 cross-compiler installed on your Linux distribution.

#### Installing MinGW-w64:

* **Arch Linux / Manjaro:** `sudo pacman -S mingw-w64-gcc`
* **Ubuntu / Debian / Mint:** `sudo apt install g++-mingw-w64-x86-64 gcc-mingw-w64-x86-64`
* **Fedora:** `sudo dnf install mingw64-gcc-c++`

#### Build Command:

```bash
x86_64-w64-mingw32-g++ -shared -static -O3 -s ds2_fix.cpp -o dinput8.dll
```

---

### Installation & Launch Options

#### Linux / Steam Deck

1. Copy the compiled `dinput8.dll` to the game's executable folder:
`.../steamapps/common/Dark Souls II Scholar of the First Sin/Game/`
2. Set your Steam launch options for the game. To completely stabilize frametimes to 60 FPS alongside the DLL fix, use the following:

**Standard Play:**

```bash
MANGOHUD=1 MANGOHUD_CONFIG=fps_limit=60 DXVK_FRAME_RATE=60 WINEDLLOVERRIDES="dinput8=n,b" game-performance %command%

```

*(Note: `MANGOHUD=1` is optional if you want the visual overlay, but combining `DXVK_FRAME_RATE` and `MANGOHUD_CONFIG` ensures perfectly consistent frame pacing).*

**Seamless Co-op Mod:**
If you are playing with the Seamless Co-op mod, use this command string instead to route the launcher correctly while maintaining the FPS limits and fixes:

```bash
MANGOHUD=1 MANGOHUD_CONFIG=fps_limit=60 DXVK_FRAME_RATE=60 WINEDLLOVERRIDES="dinput8=n,b" bash -c 'exec "${@/DarkSoulsII.exe/ds2sc_launcher.exe}"' -- game-performance %command%
```

#### Windows (Untested)

*Note: This cascading loop is primarily a Proton/Linux translation issue. This fix has not been actively tested on native Windows.*

1. Place `dinput8.dll` directly inside the `Game` folder next to `DarkSoulsII.exe`.

---

### Alternative Option: Achievements Disabled

If you experience unexpected behavior or memory issues with the standard background sync method, an alternative version of the code (`ds2_fix_achievements_disabled.cpp`) is available.

This version simply forces `StoreStats` to return `false` instantly without spinning up background threads. This tricks the game into thinking you are offline, which guarantees a 100% stable framerate, but **it will permanently break Steam achievement unlocking** for that character session.

---

### Ban Disclaimer

> **Use at your own risk.**
>
> This mod hooks the Steamworks API in volatile memory purely to offload a performance-blocking call. It does **not** modify save data, game files, or in-game player parameters. While this mechanism does not trigger VAC (which is not used by DS2) or standard FromSoftware save integrity softbans, modifying game memory online always carries an inherent, non-zero risk.
