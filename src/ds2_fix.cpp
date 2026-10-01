#include "windows.h"
#include "string.h"

volatile LONG g_isSyncing = 0;

typedef bool (*StoreStats_t)(void*);
StoreStats_t Original_StoreStats = nullptr;

DWORD WINAPI BackgroundStoreStats(LPVOID steamStatsInstance) {
    if (Original_StoreStats && steamStatsInstance) {
        Original_StoreStats(steamStatsInstance);
    }
    Sleep(1500); 
    InterlockedExchange(&g_isSyncing, 0);
    return 0;
}

bool Hooked_StoreStats(void* steamStatsInstance) {
    if (InterlockedCompareExchange(&g_isSyncing, 1, 0) == 0) {
        HANDLE hThread = CreateThread(nullptr, 0, BackgroundStoreStats, steamStatsInstance, 0, nullptr);
        if (hThread) {
            CloseHandle(hThread); 
        } else {
            InterlockedExchange(&g_isSyncing, 0);
        }
    }
    return true; 
}

DWORD WINAPI InstallSteamHook(LPVOID lpParam) {
    HMODULE hSteamApi = nullptr;
    while (!hSteamApi) {
        hSteamApi = GetModuleHandleA("steam_api64.dll");
        Sleep(500);
    }

    typedef void* (*SteamUserStatsFn)();
    SteamUserStatsFn getSteamUserStats = (SteamUserStatsFn)GetProcAddress(hSteamApi, "SteamUserStats");
    
    if (getSteamUserStats) {
        void* statsInterface = nullptr;
        while (!statsInterface) {
            statsInterface = getSteamUserStats();
            Sleep(500);
        }

        uintptr_t** vtable = (uintptr_t**)statsInterface;
        DWORD oldProtect;
        
        VirtualProtect(&vtable[0][10], sizeof(uintptr_t), PAGE_EXECUTE_READWRITE, &oldProtect);
        Original_StoreStats = (StoreStats_t)vtable[0][10];
        vtable[0][10] = (uintptr_t)&Hooked_StoreStats;
        VirtualProtect(&vtable[0][10], sizeof(uintptr_t), oldProtect, &oldProtect);
    }
    return 0;
}

typedef HRESULT(WINAPI *DirectInput8Create_t)(HINSTANCE, DWORD, REFIID, LPVOID*, LPUNKNOWN);
DirectInput8Create_t Real_DirectInput8Create = nullptr;

extern "C" __declspec(dllexport) HRESULT WINAPI DirectInput8Create(HINSTANCE hinst, DWORD dwVersion, REFIID riidltf, LPVOID* ppvOut, LPUNKNOWN punkOuter) {
    if (!Real_DirectInput8Create) {
        char systemFolderPath[MAX_PATH];
        GetSystemDirectoryA(systemFolderPath, MAX_PATH);
        strcat(systemFolderPath, "\\dinput8.dll");
        HMODULE realLibrary = LoadLibraryA(systemFolderPath);
        Real_DirectInput8Create = (DirectInput8Create_t)GetProcAddress(realLibrary, "DirectInput8Create");
    }
    return Real_DirectInput8Create(hinst, dwVersion, riidltf, ppvOut, punkOuter);
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD reasonForCall, LPVOID lpReserved) {
    if (reasonForCall == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hModule);
        CreateThread(nullptr, 0, InstallSteamHook, nullptr, 0, nullptr);
    }
    return TRUE;
}
