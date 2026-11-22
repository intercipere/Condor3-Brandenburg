"""Lesen/Schreiben der 22,5-m-Gelände-OBJ des Landscape Editors und Abtasten von DGM1."""
import glob, os, zipfile
import numpy as np
import rasterio
import rasterio.transform

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E0, N0, PATCH = 605160.0, 5558120.0, 5760.0
from config import LAND
WORK = LAND + "/Working/HeightMaps/22.5m"


def patch_mitte(col, row):
    return E0 - (col + 0.5) * PATCH, N0 + (row + 0.5) * PATCH


def lies_obj(pfad):
    kopf, v, rest = [], [], []
    for z in open(pfad):
        if z.startswith("v "):
            v.append([float(a) for a in z.split()[1:4]])
        elif not v:
            kopf.append(z)
        else:
            rest.append(z)
    return kopf, np.array(v), rest


def schreibe_obj(pfad, kopf, v, rest):
    with open(pfad, "w", newline="\n") as f:
        f.writelines(kopf)
        for x, y, z in v:
            f.write(f"v {x:g} {y:g} {z:.2f}\n")
        f.writelines(rest)


def dgm_mosaik():
    ziel = os.path.join(PROJ, "Daten", "LGB", "dgm_tif")
    os.makedirs(ziel, exist_ok=True)
    for z in glob.glob(os.path.join(PROJ, "Daten", "LGB", "dgm", "*.zip")):
        with zipfile.ZipFile(z) as zf:
            for n in zf.namelist():
                if n.endswith((".tif", ".tfw")) and not os.path.exists(os.path.join(ziel, n)):
                    zf.extract(n, ziel)
    # Alle Kacheln: 1000 x 1000 px, 1 m, ETRS89/UTM33 (teils mit, teils ohne Höhen-CRS in den Metadaten),
    # daher von Hand nach ihrer linken oberen Ecke zusammensetzen.
    ds = [rasterio.open(f) for f in sorted(glob.glob(os.path.join(ziel, "*.tif")))]
    w = min(d.bounds.left for d in ds); nn = max(d.bounds.top for d in ds)
    e = max(d.bounds.right for d in ds); s = min(d.bounds.bottom for d in ds)
    arr = np.full((int(nn - s), int(e - w)), np.nan, np.float32)
    for d in ds:
        a = d.read(1).astype(np.float32)
        a[a == d.nodata] = np.nan
        r0, c0 = int(nn - d.bounds.top), int(d.bounds.left - w)
        arr[r0:r0 + a.shape[0], c0:c0 + a.shape[1]] = a
    return arr, rasterio.transform.from_origin(w, nn, 1.0, 1.0)


def taste_ab(dgm, trans, e, n):
    """Bilineare Abtastung des DGM an UTM-Koordinaten (Pixelmitten-Konvention)."""
    inv = ~trans
    c, r = inv * (e, n)
    c, r = np.asarray(c) - 0.5, np.asarray(r) - 0.5
    c0, r0 = np.floor(c).astype(int), np.floor(r).astype(int)
    fc, fr = c - c0, r - r0
    g = lambda rr, cc: dgm[np.clip(rr, 0, dgm.shape[0] - 1), np.clip(cc, 0, dgm.shape[1] - 1)]
    return (g(r0, c0) * (1 - fc) * (1 - fr) + g(r0, c0 + 1) * fc * (1 - fr)
            + g(r0 + 1, c0) * (1 - fc) * fr + g(r0 + 1, c0 + 1) * fc * fr)
