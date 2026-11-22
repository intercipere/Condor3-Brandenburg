"""Gelände der Landschaft Brandenburg direkt aus DGM1: TRN (90 m), TR3 (30 m) und TR3F (22,5 m) für alle Patches.

Layout (gegen DGM1 und EG2/EG3 geprüft): Der erste Index zählt vom Ostrand nach Westen, der zweite vom Südrand
nach Norden. TR3: 193 × 193 int16, ganze Meter. TR3F: 257 × 257 float32. Ränder benachbarter Patches sind gleich.
TRN: 36 Byte Kopf, dann uint16 [Spalte, Zeile] mit 256 Werten je Kachel, Mittelwert jeder 90-m-Zelle.
Aufruf: python bb_gelaende.py
"""
import os
import struct
import cv2
import numpy as np
import rasterio
import neukarte as nk

RAND = 200  # Meter DGM über den Patch hinaus, damit die Glättung am Rand nicht abschneidet


def dgm_ausschnitt(west, ost, sued, nord):
    """DGM1 (1 m) für das Rechteck, Zeile 0 = Norden. Gibt (Feld, west, nord) zurück."""
    w, o = int(np.floor(west / 1000)), int(np.ceil(ost / 1000))
    s, n = int(np.floor(sued / 1000)), int(np.ceil(nord / 1000))
    feld = np.full(((n - s) * 1000, (o - w) * 1000), np.nan, np.float32)
    for e in range(w, o):
        for nn in range(s, n):
            with rasterio.open(nk.lgb_datei("dgm", e, nn, ".tif")) as d:
                assert d.res == (1.0, 1.0) and d.bounds.left == e * 1000 and d.bounds.top == (nn + 1) * 1000, d.name
                a = d.read(1).astype(np.float32)
                if d.nodata is not None:
                    a[a == d.nodata] = np.nan
            feld[(n - nn - 1) * 1000:(n - nn) * 1000, (e - w) * 1000:(e - w + 1) * 1000] = a
    assert np.isfinite(feld).all(), "DGM hat Lücken"
    return feld, w * 1000, n * 1000


def taste_ab(feld, west, nord, e, n):
    """Bilinear an UTM-Punkten; Pixel (r, c) hat seine Mitte bei (west + c + 0.5, nord - r - 0.5)."""
    c, r = e - west - 0.5, nord - n - 0.5
    c0, r0 = np.floor(c).astype(int), np.floor(r).astype(int)
    fc, fr = c - c0, r - r0
    return (feld[r0, c0] * (1 - fc) * (1 - fr) + feld[r0, c0 + 1] * fc * (1 - fr)
            + feld[r0 + 1, c0] * (1 - fc) * fr + feld[r0 + 1, c0 + 1] * fc * fr)


def raster(ost, sued, schritt, anzahl, feld, west0, nord0):
    """Werte [i, j] bei E = ost - i*schritt, N = sued + j*schritt."""
    i = np.arange(anzahl) * schritt
    e, n = np.meshgrid(ost - i, sued + i, indexing="ij")
    return taste_ab(feld, west0, nord0, e, n)


def main():
    os.makedirs(nk.LAND + "/HeightMaps/22.5m", exist_ok=True)
    trn = np.zeros((nk.PATCHES_X * 64, nk.PATCHES_Y * 64), np.uint16)
    for col in range(nk.PATCHES_X):
        for row in range(nk.PATCHES_Y):
            west, ost, sued, nord = nk.patch_ecken(col, row)
            feld, w0, n0 = dgm_ausschnitt(west - RAND, ost + RAND, sued - RAND, nord + RAND)
            # Box-Mittel über eine Rasterzelle, damit das gröbere Raster nicht flimmert
            tr3 = raster(ost, sued, 30.0, 193, cv2.blur(feld, (31, 31)), w0, n0)
            tr3f = raster(ost, sued, 22.5, 257, cv2.blur(feld, (23, 23)), w0, n0)
            # TRN: Mittel jeder 90-m-Zelle, Zelle (i, j) reicht von ost - 90 i nach Westen, sued + 90 j nach Norden
            r0, c0 = int(n0 - nord), int(west - w0)
            kern = feld[r0:r0 + 5760, c0:c0 + 5760].reshape(64, 90, 64, 90).mean(axis=(1, 3))  # [Nord→Süd, West→Ost]
            trn[col * 64:(col + 1) * 64, row * 64:(row + 1) * 64] = np.round(kern[::-1, ::-1].T)
            np.round(tr3).astype(np.int16).tofile(f"{nk.LAND}/HeightMaps/h{col:02d}{row:02d}.tr3")
            tr3f.astype(np.float32).tofile(f"{nk.LAND}/HeightMaps/22.5m/h{col:03d}{row:03d}.tr3f")
            print(f"Patch {col:02d}{row:02d}: {tr3f.min():.1f}–{tr3f.max():.1f} m", flush=True)
    kopf = struct.pack("<2i3f2f2i", trn.shape[0], trn.shape[1], 90.0, -90.0, 90.0, nk.E0, nk.N0, nk.ZONE, ord("N"))
    with open(f"{nk.LAND}/{nk.NAME}.trn", "wb") as f:
        f.write(kopf)
        trn.tofile(f)
    print(f"{nk.NAME}.trn: {trn.shape}, {trn.min()}–{trn.max()} m")


if __name__ == "__main__":
    main()
