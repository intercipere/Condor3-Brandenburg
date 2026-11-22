"""Baut aus LGB-DOP20-Kacheln die Textur eines Condor-Patches (Nord oben, Ost rechts).

Aufruf: python patch_textur.py <pixel> <ausgabeordner> <spalte,zeile> [<spalte,zeile> ...]  (alle Patches in einer Reihe)
Die Farben werden an die bisherige Patch-Textur angepasst, damit an den Rändern keine harten Kanten entstehen.
"""
import glob, os, re, sys, zipfile
import cv2
import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.merge import merge
from PIL import Image

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from config import LAND_ORIGINAL as LAND
# Kalibrierung der Landschaft aus EastGermany2.trn: rechte untere Ecke, Spalten zählen nach Westen.
E0, N0, PATCH = 605160.0, 5558120.0, 5760.0


def patch_bounds(col, row):
    east = E0 - col * PATCH
    south = N0 + row * PATCH
    return east - PATCH, south, east, south + PATCH  # west, south, east, north


def entpacke_dop(dop_dir, ziel):
    os.makedirs(ziel, exist_ok=True)
    for z in glob.glob(os.path.join(dop_dir, "*.zip")):
        with zipfile.ZipFile(z) as zf:
            for n in zf.namelist():
                if n.endswith((".jpg", ".jgw")) and not os.path.exists(os.path.join(ziel, n)):
                    zf.extract(n, ziel)


def farbangleich(neu, ref_neu, ref_alt):
    """Mittelwert und Streuung je Kanal angleichen. Die Statistik kommt aus dem ganzen Gebiet (alle Patches zusammen),
    damit benachbarte Patches dieselbe Umrechnung bekommen und keine Farbkante entsteht."""
    neu = neu.astype(np.float32)
    for k in range(3):
        n, a = ref_neu[..., k], ref_alt[..., k]
        neu[..., k] = (neu[..., k] - n.mean()) / (n.std() + 1e-6) * a.std() + a.mean()
    return np.clip(neu, 0, 255).astype(np.uint8)


def rand_angleich(neu, alt, rand_m=1500.0, sigma_m=200.0):
    """Gleicht die großflächigen Farben zum Außenrand hin an die alte Textur an (die zu ihren Nachbarn passt).
    neu/alt: gleiches Gebiet, beliebige Auflösung. Feine Details bleiben vom neuen Luftbild,
    nur der weichgezeichnete Farbunterschied (sigma ~200 m) wird am Rand voll, nach innen auf rand_m auslaufend addiert."""
    h, w = neu.shape[:2]  # Streifen: h entspricht einer Patch-Höhe (5760 m)
    kh = 1024
    k = kh * w // h
    m_pro_px = PATCH / kh  # Meter pro Pixel der kleinen Fassung
    n_s = cv2.resize(neu, (k, kh), interpolation=cv2.INTER_AREA).astype(np.float32)
    a_s = cv2.resize(alt, (k, kh), interpolation=cv2.INTER_AREA).astype(np.float32)
    sig = sigma_m / m_pro_px
    diff = cv2.GaussianBlur(a_s, (0, 0), sig, borderType=cv2.BORDER_REFLECT) - cv2.GaussianBlur(n_s, (0, 0), sig, borderType=cv2.BORDER_REFLECT)
    yy, xx = np.mgrid[0:kh, 0:k]
    d = np.minimum.reduce([xx, yy, k - 1 - xx, kh - 1 - yy]) * m_pro_px
    t = np.clip(1 - d / rand_m, 0, 1)
    wgt = t * t * (3 - 2 * t)
    korr = cv2.resize(diff * wgt[..., None], (w, h), interpolation=cv2.INTER_LINEAR)
    return np.clip(neu.astype(np.float32) + korr, 0, 255).astype(np.uint8)


def bildflugdatum(jpg_pfad):
    """Bildflugdatum aus der HTML-Metadatei im zugehörigen LGB-Zip."""
    name = os.path.splitext(os.path.basename(jpg_pfad))[0]
    with zipfile.ZipFile(os.path.join(PROJ, "Daten", "LGB", "dop", name + ".zip")) as zf:
        html = zf.read(name + ".html").decode("utf-8", "ignore")
    m = re.search(r"Bildflugdatum:\s*(\d{4}-\d{2}-\d{2})", re.sub("<[^>]+>", " ", html))
    assert m, f"kein Bildflugdatum in {name}"
    return m.group(1)


