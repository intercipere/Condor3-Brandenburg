"""Baut alle Siedlungen der Landschaft Brandenburg aus LoD2 (LGB) als Condor-Autogen, mit Sonderbehandlung für den
Löwendorfer Geflügelhof mit dem Landwerk Ahrensdorf (Raster aus neukarte.py; die Fassung für EG3 baute nur Schönhagen,
Ahrensdorf und Löwendorf im EG2-Raster und liegt im EDAZ-Projekt).

- Gebiet: LoD2-Gebäude außerhalb des Flugplatzes (die stehen schon in SchoenhagenO.c3d) werden über 40-m-Puffer
  zu Siedlungen zusammengefasst; eine Gruppe sind alle Siedlungen bis zum Radius um ihre Ortspunkte (GRUPPEN).
  Jede weitere Siedlung ab MIN_GEBAEUDE Gebäuden wird eine eigene Gruppe, benannt nach dem nächsten OSM-Ort
  (Daten/OSM/places_bb.json, © OpenStreetMap-Mitwirkende, ODbL).
- Hallen: Landwirtschaft graubeige mit Zuluftklappen, Gewerbe mittelgrau (fassaden.BLECH_FARBEN).
- Geflügelhof (Gruppe Loewendorf, lange Ställe 2720 ab 800 m²): Abluftventilatoren am Südgiebel, je drei Futtersilos vor
  dem Nordgiebel (Silos und Schatten im DOP20 an den Nordwest-Giebeln erkennbar, Anzahl und Maße geschätzt).
- Geometrie, Dreiecke, Wandtexturen wie edaz_gebaeude.py (ohne Hallentore). Dachtextur: DOP20 senkrecht projiziert,
  eine Textur je Dorf (Größe nach Ausdehnung, höchstens DACH_PX), Farben je Bildflug wie die Patch-Texturen.
  Wände reichen bis unter das 22,5-m-Gelände des Patches (mindestens SCHURZ unter LoD2-Boden).
- Gelände: die TR3F der Landschaft (bb_gelaende.py), Dreiecke wie in Condor (edaz_flaechen.gelaende_dreiecke).
- Ausgabe: Working/Autogen/o<Patch>.obj/.mtl (autogen.py) und die Texturen nach Daten/Arbeit_BB/Autogen. Danach im
  Landscape Editor "Export autogen C3D from OBJ", C3D nach <Landschaft>/Autogen, Texturen nach Autogen/Textures,
  dann "Export autogen hash (OHA)".
"""
import os
import re
from collections import Counter

import cv2
import numpy as np
import rasterio
import shapely
from rasterio.enums import Resampling
from rasterio.merge import merge
from shapely.geometry import Point, Polygon, box

import autogen
import bb_textur
import edaz_gebaeude as eg
import fassaden as fs
from dds_dxt1 import schreibe_dds
import neukarte as nk
from edaz_flaechen import ZELLE, ist_geschlossen, osm_elemente, utm

# Gruppe -> (Ortspunkte UTM33, Radius): OSM place=village/town (Trebbin: node 60122712) bzw. Geflügelhof
# (way 98596298) und Landwerk (way 732965215)
GRUPPEN = {"Schoenhagen": ([(373426.0, 5786222.0)], 600.0), "Ahrensdorf": ([(374452.0, 5783582.0)], 600.0),
           "Loewendorf": ([(375540.0, 5784412.0), (375615.0, 5784678.0)], 150.0),
           "Trebbin": ([(377985.0, 5786459.0)], 800.0)}
