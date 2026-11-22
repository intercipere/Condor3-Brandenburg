# Hilfsfunktionen für die Win32-Steuerung der Editoren (wird von front.ps1 und okdialog.ps1 per Dot-Sourcing geladen).
# Funktionen: LE-Pid, LE-Main, Rect, Dump-Menu (listet Menüpunkte mit ID, z. B. Dump-Menu ([U]::GetMenu((LE-Main)))).
Add-Type @"
using System; using System.Text; using System.Collections.Generic; using System.Runtime.InteropServices;
public class U {
 public delegate bool P(IntPtr h, IntPtr l);
 [DllImport("user32.dll")] public static extern bool EnumWindows(P p, IntPtr l);
 [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr w, P p, IntPtr l);
 [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
 [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
 [DllImport("user32.dll")] public static extern IntPtr GetMenu(IntPtr h);
 [DllImport("user32.dll")] public static extern int GetMenuItemCount(IntPtr m);
 [DllImport("user32.dll")] public static extern IntPtr GetSubMenu(IntPtr m, int i);
 [DllImport("user32.dll")] public static extern uint GetMenuItemID(IntPtr m, int i);
 [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetMenuString(IntPtr m, uint id, StringBuilder s, int n, uint f);
 [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
 [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
 [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, StringBuilder l);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint p);
 [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
 public struct RECT { public int L, T, R, B; }
 public static string Txt(IntPtr h){var s=new StringBuilder(512);GetWindowText(h,s,512);return s.ToString();}
 public static string Cls(IntPtr h){var s=new StringBuilder(256);GetClassName(h,s,256);return s.ToString();}
 public static List<IntPtr> Tops(uint pid){var l=new List<IntPtr>();EnumWindows((h,x)=>{uint p;GetWindowThreadProcessId(h,out p);if(p==pid&&IsWindowVisible(h))l.Add(h);return true;},IntPtr.Zero);return l;}
 public static List<IntPtr> Kids(IntPtr w){var l=new List<IntPtr>();EnumChildWindows(w,(h,x)=>{l.Add(h);return true;},IntPtr.Zero);return l;}
}
"@
[U]::SetProcessDPIAware() | Out-Null
function LE-Pid { (Get-Process LandscapeEditor -ErrorAction Stop | Select-Object -First 1).Id }
function LE-Main { [U]::Tops((LE-Pid)) | Where-Object { [U]::Txt($_) -like "Condor Landscape Editor*" } | Select-Object -First 1 }
function Rect($h) { $r = New-Object U+RECT; [U]::GetWindowRect($h, [ref]$r) | Out-Null; "$($r.L),$($r.T)-$($r.R),$($r.B)" }
function Dump-Menu($m, $indent = "") {
  for ($i = 0; $i -lt [U]::GetMenuItemCount($m); $i++) {
    $s = New-Object System.Text.StringBuilder 256; [U]::GetMenuString($m, [uint32]$i, $s, 256, 0x400) | Out-Null
    $id = [U]::GetMenuItemID($m, $i); "$indent[$id] $s"
    $sub = [U]::GetSubMenu($m, $i); if ($sub -ne [IntPtr]::Zero) { Dump-Menu $sub ($indent + "  ") }
  }
}
