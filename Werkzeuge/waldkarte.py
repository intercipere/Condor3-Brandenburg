"""Erzeugt Condor-Waldkarten (.for) aus LGB-Daten: Baumhöhe = bDOM - DGM1, Laub/Nadel aus dem April-Luftbild.

.for-Format (aus EastGermany2 ermittelt): 512 x 512 uint8 pro Patch (11,25 m/px, Condors Maximum),
Wert 1 = Nadelwald (s-Karte), 2 = Laubwald (b-Karte), 0 = kein Wald.
Ausrichtung: Datei = Bild[::-1, ::-1].T, wobei Bild Zeile 0 = Norden, Spalte 0 = Westen
(Korrelation mit dunklen Texturflächen 0,60 gegenüber höchstens 0,22 bei allen anderen Ausrichtungen).

Aufruf: python waldkarte.py   (Patches siehe PATCHES)
"""
import glob
import os
import zipfile

import cv2
import numpy as np
import rasterio
import rasterio.enums
from PIL import Image

import gelaende as g

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LGB = os.path.join(PROJ, "Daten", "LGB")
from config import LAND
PATCHES = [(40, 39), (39, 39)]
ZELLE = g.PATCH / 512  # 11,25 m
MIN_HOEHE = 3.0         # ab hier zählt Bewuchs als Baum
MIN_ANTEIL = 0.35       # Anteil Baumfläche in einer Zelle, ab dem Condor dort Wald setzt
HELL_NADEL = 58.0       # mittlere Helligkeit der Baumpixel einer Zelle, bis zu der Nadelwald gilt


def raster_mosaik(ordner_zip, ordner_tif, endung=".tif", res=1.0):
    """Setzt 1-km-Kacheln zu einem Raster zusammen, beim Einlesen auf res (m) gemittelt."""
    os.makedirs(ordner_tif, exist_ok=True)
    for z in glob.glob(os.path.join(ordner_zip, "*.zip")):
        with zipfile.ZipFile(z) as zf:
            for n in zf.namelist():
                if n.endswith((endung, ".tfw")) and not os.path.exists(os.path.join(ordner_tif, n)):
                    zf.extract(n, ordner_tif)
    ds = [rasterio.open(f) for f in sorted(glob.glob(os.path.join(ordner_tif, "*" + endung)))]
    w = min(d.bounds.left for d in ds); n = max(d.bounds.top for d in ds)
    e = max(d.bounds.right for d in ds); s = min(d.bounds.bottom for d in ds)
    arr = np.full((int(round((n - s) / res)), int(round((e - w) / res))), np.nan, np.float32)
    for d in ds:
        a = d.read(1, masked=True, out_shape=(int(round(d.height * d.res[0] / res)), int(round(d.width * d.res[0] / res))),
                   resampling=rasterio.enums.Resampling.average).astype(np.float32).filled(np.nan)
        r0, c0 = int(round((n - d.bounds.top) / res)), int(round((d.bounds.left - w) / res))
        arr[r0:r0 + a.shape[0], c0:c0 + a.shape[1]] = a
    return arr, w, n, res


def ausschnitt(arr, w, n, res, west, nord, groesse):
    """Patch-Ausschnitt (Nord oben) aus einem Mosaik."""
    r0, c0 = int(round((n - nord) / res)), int(round((west - w) / res))
    k = int(round(groesse / res))
    a = arr[r0:r0 + k, c0:c0 + k]
    assert a.shape == (k, k) and np.isfinite(a).all(), "Daten decken den Patch nicht vollständig ab"
    return a


def gebaeude_maske(west, nord, groesse, lgb_ordner=(LGB,)):
    """1-m-Maske aller LoD2-Grundrisse (um 2 m vergrößert), Nord oben."""
    from lxml import etree
    import re
    k = int(round(groesse))
    maske = np.zeros((k, k), np.uint8)
    for z in [z for o in lgb_ordner for z in glob.glob(os.path.join(o, "lod2", "*.zip"))]:
        ke, kn = map(int, re.findall(r"_33(\d+)-(\d+)", z)[0])
        if ke * 1000 > west + groesse or (ke + 1) * 1000 < west or kn * 1000 > nord or (kn + 1) * 1000 < nord - groesse:
            continue
        with zipfile.ZipFile(z) as zf:
            baum = etree.fromstring(zf.read([x for x in zf.namelist() if x.endswith(".gml")][0]))
        # Die LGB-Dateien nutzen CityGML 1.0 und 2.0. Ohne GroundSurface ergibt das Dach den Grundriss.
        for haus in baum.iter("{*}Building"):
            for gs in list(haus.iter("{*}GroundSurface")) or list(haus.iter("{*}RoofSurface")):
                for p in gs.iter("{*}posList"):
                    xy = np.array(p.text.split(), float).reshape(-1, 3)[:, :2]
                    pts = np.c_[xy[:, 0] - west, nord - xy[:, 1]].round().astype(np.int32)
                    cv2.fillPoly(maske, [pts], 1)
    return cv2.dilate(maske, np.ones((5, 5), np.uint8)).astype(bool)