STALL_MIN_FLAECHE, STALL_MIN_LAENGE = 800.0, 60.0
SILO_R, SILO_H, SILO_KEGEL, SILO_ABSTAND, SILO_VOR = 1.2, 7.5, 1.8, 3.0, 3.0
GIEBEL_BREITE = (9.0, 16.0)  # nur Stallgiebel dieser Breite bekommen Silos (nicht die Verbindungsbauten)
FIRST_MIN = 4.0  # Giebelstücke mit Lüftern reichen mindestens so hoch über den Boden (Ställe 4,7 m, Verbinder ~3 m)
CLUSTER_PUFFER = 40.0
MIN_GEBAEUDE = 10  # kleinere Gebäudegruppen (Einzelhöfe, Scheunen) bleiben ohne Autogen
NAME_RADIUS = 2000.0
ORTSARTEN = ("town", "village", "suburb", "hamlet", "isolated_dwelling", "farm")  # bevorzugt vor "locality"
DACH_PX, DACH_RES = 4096, 0.2
SCHURZ = 1.5
ZIEL = os.path.join(nk.ARBEIT, "Autogen")
PREFIX = "BBDorf"
# Wandart -> (Objektname, Texturdatei)
WAND = {"putz": ("Waende", f"{PREFIX}_Putz.dds"), "fassade": ("Fassaden", f"{PREFIX}_Fassade.dds"),
        "blech_stall": ("Staelle", f"{PREFIX}_Stall.dds"), "blech_gewerbe": ("Hallen", f"{PREFIX}_Gewerbe.dds"),
        "blech_luefter": ("Giebel", f"{PREFIX}_Luefter.dds"), "silo": ("Silos", f"{PREFIX}_Silo.dds")}
GARAGEN = {"2460", "2461", "2462", "2463", "2465"}


def dorftyp(i):
    """'halle_stall'/'halle_gewerbe' (Trapezblech), 'fassade' (Putz mit Fenstern) oder 'neben' (Putz ohne Fenster), aus
    ALKIS-Funktion und Grundfläche: Garagen ohne Fenster; Landwirtschaft, Gewerbe und Unbekanntes ab 250 m² als Halle
    (Landwirtschaft 27xx als Stall, sonst Gewerbe), unter 100 m² ohne Fenster, dazwischen Landwirtschaft ohne, Gewerbe und
    Unbekanntes mit Fenstern; Wohn- und übrige Gebäude mit Fenstern (unter 25 m² ohne)."""
    f, a = i["funktion"], i["flaeche"]
    if f in GARAGEN:
        return "neben"
    if f[:2] in ("20", "21", "27") or f in ("9998", "9999"):
        if a >= 250:
            return "halle_stall" if f.startswith("27") else "halle_gewerbe"
        if a < 100 or f.startswith("27"):
            return "neben"
        return "fassade"
    return "neben" if a < 25 else "fassade"


def waehle_doerfer(info, flugplatz):
    ids = [g for g in info if not flugplatz.intersects(info[g]["zentrum"])]  # gleicher Test wie edaz_gebaeude
    U = shapely.unary_union([info[g]["grundriss"].buffer(CLUSTER_PUFFER) for g in ids])
    doerfer = {}
    for name, (orte, radius) in GRUPPEN.items():
        cl = shapely.unary_union([c for c in shapely.get_parts(U) if min(c.distance(Point(o)) for o in orte) <= radius])
        doerfer[name] = [g for g in ids if cl.contains(info[g]["zentrum"])]
    doppelt = [g for a in doerfer for b in doerfer if a < b for g in set(doerfer[a]) & set(doerfer[b])]
    assert not doppelt, f"Gebäude in zwei Gruppen: {doppelt}"
    return doerfer


def ist_gefluegelstall(gruppe, i):
    if gruppe != "Loewendorf" or i["funktion"] != "2720" or i["flaeche"] < STALL_MIN_FLAECHE:
        return False
    return max(achsen(i["grundriss"])[1:]) >= STALL_MIN_LAENGE


def achsen(grundriss):
    """Längsrichtung (Einheitsvektor) und Seitenlängen des kleinsten umschließenden Rechtecks."""
    c = np.array(grundriss.minimum_rotated_rectangle.exterior.coords)[:3]
    a, b = c[1] - c[0], c[2] - c[1]
    lang = a if np.linalg.norm(a) >= np.linalg.norm(b) else b
    return lang / np.linalg.norm(lang), np.linalg.norm(a), np.linalg.norm(b)


