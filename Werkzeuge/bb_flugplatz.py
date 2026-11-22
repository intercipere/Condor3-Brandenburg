"""Flugplatzdateien von EDAZ für die Landschaft Brandenburg (Airports/SchoenhagenG.c3d, SchoenhagenO.c3d, Texturen).

1. G-Datei und Gebäudetexturen stammen aus der eigenen EDAZ-Arbeit in EG3 und werden kopiert.
2. O-Datei: die eigenen Gebäude aus EG3, ohne Windsack-Markierung und Mast aus EG2 („Windsack1“, „Mat“). Dafür eigene:
   Markierung „Windsack1“ (ein Dreieck, dort zeichnet Condor seinen Windsack) auf einem eigenen Mast an derselben Stelle.
3. Unter-Textur der Flächen (Schoenhagen.dds): Die EG3-Fassung ist an die EG3-Farben angeglichen und gibt auf den
   Brandenburg-Patches eine harte Kante am Rand der Grass3D-Fläche. Grashöhe (Alpha) aus EG3, Farben neu aus DOP20 mit
   der Farbumrechnung der Patch-Texturen (bb_textur.farbumrechnung), genau dort, wo Condor die Fläche zeichnet:
   Lage aus den UV der G-Datei, Ursprung und Drehung aus Brandenburg.apt (+y in Pistenrichtung d, +x nach d-90°).
Aufruf: python bb_flugplatz.py (nach bb_textur.py und bb_grunddateien.py)
"""
import os
import shutil
import struct

import cv2
import numpy as np
import rasterio
from PIL import Image
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.merge import merge

import bb_textur
import c3d
import neukarte as nk
from config import CONDOR_DIR
from edaz_flaechen import NAME, SUB_M, SUB_PX, schreibe_dds_argb

EG3 = f"{CONDOR_DIR}/Landscapes/EastGermany3/Airports"  # wird nur gelesen
QUELLE_ALPHA = f"{EG3}/Textures/{NAME}.dds"
AUS_EG2 = ("Windsack1", "Mat")
WINDSACK_XY = (-70.0, 0.0)  # Lage wie bisher: 70 m links der Piste vom Flugplatzpunkt (G-/O-Koordinaten)
MAST_H, MAST_B = 20.0, 0.5  # Höhe wie bisher, Kantenlänge
GRAU = (0.6, 0.6, 0.6, 1.0, 0.0, 0.0)


def lies_apt():
    a = open(f"{nk.LAND}/{nk.NAME}.apt", "rb").read()
    for o in range(0, len(a), 72):
        if a[o + 1:o + 1 + a[o]].decode("latin1") == NAME:
            lat, lon = struct.unpack_from("<2f", a, o + 36)
            return lat, lon, struct.unpack_from("<I", a, o + 48)[0] % 100000 / 100.0
    raise SystemExit("Flugplatz nicht in der .apt")


def lage_unter_textur():
    """Westkante und Nordkante der Unter-Textur in UTM, aus G-Datei-Vertices und deren UV."""
    lat, lon, d = lies_apt()
    ec, nc = Transformer.from_crs(4326, 32633, always_xy=True).transform(lon, lat)
    cs, sn = np.cos(np.radians(d)), np.sin(np.radians(d))
    _, _, vert, _ = c3d.lies(f"{nk.LAND}/Airports/{NAME}G.c3d")
    x, y, u, v = vert[:, 0].astype(float), vert[:, 1].astype(float), vert[:, 6].astype(float), vert[:, 7].astype(float)
    e, n = ec - cs * x + sn * y, nc + sn * x + cs * y
    w, nord = e - u * SUB_M, n + v * SUB_M
    streu = max(np.ptp(w), np.ptp(nord))
    assert streu < 0.05, f"UV passen nicht zur Lage aus der .apt (Streuung {streu:.3f} m)"
    return float(np.median(w)), float(np.median(nord))


