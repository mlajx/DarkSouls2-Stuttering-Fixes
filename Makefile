all: standard

standard: ./src/ds2_fix.cpp
	mkdir -p output
	x86_64-w64-mingw32-g++ -shared -static -O2 ./src/ds2_fix.cpp -o output/dinput8.dll

no_achievements: ./src/ds2_fix_achievements_disabled.cpp
	mkdir -p output
	x86_64-w64-mingw32-g++ -shared -static -O2 ./src/ds2_fix_achievements_disabled.cpp -o output/dinput8.dll

clean:
	rm -f output/*.dll
