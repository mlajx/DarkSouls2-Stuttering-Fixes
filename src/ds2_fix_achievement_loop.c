/*
 * ds2_fix_achievement_loop.c: a dinput8.dll for Dark Souls II: Scholar of the
 * First Sin that fixes the slowdown with every death by changing 45 bytes of
 * the game's code in memory, instead of in its executable file. See
 * docs/ACHIEVEMENT_LOOP.md for what the bug is and what the change does.
 *
 * The game imports DirectInput8Create from dinput8.dll, so a dinput8.dll in
 * the game's folder is loaded by it (on Wine and Proton too, with no override
 * needed). When loaded, this changes the 45 bytes, but only if they are
 * exactly the ones the game ships, and forwards DirectInput8Create to the
 * system's dinput8.dll. It does nothing else: no hooks, no threads, no files.
 *
 * The two byte strings below, ORIGINAL_CODE and FIXED_CODE, must equal those in
 * patch/patch_achievement_loop.py and .ps1 (tests/test_patch.py checks it).
 * No C runtime is used, which keeps the DLL at about 3 KB; see the Makefile.
 */
#include <windows.h>

/* Virtual address 0x140b5e82c, relative to the image base 0x140000000. */
#define PATCH_RVA 0xB5E82CUL
#define PATCH_SIZE 45

static const unsigned char ORIGINAL_CODE[PATCH_SIZE] = {
	0x44, 0x38, 0x7b, 0x7c, 0x0f, 0x85, 0xb8, 0x00, 0x00,
	0x00, 0x40, 0x84, 0xff, 0x0f, 0x84, 0xaf, 0x00, 0x00,
	0x00, 0x48, 0x8b, 0x43, 0x68, 0xc6, 0x43, 0x7c, 0x01,
	0x48, 0x8b, 0x78, 0x08, 0x44, 0x38, 0x7b, 0x74, 0x0f,
	0x84, 0x99, 0x00, 0x00, 0x00, 0x44, 0x88, 0x7b, 0x7c
};
static const unsigned char FIXED_CODE[PATCH_SIZE] = {
	0x40, 0x3a, 0x7b, 0x7c, 0x0f, 0x86, 0xb8, 0x00, 0x00,
	0x00, 0x48, 0x8b, 0x43, 0x68, 0x44, 0x38, 0xb8, 0x90,
	0x01, 0x00, 0x00, 0x0f, 0x85, 0xa7, 0x00, 0x00, 0x00,
	0x48, 0x8b, 0x78, 0x08, 0x44, 0x38, 0x7b, 0x74, 0x0f,
	0x94, 0x43, 0x7c, 0x0f, 0x84, 0x95, 0x00, 0x00, 0x00
};

static void apply_patch(void)
{
	unsigned char *base = (unsigned char *)GetModuleHandleA(NULL);
	IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)base;
	IMAGE_NT_HEADERS64 *nt;
	unsigned char *at;
	DWORD old;
	int i;

	if (!base || dos->e_magic != IMAGE_DOS_SIGNATURE)
		return;
	nt = (IMAGE_NT_HEADERS64 *)(base + dos->e_lfanew);
	if (nt->Signature != IMAGE_NT_SIGNATURE
	    || nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR64_MAGIC
	    || nt->OptionalHeader.SizeOfImage < PATCH_RVA + PATCH_SIZE)
		return;
	at = base + PATCH_RVA;
	for (i = 0; i < PATCH_SIZE; i++)
		if (at[i] != ORIGINAL_CODE[i])
			return; /* another version, or already changed */
	if (!VirtualProtect(at, PATCH_SIZE, PAGE_EXECUTE_READWRITE, &old))
		return;
	for (i = 0; i < PATCH_SIZE; i++)
		at[i] = FIXED_CODE[i];
	VirtualProtect(at, PATCH_SIZE, old, &old);
	FlushInstructionCache(GetCurrentProcess(), at, PATCH_SIZE);
}

typedef HRESULT (WINAPI *create_fn)(HINSTANCE, DWORD, REFIID, LPVOID *,
				    LPUNKNOWN);

__declspec(dllexport) HRESULT WINAPI DirectInput8Create(
	HINSTANCE instance, DWORD version, REFIID iid, LPVOID *out,
	LPUNKNOWN outer)
{
	char path[MAX_PATH + 16];
	static const char name[] = "\\dinput8.dll";
	UINT n = GetSystemDirectoryA(path, MAX_PATH);
	HMODULE real;
	create_fn create;
	UINT i;

	if (!n || n > MAX_PATH)
		return E_FAIL;
	for (i = 0; i < sizeof(name); i++)
		path[n + i] = name[i];
	real = LoadLibraryA(path);
	create = real ? (create_fn)(void *)GetProcAddress(real, "DirectInput8Create")
		      : NULL;
	return create ? create(instance, version, iid, out, outer) : E_FAIL;
}

/*
 * A pointer the loader has to fix up when it moves the DLL, which is what makes
 * the linker keep a relocation table. Without one, the DLL could only load at
 * the address it is built for, and if something else held that address the
 * game would not start (Windows does not move a DLL that cannot be fixed up).
 */
volatile const void *const keep_relocations = (const void *)DirectInput8Create;

BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID reserved)
{
	(void)module;
	(void)reserved;
	if (reason == DLL_PROCESS_ATTACH)
		apply_patch();
	return TRUE;
}
