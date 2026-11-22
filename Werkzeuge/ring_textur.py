"""Baut die Luftbilder für den 3 x 3-Ring um EDAZ (Spalten 41-39, Reihen 40-38) aus LGB-DOP20.

Aufruf: python ring_textur.py
Ergebnis in Daten\\Arbeit\\Ring: t<SS><ZZ>.dds und flug_<SS><ZZ>.npy (örtlich angeglichenes Bild, für ring_wald.py).
Schreibt nichts in die Landschaft. Die abgenommenen Kern-Patches 40/39 und 39/39 bleiben unverändert:
Der Ring wird am Kernrand an die eingebauten Kern-Texturen angeglichen, am Außenrand an die alten Nachbarn.
Die zusammengesetzten Rohbilder liegen als Zwischenspeicher in Daten\\Arbeit\\Ring\\Cache und werden nur neu gebaut,
wenn eine DOP-Kachel neuer ist. Nach Änderungen an roh_bauen den Ordner Cache löschen.
"""
import json
import os
import re
import zipfile
from concurrent.futures import ProcessPoolExecutor

import cv2
import numpy as np
import rasterio
from PIL import Image
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.merge import merge

from config import LAND, LAND_ORIGINAL
from dds_dxt1 import schreibe_dds
from patch_textur import PATCH, entpacke_dop, patch_bounds

Image.MAX_IMAGE_PIXELS = None
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LGB_ORDNER = [os.path.join(PROJ, "Daten", "LGB"), os.path.join(PROJ, "Daten", "LGB_Ring")]
ZIEL = os.path.join(PROJ, "Daten", "Arbeit", "Ring")
CACHE = os.path.join(ZIEL, "Cache")
PROZESSE = 5            # parallele Patches beim Zusammensetzen der Rohbilder und im Wald
PROZESSE_FERTIG = 2     # parallele Patches im letzten Schritt, der braucht bis zu 6 GB je Patch

SPALTEN = [41, 40, 39]  # von West nach Ost
REIHEN = [40, 39, 38]   # von Nord nach Süd
KERN = [(40, 39), (39, 39)]
RING = [(c, r) for r in REIHEN for c in SPALTEN if (c, r) not in KERN]
PX = 8192
KLEIN = 1024            # Pixel je Patch für die großflächige Farbkorrektur
RAND_M = 1500.0         # Breite der Angleichzone am Außen- und am Kernrand
SIGMA_M = 200.0         # Glättung des Farbunterschieds
SIGMA_LOKAL_M = 1500.0  # Umkreis des örtlichen Farbangleichs gegen Dunst


