# Tastendruck als Scancode (für Spiele mit DirectInput). Aufruf: taste.ps1 -Scan 0x19 [-HaltenMs 80] [-Ext]
# Condor-Tasten: P = 0x19 (Pause), F2 = 0x3C (Außenansicht), Pfeiltasten mit -Ext: hoch 0x48, runter 0x50, links 0x4B, rechts 0x4D.
param([int]$Scan, [int]$HaltenMs = 80, [switch]$Ext)
Add-Type @"
using System; using System.Runtime.InteropServices;
public class K { [DllImport("user32.dll")] public static extern void keybd_event(byte k, byte s, uint f, IntPtr e); }
"@
$f = 0x8; if ($Ext) { $f = $f -bor 0x1 }
[K]::keybd_event(0, [byte]$Scan, $f, [IntPtr]::Zero); Start-Sleep -Milliseconds $HaltenMs
[K]::keybd_event(0, [byte]$Scan, ($f -bor 0x2), [IntPtr]::Zero)