def giebel_von(ring, i, boden_hoehen, gid):
    """Für Wände von Geflügelställen: None (Längswand), 'nord' oder 'sued' (Giebel am Boden, quer zur Längsachse)."""
    achse, _, _ = achsen(i["grundriss"])
    nh = eg.newell(ring)[:2]
    if np.linalg.norm(nh) < 1e-6:
        return None
    richtung = np.array([-nh[1], nh[0]]) / np.linalg.norm(nh)
    if abs(richtung @ achse) > 0.3:
        return None
    if not (np.abs(ring[:, 2][:, None] - boden_hoehen[gid][None, :]).min(1) < 0.1).any():
        return None
    if achse[1] < 0:  # Achse zeigt nach Norden
        achse = -achse
    c = i["grundriss"].centroid
    return "nord" if (ring[:, :2].mean(0) - [c.x, c.y]) @ achse > 0 else "sued"


def stallgiebel(fl_geb, i, boden_hoehen, gid):
    """Giebel eines Geflügelstalls: LoD2 teilt Giebel teils in mehrere Wandstücke. Die Unterkanten der Stücke einer
    Seite werden zu ganzen Giebeln zusammengefügt. Ergebnis: Liste von (seite, mitte_xy, aussen_xy, breite, ring_ids)."""
    stuecke = {"nord": [], "sued": []}
    for art, ring, innen, g in fl_geb:
        if art == "WallSurface":
            seite = giebel_von(ring, i, boden_hoehen, gid)
            if seite:
                am_boden = np.abs(ring[:, 2][:, None] - boden_hoehen[gid][None, :]).min(1) < 0.1
                stuecke[seite].append((ring, shapely.LineString(ring[am_boden, :2]) if am_boden.sum() >= 2 else None))
    out = []
    for seite, liste in stuecke.items():
        linien = [l for _, l in liste if l is not None]
        if not linien:
            continue
        for teil in shapely.get_parts(shapely.unary_union([l.buffer(0.3) for l in linien])):
            ringe = [r for r, l in liste if l is not None and teil.intersects(l)]
            punkte = np.vstack([r[:, :2] for r in ringe])
            # Achsrichtung des Stalls statt Summe der Ringnormalen (einzelne LoD2-Ringe sind falsch herum)
            aussen, _, _ = achsen(i["grundriss"])
            if (aussen[1] < 0) == (seite == "nord"):
                aussen = -aussen
            entlang = np.array([-aussen[1], aussen[0]])
            s = punkte @ entlang
            breite = s.max() - s.min()
            mitte = punkte[np.argmin(s)] + entlang * (breite / 2)
            mitte = mitte - aussen * ((mitte - punkte.mean(0)) @ aussen)  # auf die Wandebene
            if i["grundriss"].contains(Point(*(mitte + 0.5 * aussen))):
                continue  # Außenrichtung unklar: lieber keine Silos/Lüfter-Ursprung als falsche
            out.append((seite, mitte, aussen, breite, {id(r) for r in ringe}))
    return out