def kacheln(c, r):
    """Pfade der DOP-Kacheln, die den Patch berühren."""
    w, s, e, n = patch_bounds(c, r)
    pfade = []
    for ost in range(int(w // 1000), int(np.ceil(e / 1000))):
        for nord in range(int(s // 1000), int(np.ceil(n / 1000))):
            name = f"dop_33{ost}-{nord}.jpg"
            treffer = [p for o in LGB_ORDNER if os.path.exists(p := os.path.join(o, "dop_jpg", name))]
            assert treffer, f"Kachel fehlt: {name}"
            pfade.append(treffer[0])
    return pfade


def bildflugdatum(jpg):
    name = os.path.splitext(os.path.basename(jpg))[0]
    zip_pfad = os.path.join(os.path.dirname(os.path.dirname(jpg)), "dop", name + ".zip")
    with zipfile.ZipFile(zip_pfad) as zf:
        html = zf.read(name + ".html").decode("utf-8", "ignore")
    m = re.search(r"Bildflugdatum:\s*(\d{4}-\d{2}-\d{2})", re.sub("<[^>]+>", " ", html))
    assert m, f"kein Bildflugdatum in {name}"
    return m.group(1)


def roh_bauen(c, r, datum_von, daten):
    """Patch aus den DOP-Kacheln: Bild (Nord oben) und Index des Bildflugs je Pixel."""
    w, s, e, n = patch_bounds(c, r)
    quellen = [rasterio.open(p) for p in kacheln(c, r)]
    img = np.zeros((PX, PX, 3), np.uint8)
    flug = np.full((PX, PX), 255, np.uint8)
    for k, datum in enumerate(daten):
        teil = [q for q in quellen if datum_von[os.path.basename(q.name)] == datum]
        if not teil:
            continue
        arr, _ = merge(teil, bounds=(w, s, e, n), res=PATCH / PX, resampling=Resampling.average, dst_kwds={"crs": CRS.from_epsg(25833)})
        a = np.transpose(arr[:3], (1, 2, 0))[:PX, :PX]
        da = a.sum(axis=2) > 0
        img[da] = a[da]
        flug[da] = k
    for q in quellen:
        q.close()
    maske = (img.sum(axis=2) == 0).astype(np.uint8)
    assert maske.mean() < 0.01, f"t{c}{r}: {maske.mean():.2%} des Patches ohne Bilddaten"
    img = cv2.inpaint(np.ascontiguousarray(img), maske, 2, cv2.INPAINT_TELEA)
    if (flug == 255).any():  # aufgefüllte Pixel bekommen den Flug des nächsten Nachbarn
        idx = cv2.distanceTransformWithLabels((flug == 255).astype(np.uint8), cv2.DIST_L2, 3, labelType=cv2.DIST_LABEL_PIXEL)[1]
        quelle = np.zeros(idx.max() + 1, np.uint8)
        quelle[idx[flug != 255]] = flug[flug != 255]
        flug = quelle[idx]
    return img, flug


def roh_pfade(c, r):
    return [os.path.join(CACHE, f"{name}_{c:02d}{r:02d}.npy") for name in ("roh", "flug")]


def roh_aus_cache(c, r, datum_von, daten):
    """Baut das Rohbild nur, wenn der Zwischenspeicher fehlt, älter als eine der DOP-Kacheln ist oder mit anderen
    Kacheln oder Bildflügen gebaut wurde (der Flugindex zählt in der Liste aller Flüge des Blocks).
    Gibt das kleine Bild und den kleinen Flugindex für die Farbstatistik zurück."""
    pfade = roh_pfade(c, r)
    info_pfad = os.path.join(CACHE, f"info_{c:02d}{r:02d}.json")
    info = {"kacheln": kacheln(c, r), "daten": daten}
    gueltig = os.path.exists(info_pfad) and all(os.path.exists(p) for p in pfade)
    if gueltig:
        with open(info_pfad, encoding="utf-8") as f:
            gueltig = json.load(f) == info and \
                min(os.path.getmtime(p) for p in pfade) > max(os.path.getmtime(j) for j in info["kacheln"])
    if gueltig:
        img, flug = (np.load(p) for p in pfade)
        meldung = "aus Zwischenspeicher"
    else:
        if os.path.exists(info_pfad):
            os.remove(info_pfad)
        img, flug = roh_bauen(c, r, datum_von, daten)
        for p, a in zip(pfade, (img, flug)):
            np.save(p + ".part.npy", a)
            os.replace(p + ".part.npy", p)
        with open(info_pfad, "w", encoding="utf-8") as f:  # zuletzt: zeigt den vollständigen Zwischenspeicher an
            json.dump(info, f)
        meldung = "Rohbild fertig"
    return klein(img), cv2.resize(flug, (KLEIN, KLEIN), interpolation=cv2.INTER_NEAREST), meldung


def fertig_schreiben(p, felder, korr):
    """Örtlich angleichen, flug_*.npy für den Wald speichern und (nur im Ring) die DDS schreiben.
    felder und korr sind schon auf den Ausschnitt dieses Patches zugeschnitten."""
    img, flug = (np.load(x) for x in roh_pfade(*p))
    # Der Wald nutzt das entdunstete Bild: Mit dem Gesamtangleich je Flug galten Kiefern im Dunst als Laubwald.
    fest = wende_lokal_an(img, flug, felder)
    np.save(os.path.join(ZIEL, f"flug_{p[0]:02d}{p[1]:02d}.npy"), cv2.resize(fest, (5760, 5760), interpolation=cv2.INTER_AREA))
    if p in KERN:  # Kern nur zur Kontrolle der Laub/Nadel-Schwelle gegen die eingebauten Waldkarten
        return f"t{p[0]:02d}{p[1]:02d}: Kontrollbild gespeichert"
    feld = cv2.resize(korr, (PX, PX), interpolation=cv2.INTER_LINEAR)
    fertig = np.clip(fest.astype(np.float32) + feld, 0, 255).astype(np.uint8)
    schreibe_dds(fertig, os.path.join(ZIEL, f"t{p[0]:02d}{p[1]:02d}.dds"))
    return f"t{p[0]:02d}{p[1]:02d}: DDS geschrieben"


def lies_textur(ordner, c, r):
    return np.asarray(Image.open(os.path.join(ordner, "Textures", f"t{c:02d}{r:02d}.dds")).convert("RGB"))


def klein(bild):
    return cv2.resize(bild, (KLEIN, KLEIN), interpolation=cv2.INTER_AREA)


def block(teile):
    """Setzt die kleinen Patches zum 3 x 3-Block zusammen (Nord oben, West links)."""
    return np.concatenate([np.concatenate([teile[(c, r)] for c in SPALTEN], 1) for r in REIHEN], 0)


def lokale_felder(neu, flug, alt, umrechnung):
    """Örtlicher Farbangleich je Bildflug gegen Dunst: Verstärkung und Versatz je Kanal aus Mittelwert und Streuung
    im Umkreis von etwa SIGMA_LOKAL_M, getrennt je Flug, damit die Statistik nicht über die Bildfluggrenze greift."""
    # Geglättet wird auf einem Viertel der Auflösung: Bei 1,5 km Umkreis ändert das nichts Sichtbares,
    # in voller Auflösung dauerte allein dieser Schritt 2,5 Minuten.
    sig = SIGMA_LOKAL_M / (PATCH / KLEIN) / 4
    h, b = neu.shape[:2]

    def glatt(a):
        k = cv2.resize(a, (b // 4, h // 4), interpolation=cv2.INTER_AREA)
        return cv2.resize(cv2.GaussianBlur(k, (0, 0), sig, borderType=cv2.BORDER_REFLECT), (b, h), interpolation=cv2.INTER_LINEAR)

    neu, alt = neu.astype(np.float32), alt.astype(np.float32)
    felder = {}
    for k, (m_neu, s_neu, m_alt, s_alt) in umrechnung.items():
        maske = (flug == k).astype(np.float32)
        gewicht = glatt(maske)
        g3 = np.maximum(gewicht, 1e-4)[..., None]
        sicher = np.clip(gewicht / 0.05, 0, 1)[..., None]  # wo der Flug kaum vorkommt, gelten seine Gesamtwerte
        statistik = []
        for bild, m_ges, s_ges in ((neu, m_neu, s_neu), (alt, m_alt, s_alt)):
            m = glatt(bild * maske[..., None]) / g3
            s = np.sqrt(np.maximum(glatt(bild * bild * maske[..., None]) / g3 - m * m, 1.0))
            statistik.append((sicher * m + (1 - sicher) * m_ges, sicher * s + (1 - sicher) * s_ges))
        (mn, sn), (ma, sa) = statistik
        verstaerkung = np.clip(sa / sn, 0.6, 1.6).astype(np.float32)
        felder[k] = (verstaerkung, (ma - verstaerkung * mn).astype(np.float32))
    return felder


def wende_lokal_an(bild, flug, felder):
    """Wendet die Felder an; sie decken dieselbe Fläche ab wie das Bild."""
    aus = bild.astype(np.float32)
    h, b = bild.shape[:2]
    for k, (verstaerkung, versatz) in felder.items():
        t = flug == k
        if not t.any():
            continue
        g = cv2.resize(verstaerkung, (b, h), interpolation=cv2.INTER_LINEAR)
        o = cv2.resize(versatz, (b, h), interpolation=cv2.INTER_LINEAR)
        aus[t] = aus[t] * g[t] + o[t]
    return np.clip(aus, 0, 255).astype(np.uint8)


def korrekturfeld(neu, alt, kern_ist, kern_maske):
    """Großflächige Farbkorrektur für den Block: zum Außenrand auf die alte Textur, zum Kern auf den eingebauten Kern."""
    groesse = neu.shape[0]
    m_pro_px = PATCH / KLEIN
    sig = SIGMA_M / m_pro_px
    glatt = lambda a: cv2.GaussianBlur(a, (0, 0), sig, borderType=cv2.BORDER_REFLECT)
    neu, alt, kern_ist = neu.astype(np.float32), alt.astype(np.float32), kern_ist.astype(np.float32)
    diff_alt = glatt(alt) - glatt(neu)
    # Unterschied zum Kern nur innerhalb des Kerns glätten und nach außen vom nächsten Kernpixel übernehmen.
    gewicht = glatt(kern_maske.astype(np.float32))[..., None]
    diff_kern = glatt((kern_ist - neu) * kern_maske[..., None]) / np.maximum(gewicht, 1e-3)
    abstand, idx = cv2.distanceTransformWithLabels((~kern_maske).astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    zeile, spalte = np.nonzero(kern_maske)
    naechstes = np.zeros((idx.max() + 1, 2), np.int32)
    naechstes[idx[kern_maske]] = np.c_[zeile, spalte]
    diff_kern = glatt(diff_kern[naechstes[idx][..., 0], naechstes[idx][..., 1]])
    weich = lambda d: (lambda t: t * t * (3 - 2 * t))(np.clip(1 - d / RAND_M, 0, 1))
    yy, xx = np.mgrid[0:groesse, 0:groesse]
    w_aussen = weich(np.minimum.reduce([xx, yy, groesse - 1 - xx, groesse - 1 - yy]) * m_pro_px)[..., None]
    w_kern = weich(abstand * m_pro_px)[..., None]
    return w_kern * diff_kern + (1 - w_kern) * w_aussen * diff_alt  # an der Kernnaht hat der Kern Vorrang


def main():
    os.makedirs(CACHE, exist_ok=True)
    for o in LGB_ORDNER:
        entpacke_dop(os.path.join(o, "dop"), os.path.join(o, "dop_jpg"))
    alle = [(c, r) for r in REIHEN for c in SPALTEN]
    datum_von = {os.path.basename(j): bildflugdatum(j) for p in alle for j in kacheln(*p)}
    daten = sorted(set(datum_von.values()))
    print("Bildflüge:", {d: sum(v == d for v in datum_von.values()) for d in daten}, flush=True)

    roh_k, flug_k = {}, {}
    with ProcessPoolExecutor(PROZESSE) as pool:
        auftraege = {p: pool.submit(roh_aus_cache, *p, datum_von, daten) for p in alle}
        for p, a in auftraege.items():
            roh_k[p], flug_k[p], meldung = a.result()
            print(f"t{p[0]:02d}{p[1]:02d}: {meldung}", flush=True)

    alt_k = {p: klein(lies_textur(LAND_ORIGINAL, *p)) for p in alle}
    neu_b, flug_b, alt_b = block(roh_k), block(flug_k), block(alt_k)
    umrechnung = {}
    for k in np.unique(flug_b):
        t = flug_b == k
        umrechnung[int(k)] = (neu_b[t].mean(0), neu_b[t].std(0) + 1e-6, alt_b[t].mean(0), alt_b[t].std(0))

    felder = lokale_felder(neu_b, flug_b, alt_b, umrechnung)
    angeglichen = wende_lokal_an(neu_b, flug_b, felder)
    kern_ist = {p: klein(lies_textur(LAND, *p)) if p in KERN else np.zeros((KLEIN, KLEIN, 3), np.uint8) for p in alle}
    kern_maske = block({p: np.full((KLEIN, KLEIN), p in KERN, bool) for p in alle})
    korr = korrekturfeld(angeglichen, alt_b, block(kern_ist), kern_maske)

    with ProcessPoolExecutor(PROZESSE_FERTIG) as pool:
        auftraege = []
        for p in KERN + RING:
            z, s = REIHEN.index(p[1]) * KLEIN, SPALTEN.index(p[0]) * KLEIN
            ausschnitt = {k: (v[z:z + KLEIN, s:s + KLEIN], o[z:z + KLEIN, s:s + KLEIN]) for k, (v, o) in felder.items()}
            auftraege.append(pool.submit(fertig_schreiben, p, ausschnitt, korr[z:z + KLEIN, s:s + KLEIN]))
        for a in auftraege:
            print(a.result(), flush=True)


if __name__ == "__main__":
    main()
