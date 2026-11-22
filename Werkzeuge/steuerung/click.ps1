# Mausklick an Bildschirmkoordinate (physische Pixel). Nur für die Editoren; Condor ignoriert simulierte Mausbewegungen.
# Aufruf: powershell -File click.ps1 -X 500 -Y 300 [-Button right] [-Double]
param([int]$X, [int]$Y, [string]$Button = "left", [switch]$Double)
Add-Type @"
using System; using System.Runtime.InteropServices;
public class M { [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
 [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
 [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); }
"@
[M]::SetProcessDPIAware() | Out-Null
[M]::SetCursorPos($X, $Y) | Out-Null; Start-Sleep -Milliseconds 150
if ($Button -eq "right") { $d = 0x08; $u = 0x10 } else { $d = 0x02; $u = 0x04 }
$n = 1; if ($Double) { $n = 2 }
for ($i = 0; $i -lt $n; $i++) { [M]::mouse_event($d,0,0,0,[IntPtr]::Zero); Start-Sleep -Milliseconds 90; [M]::mouse_event($u,0,0,0,[IntPtr]::Zero); Start-Sleep -Milliseconds 80 }
