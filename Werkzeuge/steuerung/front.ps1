# Holt ein Fenster nach vorn und maximiert es (Titelanfang -Title, Standard: Landscape Editor).
# Aufruf: powershell -File front.ps1 [-Title "Condor"]
param([string]$Title = "Condor Landscape Editor")
. "$PSScriptRoot\win.ps1"
Add-Type @"
using System; using System.Runtime.InteropServices;
public class F { [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
 [DllImport("user32.dll")] public static extern void keybd_event(byte k, byte s, uint f, IntPtr e); }
"@
$h = $null
foreach ($p in Get-Process) { foreach ($w in [U]::Tops($p.Id)) { if ([U]::Txt($w) -like "$Title*") { $h = $w } } }
if (-not $h) { "nicht gefunden"; exit 1 }
[F]::keybd_event(0x12, 0, 0, [IntPtr]::Zero); [F]::keybd_event(0x12, 0, 2, [IntPtr]::Zero)  # Alt antippen, sonst verweigert Windows den Fokuswechsel
[F]::ShowWindow($h, 3) | Out-Null; [F]::SetForegroundWindow($h) | Out-Null; "vorne: $([U]::Txt($h))"
