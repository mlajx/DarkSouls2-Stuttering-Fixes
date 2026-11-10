<#
.SYNOPSIS
Fixes Dark Souls II: Scholar of the First Sin slowing down with every death, by
patching 45 bytes of DarkSoulsII.exe in place.

.DESCRIPTION
Close the game first. The executable is only changed if the 45 bytes in it are
exactly the ones the game ships (or the fixed ones, with -Revert), so another
game version is never touched. A copy of the file is kept next to it as
DarkSoulsII.exe.orig, unless -NoBackup is given; Steam's "Verify integrity of
game files" restores the original too.

What the change is, and why, is in docs/ACHIEVEMENT_LOOP.md. The same bytes are
in patch_achievement_loop.py and ../src/ds2_fix_achievement_loop.c.

.EXAMPLE
.\patch_achievement_loop.ps1 "C:\Program Files (x86)\Steam\steamapps\common\Dark Souls II Scholar of the First Sin\Game\DarkSoulsII.exe"

.EXAMPLE
.\patch_achievement_loop.ps1 -Path .\DarkSoulsII.exe -Revert
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Path,
    # Put the game's own code back.
    [switch]$Revert,
    # Only say which it has.
    [switch]$Check,
    # Don't keep a copy as DarkSoulsII.exe.orig first.
    [switch]$NoBackup
)

$ErrorActionPreference = 'Stop'

# The file offset of virtual address 0x140b5e82c, in the executable's first
# code section (raw pointer 0x400 for virtual address 0x140001000).
$Offset = 0xB5DC2C

function ConvertFrom-Hex([string]$Hex) {
    $bytes = New-Object byte[] ($Hex.Length / 2)
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        $bytes[$i] = [Convert]::ToByte($Hex.Substring($i * 2, 2), 16)
    }
    , $bytes
}

$OriginalCode = ConvertFrom-Hex ('44387b7c0f85b80000004084ff0f84af000000488b4368c6437c01488b7808' + '44387b740f849900000044887b7c')
$FixedCode = ConvertFrom-Hex ('403a7b7c0f86b8000000488b43684438b8900100000f85a7000000488b7808' + '44387b740f94437c0f8495000000')

function Get-State([byte[]]$Code) {
    $text = [BitConverter]::ToString($Code)
    if ($text -eq [BitConverter]::ToString($OriginalCode)) { return 'original' }
    if ($text -eq [BitConverter]::ToString($FixedCode)) { return 'fixed' }
    return 'unknown'
}

if ($Revert -and $Check) {
    Write-Error 'Use only one of -Revert and -Check.'
    exit 1
}
$Path = (Resolve-Path -LiteralPath $Path).ProviderPath

try {
    $file = [System.IO.File]::Open($Path, 'Open', 'Read', 'ReadWrite')
    try {
        $found = New-Object byte[] $OriginalCode.Length
        $null = $file.Seek($Offset, 'Begin')
        $count = $file.Read($found, 0, $found.Length)
    } finally {
        $file.Dispose()
    }
} catch {
    Write-Error "Could not read ${Path}: $($_.Exception.Message)"
    exit 1
}
$state = if ($count -eq $found.Length) { Get-State $found } else { 'unknown' }
Write-Host "${Path}: $state"
if ($state -eq 'unknown') {
    Write-Warning ('These are not the bytes of a game version this is made for, so the file is left alone. ' +
        'After a game update, verify the game files in Steam.')
    if ($Check) { exit 0 } else { exit 1 }
}
if ($Check) { exit 0 }

$want = if ($Revert) { 'original' } else { 'fixed' }
if ($state -eq $want) {
    Write-Host 'Already so; nothing to do.'
    exit 0
}
try {
    if (-not $NoBackup -and -not $Revert) {
        Copy-Item -LiteralPath $Path -Destination "$Path.orig" -Force
        Write-Host "Copied the game's file to $Path.orig."
    }
    $file = [System.IO.File]::Open($Path, 'Open', 'ReadWrite', 'Read')
    try {
        $null = $file.Seek($Offset, 'Begin')
        $code = if ($Revert) { $OriginalCode } else { $FixedCode }
        $file.Write($code, 0, $code.Length)
    } finally {
        $file.Dispose()
    }
} catch {
    Write-Error "Could not write ${Path}: $($_.Exception.Message) Is the game closed?"
    exit 1
}
Write-Host "Done: $want."
