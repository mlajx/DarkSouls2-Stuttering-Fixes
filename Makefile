all: standard

standard: ./src/ds2_fix.cpp
	mkdir -p output
	x86_64-w64-mingw32-g++ -shared -static -O2 ./src/ds2_fix.cpp -o output/dinput8.dll

no_achievements: ./src/ds2_fix_achievements_disabled.cpp
	mkdir -p output
	x86_64-w64-mingw32-g++ -shared -static -O2 ./src/ds2_fix_achievements_disabled.cpp -o output/dinput8.dll

# The fix for the cause, in 3 KB: patches the game's code in memory, with no hooks
# (see docs/ACHIEVEMENT_LOOP.md). No C runtime, so it is built differently.
achievement_loop: ./src/ds2_fix_achievement_loop.c
	mkdir -p output
	x86_64-w64-mingw32-gcc -shared -nostdlib -nostartfiles -Os -Wall -Wextra -s \
		-ffreestanding -fno-asynchronous-unwind-tables -fno-ident \
		-fno-tree-loop-distribute-patterns \
		-Wl,--entry,DllMain -Wl,--gc-sections \
		-Wl,--file-alignment,512 -Wl,--section-alignment,512 \
		-Wl,--no-insert-timestamp \
		-o output/dinput8.dll ./src/ds2_fix_achievement_loop.c -lkernel32

test:
	python3 -m unittest discover tests

clean:
	rm -f output/*.dll
