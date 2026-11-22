"""Baut die Gebäude des Flugplatzes EDAZ aus LoD2 (LGB) als Objektdatei SchoenhagenO.c3d.

- Geometrie: Dach- und Wandflächen aus CityGML (3D, UTM33, Höhen DHHN2016 wie DGM1).
- Dachtextur: senkrechte Projektion des DOP20-Luftbilds (0,4 m/px) -> echte Dächer.
- Wände je Gebäudetyp (aus ALKIS-Funktion, Dachform, Grundfläche, siehe gebaeudetyp): Hallen Trapezblech mit Toren
  an Wänden zum Vorfeld/Rollweg, sonst Putz mit Fensterreihen bis unter die Traufe, Nebengebäude glatter Putz.
  Texturen prozedural aus fassaden.py.
- Wände reichen 1,5 m unter das Gelände, damit kein Spalt zum 22,5-m-Gelände entsteht.
- Koordinaten wie die G-Datei: Ursprung Flugplatzpunkt, y in Pistenrichtung, x nach Richtung - 90°, z über Flugplatzhöhe.
- Dreiecke so orientiert, dass das Kreuzprodukt (v1-v0)x(v2-v0) nach außen zeigt (wie alle Original-Objekte).
"""
import glob
import json
import os
import re
import zipfile

import cv2
import numpy as np
import rasterio
import shapely
from lxml import etree
from PIL import Image
from rasterio.enums import Resampling
from rasterio.merge import merge
from shapely.geometry import Polygon

import c3d
import fassaden as fs
from dds_dxt1 import schreibe_dds
from edaz_flaechen import ARBEIT, NAME, OSM, T, lies_apt, osm_elemente, utm, ist_geschlossen

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LGB = os.path.join(PROJ, "Daten", "LGB")
from config import LAND
NS = {"gml": "http://www.opengis.net/gml", "bldg": "http://www.opengis.net/citygml/building/1.0"}
DACH_PX, DACH_RES = 4096, 0.4
SCHURZ = 1.5
PUFFER = 60.0  # Gebäude bis 60 m außerhalb des Flugplatzumrisses mitnehmen
# Hallentore: Wand ab Boden, mindestens so lang/hoch, und vor der Wandmitte liegt in einem dieser Abstände Vorfeld/Rollweg
TOR_MIN_L, TOR_MIN_TRAUF = 6.0, 4.0
TOR_ABSTAENDE = (4.0, 10.0, 20.0, 30.0, 40.0)
TOR_ROLLWEG_B = 10.0  # angenommene Breite der Rollwege (OSM-Linien)
# (Objektname in der .c3d, Wandart, Texturdatei Schoenhagen_<..>.dds)
WAND_OBJEKTE = (("Waende", "putz", "Waende"), ("Fassaden", "fassade", "Fassade"),
                ("Hallen", "blech", "Blech"), ("Tore", "tore", "Tore"))


def lies_gebaeude(gebiet, ordner=None):
    """Liefert (flaechen, boden, info): flaechen = Liste von (art, aussenring[N,3], [innenringe], gebaeude_id),
    boden = {gebaeude_id: Bodenhöhen aller GroundSurfaces}, info = {gebaeude_id: dict(funktion, dachformen, flaeche,
    grundriss)}. Nur Gebäude, deren Grundriss-Schwerpunkt im Gebiet liegt. ordner: LGB-Ordner mit lod2/*.zip (Standard LGB);
    liegt eine Kachel in mehreren, zählt der erste."""
    flaechen, boden_hoehen, info = [], {}, {}
    w, s, e, n = gebiet.bounds
    zips = {}
    for o in ordner or [LGB]:
        for z in sorted(glob.glob(os.path.join(o, "lod2", "*.zip"))):
            zips.setdefault(os.path.basename(z), z)
    for z in sorted(zips.values()):
        ke, kn = map(int, re.findall(r"_33(\d+)-(\d+)", z)[0])
        if ke * 1000 > e or (ke + 1) * 1000 < w or kn * 1000 > n or (kn + 1) * 1000 < s:
            continue
        with zipfile.ZipFile(z) as zf:
            gml = [x for x in zf.namelist() if x.endswith(".gml")][0]
            baum = etree.fromstring(zf.read(gml))
        for geb in baum.iter("{%s}Building" % NS["bldg"]):
            gid = geb.get("{%s}id" % NS["gml"])
            boden = [np.array(p.text.split(), float).reshape(-1, 3)
                     for g in geb.iter("{%s}GroundSurface" % NS["bldg"]) for p in g.iter("{%s}posList" % NS["gml"])]
            if not boden or not gebiet.intersects(Polygon(boden[0][:, :2]).centroid):
                continue
            boden_hoehen[gid] = np.unique(np.round(np.concatenate([b[:, 2] for b in boden]), 2))
            fn = geb.find("bldg:function", NS)
            grundriss = shapely.unary_union([shapely.make_valid(Polygon(b[:, :2])) for b in boden])
            info[gid] = dict(funktion=fn.text.split("_")[-1] if fn is not None else "",
                             dachformen=[r.text for r in geb.iter("{%s}roofType" % NS["bldg"])],
                             flaeche=grundriss.area, grundriss=grundriss,
                             zentrum=Polygon(boden[0][:, :2]).centroid)  # wie der Gebietstest oben
            for art in ("RoofSurface", "WallSurface"):
                for f in geb.iter("{%s}%s" % (NS["bldg"], art)):
                    for poly in f.iter("{%s}Polygon" % NS["gml"]):
                        ring = lambda el: np.array(el.text.split(), float).reshape(-1, 3)
                        aussen = ring(poly.find("gml:exterior//gml:posList", NS))
                        innen = [ring(p) for p in poly.findall("gml:interior//gml:posList", NS)]
                        flaechen.append((art, aussen, innen, gid))
    return flaechen, boden_hoehen, info