def baue(col, row, px):
    jpg_dir = os.path.join(PROJ, "Daten", "LGB", "dop_jpg")
    entpacke_dop(os.path.join(PROJ, "Daten", "LGB", "dop"), jpg_dir)
    w, s, e, n = patch_bounds(col, row)
    crs = CRS.from_epsg(25833)
    quellen = []
    for f in sorted(glob.glob(os.path.join(jpg_dir, "*.jpg"))):
        ds = rasterio.open(f)
        b = ds.bounds
        if b.right > w and b.left < e and b.top > s and b.bottom < n:
            quellen.append(ds)
    res = PATCH / px
    # JPGs haben nur ein World-File ohne CRS; alle liegen in ETRS89/UTM33 (EPSG:25833).
    # Je Bildflug getrennt zusammensetzen; Pixel merken, welcher Flug sie liefert (für den Farbangleich je Flug).
    daten = sorted({bildflugdatum(q.name) for q in quellen})
    img = np.zeros((px, px, 3), np.uint8)
    flug = np.full((px, px), -1, np.int16)
    for k, datum in enumerate(daten):
        teil = [q for q in quellen if bildflugdatum(q.name) == datum]
        arr, _ = merge(teil, bounds=(w, s, e, n), res=res, resampling=Resampling.average, dst_kwds={"crs": crs})
        a = np.transpose(arr[:3], (1, 2, 0))[:px, :px]
        da = a.sum(axis=2) > 0
        img[da] = a[da]
        flug[da] = k
    flug_datum = {k: d for k, d in enumerate(daten)}
    # An den Kachelgrenzen lässt merge() durch Rundung einzelne Pixelreihen leer; die werden aus den Nachbarn aufgefüllt.
    maske = (img.sum(axis=2) == 0).astype(np.uint8)
    luecken = maske.mean()
    img = cv2.inpaint(np.ascontiguousarray(img), maske, 2, cv2.INPAINT_TELEA)
    # Lücken (aufgefüllte Pixel) dem Flug des nächsten Nachbarn zuordnen
    if (flug < 0).any():
        idx = cv2.distanceTransformWithLabels((flug < 0).astype(np.uint8), cv2.DIST_L2, 3, labelType=cv2.DIST_LABEL_PIXEL)[1]
        quelle = np.zeros(idx.max() + 1, np.int16)
        quelle[idx[flug >= 0]] = flug[flug >= 0]
        flug = quelle[idx]
    datum_karte = np.array([flug_datum[k] for k in range(len(daten))])[flug]
    print(f"t{col:02d}{row:02d}: {len(quellen)} Kacheln, Bildflüge {daten}, {px}x{px} px, {res:.4f} m/px, Lückenanteil {luecken:.4%}")
    return img, datum_karte


def main():
    """Aufruf: python patch_textur.py <pixel> <ausgabeordner> <spalte,zeile> [<spalte,zeile> ...]"""
    px, ziel = int(sys.argv[1]), sys.argv[2]
    patches = [tuple(int(v) for v in a.split(",")) for a in sys.argv[3:]]
    gebaut = {p: baue(*p, px) for p in patches}
    alt = {p: np.asarray(Image.open(os.path.join(LAND, "Textures", f"t{p[0]:02d}{p[1]:02d}.dds")).convert("RGB")) for p in patches}
    # Patches einer Reihe von West nach Ost (Spalten zählen nach Westen) zu einem Streifen zusammensetzen,
    # damit der Randangleich nur an den Außenkanten des Gebiets greift.
    assert len({p[1] for p in patches}) == 1, "nur eine Patch-Reihe unterstützt"
    reihe = sorted(patches, key=lambda p: -p[0])
    roh = np.concatenate([gebaut[p][0] for p in reihe], 1)
    datum = np.concatenate([gebaut[p][1] for p in reihe], 1)
    alt_streifen = np.concatenate([cv2.resize(alt[p], (px, px), interpolation=cv2.INTER_LINEAR) for p in reihe], 1)
    # Farbangleich je Bildflug: Statistik des Flugs gegen die alte Textur auf genau derselben Fläche
    streifen = np.zeros_like(roh)
    for d in np.unique(datum):
        m = datum == d
        stich = np.flatnonzero(m.ravel())[::64]
        r_neu = roh.reshape(-1, 3)[stich][None]
        r_alt = alt_streifen.reshape(-1, 3)[stich][None]
        streifen[m] = farbangleich(roh[m][None], r_neu, r_alt)[0]
        print(f"Bildflug {d}: {m.mean():.1%} der Fläche")
    # Fassung ohne Randangleich für Auswertungen (z. B. Laub/Nadel in waldkarte.py), damit feste Schwellen gelten
    np.save(os.path.join(ziel, "mosaik_flug.npy"), streifen)
    streifen = rand_angleich(streifen, alt_streifen)
    np.save(os.path.join(ziel, "mosaik.npy"), streifen)
    for k, p in enumerate(reihe):
        out = os.path.join(ziel, f"t{p[0]:02d}{p[1]:02d}_{px}.png")
        Image.fromarray(streifen[:, k * px:(k + 1) * px]).save(out)
        print("gespeichert", out)


if __name__ == "__main__":
    main()
