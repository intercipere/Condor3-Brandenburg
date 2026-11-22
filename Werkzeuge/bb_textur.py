"""Patch-Texturen der Landschaft Brandenburg aus LGB-DOP20 (Nord oben, Ost rechts), DXT1 mit Mipmaps.

Aufruf: python bb_textur.py [spalte,zeile ...]   (ohne Angabe alle Patches)
Die DOP-Kacheln stammen aus mehreren Bildflügen. Jeder Flug wird je Kanal über die Helligkeitsverteilung im Streifen
an der Fluggrenze an den Flug mit der größten Fläche angeglichen (Quantil-Abgleich als Tabelle 0–255, siehe angleich).
Eine lineare Angleichung über Mittelwert und Streuung (bis 22.11.2026) verstärkte Grün und Blau der Flüge 2025 um bis
zu 1,9 und ließ helle Felder fast weiß werden. Die Tabellen gelten für alle Patches, damit keine Kante an
Patchgrenzen entsteht. Rohbilder liegen als Zwischenspeicher in Daten/Arbeit_BB/Textur.
"""
import os
import re
import sys
import zipfile
from concurrent.futures import ProcessPoolExecutor

import cv2
import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.merge import merge

import neukarte as nk
from dds_dxt1 import schreibe_dds

PX = 8192
KLEIN = 1024
CACHE = os.path.join(nk.ARBEIT, "Textur")
PROZESSE = 4
STREIFEN_M = 1500.0  # Breite des Vergleichsstreifens an Bildfluggrenzen
MIN_STREIFEN_PX = 1000  # weniger Vergleichspixel (kleine Fassung): Flug bleibt unverändert


def bildflugdatum(jpg):
    """Bildflugdatum aus den Metadaten im Original-Zip der Kachel."""
    name = os.path.splitext(os.path.basename(jpg))[0]
    ost, nord = map(int, re.findall(r"_33(\d+)-(\d+)", name)[0])
    with zipfile.ZipFile(nk.lgb_zip("dop", ost, nord)) as zf:
        html = zf.read(name + ".html").decode("utf-8", "ignore")
    m = re.search(r"Bildflugdatum:\s*(\d{4}-\d{2}-\d{2})", re.sub("<[^>]+>", " ", html))
    assert m, f"kein Bildflugdatum in {name}"
    return m.group(1)