# ALKIS-Gebäudefunktion (bldg:function 31001_xxxx) -> Fassadentyp
HALLE_FKT = {"2431"}  # Flugzeughalle
BETRIEB_FLUG = "2430"  # Betriebsgebäude Flugverkehr: Halle, wenn groß und ohne Walmdach (Walmdach = Verwaltungsbau)
NEBEN_FKT = {"2460", "2461", "2462", "2463", "2465", "2512", "2720", "2721", "2723", "2724", "2729", "9998"}
WALMDACH = "3200"


def gebaeudetyp(i):
    """'halle' (Trapezblech, Tore), 'fassade' (Putz mit Fenstern) oder 'neben' (Putz ohne Fenster)."""
    if i["funktion"] in HALLE_FKT:
        return "halle"
    if i["funktion"] == BETRIEB_FLUG and i["flaeche"] >= 500 and WALMDACH not in i["dachformen"]:
        return "halle"
    if i["funktion"] in NEBEN_FKT and i["flaeche"] < 100:
        return "neben"
    return "fassade"


def teile_bei_z(tri, z0):
    """Dreieck an der waagerechten Ebene z = z0 teilen -> (unten, oben) als Dreieckslisten, Umlaufsinn bleibt
    erhalten (Sutherland-Hodgman; Punkte genau auf der Ebene gehören zu beiden Seiten)."""
    unten, oben = [], []
    for k in range(3):
        a, b = tri[k], tri[(k + 1) % 3]
        if a[2] <= z0:
            unten.append(a)
        if a[2] >= z0:
            oben.append(a)
        if (a[2] - z0) * (b[2] - z0) < 0:
            p = a + (z0 - a[2]) / (b[2] - a[2]) * (b - a)
            unten.append(p); oben.append(p)
    facher = lambda poly: [np.array([poly[0], poly[i], poly[i + 1]]) for i in range(1, len(poly) - 1)]
    return facher(unten), facher(oben)


def bewegungsflaeche():
    """Vorfelder und Rollwege (OSM) als Fläche; dient nur zur Wahl der Hallenwände mit Tor."""
    teile = []
    for e in osm_elemente("edaz_aeroway.json"):
        art, geom = e.get("tags", {}).get("aeroway"), e.get("geometry")
        if not geom:
            continue
        if art == "apron" and ist_geschlossen(geom):
            teile.append(Polygon(utm(geom)))
        elif art in ("taxiway", "taxilane"):
            teile.append(shapely.LineString(utm(geom)).buffer(TOR_ROLLWEG_B / 2))
    return shapely.unary_union(teile)


def newell(ring):
    """Flächennormale eines (auch nicht ganz ebenen) Polygons; CityGML-Außenringe laufen von außen gesehen gegen den
    Uhrzeigersinn, die Normale zeigt also nach außen (geprüft: 139/139 Dächer nach oben, 349/354 Außenwände nach außen)."""
    a, b = ring, np.roll(ring, -1, 0)
    return np.array([((a[:, 1] - b[:, 1]) * (a[:, 2] + b[:, 2])).sum(),
                     ((a[:, 2] - b[:, 2]) * (a[:, 0] + b[:, 0])).sum(),
                     ((a[:, 0] - b[:, 0]) * (a[:, 1] + b[:, 1])).sum()])


