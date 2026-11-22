"""Thermikkarte der Landschaft Brandenburg als Working/ThermalMap/ThermalMap.bmp (90 m/px, 256 × 256 je Kachel, Nord oben).

Grauwerte laut Condor Landscape Guide: Wasser 0, Laubwald 64, Wald/Gras/Ort 102, Felder 178.
Klassen je 90-m-Zelle:
  Wasser: DGM1 in der Zelle fast eben (Streuung < WASSER_STREUUNG), dunkles Luftbild, kein Wald.
  Wald: Mehrheit der .for-Zellen (bb_wald.py), Laub -> 64, Nadel -> 102.
  Ort: LoD2-Grundrisse decken mehr als ORT_ANTEIL der Zelle -> 102.
  Sonst Feld -> 178.
Zusätzlich <Name>.tdm: 8 Byte Kopf (int Breite, Höhe in Zellen, wie die .trn; bei EG3 3584, 5632), dann 1 Byte je Zelle, Zeilen von Süd nach Nord, Spalten von
Ost nach West. Ermittelt an EG3: die .tdm ist exakt Kanal 0 der .tm3 (3 Byte je Zelle, gleiche Anordnung).
Condor selbst verlangt die .tm3 (sonst „landscape not installed“); der Editor legt keine erste .tm3 an
(„Thermal map not loaded“), die Umwandlung im Condor Updater braucht ein Premium-Abo. Darum schreibt dieses Skript
sie selbst, 3 Byte je Zelle in derselben Anordnung wie die .tdm, ohne Kopf:
  Kanal 0 = .tdm-Wert.
  Kanal 1 = 2,578 × Standardabweichung der Höhe über 27 × 27 Zellen (an EG2 angepasst, mittlerer Rest 0,96).
  Kanal 2 = 127 + 0,2537 × (Höhe − Mittel über 27 × 27 Zellen) (an EG2 angepasst, mittlerer Rest 0,32).
Höhe aus der .trn (bb_gelaende.py vorher).
Aufruf: python bb_thermik.py
"""
import os
import struct

import cv2
import numpy as np
from PIL import Image

import neukarte as nk
from bb_gelaende import dgm_ausschnitt
from waldkarte import gebaeude_maske

Image.MAX_IMAGE_PIXELS = None
Z = 64                    # 90-m-Zellen je Patch
WASSER_STREUUNG = 0.05    # m, Wasserflächen sind im DGM1 eben
WASSER_HELL = 80.0        # mittlere Helligkeit des Luftbilds, bis zu der Wasser möglich ist
ORT_ANTEIL = 0.10


def patch_karte(c, r):
    """64 × 64 Grauwerte eines Patches (Nord oben, West links)."""
    west, ost, sued, nord = nk.patch_ecken(c, r)
    feld, w0, n0 = dgm_ausschnitt(west, ost, sued, nord)
    r0, c0 = int(n0 - nord), int(west - w0)
    dgm = feld[r0:r0 + 5760, c0:c0 + 5760].reshape(Z, 90, Z, 90)
    streuung = dgm.std(axis=(1, 3))
    foto = np.asarray(Image.open(f"{nk.LAND}/Textures/t{c:02d}{r:02d}.dds").convert("L"))
    hell = cv2.resize(foto, (Z, Z), interpolation=cv2.INTER_AREA).astype(np.float32)
    wald = np.fromfile(f"{nk.LAND}/ForestMaps/{c:02d}{r:02d}.for", np.uint8).reshape(512, 512).T[::-1, ::-1]
    w8 = wald.reshape(Z, 8, Z, 8)
    nadel, laub = (w8 == 1).mean(axis=(1, 3)), (w8 == 2).mean(axis=(1, 3))
    ort = cv2.resize(gebaeude_maske(west, nord, nk.PATCH, nk.LGB_ORDNER).astype(np.float32), (Z, Z),
                     interpolation=cv2.INTER_AREA)
    karte = np.full((Z, Z), 178, np.uint8)
    karte[ort > ORT_ANTEIL] = 102
    karte[nadel + laub > 0.5] = 102
    karte[(laub > 0.5) | ((nadel + laub > 0.5) & (laub > nadel))] = 64
    karte[(streuung < WASSER_STREUUNG) & (hell < WASSER_HELL) & (nadel + laub < 0.1)] = 0
    return karte


def main():
    bild = np.zeros((nk.PATCHES_Y * Z, nk.PATCHES_X * Z), np.uint8)
    for c in range(nk.PATCHES_X):
        for r in range(nk.PATCHES_Y):
            z0, s0 = (nk.PATCHES_Y - 1 - r) * Z, (nk.PATCHES_X - 1 - c) * Z
            bild[z0:z0 + Z, s0:s0 + Z] = patch_karte(c, r)
    os.makedirs(nk.LAND + "/Working/ThermalMap", exist_ok=True)  # dort sucht der Editor
    Image.fromarray(bild).convert("RGB").save(nk.LAND + "/Working/ThermalMap/ThermalMap.bmp")
    with open(f"{nk.LAND}/{nk.NAME}.tdm", "wb") as f:
        f.write(struct.pack("<2i", bild.shape[1], bild.shape[0]))
        f.write(np.ascontiguousarray(bild[::-1, ::-1]).tobytes())
    trn = np.fromfile(f"{nk.LAND}/{nk.NAME}.trn", np.uint16, offset=36).reshape(bild.shape[1], bild.shape[0])
    h = trn.T.astype(np.float32)  # [Zeile Süd→Nord, Spalte Ost→West], wie die .tdm
    mittel = cv2.blur(h, (27, 27), borderType=cv2.BORDER_REFLECT)
    streuung = np.sqrt(np.maximum(cv2.blur(h * h, (27, 27), borderType=cv2.BORDER_REFLECT) - mittel ** 2, 0))
    tm3 = np.stack([bild[::-1, ::-1].astype(np.float32), 2.578 * streuung, 127 + 0.2537 * (h - mittel)], -1)
    np.clip(np.round(tm3), 0, 255).astype(np.uint8).tofile(f"{nk.LAND}/{nk.NAME}.tm3")
    werte = {0: "Wasser", 64: "Laub", 102: "Wald/Ort", 178: "Feld"}
    print("ThermalMap.bmp:", ", ".join(f"{n} {np.mean(bild == v):.1%}" for v, n in werte.items()))


if __name__ == "__main__":
    main()