def kacheln(c, r):
    west, ost, sued, nord = nk.patch_ecken(c, r)
    return [nk.lgb_datei("dop", e, n, ".jpg")
            for e in range(int(west // 1000), int(np.ceil(ost / 1000)))
            for n in range(int(sued // 1000), int(np.ceil(nord / 1000)))]


def roh(c, r, daten):
    """Rohbild (PX × PX, Nord oben) und Flugindex je Pixel, aus dem Zwischenspeicher oder neu gebaut."""
    pfad = os.path.join(CACHE, f"roh_{c:02d}{r:02d}.npz")
    if os.path.exists(pfad):
        with np.load(pfad) as z:
            if "daten" in z and list(z["daten"]) == daten:  # Flugindex zählt in dieser Liste
                return z["img"], z["flug"]
    west, ost, sued, nord = nk.patch_ecken(c, r)
    quellen = [rasterio.open(p) for p in kacheln(c, r)]
    img = np.zeros((PX, PX, 3), np.uint8)
    flug = np.full((PX, PX), 255, np.uint8)
    for k, datum in enumerate(daten):
        teil = [q for q in quellen if bildflugdatum(q.name) == datum]
        if not teil:
            continue
        arr, _ = merge(teil, bounds=(west, sued, ost, nord), res=nk.PATCH / PX, resampling=Resampling.average,
                       dst_kwds={"crs": CRS.from_epsg(25833)})
        a = np.transpose(arr[:3], (1, 2, 0))[:PX, :PX]
        da = a.sum(axis=2) > 0
        img[da] = a[da]
        flug[da] = k
    for q in quellen:
        q.close()
    luecke = flug == 255
    assert luecke.mean() < 0.001, f"t{c:02d}{r:02d}: {luecke.mean():.2%} ohne Bilddaten"
    if luecke.any():  # Lücken auffüllen, Flug vom nächsten Nachbarn
        img = cv2.inpaint(img, luecke.astype(np.uint8), 2, cv2.INPAINT_TELEA)
        idx = cv2.distanceTransformWithLabels(luecke.astype(np.uint8), cv2.DIST_L2, 3, labelType=cv2.DIST_LABEL_PIXEL)[1]
        quelle = np.zeros(idx.max() + 1, np.uint8)
        quelle[idx[~luecke]] = flug[~luecke]
        flug = quelle[idx]
    np.savez(pfad + ".part.npz", img=img, flug=flug, daten=np.array(daten))
    os.replace(pfad + ".part.npz", pfad)
    return img, flug


def roh_klein(c, r, daten):
    img, flug = roh(c, r, daten)
    return (c, r), cv2.resize(img, (KLEIN, KLEIN), interpolation=cv2.INTER_AREA), \
        cv2.resize(flug, (KLEIN, KLEIN), interpolation=cv2.INTER_NEAREST)


def anwenden(img, flug, umrechnung):
    """Farbtabellen je Flug anwenden: umrechnung = {Flugindex: uint8[3, 256]}; Flüge ohne Tabelle bleiben."""
    aus = img.copy()
    for k, lut in umrechnung.items():
        t = flug == k
        for ch in range(3):
            aus[..., ch][t] = lut[ch][img[..., ch][t]]
    return aus


def tabelle(quelle, ziel):
    """Quantil-Abgleich eines Kanals: Wert v der Quelle -> Wert gleichen Rangs (Mittelrang) in der Zielverteilung."""
    h = np.bincount(quelle, minlength=256).astype(np.float64)
    cdf = np.cumsum(h) / h.sum()
    mitte = cdf - h / h.sum() / 2
    return np.clip(np.round(np.quantile(ziel, mitte)), 0, 255).astype(np.uint8)


def fertig(c, r, daten, umrechnung):
    img, flug = roh(c, r, daten)
    schreibe_dds(anwenden(img, flug, umrechnung), f"{nk.LAND}/Textures/t{c:02d}{r:02d}.dds")
    return f"t{c:02d}{r:02d}: DDS geschrieben"


def angleich(bild, flug, daten):
    """Farbtabelle je Flug und Kanal (uint8[3, 256]). Verglichen wird nur in einem Streifen von STREIFEN_M beidseits
    der Fluggrenze, sonst verfälscht der unterschiedliche Inhalt (Wald, Felder) die Statistik. Der Flug mit der
    größten Fläche bleibt unverändert; die übrigen werden nacheinander an schon angeglichene Nachbarn angeschlossen."""
    px = STREIFEN_M / (nk.PATCH / KLEIN)
    flaeche = {k: int((flug == k).sum()) for k in range(len(daten)) if (flug == k).any()}
    gleich = np.tile(np.arange(256, dtype=np.uint8), (3, 1))
    fertig_k = {max(flaeche, key=flaeche.get): gleich}
    print(f"Bezug: Flug {daten[next(iter(fertig_k))]}")
    while len(fertig_k) < len(flaeche):
        bezug = np.isin(flug, list(fertig_k))
        nah_bezug = cv2.distanceTransform((~bezug).astype(np.uint8), cv2.DIST_L2, 5) < px
        beste = None
        for k in flaeche.keys() - fertig_k.keys():
            eigen = flug == k
            nah_eigen = cv2.distanceTransform((~eigen).astype(np.uint8), cv2.DIST_L2, 5) < px
            a, b = eigen & nah_bezug, bezug & nah_eigen
            if beste is None or a.sum() > beste[1]:
                beste = (k, a.sum(), a, b)
        k, anzahl, a, b = beste
        if anzahl < MIN_STREIFEN_PX:
            print(f"WARNUNG Flug {daten[k]}: nur {anzahl} Vergleichspixel, bleibt unverändert")
            fertig_k[k] = gleich
            continue
        ziel = anwenden(bild, flug, fertig_k)  # Bezugsseite schon angeglichen
        fertig_k[k] = np.stack([tabelle(bild[a][:, ch], ziel[b][:, ch]) for ch in range(3)])
        stuetz = [32, 64, 128, 192, 240]
        print(f"Flug {daten[k]}: Tabelle bei {stuetz} -> R {fertig_k[k][0][stuetz].tolist()}, "
              f"G {fertig_k[k][1][stuetz].tolist()}, B {fertig_k[k][2][stuetz].tolist()}", flush=True)
    return fertig_k


def farbumrechnung():
    """Bildflüge (sortierte Datumsliste) und Verstärkung/Versatz je Flug für die ganze Landschaft."""
    os.makedirs(CACHE, exist_ok=True)
    alle = [(c, r) for c in range(nk.PATCHES_X) for r in range(nk.PATCHES_Y)]
    datum = {j: bildflugdatum(j) for p in alle for j in kacheln(*p)}
    daten = sorted(set(datum.values()))
    print("Bildflüge (Kacheln):", {d: sum(v == d for v in datum.values()) for d in daten}, flush=True)

    with ProcessPoolExecutor(PROZESSE) as pool:
        klein = list(pool.map(roh_klein, *zip(*alle), [daten] * len(alle)))
    # Ganze Landschaft klein zusammensetzen (Nord oben, West links)
    teile = {p: (i, f) for p, i, f in klein}
    bild = np.concatenate([np.concatenate([teile[(c, r)][0] for c in reversed(range(nk.PATCHES_X))], 1)
                           for r in reversed(range(nk.PATCHES_Y))], 0)
    flug = np.concatenate([np.concatenate([teile[(c, r)][1] for c in reversed(range(nk.PATCHES_X))], 1)
                           for r in reversed(range(nk.PATCHES_Y))], 0)
    return daten, angleich(bild, flug, daten)


def main():
    os.makedirs(nk.LAND + "/Textures", exist_ok=True)
    alle = [(c, r) for c in range(nk.PATCHES_X) for r in range(nk.PATCHES_Y)]
    gewaehlt = [tuple(int(x) for x in a.split(",")) for a in sys.argv[1:]] or alle
    daten, umrechnung = farbumrechnung()

    with ProcessPoolExecutor(2) as pool:  # DXT1-Kodierung braucht viel Speicher
        for meldung in pool.map(fertig, *zip(*gewaehlt), [daten] * len(gewaehlt), [umrechnung] * len(gewaehlt)):
            print(meldung, flush=True)


if __name__ == "__main__":
    main()