def trianguliere(ring, innen=()):
    """Ebenes 3D-Polygon (mit Löchern) -> Dreiecke (Liste von 3x3-Arrays), über Projektion auf die Polygonebene."""
    p = ring[:-1] if np.allclose(ring[0], ring[-1]) else ring
    if len(p) < 3:
        return []
    m = p.mean(0)
    _, _, vt = np.linalg.svd(p - m)
    u, v = vt[0], vt[1]
    proj = lambda r: np.c_[(r - m) @ u, (r - m) @ v]
    poly = Polygon(proj(p), [proj(r) for r in innen])
    if not poly.is_valid:
        poly = shapely.make_valid(poly)
    out = []
    for teil in shapely.get_parts(poly):
        if teil.geom_type != "Polygon" or teil.area < 0.05:
            continue
        for tri in shapely.get_parts(shapely.constrained_delaunay_triangles(teil)):
            k = np.array(tri.exterior.coords)[:3]
            out.append(m + k[:, :1] * u + k[:, 1:2] * v)
    return out


def lokal_richtung(n, cs, sn):
    """Richtungsvektor (UTM) in den gespiegelten lokalen Flugplatzrahmen drehen (ohne Verschiebung)."""
    return np.array([-cs * n[0] + sn * n[1], sn * n[0] + cs * n[1], n[2]])