def klassifiziere(hoehe, foto, gebaeude, hell_nadel=HELL_NADEL):
    """Waldklassen je Zelle (512 x 512, Nord oben) aus Baumhöhe, Luftbild und Gebäudemaske, alle mit 1 m pro Pixel."""
    hell = foto.mean(2)
    gruen = foto[..., 1] - (foto[..., 0] + foto[..., 2]) / 2
    baum = (hoehe >= MIN_HOEHE) & (gruen > -6) & ~gebaeude  # Gebäude aus LoD2 raus, Masten u. Ä. sind grau
    anteil = cv2.resize(baum.astype(np.float32), (512, 512), interpolation=cv2.INTER_AREA)
    summe_hell = cv2.resize(np.where(baum, hell, 0).astype(np.float32), (512, 512), interpolation=cv2.INTER_AREA)
    hell_zelle = summe_hell / np.maximum(anteil, 1e-6)
    bild = np.zeros((512, 512), np.uint8)
    wald = anteil >= MIN_ANTEIL
    bild[wald & (hell_zelle <= hell_nadel)] = 1
    bild[wald & (hell_zelle > hell_nadel)] = 2
    # Einzelne abweichende Zellen in Mischbeständen glätten (3x3-Mehrheit innerhalb des Waldes)
    geglaettet = cv2.medianBlur(bild, 3)
    return np.where(wald, np.where(geglaettet > 0, geglaettet, bild), 0).astype(np.uint8)


def main():
    bdom, bw, bn, bres = raster_mosaik(os.path.join(LGB, "bdom"), os.path.join(LGB, "bdom_tif"))
    dgm, dw, dn, dres = raster_mosaik(os.path.join(LGB, "dgm"), os.path.join(LGB, "dgm_tif"))
    assert bres == dres == 1.0
    # Laub/Nadel aus dem April-Luftbild (DOP, Ende April): Kiefern sind dunkel, Laubbäume noch kahl oder frisch belaubt
    # und deutlich heller. Das Sommer-Infrarot (WMS) trennt hier nicht: dort leuchten alle Bäume gleich.
    # Schwelle: 95. Perzentil der Helligkeit im bekannten Kiefernforst südlich der Piste (56,7) -> 58.
    mosaik = np.load(os.path.join(PROJ, "Daten", "Arbeit", "mosaik_flug.npy"))
    assert mosaik.shape[:2] == (8192, 8192 * len(PATCHES))
    for k, (c, r) in enumerate(PATCHES):
        ec, nc = g.patch_mitte(c, r)
        west, nord = ec - g.PATCH / 2, nc + g.PATCH / 2
        hoehe = ausschnitt(bdom, bw, bn, bres, west, nord, g.PATCH) - ausschnitt(dgm, dw, dn, dres, west, nord, g.PATCH)
        foto = cv2.resize(mosaik[:, k * 8192:(k + 1) * 8192], hoehe.shape[::-1], interpolation=cv2.INTER_AREA).astype(np.float32)
        gebaeude = gebaeude_maske(west, nord, g.PATCH)
        print(f"{c:02d}{r:02d}: Gebäudefläche {gebaeude.mean():.2%}")
        bild = klassifiziere(hoehe, foto, gebaeude)
        datei = np.ascontiguousarray(bild[::-1, ::-1].T)
        pfad = os.path.join(LAND, "ForestMaps", f"{c:02d}{r:02d}.for")
        alt = np.fromfile(pfad, np.uint8)
        datei.tofile(pfad)
        v = {0: "kein", 1: "Nadel", 2: "Laub"}
        print(f"{c:02d}{r:02d}.for: neu " + ", ".join(f"{v[x]} {np.mean(bild == x):.1%}" for x in (0, 1, 2))
              + " | alt " + ", ".join(f"{v[x]} {np.mean(alt == x):.1%}" for x in (0, 1, 2)))
        vorschau = np.zeros((512, 512, 3), np.uint8)
        vorschau[bild == 1] = (20, 90, 30); vorschau[bild == 2] = (140, 200, 60)
        Image.fromarray(vorschau).save(os.path.join(PROJ, "Daten", "Arbeit", f"wald_{c:02d}{r:02d}.png"))


if __name__ == "__main__":
    main()
