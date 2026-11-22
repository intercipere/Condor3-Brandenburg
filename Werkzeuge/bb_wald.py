"""Waldkarten (.for) der Landschaft Brandenburg: Baumhöhe = bDOM - DGM1, Laub/Nadel aus der fertigen Patch-Textur.

Regeln wie waldkarte.py (Format und Ausrichtung dort beschrieben). Die Helligkeitsschwelle Laub/Nadel hängt vom
Farbabgleich der Textur ab und wird deshalb gegen die EG3-Waldkarten der EDAZ-Patches kalibriert:
    python bb_wald.py kalibrieren     # Übereinstimmung mit EG3 für mehrere Schwellen
    python bb_wald.py [schwelle]      # alle Patches schreiben (Standard: SCHWELLE)
Vorher bb_textur.py.
"""
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import cv2
import numpy as np
import rasterio
import rasterio.enums
from PIL import Image

import neukarte as nk
from config import CONDOR_DIR
from waldkarte import gebaeude_maske, klassifiziere

Image.MAX_IMAGE_PIXELS = None
SCHWELLE = 85.0  # kalibriert 22.11.2026: Laub/Nadel 94,7 % wie EG3, Nadelanteil 90,0 % (EG3 89,7 %)
K = int(nk.PATCH)
EG3 = CONDOR_DIR + "/Landscapes/EastGermany3"
EG3_E0, EG3_N0 = 605160.0, 5558120.0


def raster_1m(datensatz, west, nord):
    arr = np.full((K, K), np.nan, np.float32)
    for e in range(int(west // 1000), int(np.ceil((west + K) / 1000))):
        for n in range(int((nord - K) // 1000), int(np.ceil(nord / 1000))):
            with rasterio.open(nk.lgb_datei(datensatz, e, n, ".tif")) as d:
                a = d.read(1, masked=True, out_shape=(1000, 1000),
                           resampling=rasterio.enums.Resampling.average).astype(np.float32).filled(np.nan)
                r0, c0 = int(round(nord - d.bounds.top)), int(round(d.bounds.left - west))
            z0, s0, z1, s1 = max(r0, 0), max(c0, 0), min(r0 + 1000, K), min(c0 + 1000, K)
            arr[z0:z1, s0:s1] = a[z0 - r0:z1 - r0, s0 - c0:s1 - c0]
    return arr


def grundlagen(c, r):
    """Baumhöhe, Foto (1 m, Nord oben) und Gebäudemaske eines Patches."""
    west, _, _, nord = nk.patch_ecken(c, r)
    hoehe = raster_1m("bdom", west, nord) - raster_1m("dgm", west, nord)
    luecken = ~np.isfinite(hoehe)
    assert luecken.mean() < 1e-3, f"{c:02d}{r:02d}: {luecken.mean():.3%} ohne Höhendaten"
    hoehe[luecken] = 0
    foto = np.asarray(Image.open(f"{nk.LAND}/Textures/t{c:02d}{r:02d}.dds").convert("RGB"))
    foto = cv2.resize(foto, (K, K), interpolation=cv2.INTER_AREA).astype(np.float32)
    return hoehe, foto, gebaeude_maske(west, nord, nk.PATCH, nk.LGB_ORDNER)


def schreiben(c, r, schwelle):
    bild = klassifiziere(*grundlagen(c, r), hell_nadel=schwelle)
    os.makedirs(nk.LAND + "/ForestMaps", exist_ok=True)
    np.ascontiguousarray(bild[::-1, ::-1].T).tofile(f"{nk.LAND}/ForestMaps/{c:02d}{r:02d}.for")
    return f"{c:02d}{r:02d}.for: Nadel {np.mean(bild == 1):.1%}, Laub {np.mean(bild == 2):.1%}"


def eg3_klasse(e, n):
    """Waldklasse der EG3-Karte an UTM-Punkten (nur EDAZ-Kernpatches 40/39 und 39/39, sonst 255)."""
    aus = np.full(e.shape, 255, np.uint8)
    for pc, pr in [(40, 39), (39, 39)]:
        datei = np.fromfile(f"{EG3}/ForestMaps/{pc:02d}{pr:02d}.for", np.uint8).reshape(512, 512)
        bild = datei.T[::-1, ::-1]  # zurück nach Nord oben, West links
        ost, sued = EG3_E0 - pc * nk.PATCH, EG3_N0 + pr * nk.PATCH
        s = ((e - (ost - nk.PATCH)) / (nk.PATCH / 512)).astype(int)
        z = ((sued + nk.PATCH - n) / (nk.PATCH / 512)).astype(int)
        t = (s >= 0) & (s < 512) & (z >= 0) & (z < 512)
        aus[t] = bild[z[t], s[t]]
    return aus


def kalibrieren():
    c, r = 2, 2  # enthält EDAZ und den größten Teil der EG3-Kernpatches
    hoehe, foto, geb = grundlagen(c, r)
    west, _, _, nord = nk.patch_ecken(c, r)
    zelle = nk.PATCH / 512
    e, n = np.meshgrid(west + (np.arange(512) + 0.5) * zelle, nord - (np.arange(512) + 0.5) * zelle)
    ref = eg3_klasse(e, n)
    wald = (ref > 0) & (ref < 255)
    for s in range(50, 121, 5):
        bild = klassifiziere(hoehe, foto, geb, hell_nadel=s)
        beide = wald & (bild > 0)
        print(f"Schwelle {s}: Wald gleich {np.mean((bild > 0)[ref < 255] == (ref > 0)[ref < 255]):.1%}, "
              f"Laub/Nadel gleich {np.mean(bild[beide] == ref[beide]):.1%}, Nadelanteil neu {np.mean(bild[beide] == 1):.1%} "
              f"(EG3 {np.mean(ref[beide] == 1):.1%})")


def main():
    if sys.argv[1:] == ["kalibrieren"]:
        return kalibrieren()
    schwelle = float(sys.argv[1]) if len(sys.argv) > 1 else SCHWELLE
    alle = [(c, r) for c in range(nk.PATCHES_X) for r in range(nk.PATCHES_Y)]
    for c, r in alle:  # Kacheln vorher entpacken, parallel würden sich Nachbarn stören
        west, ost, sued, nord = nk.patch_ecken(c, r)
        for d in ("bdom", "dgm"):
            for e in range(int(west // 1000), int(np.ceil(ost / 1000))):
                for n in range(int(sued // 1000), int(np.ceil(nord / 1000))):
                    nk.lgb_datei(d, e, n, ".tif")
    with ProcessPoolExecutor(4) as pool:
        for zeile in pool.map(schreiben, *zip(*alle), [schwelle] * len(alle)):
            print(zeile, flush=True)


if __name__ == "__main__":
    main()