def main():
    o_apt, lat, lon, alt, d = lies_apt()
    Ec, Nc = T.transform(lon, lat)
    cs, sn = np.cos(np.radians(d)), np.sin(np.radians(d))
    lokal = lambda P: np.c_[-cs * (P[:, 0] - Ec) + sn * (P[:, 1] - Nc), sn * (P[:, 0] - Ec) + cs * (P[:, 1] - Nc), P[:, 2] - alt]

    flugplatz = [Polygon(utm(e["geometry"])) for e in osm_elemente("edaz_aeroway.json")
                 if e.get("tags", {}).get("aeroway") == "aerodrome" and ist_geschlossen(e["geometry"])][0]
    gebiet = flugplatz.buffer(PUFFER)
    flaechen, boden_hoehen, info = lies_gebaeude(gebiet)
    ids = {f[3] for f in flaechen}
    print(f"{len(ids)} Gebäude, {len(flaechen)} Flächen")

    # Dach-Luftbild über alle Gebäude
    alle = np.vstack([f[1] for f in flaechen])
    w0, n0 = alle[:, 0].min() - 20, alle[:, 1].max() + 20
    groesse = max(alle[:, 0].max() - w0, n0 - alle[:, 1].min()) + 20
    res = max(DACH_RES, groesse / DACH_PX)
    quellen = [rasterio.open(f) for f in glob.glob(os.path.join(LGB, "dop_jpg", "*.jpg"))]
    quellen = [q for q in quellen if q.bounds.right > w0 and q.bounds.left < w0 + groesse and q.bounds.top > n0 - groesse and q.bounds.bottom < n0]
    arr, _ = merge(quellen, bounds=(w0, n0 - DACH_PX * res, w0 + DACH_PX * res, n0), res=res, resampling=Resampling.average)
    dach = np.ascontiguousarray(np.transpose(arr[:3], (1, 2, 0))[:DACH_PX, :DACH_PX])
    dach = cv2.inpaint(dach, (dach.sum(2) == 0).astype(np.uint8), 2, cv2.INPAINT_TELEA)
    print(f"Dachtextur: {DACH_PX} px, {res:.2f} m/px, {DACH_PX * res:.0f} m")

    typ = {gid: gebaeudetyp(i) for gid, i in info.items()}
    alle_grundrisse = shapely.unary_union([i["grundriss"] for i in info.values()])
    bewegung = bewegungsflaeche()
    from collections import Counter
    print("Gebäudetypen:", dict(Counter(typ.values())))

    v_dach = []
    wand_tris = {k: [] for k in ("putz", "fassade", "blech", "tore")}
    tor_hallen, tor_waende = set(), 0
    for art, ring, innen, gid in flaechen:
        aussen_n = lokal_richtung(newell(ring), cs, sn)  # Außenrichtung im lokalen Rahmen
        if art == "WallSurface":
            ring = ring.copy()
            # Nur Punkte auf Bodenhöhe (aus den GroundSurfaces) in den Boden verlängern; Wände, die auf einem Dach
            # beginnen, bleiben unverändert (sonst überdecken sie die Wand darunter).
            am_boden = np.abs(ring[:, 2][:, None] - boden_hoehen[gid][None, :]).min(1) < 0.1
            z_boden = ring[am_boden, 2].min() if am_boden.any() else boden_hoehen[gid].min()  # v immer ab Gebäudeboden
            trauf = ring[~am_boden, 2].min() - z_boden if am_boden.any() and (~am_boden).any() else 0.0
            ring[am_boden, 2] -= SCHURZ
            # Texturkoordinaten einmal je Wand: u entlang der Wand, v ab Boden (Sockel unten)
            nh = newell(ring)[:2]
            richtung = np.array([-nh[1], nh[0]]) / (np.linalg.norm(nh) + 1e-9)
            s = (ring[:, :2] - ring[0, :2]) @ richtung
            s_min, laenge = s.min(), s.max() - s.min()
            ziel_unten, ziel_oben, z_teil = ("blech", "blech", None) if typ[gid] == "halle" else ("putz", "putz", None)
            if typ[gid] == "halle" and laenge >= TOR_MIN_L and trauf >= TOR_MIN_TRAUF:
                # Tor, wenn vor der Wandmitte Vorfeld/Rollweg liegt und nicht direkt ein anderes Gebäude
                mitte = ring[0, :2] + richtung * (s_min + laenge / 2)
                aussen = nh / (np.linalg.norm(nh) + 1e-9)
                vor = lambda d: shapely.Point(*(mitte + aussen * d))
                if not alle_grundrisse.contains(vor(2.0)) and any(bewegung.contains(vor(d)) for d in TOR_ABSTAENDE):
                    tor_h = min(np.clip(0.75 * trauf, 3.5, 7.0), trauf - 0.8)
                    ziel_unten, z_teil = "tore", z_boden + tor_h
                    tor_hallen.add(gid); tor_waende += 1
            elif typ[gid] == "fassade" and trauf > 0 and laenge >= 2.0:  # kürzere Wandstücke: kein gequetschtes Fenster
                reihen = int((trauf - fs.FENSTER[1] - 0.2) // fs.GESCHOSS) + 1  # ganze Fensterreihen unter der Traufe
                if reihen >= 1:
                    ziel_unten, z_teil = "fassade", z_boden + min(reihen * fs.GESCHOSS, trauf)
            achsen = max(1, round(laenge / (fs.FLUEGEL_M if ziel_unten == "tore" else fs.ACHSE_M)))
            def uv_von(P, ziel, s_min=s_min, z_boden=z_boden, achse=laenge / achsen, z_teil=z_teil, richtung=richtung, r0=ring[0, :2]):
                s = (P[:, :2] - r0) @ richtung - s_min
                if ziel == "blech":
                    return np.c_[s / fs.BLECH_M, (z_boden + fs.BLECH_M - P[:, 2]) / fs.BLECH_M]
                if ziel == "tore":  # v 0 = Torsturz, 1 = Boden; ganze Flügel über die Wandlänge
                    return np.c_[s / achse / fs.ACHSEN, (z_teil - P[:, 2]) / (z_teil - z_boden)]
                # Putz und Fassade: gleiche UV, ganze Fensterachsen über die Wandlänge
                return np.c_[s / achse / fs.ACHSEN, (z_boden + fs.PUTZ_H - P[:, 2]) / fs.PUTZ_H]
        for tri in trianguliere(ring, innen):
            if np.linalg.norm(np.cross(tri[1] - tri[0], tri[2] - tri[0])) < 1e-6:
                continue
            L = lokal(tri)
            nl = np.cross(L[1] - L[0], L[2] - L[0])
            if nl @ aussen_n < 0:
                L = L[::-1]; tri = tri[::-1]
            if art == "RoofSurface":
                uv = np.c_[(tri[:, 0] - w0) / (DACH_PX * res), (n0 - tri[:, 1]) / (DACH_PX * res)]
                v_dach.append((L, uv))
                continue
            # Schürze unter dem Boden abtrennen: dort v fest auf die unterste Texturzeile (Sockel), sonst wiederholt
            # sich der obere Kachelrand (Torschiene, Fenster) direkt unter der Bodenlinie.
            schurz, ueber = teile_bei_z(tri, z_boden)
            teile = [(t, "blech" if ziel_unten == "tore" else ziel_unten if ziel_unten != "fassade" else "putz", True) for t in schurz]
            for t in ueber:
                teile += [(t, ziel_oben, False)] if z_teil is None else \
                    [(u, z, False) for us, z in zip(teile_bei_z(t, z_teil), (ziel_unten, ziel_oben)) for u in us]
            for t, ziel, unter_boden in teile:
                kante = max(np.linalg.norm(t[k] - t[k - 1]) for k in range(3))
                if np.linalg.norm(np.cross(t[1] - t[0], t[2] - t[0])) / kante < 0.01:
                    continue  # Splitter aus dem Schnitt (< 1 cm breit): Normale in float32 ungenau, unsichtbar
                uv = uv_von(t, ziel)
                if unter_boden:
                    uv[:, 1] = 0.999
                wand_tris[ziel].append((lokal(t), uv))
            if art == "WallSurface" and tri[:, 2].max() - z_boden > (fs.BLECH_M if typ[gid] == "halle" else fs.PUTZ_H):
                print(f"WARNUNG: Wand von {gid[-6:]} höher als die Texturkachel, Sockel wiederholt sich oben")
    hallen = [g for g in typ if typ[g] == "halle"]
    print(f"Tore: {tor_waende} Wände an {len(tor_hallen)} von {len(hallen)} Hallen; ohne Tor: {sorted(g[-6:] for g in set(hallen) - tor_hallen)}")

    def zu_vertices(liste):
        V = []
        for L, uv in liste:
            nrm = np.cross(L[1] - L[0], L[2] - L[0]); nrm /= np.linalg.norm(nrm)
            for k in range(3):
                V.append([*L[k], *nrm, *uv[k]])
        return np.array(V, np.float32)

    vd = zu_vertices(v_dach)
    # Windsack aus der bisherigen O-Datei übernehmen
    sicherung = sorted(glob.glob(os.path.join(PROJ, "Backup", "EG3_vor_EDAZ_*")))[0]
    _, alt_obs, alt_v, alt_i = c3d.lies(os.path.join(sicherung, "Airports", f"{NAME}O.c3d"))
    obs, verts, idx = [], [], []
    mat = (1, 1, 1, 1, 0.0, 0.1)
    teile = [("Daecher", vd, f"Textures/{NAME}_Daecher.dds")]
    teile += [(obj, zu_vertices(wand_tris[ziel]), f"Textures/{NAME}_{datei}.dds") for obj, ziel, datei in WAND_OBJEKTE if wand_tris[ziel]]
    for name, V, tex in teile:
        obs.append(dict(name=name, vstart=sum(len(x) for x in verts), vanz=len(V), istart=sum(len(x) for x in idx),
                        ianz=len(V), textur=tex, material=mat, rest=0))
        idx.append(np.arange(len(V), dtype=np.uint32) + sum(len(x) for x in verts)); verts.append(V)
    for o in alt_obs:
        vs = sum(len(x) for x in verts); is_ = sum(len(x) for x in idx)
        verts.append(alt_v[o["vstart"]:o["vstart"] + o["vanz"]])
        idx.append(alt_i[o["istart"]:o["istart"] + o["ianz"]] - o["vstart"] + vs)
        obs.append(dict(o, vstart=vs, istart=is_))
    ziel = os.path.join(ARBEIT, "EDAZ")
    c3d.schreibe(os.path.join(ziel, f"{NAME}O.c3d"), obs, np.vstack(verts), np.concatenate(idx))
    schreibe_dds(dach, os.path.join(ziel, f"{NAME}_Daecher.dds"))
    texturen = fs.alle(fs.PUTZ_FLUGPLATZ)
    for _, ziel_art, datei in WAND_OBJEKTE:
        schreibe_dds(texturen[ziel_art], os.path.join(ziel, f"{NAME}_{datei}.dds"))
    print(f"Dächer {len(vd) // 3} Dreiecke, Wände " + ", ".join(f"{k} {len(v)}" for k, v in wand_tris.items())
          + f" Dreiecke, z {np.vstack(verts)[:, 2].min():.1f}..{np.vstack(verts)[:, 2].max():.1f} m")
    # Kontrolle: Draufsicht der Dächer
    k = Image.fromarray(dach).resize((2048, 2048))
    from PIL import ImageDraw
    dr = ImageDraw.Draw(k)
    for L, uv in v_dach:
        dr.polygon([(a * 2048, b * 2048) for a, b in uv], outline=(255, 0, 0))
    k.save(os.path.join(ziel, "kontrolle_daecher.png"))


if __name__ == "__main__":
    main()
