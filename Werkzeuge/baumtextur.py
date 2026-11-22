"""Baut die landschaftseigene Baumtextur (EastGermany3/World/Textures/Drevesa.dds).

Condor lädt /World/textures/Drevesa.dds zuerst aus dem Landschaftsordner (bestätigt mit rot eingefärbter Testtextur).
Atlas 1024 x 1024, DXT3, 11 Mip-Ebenen. Belegung des Originals:
  oben rechts  = Nadelbaum (Fichte), Stammfuß bei (346, 501) im Quadranten, Höhe ~470 px
  unten links  = Laubbaum, Stammfuß bei (214, 511)
  übrige Quadranten leer.
Hier: Nadelbaum-Quadrant durch die gerenderte Kiefer ersetzen (gleicher Fußpunkt, gleiche Höhe), Laubbaum bleibt original.

Aufruf: python baumtextur.py <kiefer.png> <ausgabe.dds>
"""
import struct
import sys

import cv2
import numpy as np
from PIL import Image

from dds_dxt1 import kodiere_bloecke

from config import GLOBAL_BAUMTEXTUR as ORIGINAL
FUSS_NADEL = (346, 501)   # im Quadranten oben rechts
HOEHE_PX = 470


def kiefer_quadrant(pfad):
    """Kiefer-Render (1024 px, Fuß bei (512, 1000), Baumhöhe = 940 px) so skalieren, dass die Baumhöhe HOEHE_PX ergibt,
    und auf den Fußpunkt der Fichte setzen. Kronenbüschel dürfen etwas über die Baumhöhe hinausragen."""
    k = Image.open(pfad).convert("RGBA")
    zeilen = np.nonzero((np.asarray(k)[..., 3] > 128).any(1))[0]
    spalten = np.nonzero((np.asarray(k)[..., 3] > 128).any(0))[0]
    assert zeilen[0] > 0 and spalten[0] > 0 and spalten[-1] < 1023, "Kiefer im Render abgeschnitten"
    s = HOEHE_PX / 940
    k = k.resize((round(1024 * s), round(1024 * s)), Image.LANCZOS)
    fx, fy = 512 * s, 1000 * s
    q = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    q.alpha_composite(k, (round(FUSS_NADEL[0] - fx), round(FUSS_NADEL[1] - fy)))
    return np.asarray(q)


def farbe_ausdehnen(rgba):
    """Farbe in transparente Bereiche fortsetzen, damit Mip-Ebenen keine dunklen Ränder bekommen."""
    rgba = rgba.copy()
    rgba[rgba[..., 3] < 9, 3] = 0  # wird in DXT3 (4 bit) ohnehin 0; die Farbe dort ist vom Skalieren oft schwarz
    rgb = rgba[..., :3].astype(np.float32); a = rgba[..., 3]
    voll = (a > 0).astype(np.float32)
    summe, gew = rgb * voll[..., None], voll.copy()
    for sigma in (2, 6, 18, 54):
        s = cv2.GaussianBlur(summe, (0, 0), sigma); w = cv2.GaussianBlur(gew, (0, 0), sigma)
        leer = (gew == 0) & (w > 1e-4)
        summe[leer] = s[leer] / w[leer, None]; gew[leer] = 1
    summe[gew == 0] = rgb[a > 0].mean(0)  # ganz entfernte Leerbereiche: mittlere Baumfarbe statt Schwarz
    out = rgba.copy(); out[..., :3] = np.clip(summe, 0, 255).astype(np.uint8)
    out[a > 0, :3] = rgba[a > 0, :3]
    return out


def dxt3_bloecke(rgba):
    h, w = rgba.shape[:2]
    al = (rgba[..., 3].astype(np.int32) * 15 + 127) // 255  # 4 bit
    al = al.reshape(h // 4, 4, w // 4, 4).transpose(0, 2, 1, 3).reshape(-1, 16).astype(np.uint64)
    alpha = (al << (4 * np.arange(16, dtype=np.uint64))).sum(1).astype("<u8")
    farbe = np.frombuffer(kodiere_bloecke(np.ascontiguousarray(rgba[..., :3])), "<u8")
    return np.stack([alpha, farbe], 1).tobytes()


def schreibe_dxt3(rgba, pfad):
    ebenen, stufe = [], rgba
    while True:
        hh, ww = stufe.shape[:2]
        pad = stufe
        if hh % 4 or ww % 4:
            pad = np.zeros((max(4, hh), max(4, ww), 4), np.uint8); pad[:hh, :ww] = stufe
            pad[:, ww:] = pad[:, ww - 1:ww]; pad[hh:] = pad[hh - 1:hh]
        ebenen.append(dxt3_bloecke(pad))
        if hh == 1 and ww == 1:
            break
        stufe = cv2.resize(stufe, (max(1, ww // 2), max(1, hh // 2)), interpolation=cv2.INTER_AREA)
    h, w = rgba.shape[:2]
    kopf = struct.pack("<4sIIIIIII44sIIIIIIIIIIIII", b"DDS ", 124, 0x1 | 0x2 | 0x4 | 0x1000 | 0x20000 | 0x80000, h, w,
                       len(ebenen[0]), 0, len(ebenen), b"\0" * 44, 32, 0x4, 0x33545844, 0, 0, 0, 0, 0,
                       0x1000 | 0x8 | 0x400000, 0, 0, 0, 0)
    with open(pfad, "wb") as f:
        f.write(kopf); f.writelines(ebenen)


def main():
    atlas = np.asarray(Image.open(ORIGINAL).convert("RGBA")).copy()
    atlas[0:512, 512:1024] = kiefer_quadrant(sys.argv[1])
    atlas = farbe_ausdehnen(atlas)
    schreibe_dxt3(atlas, sys.argv[2])
    test = np.asarray(Image.open(sys.argv[2]).convert("RGBA")).astype(np.float32)
    sichtbar = atlas[..., 3] > 128
    fehler_rgb = np.abs(test[..., :3] - atlas[..., :3])[sichtbar].mean()
    fehler_a = np.abs(test[..., 3] - atlas[..., 3]).mean()
    q = atlas[0:512, 512:1024, 3] > 0; ys, xs = np.nonzero(q)
    assert xs.min() >= 2 and xs.max() <= 509 and ys.min() >= 2, "Kiefer am Quadrantenrand abgeschnitten"
    print(f"{sys.argv[2]}: Kiefer Box x {xs.min()}-{xs.max()} y {ys.min()}-{ys.max()} | Rückgelesen: mittl. Farbfehler {fehler_rgb:.1f}, Alphafehler {fehler_a:.1f}")


if __name__ == "__main__":
    main()