def farben(w, nord):
    """RGB der Unter-Textur direkt aus DOP20 (0,625 m/px, schärfer als die Patch-Textur mit 0,7 m/px und DXT1),
    je Bildflug mit derselben Farbumrechnung wie die Patch-Texturen (bb_textur.farbumrechnung)."""
    daten, umrechnung = bb_textur.farbumrechnung()
    grenzen = (w, nord - SUB_M, w + SUB_M, nord)
    kacheln = [nk.lgb_datei("dop", e, n, ".jpg")
               for e in range(int(grenzen[0] // 1000), int(np.ceil(grenzen[2] / 1000)))
               for n in range(int(grenzen[1] // 1000), int(np.ceil(grenzen[3] / 1000)))]
    rgb = np.zeros((SUB_PX, SUB_PX, 3), np.float32)
    gesetzt = np.zeros((SUB_PX, SUB_PX), bool)
    for k, datum in enumerate(daten):
        teil = [rasterio.open(p) for p in kacheln if bb_textur.bildflugdatum(p) == datum]
        if not teil:
            continue
        try:
            arr, _ = merge(teil, bounds=grenzen, res=SUB_M / SUB_PX, resampling=Resampling.average,
                           dst_kwds={"crs": CRS.from_epsg(25833)})
        finally:
            for q in teil:
                q.close()
        a = np.ascontiguousarray(np.transpose(arr[:3], (1, 2, 0))[:SUB_PX, :SUB_PX])
        da = a.sum(axis=2) > 0
        a = bb_textur.anwenden(a, np.full(da.shape, k, np.uint8), umrechnung)  # Flüge ohne Tabelle bleiben unverändert
        rgb[da] = a[da]
        gesetzt |= da
    assert (~gesetzt).mean() < 0.001, f"{(~gesetzt).mean():.2%} der Unter-Textur ohne DOP"
    rgb = np.clip(np.round(rgb), 0, 255).astype(np.uint8)
    if not gesetzt.all():
        rgb = cv2.inpaint(rgb, (~gesetzt).astype(np.uint8), 2, cv2.INPAINT_TELEA)
    return rgb


def windsack_mast():
    """Eigene Vertices und Indizes: Mast als Quader ohne Boden, darauf die Windsack-Markierung (ein Dreieck)."""
    x0, y0 = WINDSACK_XY
    h = MAST_B / 2
    v = []
    for nx, ny in ((1, 0), (0, 1), (-1, 0), (0, -1)):  # vier Seiten, je vier Ecken unten/oben
        tx, ty = -ny, nx
        for a, z in ((-1, 0.0), (1, 0.0), (1, MAST_H), (-1, MAST_H)):
            v.append([x0 + nx * h + tx * a * h, y0 + ny * h + ty * a * h, z, nx, ny, 0, 0, 0])
    for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):  # Deckel
        v.append([x0 + dx * h, y0 + dy * h, MAST_H, 0, 0, 1, 0, 0])
    i_mast = [b + k for b in range(0, 20, 4) for k in (0, 1, 2, 0, 2, 3)]
    zs = MAST_H + 0.1  # knapp über dem Deckel, sonst flimmern beide Flächen (wie bisher 0,1 m darüber)
    sack = [[x0 + 0.1, y0, zs, 0, 0, 1, 0, 0], [x0 - 0.1, y0, zs, 0, 0, 1, 0, 0], [x0, y0 + 0.2, zs, 0, 0, 1, 0, 0]]
    return np.array(sack, np.float32), np.array([0, 1, 2, 0, 2, 1], np.uint32), np.array(v, np.float32),         np.array(i_mast, np.uint32)


def flugplatz_dateien():
    os.makedirs(f"{nk.LAND}/Airports/Textures", exist_ok=True)
    shutil.copy2(f"{EG3}/{NAME}G.c3d", f"{nk.LAND}/Airports/{NAME}G.c3d")
    _, obs, vert, idx = c3d.lies(f"{EG3}/{NAME}O.c3d")
    assert {o["name"] for o in obs} >= set(AUS_EG2), "O-Datei in EG3 hat sich geändert"
    n_obs, n_v, n_i = [], [], []
    for o in obs:
        if o["name"] in AUS_EG2:
            continue
        vs, is_ = sum(map(len, n_v)), sum(map(len, n_i))
        n_v.append(vert[o["vstart"]:o["vstart"] + o["vanz"]])
        n_i.append(idx[o["istart"]:o["istart"] + o["ianz"]] - o["vstart"] + vs)
        n_obs.append(dict(o, vstart=vs, istart=is_))
        if o["textur"]:
            shutil.copy2(f"{EG3}/{o['textur'].strip()}", f"{nk.LAND}/Airports/{o['textur'].strip()}")
    sv, si, mv, mi = windsack_mast()
    for name, v, i in (("Windsack1", sv, si), ("Mast", mv, mi)):
        vs, is_ = sum(map(len, n_v)), sum(map(len, n_i))
        n_obs.append(dict(name=name, vstart=vs, vanz=len(v), istart=is_, ianz=len(i), textur="", material=GRAU, rest=0))
        n_v.append(v)
        n_i.append(i + vs)
    c3d.schreibe(f"{nk.LAND}/Airports/{NAME}O.c3d", n_obs, np.vstack(n_v), np.concatenate(n_i))
    print(f"{NAME}G.c3d kopiert, {NAME}O.c3d: " + ", ".join(o["name"] for o in n_obs))


def main():
    flugplatz_dateien()
    w, nord = lage_unter_textur()
    alpha = np.asarray(Image.open(QUELLE_ALPHA).getchannel("A"))
    assert alpha.shape == (SUB_PX, SUB_PX)
    schreibe_dds_argb(np.dstack([farben(w, nord), alpha]), f"{nk.LAND}/Airports/Textures/{NAME}.dds")
    print(f"{NAME}.dds: Unter-Textur ab W {w:.1f} / N {nord:.1f}, Farben aus DOP20 wie die Patch-Texturen")


if __name__ == "__main__":
    main()
