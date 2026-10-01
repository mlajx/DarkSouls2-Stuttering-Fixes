#include "windows.h"
#include "string.h"

bool Hooked_RequestCurrentStats(void* thisptr) {
    return false;
}

bool Hooked_StoreStats(void* thisptr) {
    return false;
}

DWORD WINAPI PatchThread(LPVOID lpParam) {
    HMODULE hSteamApi = nullptr;
    while (!hSteamApi) {
        hSteamApi = GetModuleHandleA("steam_api64.dll");
        Sleep(500);
    }

    typedef void* (*SteamUserStatsFn)();
    SteamUserStatsFn pSteamUserStats = (SteamUserStatsFn)GetProcAddress(hSteamApi, "SteamUserStats");
    
    if (pSteamUserStats) {
        void* statsInterface = nullptr;
        while (!statsInterface) {
            statsInterface = pSteamUserStats();
            Sleep(500);
        }

        uintptr_t** vtable = (uintptr_t**)statsInterface;
        DWORD oldProtect;

        VirtualProtect(&vtable[0][0], sizeof(uintptr_t), PAGE_EXECUTE_READWRITE, &oldProtect);
        vtable[0][0] = (uintptr_t)&Hooked_RequestCurrentStats;
        VirtualProtect(&vtable[0][0], sizeof(uintptr_t), oldProtect, &oldProtect);

        VirtualProtect(&vtable[0][10], sizeof(uintptr_t), PAGE_EXECUTE_READWRITE, &oldProtect);
        vtable[0][10] = (uintptr_t)&Hooked_StoreStats;
        VirtualProtect(&vtable[0][10], sizeof(uintptr_t), oldProtect, &oldProtect);
    }
    return 0;
}

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