def silos(mitte, aussen, gel):
    """Drei Futtersilos vor einem Giebel: Zylinder mit Kegeldach, Dreiecke (UTM) und UV wie die Wände."""
    entlang = np.array([-aussen[1], aussen[0]])
    out = []
    w = np.linspace(0, 2 * np.pi, 17)
    for k in (-1, 0, 1):
        c = mitte + aussen * (SILO_VOR + SILO_R) + entlang * k * SILO_ABSTAND
        zb = float(gel(c[0], c[1])) - 0.5
        zt = zb + 0.5 + SILO_H
        rand = np.c_[c[0] + SILO_R * np.cos(w), c[1] + SILO_R * np.sin(w)]
        u = w / (2 * np.pi) * max(1, round(2 * np.pi * SILO_R / fs.SILO_M))  # ganze Kacheln um den Umfang
        v = lambda z: np.clip((zb + fs.SILO_M - z) / fs.SILO_M, 0.0, 0.999)
        for a in range(16):
            p0, p1 = [*rand[a], zb], [*rand[a + 1], zb]
            p2, p3 = [*rand[a + 1], zt], [*rand[a], zt]
            uv = lambda P, uu: np.c_[uu, [v(q[2]) for q in P]]
            for tri, uu in (((p0, p1, p2), (u[a], u[a + 1], u[a + 1])), ((p0, p2, p3), (u[a], u[a + 1], u[a]))):
                out.append((np.array(tri), uv(tri, uu)))
            spitze = [c[0], c[1], zt + SILO_KEGEL]
            tri = (p3, p2, spitze)
            out.append((np.array(tri), np.c_[(u[a], u[a + 1], (u[a] + u[a + 1]) / 2), (0.08, 0.08, 0.05)]))
    return out


def lade_raster(patches):
    """22,5-m-Gelände der Patches als H[j, i] (j ab Süd, i ab West) mit Südwestecke (w0, s0), aus den TR3F
    (Layout wie bb_grunddateien.gelaende_hoehe: f[Index ab Ost, Index ab Süd])."""
    cols, rows = [c for c, _ in patches], [r for _, r in patches]
    w0, s0 = nk.patch_ecken(max(cols), 0)[0], nk.patch_ecken(0, min(rows))[2]
    H = np.full((256 * (max(rows) - min(rows) + 1) + 1, 256 * (max(cols) - min(cols) + 1) + 1), np.nan)
    for c in range(min(cols), max(cols) + 1):
        for r in range(min(rows), max(rows) + 1):
            f = np.fromfile(f"{nk.LAND}/HeightMaps/22.5m/h{c:03d}{r:03d}.tr3f", np.float32).reshape(257, 257)
            i0, j0 = 256 * (max(cols) - c), 256 * (r - min(rows))
            H[j0:j0 + 257, i0:i0 + 257] = f[::-1, :].T
    return H, w0, s0


def gelaende_hoehe(H, w0, s0):
    """Höhe des 22,5-m-Geländes an UTM-Punkten, auf denselben Dreiecken wie Condor
    (Diagonale je Zelle wechselnd, siehe edaz_flaechen.gelaende_dreiecke; w0 liegt auf einer Patchkante)."""
    def h(e, n):
        c, r = (np.asarray(e, float) - w0) / ZELLE, (np.asarray(n, float) - s0) / ZELLE
        c0 = np.clip(np.floor(c).astype(int), 0, H.shape[1] - 2); r0 = np.clip(np.floor(r).astype(int), 0, H.shape[0] - 2)
        fc, fr = np.clip(c - c0, 0, 1), np.clip(r - r0, 0, 1)
        h00, h10, h01, h11 = H[r0, c0], H[r0, c0 + 1], H[r0 + 1, c0], H[r0 + 1, c0 + 1]
        gerade = (c0 + r0) % 2 == 0  # Diagonale (0,0)-(1,1), sonst (1,0)-(0,1)
        z_g = np.where(fc >= fr, h00 + fc * (h10 - h00) + fr * (h11 - h10), h00 + fr * (h01 - h00) + fc * (h11 - h01))
        z_u = np.where(fc + fr <= 1, h00 + fc * (h10 - h00) + fr * (h01 - h00),
                       h11 + (1 - fc) * (h01 - h11) + (1 - fr) * (h10 - h11))
        return np.where(gerade, z_g, z_u)
    return h


