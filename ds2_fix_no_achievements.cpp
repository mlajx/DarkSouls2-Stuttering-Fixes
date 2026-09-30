#include "windows.h"
#include "string.h"

// The hook functions. Returning false instantly aborts the Steam stats operations.
bool Hooked_RequestCurrentStats(void* thisptr) {
    return false;
}

bool Hooked_StoreStats(void* thisptr) {
    return false;
}

DWORD WINAPI PatchThread(LPVOID lpParam) {
    // Wait 5 seconds to ensure Dark Souls II has fully initialized steam_api64.dll
    Sleep(5000); 

    HMODULE hSteam = GetModuleHandleA("steam_api64.dll");
    if (!hSteam) return 0;

    // Grab the global SteamUserStats interface directly from the loaded DLL
    typedef void* (*SteamUserStatsFn)();
    SteamUserStatsFn pSteamUserStats = (SteamUserStatsFn)GetProcAddress(hSteam, "SteamUserStats");
    
    if (pSteamUserStats) {
        void* pStatsIface = pSteamUserStats();
        if (pStatsIface) {
            uintptr_t** vtable = (uintptr_t**)pStatsIface;
            DWORD oldProtect;
            
            // Unprotect the memory page containing the vtable (covering up to index 10)
            VirtualProtect(vtable[0], 12 * sizeof(uintptr_t), PAGE_EXECUTE_READWRITE, &oldProtect);
            
            // Index 0: RequestCurrentStats
            vtable[0][0] = (uintptr_t)&Hooked_RequestCurrentStats;
            
            // Index 10: StoreStats
            vtable[0][10] = (uintptr_t)&Hooked_StoreStats;
            
            // Restore memory protection
            VirtualProtect(vtable[0], 12 * sizeof(uintptr_t), oldProtect, &oldProtect);
        }
    }
    return 0;
}

// Forward the standard DirectInput8Create export to the real Windows system DLL
typedef HRESULT(WINAPI *DirectInput8Create_t)(HINSTANCE, DWORD, REFIID, LPVOID*, LPUNKNOWN);
DirectInput8Create_t Original_DirectInput8Create = nullptr;

extern "C" __declspec(dllexport) HRESULT WINAPI DirectInput8Create(HINSTANCE hinst, DWORD dwVersion, REFIID riidltf, LPVOID* ppvOut, LPUNKNOWN punkOuter) {
    if (!Original_DirectInput8Create) {
        char syspath[MAX_PATH];
        GetSystemDirectoryA(syspath, MAX_PATH);
        strcat(syspath, "\\dinput8.dll");
        HMODULE hOrig = LoadLibraryA(syspath);
        Original_DirectInput8Create = (DirectInput8Create_t)GetProcAddress(hOrig, "DirectInput8Create");
    }
    return Original_DirectInput8Create(hinst, dwVersion, riidltf, ppvOut, punkOuter);
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved) {
    if (ul_reason_for_call == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hModule);
        CreateThread(nullptr, 0, PatchThread, nullptr, 0, nullptr);
    }
    return TRUE;
}