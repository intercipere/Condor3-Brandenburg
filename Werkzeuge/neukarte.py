"""Festlegungen der neuen Landschaft „Brandenburg“ (Pilot: 1 Kachel = 4 × 4 Patches um EDAZ).

Raster wie in Condor: Ursprung rechts unten, Spalten zählen nach Westen, Zeilen nach Norden.
EDAZ (UTM 33: 374261 / 5785235) liegt in der Mitte von Patch 2/2, nicht auf einer Patchgrenze.
Damit reicht die Kachel 14,4 km nach Osten und Süden (Sperenberg, Rand Luckenwalde) und 8,6 km nach Westen und Norden.
"""
import os
import zipfile
from config import LAND

NAME = os.path.basename(LAND)  # Brandenburg

ZONE = 33
PATCH = 5760.0
KACHEL = 4 * PATCH
KACHELN_X, KACHELN_Y = 1, 1
E0, N0 = 388660.0, 5770840.0                 # rechte untere Ecke (UTM 33, ETRS89)
E_LINKS = E0 - KACHELN_X * KACHEL            # 365620
N_OBEN = N0 + KACHELN_Y * KACHEL             # 5793880
PATCHES_X, PATCHES_Y = 4 * KACHELN_X, 4 * KACHELN_Y

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# LGB-Kacheln: vorhandene Daten aus dem EDAZ-Projekt (nur lesen) und Nachladungen für die neue Karte
LGB_ORDNER = [
    os.path.join(PROJ, "..", "Condor3", "Daten", "LGB"),
    os.path.join(PROJ, "..", "Condor3", "Daten", "LGB_Ring"),
    os.path.join(PROJ, "Daten", "LGB_BB"),
]
ARBEIT = os.path.join(PROJ, "Daten", "Arbeit_BB")


def lgb_datei(datensatz, ost_km, nord_km, endung):
    """Pfad einer entpackten LGB-Kachel (z. B. dgm, .tif). Entpackt bei Bedarf nach Daten/LGB_BB/<datensatz>_<endung>."""
    name = f"{datensatz}_33{ost_km}-{nord_km}"
    ordner_entpackt = f"{datensatz}_{endung[1:]}"
    for o in LGB_ORDNER:
        p = os.path.join(o, ordner_entpackt, name + endung)
        if os.path.exists(p):
            return p
    for o in LGB_ORDNER:
        z = os.path.join(o, datensatz, name + ".zip")
        if os.path.exists(z):
            ziel = os.path.join(PROJ, "Daten", "LGB_BB", ordner_entpackt)
            os.makedirs(ziel, exist_ok=True)
            with zipfile.ZipFile(z) as zf:
                # Die Hauptdatei zuletzt: Nur sie wird oben als vorhanden erkannt, und erst vollständig umbenannt
                for n in sorted(zf.namelist(), key=lambda n: n == name + endung):
                    if n.startswith(name) and not n.endswith((".xml", ".html")):
                        pfad = os.path.join(ziel, n)
                        with open(pfad + ".part", "wb") as f:
                            f.write(zf.read(n))
                        os.replace(pfad + ".part", pfad)
            return os.path.join(ziel, name + endung)
    raise FileNotFoundError(f"LGB-Kachel fehlt: {name}")


def lgb_zip(datensatz, ost_km, nord_km):
    """Pfad des Original-Zips einer LGB-Kachel (enthält die Metadaten, z. B. das Bildflugdatum)."""
    name = f"{datensatz}_33{ost_km}-{nord_km}.zip"
    for o in LGB_ORDNER:
        if os.path.exists(p := os.path.join(o, datensatz, name)):
            return p
    raise FileNotFoundError(f"LGB-Zip fehlt: {name}")


def patch_ecken(col, row):
    """(west, ost, süd, nord) eines Patches in UTM."""
    ost = E0 - col * PATCH
    sued = N0 + row * PATCH
    return ost - PATCH, ost, sued, sued + PATCH
