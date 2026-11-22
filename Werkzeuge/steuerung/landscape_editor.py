"""Steuert den Condor Landscape Editor ohne Maus über Win32-Nachrichten: starten, Landschaft wählen, Menüpunkte
auslösen und die Meldung danach per OK-Knopf schließen. Die Menüpunkte werden über ihre Beschriftung gefunden, die
Menü-IDs (z. B. 23 = Export autogen C3D from OBJ, 14 = Export autogen hash (OHA)) vergibt das Programm selbst.
Rückfragen mit Ja/Nein werden nie automatisch beantwortet, sondern führen zu einem Fehler.
Pfade kommen aus Werkzeuge/config.py (CONDOR_DIR, LAND).

Aufruf (aus Werkzeuge/):
    python steuerung/landscape_editor.py start                  # minimiert starten bzw. laufenden nehmen, LAND wählen
    python steuerung/landscape_editor.py menue "Export autogen hash (OHA)"
    python steuerung/landscape_editor.py pruefen                # Tools > Check autogen files and hashlist
    python steuerung/landscape_editor.py liste                  # alle Menüpunkte mit ID
Als Modul: from steuerung.landscape_editor import Editor
"""
import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

u32 = ctypes.WinDLL("user32", use_last_error=True)
u32.SetProcessDPIAware()
H = wintypes.HWND
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, H, wintypes.LPARAM)
for name, args, res in (
        ("SendMessageW", [H, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM], ctypes.c_ssize_t),
        ("PostMessageW", [H, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM], wintypes.BOOL),
        ("EnumWindows", [WNDENUMPROC, wintypes.LPARAM], wintypes.BOOL),
        ("EnumChildWindows", [H, WNDENUMPROC, wintypes.LPARAM], wintypes.BOOL),
        ("GetWindowTextW", [H, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
        ("GetClassNameW", [H, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
        ("GetWindowThreadProcessId", [H, ctypes.POINTER(wintypes.DWORD)], wintypes.DWORD),
        ("IsWindowVisible", [H], wintypes.BOOL),
        ("IsWindow", [H], wintypes.BOOL),
        ("GetDlgCtrlID", [H], ctypes.c_int),
        ("GetMenu", [H], wintypes.HMENU),
        ("GetSubMenu", [wintypes.HMENU, ctypes.c_int], wintypes.HMENU),
        ("GetMenuItemCount", [wintypes.HMENU], ctypes.c_int),
        ("GetMenuItemID", [wintypes.HMENU, ctypes.c_int], wintypes.UINT),
        ("GetMenuState", [wintypes.HMENU, wintypes.UINT, wintypes.UINT], wintypes.UINT),
        ("GetMenuStringW", [wintypes.HMENU, wintypes.UINT, wintypes.LPWSTR, ctypes.c_int, wintypes.UINT], ctypes.c_int)):
    f = getattr(u32, name)
    f.argtypes, f.restype = args, res

WM_GETTEXT, WM_COMMAND, BM_CLICK = 0x000D, 0x0111, 0x00F5
CB_GETCOUNT, CB_GETLBTEXT, CB_SETCURSEL, CBN_SELCHANGE = 0x0146, 0x0148, 0x014E, 1
MF_BYPOSITION, MF_BYCOMMAND, MF_GRAYED, MF_DISABLED = 0x400, 0x0, 0x1, 0x2
DIALOGKLASSEN = ("#32770", "TMessageForm")
JA_NEIN = ("Ja", "Yes", "Nein", "No", "Abbrechen", "Cancel")


def _text(h):
    b = ctypes.create_unicode_buffer(512)
    u32.GetWindowTextW(h, b, 512)
    return b.value


def _klasse(h):
    b = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(h, b, 256)
    return b.value


def _pid(h):
    p = wintypes.DWORD()
    u32.GetWindowThreadProcessId(h, ctypes.byref(p))
    return p.value


def _fenster(pid=None, sichtbar=True):
    out = []
    cb = WNDENUMPROC(lambda h, _: out.append(h) or True)
    u32.EnumWindows(cb, 0)
    return [h for h in out if (not sichtbar or u32.IsWindowVisible(h)) and (pid is None or _pid(h) == pid)]


def _kinder(h):
    out = []
    cb = WNDENUMPROC(lambda k, _: out.append(k) or True)
    u32.EnumChildWindows(h, cb, 0)
    return out


class Editor:
    def __init__(self, landschaft=None, starten=True, warte_laden=8.0):
        self.landschaft = landschaft or os.path.basename(config.LAND)
        self.haupt = self._finde_haupt()
        if self.haupt is None:
            if not starten:
                raise RuntimeError("Landscape Editor läuft nicht")
            self._starte()
        self.pid = _pid(self.haupt)
        self.waehle_landschaft(warte_laden)

    def _finde_haupt(self):
        # ohne Sichtbarkeitsfilter: minimierte VCL-Formulare können unsichtbar sein
        for h in _fenster(sichtbar=False):
            if _klasse(h) == "TForm1" and _text(h).startswith("Condor Landscape Editor"):
                return h
        return None

    def _starte(self):
        exe = os.path.join(config.CONDOR_DIR, "LandscapeEditor.exe")  # läuft nur aus dem Condor-Ordner
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 7  # SW_SHOWMINNOACTIVE: minimiert, ohne Condor den Fokus zu nehmen
        subprocess.Popen([exe], cwd=config.CONDOR_DIR, startupinfo=si)
        for _ in range(60):
            time.sleep(0.5)
            self.haupt = self._finde_haupt()
            if self.haupt:
                time.sleep(2.0)
                return
        raise RuntimeError("Landscape Editor startet nicht")

    def _combo_text(self, cb):
        b = ctypes.create_unicode_buffer(512)
        u32.SendMessageW(cb, WM_GETTEXT, 512, ctypes.addressof(b))
        return b.value

    def waehle_landschaft(self, warte=8.0):
        """Landschaft in der Combobox wählen (CB_SETCURSEL + WM_COMMAND/CBN_SELCHANGE, gepostet, damit eine Rückfrage
        beim Laden das Skript nicht blockiert). Danach warten und prüfen, dass keine Meldung offen ist."""
        cb = next(k for k in _kinder(self.haupt) if _klasse(k) == "TComboBox")
        if self._combo_text(cb) == self.landschaft:
            return
        namen = []
        b = ctypes.create_unicode_buffer(512)
        for i in range(u32.SendMessageW(cb, CB_GETCOUNT, 0, 0)):
            u32.SendMessageW(cb, CB_GETLBTEXT, i, ctypes.addressof(b))
            namen.append(b.value)
        if self.landschaft not in namen:
            raise RuntimeError(f"Landschaft {self.landschaft} nicht in der Liste: {namen}")
        u32.SendMessageW(cb, CB_SETCURSEL, namen.index(self.landschaft), 0)
        u32.PostMessageW(self.haupt, WM_COMMAND, (u32.GetDlgCtrlID(cb) & 0xFFFF) | (CBN_SELCHANGE << 16), cb)
        time.sleep(warte)
        if self._combo_text(cb) != self.landschaft:
            raise RuntimeError("Landschaft wurde nicht übernommen")
        if self.dialoge():
            raise RuntimeError(f"Meldung beim Laden der Landschaft: {self._dialogtexte()}")

    def menue(self):
        """{Beschriftung: (ID, Menü)} aller Menüpunkte (Tastenkürzel nach dem Tabulator abgeschnitten)."""
        out = {}

        def lauf(m):
            for i in range(u32.GetMenuItemCount(m)):
                b = ctypes.create_unicode_buffer(256)
                u32.GetMenuStringW(m, i, b, 256, MF_BYPOSITION)
                sub = u32.GetSubMenu(m, i)
                if sub:
                    lauf(sub)
                elif b.value:
                    out[b.value.split("\t")[0].replace("&", "")] = (u32.GetMenuItemID(m, i), m)
        lauf(u32.GetMenu(self.haupt))
        return out

    def dialoge(self):
        return [h for h in _fenster(self.pid) if _klasse(h) in DIALOGKLASSEN]

    def _dialogtexte(self):
        return [" | ".join(t for t in map(_text, _kinder(d)) if t) for d in self.dialoge()]

    def schliesse_dialoge(self):
        """Offene reine OK-Meldungen schließen und ihre Texte liefern. Rückfragen (Ja/Nein/Abbrechen) werden nicht
        beantwortet: Fehler. Meldungen, die danach noch offen sind, ebenfalls Fehler."""
        texte = []
        for d in self.dialoge():
            kinder = _kinder(d)
            beschriftungen = [_text(k).replace("&", "") for k in kinder]
            text = " | ".join(t for t in map(_text, kinder) if t)
            if any(x in beschriftungen for x in JA_NEIN):
                raise RuntimeError(f"Rückfrage des Editors, bitte von Hand beantworten: {text}")
            ok = [k for k, t in zip(kinder, beschriftungen) if t == "OK"]
            if not ok:
                raise RuntimeError(f"Meldung ohne OK-Knopf: {text}")
            u32.SendMessageW(ok[0], BM_CLICK, 0, 0)
            texte.append(text)
        time.sleep(0.3)
        if self.dialoge():
            raise RuntimeError(f"Meldung ließ sich nicht schließen: {self._dialogtexte()}")
        return texte

    def ausfuehren(self, beschriftung, timeout=600.0):
        """Menüpunkt auslösen, auf die Abschlussmeldung warten, sie schließen und ihren Text liefern."""
        ids = self.menue()
        if beschriftung not in ids:
            raise KeyError(f"Menüpunkt nicht gefunden: {beschriftung}")
        mid, m = ids[beschriftung]
        if u32.GetMenuState(m, mid, MF_BYCOMMAND) & (MF_GRAYED | MF_DISABLED):
            raise RuntimeError(f"Menüpunkt ist gesperrt: {beschriftung}")
        if self.dialoge():
            raise RuntimeError(f"vor dem Befehl ist noch eine Meldung offen: {self._dialogtexte()}")
        u32.PostMessageW(self.haupt, WM_COMMAND, mid, 0)
        ende = time.time() + timeout
        while time.time() < ende:
            time.sleep(1.0)
            if self.dialoge():
                time.sleep(0.3)
                return " / ".join(self.schliesse_dialoge())
        raise TimeoutError(f"keine Meldung nach {timeout:.0f} s: {beschriftung}")


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    ed = Editor()
    if args[0] == "start":
        print("bereit:", ed.landschaft)
    elif args[0] == "liste":
        for k, (v, _) in ed.menue().items():
            print(f"{v:4d}  {k}")
    elif args[0] == "pruefen":
        print(ed.ausfuehren("Check autogen files and hashlist"))
    elif args[0] == "menue":
        print(ed.ausfuehren(args[1]))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