def dachbild(flaechen, daten, umrechnung):
    """Dachtextur aus DOP20, je Bildflug mit der Farbtabelle der Patch-Texturen (bb_textur.farbumrechnung)."""
    alle = np.vstack([f[1] for f in flaechen if f[0] == "RoofSurface"])
    w0, n0 = alle[:, 0].min() - 10, alle[:, 1].max() + 10
    groesse = max(alle[:, 0].max() - w0, n0 - alle[:, 1].min()) + 10
    px = int(min(DACH_PX, max(256, 2 ** np.ceil(np.log2(groesse / DACH_RES)))))
    res = max(DACH_RES, groesse / px)
    grenzen = (w0, n0 - px * res, w0 + px * res, n0)
    pfade = []
    for e in range(int(grenzen[0] // 1000), int(np.ceil(grenzen[2] / 1000))):
        for n in range(int(grenzen[1] // 1000), int(np.ceil(grenzen[3] / 1000))):
            try:
                pfade.append(nk.lgb_datei("dop", e, n, ".jpg"))
            except FileNotFoundError:  # außerhalb der Landschaft, wird unten aufgefüllt
                pass
    bild = np.zeros((px, px, 3), np.uint8)
    for k, datum in enumerate(daten):
        teil = [rasterio.open(p) for p in pfade if bb_textur.bildflugdatum(p) == datum]
        if not teil:
            continue
        try:
            arr, _ = merge(teil, bounds=grenzen, res=res, resampling=Resampling.average)
        finally:
            for q in teil:
                q.close()
        a = np.ascontiguousarray(np.transpose(arr[:3], (1, 2, 0))[:px, :px])
        da = a.sum(2) > 0
        bild[da] = bb_textur.anwenden(a, np.full(da.shape, k, np.uint8), umrechnung)[da]
    bild = cv2.inpaint(bild, (bild.sum(2) == 0).astype(np.uint8), 2, cv2.INPAINT_TELEA)
    return bild, w0, n0, px * res


def ascii_name(name):
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue"), ("ß", "ss")):
        name = name.replace(a, b)
    return re.sub(r"[^A-Za-z0-9]", "", name)


def weitere_orte(info, flugplatz, vergeben):
    """Alle übrigen Siedlungen ab MIN_GEBAEUDE Gebäuden: {Name: [Gebäude-IDs]}, Name vom nächsten OSM-Ort."""
    schon = {g for ids in vergeben.values() for g in ids}
    ids = [g for g in info if g not in schon and not flugplatz.intersects(info[g]["zentrum"])]
    teile = list(shapely.get_parts(shapely.unary_union([info[g]["grundriss"].buffer(CLUSTER_PUFFER) for g in ids])))
    zu = shapely.STRtree(teile).query([info[g]["zentrum"] for g in ids], predicate="within")
    mitglieder = {}
    for i, c in zip(*zu):
        mitglieder.setdefault(int(c), []).append(ids[i])
    orte = [(e["tags"].get("place"), e["tags"]["name"], Point(utm([e])[0]))
            for e in osm_elemente("places_bb.json") if "name" in e.get("tags", {})]
    out = {}
    for c, m in sorted(mitglieder.items(), key=lambda x: -len(x[1])):
        if len(m) < MIN_GEBAEUDE:
            continue
        mitte = teile[c].representative_point()
        nah = sorted((o[0] not in ORTSARTEN, o[2].distance(mitte), o[1]) for o in orte
                     if o[2].distance(mitte) <= NAME_RADIUS)
        name = ascii_name(nah[0][2]) if nah else f"Ort{int(mitte.x)}_{int(mitte.y)}"
        k, basis = 2, name
        while name in out or name in vergeben:
            name, k = f"{basis}{k}", k + 1
        out[name] = m
    return out


def waende(ring, innen, gid, typ, boden_hoehen, gel, grundriss, zaehler, blech="blech_gewerbe", ursprung=None):
    """Dreiecke einer LoD2-Wand mit Wandart und UV (v nach unten), wie edaz_gebaeude.main ohne Tore.
    blech: Texturschlüssel für Hallenwände (blech_stall, blech_gewerbe, blech_luefter).
    ursprung: gemeinsamer Punkt für u bei Wänden, die LoD2 in Stücke teilt (Stallgiebel)."""
    ring = ring.copy()
    nh = eg.newell(ring)[:2]
    if np.linalg.norm(nh) > 1e-6:  # Wand zeigt ins eigene Gebäude (falsch orientierter LoD2-Ring) -> umdrehen
        nh = nh / np.linalg.norm(nh)
        mitte = ring[:, :2].mean(0)
        if grundriss.contains(Point(*(mitte + 0.3 * nh))) and not grundriss.contains(Point(*(mitte - 0.3 * nh))):
            ring = ring[::-1]; zaehler["umgedreht"] += 1
    am_boden = np.abs(ring[:, 2][:, None] - boden_hoehen[gid][None, :]).min(1) < 0.1
    z_boden = ring[am_boden, 2].min() if am_boden.any() else boden_hoehen[gid].min()
    trauf = ring[~am_boden, 2].min() - z_boden if am_boden.any() and (~am_boden).any() else 0.0
    if am_boden.any():  # Wandfuß gleichmäßig bis unter das Condor-Gelände verlängern, entlang der ganzen Unterkante
        proben = [ring[am_boden]]
        for k in range(len(ring) - 1):
            if am_boden[k] and am_boden[k + 1]:
                proben.append(ring[k] + np.linspace(0, 1, 12)[:, None] * (ring[k + 1] - ring[k]))
        P = np.vstack(proben)
        tiefe = max(SCHURZ, float((P[:, 2] - gel(P[:, 0], P[:, 1])).max()) + 0.5)
        ring[am_boden, 2] -= tiefe
    nh = eg.newell(ring)[:2]
    richtung = np.array([-nh[1], nh[0]]) / (np.linalg.norm(nh) + 1e-9)
    s = (ring[:, :2] - ring[0, :2]) @ richtung
    s_min, laenge = s.min(), s.max() - s.min()
    if ursprung is not None:  # u ab dem gemeinsamen Ursprung (nur Blechtexturen, die nicht auf die Wandlänge gestreckt werden)
        s_min = (np.asarray(ursprung) - ring[0, :2]) @ richtung
    ziel_unten, ziel_oben, z_teil = (blech, blech, None) if typ.startswith("halle") else ("putz", "putz", None)
    if typ == "fassade" and trauf > 0 and laenge >= 2.0:
        reihen = int((trauf - fs.FENSTER[1] - 0.2) // fs.GESCHOSS) + 1
        if reihen >= 1:
            ziel_unten, z_teil = "fassade", z_boden + min(reihen * fs.GESCHOSS, trauf)
    achse = laenge / max(1, round(laenge / fs.ACHSE_M))

    def uv_von(P, ziel):
        s = (P[:, :2] - ring[0, :2]) @ richtung - s_min
        if ziel.startswith("blech"):
            return np.c_[s / fs.BLECH_M, (z_boden + fs.BLECH_M - P[:, 2]) / fs.BLECH_M]
        return np.c_[s / achse / fs.ACHSEN, (z_boden + fs.PUTZ_H - P[:, 2]) / fs.PUTZ_H]

    aussen_n = eg.newell(ring)
    out = []
    for tri in eg.trianguliere(ring, innen):
        if np.linalg.norm(np.cross(tri[1] - tri[0], tri[2] - tri[0])) < 1e-6:
            continue
        if np.cross(tri[1] - tri[0], tri[2] - tri[0]) @ aussen_n < 0:
            tri = tri[::-1]
        schurz, ueber = eg.teile_bei_z(tri, z_boden)
        teile = [(t, ziel_unten if ziel_unten.startswith("blech") else "putz", True) for t in schurz]
        for t in ueber:
            teile += [(t, ziel_oben, False)] if z_teil is None else \
                [(u, z, False) for us, z in zip(eg.teile_bei_z(t, z_teil), (ziel_unten, ziel_oben)) for u in us]
        for t, ziel, unter_boden in teile:
            kante = max(np.linalg.norm(t[k] - t[k - 1]) for k in range(3))
            if np.linalg.norm(np.cross(t[1] - t[0], t[2] - t[0])) / kante < 0.01:
                continue
            uv = uv_von(t, ziel)
            if unter_boden:
                uv[:, 1] = 0.999
            out.append((t, uv, ziel))
    return out


def anheben(fl, boden_hoehen, info, gel):
    """Gebäude, deren LoD2-Boden unter dem Condor-Gelände liegt (Senken, die das 22,5-m-Raster glättet), so weit
    anheben, dass der Boden an der tiefsten Grundrissecke auf dem Gelände steht."""
    hub = {}
    for gid in {f[3] for f in fl}:
        xy = np.vstack([np.array(p.exterior.coords) for p in shapely.get_parts(info[gid]["grundriss"])])
        d = float(gel(xy[:, 0], xy[:, 1]).min()) - float(boden_hoehen[gid].min())
        hub[gid] = max(0.0, d)
    neu = [(a, r + [0, 0, hub[g]], [i + [0, 0, hub[g]] for i in innen], g) for a, r, innen, g in fl]
    boden = {g: boden_hoehen[g] + hub[g] for g in hub}
    return neu, boden, {g: h for g, h in hub.items() if h > 0}


def patch_von(p):
    return int((nk.E0 - p.x) // nk.PATCH), int((p.y - nk.N0) // nk.PATCH)


def main():
    os.makedirs(ZIEL, exist_ok=True)
    flugplatz = [Polygon(utm(e["geometry"])) for e in osm_elemente("edaz_aeroway.json")
                 if e.get("tags", {}).get("aeroway") == "aerodrome" and ist_geschlossen(e["geometry"])][0].buffer(eg.PUFFER)
    gebiet = box(nk.E_LINKS, nk.N0, nk.E0, nk.N_OBEN)  # ganze Landschaft, Siedlungen am Rand enden dort
    flaechen, boden_hoehen, info = eg.lies_gebaeude(gebiet, nk.LGB_ORDNER)
    doerfer = waehle_doerfer(info, flugplatz)
    doerfer.update(weitere_orte(info, flugplatz, doerfer))
    print(f"{len(info)} LoD2-Gebäude, {len(doerfer)} Siedlungen mit {sum(map(len, doerfer.values()))} Gebäuden")
    daten, umrechnung = bb_textur.farbumrechnung()
    patch = {g: patch_von(info[g]["zentrum"]) for ids in doerfer.values() for g in ids}
    PATCHES = sorted(set(patch.values()))
    gel = gelaende_hoehe(*lade_raster(PATCHES))
    # je Patch: Liste von (objektname, textur, dreiecke, uv)
    teile = {p: [] for p in PATCHES}
    zaehler = Counter()
    for dorf, ids in doerfer.items():
        ids = set(ids)
        fl, boden, hub = anheben([f for f in flaechen if f[3] in ids], boden_hoehen, info, gel)
        print(f"  angehoben: {len(hub)} Gebäude, max {max(hub.values(), default=0):.2f} m")
        typ = {g: dorftyp(info[g]) for g in ids}
        stall = {g for g in ids if ist_gefluegelstall(dorf, info[g])}
        print(f"{dorf}: {len(ids)} Gebäude, {dict(Counter(typ.values()))}, "
              f"Patches {dict(Counter(patch[g] for g in ids))}")
        dach, w0, n0, breite = dachbild(fl, daten, umrechnung)
        dach_tex = f"{PREFIX}_{dorf}_Daecher.dds"
        schreibe_dds(dach, os.path.join(ZIEL, dach_tex))
        print(f"  Dachtextur {len(dach)} px, {breite / len(dach):.2f} m/px")
        sammel = {p: {"dach": [], **{w: [] for w in WAND}} for p in PATCHES}
        luefter_ringe, u_ursprung = set(), {}
        grund_gruppe = shapely.unary_union([info[g]["grundriss"] for g in ids])
        for g in stall:
            # Lüfter: Südgiebel-Stücke, die bis über FIRST_MIN reichen (die flachen Verbindungsbauten bleiben ohne)
            for art, ring, innen, gg in fl:
                if gg != g or art != "WallSurface" or giebel_von(ring, info[g], boden, g) != "sued":
                    continue
                if ring[:, 2].max() - boden[g].min() >= FIRST_MIN:
                    luefter_ringe.add(id(ring)); zaehler["luefter"] += 1
            for seite, mitte, aussen, breite_g, ringe in stallgiebel([f for f in fl if f[3] == g], info[g], boden, g):
                for r in ringe:  # Giebelstücke teilen den u-Ursprung, damit Lüfter an der Teilungsfuge durchlaufen
                    u_ursprung[r] = mitte
                if seite == "nord" and GIEBEL_BREITE[0] <= breite_g <= GIEBEL_BREITE[1]:
                    neu = silos(mitte, aussen, gel)
                    fuss = shapely.MultiPoint([t[k, :2] for t, _ in neu for k in range(3)]).convex_hull
                    if fuss.intersects(grund_gruppe):
                        zaehler["silos_verworfen"] += 1
                        continue
                    sammel[patch[g]]["silo"] += neu; zaehler["silogruppen"] += 1
        for art, ring, innen, gid in fl:
            ziel = sammel[patch[gid]]
            if art == "RoofSurface":
                n = eg.newell(ring)
                if n[2] < 0:  # Dächer zeigen immer nach oben (einzelne LoD2-Ringe sind falsch herum)
                    n = -n
                for tri in eg.trianguliere(ring, innen):
                    if np.linalg.norm(np.cross(tri[1] - tri[0], tri[2] - tri[0])) < 1e-6:
                        continue
                    if np.cross(tri[1] - tri[0], tri[2] - tri[0]) @ n < 0:
                        tri = tri[::-1]
                    ziel["dach"].append((tri, np.c_[(tri[:, 0] - w0) / breite, (n0 - tri[:, 1]) / breite]))
            elif art == "WallSurface":
                blech = "blech_luefter" if id(ring) in luefter_ringe else \
                    "blech_stall" if typ[gid] == "halle_stall" else "blech_gewerbe"
                for t, uv, w in waende(ring, innen, gid, typ[gid], boden, gel, info[gid]["grundriss"], zaehler, blech,
                                       u_ursprung.get(id(ring))):
                    ziel[w].append((t, uv))
        for p in PATCHES:
            s = sammel[p]
            if s["dach"]:
                teile[p].append((f"Daecher_{dorf}", dach_tex, [t for t, _ in s["dach"]], [u for _, u in s["dach"]]))
            for w, (obj, tex) in WAND.items():
                if s[w]:
                    teile[p].append((f"{obj}_{dorf}", tex, [t for t, _ in s[w]], [u for _, u in s[w]]))
    print("Wände umgedreht:", zaehler["umgedreht"], "| Lüftergiebel:", zaehler["luefter"], "| Silogruppen:",
          zaehler["silogruppen"], "| verworfen:", zaehler["silos_verworfen"])
    texturen = fs.alle()
    for w, (_, tex) in WAND.items():
        schreibe_dds(texturen[w], os.path.join(ZIEL, tex))
    alt = os.path.join(ZIEL, f"{PREFIX}_Blech.dds")  # frühere einheitliche Hallentextur
    if os.path.exists(alt):
        os.remove(alt)
    for p in PATCHES:
        if teile[p]:
            pfad = autogen.schreibe(*p, teile[p])
            print(pfad, ", ".join(f"{o} {len(t)}" for o, _, t, _ in teile[p]), "Dreiecke")


if __name__ == "__main__":
    main()
