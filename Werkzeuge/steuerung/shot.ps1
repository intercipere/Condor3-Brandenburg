# Screenshot als PNG, ganzer Hauptbildschirm oder ein Fenster (Titel enthält -Title; holt es nach vorn).
# Aufruf: powershell -File shot.ps1 -Out bild.png [-Title "Condor"]
param([string]$Out, [string]$Title = "")
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class W { [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
 public struct RECT { public int L, T, R, B; } }
"@
[W]::SetProcessDPIAware() | Out-Null
$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
if ($Title) {
  $p = Get-Process | Where-Object { $_.MainWindowTitle -like "*$Title*" } | Select-Object -First 1
  if ($p) { [W]::SetForegroundWindow($p.MainWindowHandle) | Out-Null; Start-Sleep -Milliseconds 400
    $r = New-Object W+RECT; [W]::GetWindowRect($p.MainWindowHandle, [ref]$r) | Out-Null
    $b = New-Object System.Drawing.Rectangle($r.L, $r.T, ($r.R - $r.L), ($r.B - $r.T)) }
}
$bmp = New-Object System.Drawing.Bitmap($b.Width, $b.Height)
$g = [System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png); "$($b.X),$($b.Y) $($b.Width)x$($b.Height)"
