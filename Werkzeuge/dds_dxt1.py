"""Schreibt RGB-Bilder als DDS (DXT1/BC1) mit vollständiger Mipmap-Kette, wie Condor sie für Patch-Texturen nutzt.

Aufruf: python dds_dxt1.py <eingabe.png> <ausgabe.dds>
Kodierung je 4x4-Block: Endpunkte entlang der Hauptachse der Blockfarben, Indizes durch Projektion (4-Farben-Modus).
"""
import struct
import sys
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
from PIL import Image


def _rgb565(c):
    c = np.clip(np.rint(c), 0, 255).astype(np.uint32)
    return ((c[..., 0] >> 3) << 11) | ((c[..., 1] >> 2) << 5) | (c[..., 2] >> 3)


def _aus565(v):
    r = (v >> 11) & 31
    g = (v >> 5) & 63
    b = v & 31
    return np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], -1).astype(np.float32)


def kodiere_bloecke(img):
    """img: (H, W, 3) uint8, H und W Vielfache von 4 -> Bytes der BC1-Blöcke in Zeilenreihenfolge."""
    h, w, _ = img.shape
    b = img.reshape(h // 4, 4, w // 4, 4, 3).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 3).astype(np.float32)
    mitte = b.mean(1, keepdims=True)
    d = b - mitte
    cov = np.einsum("nki,nkj->nij", d, d)
    achse = np.ones((len(b), 3), np.float32)
    for _ in range(8):  # Potenzmethode für die Hauptachse
        achse = np.einsum("nij,nj->ni", cov, achse)
        achse /= np.linalg.norm(achse, axis=1, keepdims=True) + 1e-9
    t = np.einsum("nki,ni->nk", d, achse)
    p0 = mitte[:, 0] + achse * t.max(1, keepdims=True)
    p1 = mitte[:, 0] + achse * t.min(1, keepdims=True)
    c0, c1 = _rgb565(p0), _rgb565(p1)
    # Für den 4-Farben-Modus muss c0 > c1 gelten; bei Gleichheit ist der Block einfarbig.
    tausch = c0 < c1
    c0, c1 = np.where(tausch, c1, c0), np.where(tausch, c0, c1)
    e0, e1 = _aus565(c0), _aus565(c1)
    palette = np.stack([e0, e1, (2 * e0 + e1) / 3, (e0 + 2 * e1) / 3], 1)  # (n, 4, 3)
    abst = ((b[:, :, None, :] - palette[:, None, :, :]) ** 2).sum(-1)  # (n, 16, 4)
    idx = abst.argmin(-1).astype(np.uint32)
    idx[c0 == c1] = 0
    bits = (idx << (2 * np.arange(16, dtype=np.uint32))).sum(1).astype(np.uint32)
    out = np.zeros((len(b), 2), np.uint32)
    out[:, 0] = c0 | (c1 << 16)
    out[:, 1] = bits
    return out.astype("<u4").tobytes()


def schreibe_dds(img, pfad):
    h, w, _ = img.shape
    ebenen = []
    stufe = img
    pool = ThreadPoolExecutor(4)
    while True:
        hh, ww = stufe.shape[:2]
        pad = stufe
        if hh % 4 or ww % 4:  # kleinste Mipmaps (2x2, 1x1) auf einen 4x4-Block auffüllen
            pad = np.zeros((max(4, hh), max(4, ww), 3), np.uint8)
            pad[:hh, :ww] = stufe
            pad[:, ww:] = pad[:, ww - 1:ww]
            pad[hh:, :] = pad[hh - 1:hh, :]
        # In Streifen kodieren, damit 8192er-Texturen nicht mehrere GB Speicher brauchen; 4 Streifen gleichzeitig.
        ebenen.append(b"".join(pool.map(kodiere_bloecke, (pad[y:y + 256] for y in range(0, pad.shape[0], 256)))))
        if hh == 1 and ww == 1:
            break
        stufe = cv2.resize(stufe, (max(1, ww // 2), max(1, hh // 2)), interpolation=cv2.INTER_AREA)
        if stufe.ndim == 2:
            stufe = stufe[:, :, None].repeat(3, 2)
    pool.shutdown()
    kopf = struct.pack(
        "<4sIIIIIII44sIIIIIIIIIIIII",
        b"DDS ", 124, 0x1 | 0x2 | 0x4 | 0x1000 | 0x20000 | 0x80000, h, w, len(ebenen[0]), 0, len(ebenen),
        b"\0" * 44,
        32, 0x4, 0x31545844, 0, 0, 0, 0, 0,  # Pixelformat: FourCC "DXT1"
        0x1000 | 0x8 | 0x400000, 0, 0, 0, 0,
    )
    with open(pfad, "wb") as f:
        f.write(kopf)
        for e in ebenen:
            f.write(e)


if __name__ == "__main__":
    bild = np.asarray(Image.open(sys.argv[1]).convert("RGB"))
    schreibe_dds(bild, sys.argv[2])
    test = np.asarray(Image.open(sys.argv[2]).convert("RGB")).astype(np.float32)
    mse = ((test - bild.astype(np.float32)) ** 2).mean()
    print(f"{sys.argv[2]}: {bild.shape[1]}x{bild.shape[0]}, PSNR {10 * np.log10(255 ** 2 / mse):.1f} dB (mit Pillow zurückgelesen)")
