"""Baut die Waldkarten für den 3 x 3-Ring um EDAZ, mit denselben Regeln wie waldkarte.py.

Aufruf: python ring_wald.py   (nach ring_textur.py)
Ergebnis in Daten\\Arbeit\\Ring: <SS><ZZ>.for und wald_<SS><ZZ>.png. Schreibt nichts in die Landschaft.
"""
import os
import zipfile
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import rasterio
import rasterio.enums
from PIL import Image

import gelaende as g
from config import LAND_ORIGINAL
from ring_textur import LGB_ORDNER, PROZESSE, RING, ZIEL
from waldkarte import gebaeude_maske, klassifiziere


def kachel_tif(ordner, name):
    """Pfad der entpackten Kachel; entpackt sie bei Bedarf aus dem Zip des jeweiligen LGB-Ordners."""
    for o in LGB_ORDNER:
        tif = os.path.join(o, ordner + "_tif", name + ".tif")
        if os.path.exists(tif):
            return tif
        z = os.path.join(o, ordner, name + ".zip")
        if os.path.exists(z):
            os.makedirs(os.path.dirname(tif), exist_ok=True)
            with zipfile.ZipFile(z) as zf:
                for n in zf.namelist():
                    if n.endswith((".tif", ".tfw")):
                        zf.extract(n, os.path.dirname(tif))
            return tif
    raise FileNotFoundError(name)


def kachel_namen(ordner, west, nord):
    """Namen der 1-km-Kacheln, die den Patch berühren."""
    k = int(g.PATCH)
    return [f"{ordner}_33{ost}-{hoch}" for ost in range(int(west // 1000), int(np.ceil((west + k) / 1000)))
            for hoch in range(int((nord - k) // 1000), int(np.ceil(nord / 1000)))]


def patch_ecke(c, r):
    ec, nc = g.patch_mitte(c, r)
    return int(ec - g.PATCH / 2), int(nc + g.PATCH / 2)


def raster_1m(ordner, west, nord):
    """Patch-Ausschnitt mit 1 m pro Pixel (Nord oben) aus den 1-km-Kacheln."""
    k = int(g.PATCH)
    arr = np.full((k, k), np.nan, np.float32)
    for name in kachel_namen(ordner, west, nord):
        with rasterio.open(kachel_tif(ordner, name)) as d:
            a = d.read(1, masked=True, out_shape=(1000, 1000), resampling=rasterio.enums.Resampling.average).astype(np.float32).filled(np.nan)
            r0, c0 = int(round(nord - d.bounds.top)), int(round(d.bounds.left - west))
        z0, s0 = max(r0, 0), max(c0, 0)
        z1, s1 = min(r0 + 1000, k), min(c0 + 1000, k)
        arr[z0:z1, s0:s1] = a[z0 - r0:z1 - r0, s0 - c0:s1 - c0]
    return arr


def patch_bauen(c, r):
    """Schreibt .for und Vorschau eines Patches und gibt die Zeile für die Ausgabe zurück."""
    v = {0: "kein", 1: "Nadel", 2: "Laub"}
    west, nord = patch_ecke(c, r)
    hoehe = raster_1m("bdom", west, nord) - raster_1m("dgm", west, nord)
    luecken = ~np.isfinite(hoehe)  # einzelne Fehlstellen im bDOM (in 39/38: 4 m²) zählen als kein Baum
    assert luecken.mean() < 1e-4, f"{c:02d}{r:02d}: {luecken.mean():.3%} ohne Höhendaten"
    hoehe[luecken] = 0
    foto = np.load(os.path.join(ZIEL, f"flug_{c:02d}{r:02d}.npy")).astype(np.float32)
    bild = klassifiziere(hoehe, foto, gebaeude_maske(west, nord, g.PATCH, LGB_ORDNER))
    np.ascontiguousarray(bild[::-1, ::-1].T).tofile(os.path.join(ZIEL, f"{c:02d}{r:02d}.for"))
    alt = np.fromfile(os.path.join(LAND_ORIGINAL, "ForestMaps", f"{c:02d}{r:02d}.for"), np.uint8)
    vorschau = np.zeros((512, 512, 3), np.uint8)
    vorschau[bild == 1] = (20, 90, 30)
    vorschau[bild == 2] = (140, 200, 60)
    Image.fromarray(vorschau).save(os.path.join(ZIEL, f"wald_{c:02d}{r:02d}.png"))
    return (f"{c:02d}{r:02d}.for: neu " + ", ".join(f"{v[x]} {np.mean(bild == x):.1%}" for x in v)
            + " | alt " + ", ".join(f"{v[x]} {np.mean(alt == x):.1%}" for x in v))


def main():
    # Erst alle Kacheln nacheinander entpacken: Nachbar-Patches teilen Kacheln, parallel würden sie sich stören.
    for ordner in ("bdom", "dgm"):
        for name in {n for p in RING for n in kachel_namen(ordner, *patch_ecke(*p))}:
            kachel_tif(ordner, name)
    with ProcessPoolExecutor(PROZESSE) as pool:
        for zeile in pool.map(patch_bauen, *zip(*RING)):
            print(zeile, flush=True)


if __name__ == "__main__":
    main()
