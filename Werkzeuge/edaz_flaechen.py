"""Baut die Flächendatei (G-Datei) für EDAZ Schönhagen: Asphalt und Grass3D, exakt auf das 22,5-m-Gelände gelegt,
plus die Unter-Textur (Luftbild + Alpha für die Grashöhe).

Grundlagen (alle durch Vergleich mit vorhandenen Dateien ermittelt, siehe PROJEKT.md):
- G-Datei-Koordinaten: Ursprung = Flugplatzpunkt aus der .apt, +y zeigt in Pistenrichtung d (Gitter-Nord),
  +x zeigt nach d-90°, z = Höhe über der Flugplatzhöhe aus der .apt.
- Gelände: 22,5-m-Raster, Zelle (i, j) mit (i+j) gerade -> Diagonale (i,j)-(i+1,j+1), sonst (i+1,j)-(i,j+1).
"""
import json
import os
import struct

import cv2
import numpy as np
import shapely
from PIL import Image
from pyproj import Transformer
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

import c3d
import gelaende as g

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from config import LAND
OSM = os.path.join(PROJ, "Daten", "OSM")
ARBEIT = os.path.join(PROJ, "Daten", "Arbeit")
NAME = "Schoenhagen"
Z_OFFSET = 0.05  # Flächen knapp über dem Gelände, gegen Flimmern
PATCHES = [(40, 39), (39, 39)]  # west nach ost
GRID_W, GRID_N0 = 369000.0, 5782760.0  # Südwestecke von Patch 40/39
ZELLE = 22.5
SUB_PX, SUB_M = 4096, 2560.0  # Unter-Textur: 4096 px auf 2560 m = 0,625 m/px

T = Transformer.from_crs(4326, 32633, always_xy=True)


# ---------- Flugplatzeintrag ----------
def lies_apt():
    a = open(os.path.join(LAND, "EastGermany3.apt"), "rb").read()
    for o in range(0, len(a), 72):
        n = a[o]
        if a[o + 1:o + 1 + n].decode("latin1") == NAME:
            lat, lon, alt = struct.unpack_from("<3f", a, o + 36)
            richtung = struct.unpack_from("<I", a, o + 48)[0] % 100000 / 100.0
            return o, lat, lon, alt, richtung
    raise SystemExit("Flugplatz nicht gefunden")


# ---------- Gelände ----------
def lade_raster():
    nx = 256 * len(PATCHES)
    H = np.zeros((257, nx + 1))
    for k, (c, r) in enumerate(PATCHES):
        _, v, _ = g.lies_obj(os.path.join(g.WORK, "Modified", f"h{c:03d}{r:03d}.obj"))
        i = np.rint((v[:, 0] + 2880) / ZELLE).astype(int) + 256 * k
        j = np.rint((v[:, 1] + 2880) / ZELLE).astype(int)
        H[j, i] = v[:, 2]
    return H


def gelaende_dreiecke(H, gebiet):
    """Alle Gelände-Dreiecke (UTM, mit Höhe), die das Gebiet berühren."""
    w, s, e, n = gebiet.bounds
    i0, i1 = int((w - GRID_W) // ZELLE), int((e - GRID_W) // ZELLE) + 1
    j0, j1 = int((s - GRID_N0) // ZELLE), int((n - GRID_N0) // ZELLE) + 1
    out = []
    for j in range(max(j0, 0), min(j1, 256)):
        for i in range(max(i0, 0), min(i1, H.shape[1] - 1)):
            P = lambda a, b: (GRID_W + (i + a) * ZELLE, GRID_N0 + (j + b) * ZELLE, H[j + b, i + a])
            p00, p10, p11, p01 = P(0, 0), P(1, 0), P(1, 1), P(0, 1)
            if (i + j) % 2 == 0:
                out += [(p00, p10, p11), (p00, p11, p01)]
            else:
                out += [(p00, p10, p01), (p10, p11, p01)]
    return out


def ebene(tri):
    """Koeffizienten z = a*E + b*N + c der Dreiecksebene."""
    A = np.array([[p[0], p[1], 1.0] for p in tri])
    return np.linalg.solve(A, np.array([p[2] for p in tri]))


# ---------- Flächen aus OSM + Luftbild ----------
def osm_elemente(datei):
    return json.load(open(os.path.join(OSM, datei), encoding="utf-8"))["elements"]


def utm(geom):
    return [T.transform(q["lon"], q["lat"]) for q in geom]


def ist_geschlossen(geom):
    return geom[0]["lat"] == geom[-1]["lat"] and geom[0]["lon"] == geom[-1]["lon"] and len(geom) > 3


def breite_aus_luftbild(linie, sat, res=5760 / 8192):
    """Breite des grauen (befestigten) Streifens quer zur Linie, Median über viele Querprofile."""
    breiten = []
    for s in np.arange(5, linie.length - 5, 8.0):
        p = linie.interpolate(s)
        q = linie.interpolate(min(s + 1, linie.length))
        t = np.array([q.x - p.x, q.y - p.y]); t /= np.linalg.norm(t) + 1e-9
        nrm = np.array([-t[1], t[0]])
        d = np.arange(-30, 30.01, 0.5)
        x = p.x + d * nrm[0]; y = p.y + d * nrm[1]
        c = ((x - GRID_W) / res).astype(int); r = ((GRID_N0 + 5760 - y) / res).astype(int)
        grau = sat[np.clip(r, 0, sat.shape[0] - 1), np.clip(c, 0, sat.shape[1] - 1)] < 42
        mitte = len(d) // 2
        if not grau[mitte - 1:mitte + 2].any():
            continue  # Markierung/Schatten oder kein Belag: Profil auslassen
        l = mitte
        while l > 0 and grau[l - 1]:
            l -= 1
        rr = mitte
        while rr < len(d) - 1 and grau[rr + 1]:
            rr += 1
        breiten.append((rr - l + 1) * 0.5)
    return float(np.median(breiten)) if breiten else 0.0


def baue_flaechen():
    mosaik = np.load(os.path.join(ARBEIT, "mosaik.npy"))
    assert mosaik.shape[:2] == (8192, 8192 * len(PATCHES)), f"mosaik.npy hat falsche Größe {mosaik.shape}"
    sat = cv2.cvtColor(mosaik, cv2.COLOR_RGB2HSV)[..., 1]
    asphalt, gebaeude, protokoll = [], [], []
    flugplatz = None
    gras_pisten = []
    for e in osm_elemente("edaz_aeroway.json"):
        t = e.get("tags", {}); art = t.get("aeroway"); geom = e.get("geometry")
        if not geom:
            continue
        p = utm(geom)
        if art == "aerodrome" and ist_geschlossen(geom):
            flugplatz = Polygon(p)
        elif art == "apron" and ist_geschlossen(geom):
            asphalt.append(Polygon(p))
            protokoll.append(f"Vorfeld {t.get('ref', '')}: {Polygon(p).area:.0f} m²")
        elif art in ("hangar", "terminal") and ist_geschlossen(geom):
            gebaeude.append(Polygon(p))
        elif art in ("runway", "taxiway", "taxilane"):
            linie = LineString(p)
            if t.get("surface") == "grass":
                gras_pisten.append(linie)
                continue
            b = breite_aus_luftbild(linie, sat)
            if art == "runway" and t.get("width"):
                b = float(t["width"])  # Piste: Breite aus OSM (gemessen wäre durch Markierungen verfälscht)
            elif art == "taxilane":
                b = 8.0  # Rollgassen liegen auf den Vorfeldern, Breite spielt kaum eine Rolle
            elif art == "runway":
                raise SystemExit(f"Piste {t.get('ref')} ohne width-Tag in OSM")
            elif b > 18:
                b = 12.0  # Rollweg neben Vorfeld: Messung erfasst das Vorfeld mit, typische Breite annehmen
            protokoll.append(f"{art} {t.get('ref') or '-'}: {linie.length:.0f} m, Breite {b:.1f} m")
            if b < 4:
                print(f"WARNUNG: {art} {t.get('ref') or '-'} ({linie.length:.0f} m) nicht als Asphalt erkannt, ausgelassen")
            if b >= 4:
                asphalt.append(linie.buffer(b / 2, cap_style="flat", join_style="round"))
    for e in osm_elemente("edaz_bauten.json"):
        geom = e.get("geometry")
        if geom and "building" in e.get("tags", {}) and ist_geschlossen(geom):
            gebaeude.append(Polygon(utm(geom)))
    # Ränder der gepufferten Rollwege schließen, kleine Lücken zwischen Rollweg und Vorfeld füllen
    asphalt = unary_union(asphalt).buffer(1.0).buffer(-1.0).simplify(0.3)
    gebaeude = unary_union(gebaeude).buffer(3.0)
    gras = flugplatz.difference(asphalt).difference(gebaeude)
    gras = shapely.make_valid(gras)
    asphalt = asphalt.intersection(flugplatz.buffer(50))
    return flugplatz, asphalt, gras, unary_union(gras_pisten), protokoll


# ---------- Netz erzeugen ----------
def vernetze(flaeche, dreiecke, baum, zu_lokal, uv, alt):
    verts, idx = [], []
    for k in baum.query(flaeche):
        tri = dreiecke[k]
        poly = Polygon([(p[0], p[1]) for p in tri])
        teil = flaeche.intersection(poly)
        if teil.is_empty or teil.area < 1e-4:
            continue
        a, b, c = ebene(tri)
        if teil.area >= poly.area - 1e-6:
            stuecke = [poly]
        else:
            flaechig = [q for q in shapely.get_parts(teil) if q.geom_type == "Polygon" and q.area > 1e-4]
            stuecke = [s for q in flaechig for s in shapely.get_parts(shapely.constrained_delaunay_triangles(q))]
        for stueck in stuecke:
            ring = np.array(stueck.exterior.coords)[:3]
            if Polygon(ring).area < 1e-4:
                continue
            E, N = ring[:, 0], ring[:, 1]
            z = a * E + b * N + c - alt + Z_OFFSET
            x, y = zu_lokal(E, N)
            # gegen den Uhrzeigersinn in lokalen x/y (wie die Original-Dateien)
            if (x[1] - x[0]) * (y[2] - y[0]) - (y[1] - y[0]) * (x[2] - x[0]) < 0:
                E, N, z, x, y = E[::-1], N[::-1], z[::-1], x[::-1], y[::-1]
            u, v = uv(E, N)
            n0 = len(verts)
            for q in range(3):
                verts.append([x[q], y[q], z[q], 0, 0, 1, u[q], v[q]])
            idx += [n0, n0 + 1, n0 + 2]
    verts = np.array(verts, np.float32)
    # Flächennormalen: Ebene des Geländedreiecks, nach oben zeigend
    tri = verts[:, :3].reshape(-1, 3, 3)
    nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
    nrm *= np.sign(nrm[:, 2:3])
    verts[:, 3:6] = np.repeat(nrm, 3, axis=0)
    return verts, np.array(idx, np.uint32)


# ---------- Unter-Textur ----------
def schreibe_dds_argb(rgba, pfad):
    ebenen = []
    stufe = rgba
    while True:
        ebenen.append(stufe[..., [2, 1, 0, 3]].tobytes())  # BGRA
        if stufe.shape[0] == 1:
            break
        stufe = cv2.resize(stufe, (stufe.shape[1] // 2, stufe.shape[0] // 2), interpolation=cv2.INTER_AREA)
    h, w = rgba.shape[:2]
    kopf = struct.pack(
        "<4sIIIIIII44sIIIIIIIIIIIII", b"DDS ", 124, 0x1 | 0x2 | 0x4 | 0x8 | 0x1000 | 0x20000, h, w, w * 4, 0,
        len(ebenen), b"\0" * 44, 32, 0x41, 0, 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000,
        0x1000 | 0x8 | 0x400000, 0, 0, 0, 0)
    with open(pfad, "wb") as f:
        f.write(kopf)
        for e in ebenen:
            f.write(e)


def baue_unter_textur(mitte_e, mitte_n, kurz_gras):
    """Luftbild (DOP20, 0,5 m/px, Nord oben) + Alpha: 0x30 kurz gemähte Bereiche, 0x90 sonst."""
    import glob
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.merge import merge
    w, n = mitte_e - SUB_M / 2, mitte_n + SUB_M / 2
    quellen = [rasterio.open(f) for f in glob.glob(os.path.join(PROJ, "Daten", "LGB", "dop_jpg", "*.jpg"))]
    quellen = [q for q in quellen if q.bounds.right > w and q.bounds.left < w + SUB_M and q.bounds.top > n - SUB_M and q.bounds.bottom < n]
    arr, _ = merge(quellen, bounds=(w, n - SUB_M, w + SUB_M, n), res=SUB_M / SUB_PX, resampling=Resampling.average)
    rgb = np.ascontiguousarray(np.transpose(arr[:3], (1, 2, 0))[:SUB_PX, :SUB_PX])
    luecke = (rgb.sum(2) == 0).astype(np.uint8)
    rgb = cv2.inpaint(rgb, luecke, 2, cv2.INPAINT_TELEA)
    # gleiche Farbumrechnung wie die Patch-Textur, damit der Übergang am Flächenrand unsichtbar ist
    mosaik = np.load(os.path.join(ARBEIT, "mosaik.npy")).astype(np.float32)
    res = 5760 / 8192
    c0, r0 = int((w - GRID_W) / res), int((GRID_N0 + 5760 - n) / res)
    ref = mosaik[r0:r0 + int(SUB_M / res), c0:c0 + int(SUB_M / res)]
    assert r0 >= 0 and c0 >= 0 and ref.shape[:2] == (int(SUB_M / res), int(SUB_M / res)), "Unter-Textur ragt über das Mosaik hinaus"
    roh = cv2.resize(rgb, (ref.shape[1], ref.shape[0]), interpolation=cv2.INTER_AREA).astype(np.float32)
    rgb = rgb.astype(np.float32)
    for k in range(3):
        rgb[..., k] = (rgb[..., k] - roh[..., k].mean()) / (roh[..., k].std() + 1e-6) * ref[..., k].std() + ref[..., k].mean()
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    alpha = np.full((SUB_PX, SUB_PX), 0x90, np.uint8)
    if not kurz_gras.is_empty:
        maske = Image.new("L", (SUB_PX, SUB_PX), 0)
        from PIL import ImageDraw
        dr = ImageDraw.Draw(maske)
        px = lambda E, N: ((E - w) / SUB_M * SUB_PX, (n - N) / SUB_M * SUB_PX)
        for teil in shapely.get_parts(kurz_gras):
            dr.polygon([px(*p) for p in teil.exterior.coords], fill=255)
        alpha[np.asarray(maske) > 0] = 0x30
    alpha = cv2.GaussianBlur(alpha, (0, 0), 6)
    return np.dstack([rgb, alpha]), w, n


def main():
    o_apt, lat, lon, alt_alt, d = lies_apt()
    Ec, Nc = T.transform(lon, lat)
    H = lade_raster()
    cs, sn = np.cos(np.radians(d)), np.sin(np.radians(d))
    zu_lokal = lambda E, N: (-cs * (E - Ec) + sn * (N - Nc), sn * (E - Ec) + cs * (N - Nc))

    flugplatz, asphalt, gras, gras_pisten, protokoll = baue_flaechen()
    print("\n".join(protokoll))
    print(f"Flugplatz {flugplatz.area / 1e4:.1f} ha, Asphalt {asphalt.area / 1e4:.2f} ha, Gras {gras.area / 1e4:.1f} ha")

    dreiecke = gelaende_dreiecke(H, flugplatz.buffer(60))
    # Flugplatzhöhe: Gelände am Flugplatzpunkt, ganze Meter (die .apt speichert ganze Meter im Editor)
    baum = shapely.STRtree([Polygon([(p[0], p[1]) for p in t]) for t in dreiecke])
    k = baum.query(shapely.Point(Ec, Nc), predicate="intersects")[0]
    a, b, c = ebene(dreiecke[k])
    h_mitte = a * Ec + b * Nc + c
    alt = float(round(h_mitte))
    print(f"Gelände am Flugplatzpunkt {h_mitte:.2f} m -> Flugplatzhöhe {alt:.0f} m (bisher {alt_alt:.0f} m)")

    mitte_e, mitte_n = (flugplatz.bounds[0] + flugplatz.bounds[2]) / 2, (flugplatz.bounds[1] + flugplatz.bounds[3]) / 2
    rgba, tw, tn = baue_unter_textur(mitte_e, mitte_n, gras_pisten.buffer(45).union(asphalt.buffer(25)))
    uv = lambda E, N: ((E - tw) / SUB_M, (tn - N) / SUB_M)
    assert flugplatz.bounds[0] > tw and flugplatz.bounds[2] < tw + SUB_M and flugplatz.bounds[1] > tn - SUB_M and flugplatz.bounds[3] < tn, "Flugplatz größer als Unter-Textur"

    v_a, i_a = vernetze(asphalt, dreiecke, baum, zu_lokal, uv, alt)
    v_g, i_g = vernetze(gras, dreiecke, baum, zu_lokal, uv, alt)
    print(f"Asphalt: {len(i_a) // 3} Dreiecke, Grass3D: {len(i_g) // 3} Dreiecke")

    mat = (1.0, 1.0, 1.0, 1.0, 0.0, 0.1)
    obs = [
        dict(name="Grass3D", vstart=0, vanz=len(v_g), istart=0, ianz=len(i_g), textur=f"Textures/{NAME}.dds", material=mat, rest=0),
        dict(name="Asphalt", vstart=len(v_g), vanz=len(v_a), istart=len(i_g), ianz=len(i_a), textur=f"Textures/{NAME}.dds", material=mat, rest=0),
    ]
    vert = np.vstack([v_g, v_a]); idx = np.concatenate([i_g, i_a + len(v_g)])
    os.makedirs(os.path.join(ARBEIT, "EDAZ"), exist_ok=True)
    c3d.schreibe(os.path.join(ARBEIT, "EDAZ", f"{NAME}G.c3d"), obs, vert, idx, kopf=(1, 0, len(obs)))
    schreibe_dds_argb(rgba, os.path.join(ARBEIT, "EDAZ", f"{NAME}.dds"))
    # Kontrollbild: Flächen auf der Unter-Textur
    vorschau = Image.fromarray(rgba[..., :3]).convert("RGB").resize((2048, 2048))
    from PIL import ImageDraw
    dr = ImageDraw.Draw(vorschau)
    for vv, ii, farbe in ((v_g, i_g, (0, 255, 0)), (v_a, i_a, (255, 0, 0))):
        for t in ii.reshape(-1, 3)[::1]:
            dr.polygon([(vv[q, 6] * 2048, vv[q, 7] * 2048) for q in t], outline=farbe)
    vorschau.save(os.path.join(ARBEIT, "EDAZ", "kontrolle_flaechen.png"))
    json.dump(dict(apt_offset=o_apt, hoehe=alt, richtung=d, Ec=Ec, Nc=Nc), open(os.path.join(ARBEIT, "EDAZ", "info.json"), "w"))


if __name__ == "__main__":
    main()
