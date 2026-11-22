"""Bereitet die Szenerie rund um EDAZ für die Blender-Vorschau auf (läuft im normalen Python, nicht in Blender).

Liest genau die Dateien, die Condor liest (Gelände-TR3F-Quelle, Patch-Texturen, Flugplatz-G/O-Dateien, Waldkarten),
und schreibt sie als einfache Arrays + PNGs nach Daten/Vorschau. Weltkoordinaten der Vorschau:
x = Ost, y = Nord (Meter relativ zum Flugplatzpunkt), z = absolute Höhe minus Flugplatzhöhe.
"""
import glob
import json
import os

import numpy as np
from PIL import Image

import c3d
import gelaende as g
from edaz_flaechen import GRID_N0, GRID_W, PATCHES, ZELLE, T, lade_raster, lies_apt

Image.MAX_IMAGE_PIXELS = None
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from config import LAND
ZIEL = os.path.join(PROJ, "Daten", "Vorschau")
TEX_PX = 4096  # je Patch, für die Vorschau reicht 1,4 m/px


def dds_als_png(pfad, ziel, max_px=4096):
    if os.path.exists(ziel) and os.path.getmtime(ziel) >= os.path.getmtime(pfad):
        return os.path.basename(ziel)  # unverändert seit der letzten Umwandlung
    print("  wandle", os.path.basename(pfad), flush=True)
    im = Image.open(pfad).convert("RGBA")
    if im.width > max_px:
        im = im.resize((max_px, max_px * im.height // im.width), Image.BOX)
    im.save(ziel)
    return os.path.basename(ziel)


def main():
    os.makedirs(ZIEL, exist_ok=True)
    _, lat, lon, alt, d = lies_apt()
    Ec, Nc = T.transform(lon, lat)
    cs, sn = np.cos(np.radians(d)), np.sin(np.radians(d))
    M = np.array([[-cs, sn], [sn, cs]])  # lokal <-> UTM (selbstinvers, Spiegelung)
    daten = dict(alt=alt, richtung=d)

    print("Gelände ...", flush=True)
    # Gelände: 22,5-m-Raster beider Patches, wie es Condor aus den TR3F-Dateien liest
    H = lade_raster()
    E0, N0 = GRID_W - Ec, GRID_N0 - Nc
    np.save(os.path.join(ZIEL, "gelaende.npy"), (H - alt).astype(np.float32))
    daten["gelaende"] = dict(e0=E0, n0=N0, zelle=ZELLE)

    print("Luftbilder ...", flush=True)
    # Patch-Texturen (genau die eingebauten DDS) als ein Streifen West -> Ost
    reihe = sorted(PATCHES, key=lambda p: -p[0])
    bilder = [Image.open(os.path.join(LAND, "Textures", f"t{c:02d}{r:02d}.dds")).convert("RGB").resize((TEX_PX, TEX_PX), Image.BOX) for c, r in reihe]
    streifen = Image.new("RGB", (TEX_PX * len(bilder), TEX_PX))
    for k, b in enumerate(bilder):
        streifen.paste(b, (k * TEX_PX, 0))
    streifen.save(os.path.join(ZIEL, "gelaende.png"))

    print("Flugplatz und Gebäude ...", flush=True)
    # Flugplatz-Objekte: lokal (gespiegelt) -> Welt; Dreiecksreihenfolge umdrehen, weil die Spiegelung die Orientierung umkehrt
    objekte = []
    for datei in ("SchoenhagenG.c3d", "SchoenhagenO.c3d"):
        _, obs, v, idx = c3d.lies(os.path.join(LAND, "Airports", datei))
        for o in obs:
            tris = idx[o["istart"]:o["istart"] + o["ianz"]].reshape(-1, 3)[:, ::-1]
            vs = np.unique(tris)
            P = v[:, :3].copy()
            P[:, :2] = (M @ v[:, :2].T).T
            name = f"{datei[:-4]}_{o['name']}"
            tex = None
            if o["textur"]:
                tex = dds_als_png(os.path.join(LAND, "Airports", o["textur"]), os.path.join(ZIEL, os.path.basename(o["textur"])[:-4] + ".png"))
            np.savez(os.path.join(ZIEL, name + ".npz"), p=P[vs], uv=v[vs, 6:8], tris=np.searchsorted(vs, tris))
            objekte.append(dict(name=name, textur=tex, farbe=list(o["material"][:3])))
    daten["objekte"] = objekte

    print("Wald ...", flush=True)
    # Wald: Zellmitten aus den .for-Dateien (Datei = Bild[::-1, ::-1].T, Bild Zeile 0 = Nord, Spalte 0 = West)
    baeume = []
    for c, r in PATCHES:
        F = np.fromfile(os.path.join(LAND, "ForestMaps", f"{c:02d}{r:02d}.for"), np.uint8).reshape(512, 512)
        bild = F.T[::-1, ::-1]
        ec, nc = g.patch_mitte(c, r)
        zz, ss = np.nonzero(bild)
        e = ec - g.PATCH / 2 + (ss + 0.5) * (g.PATCH / 512)
        n = nc + g.PATCH / 2 - (zz + 0.5) * (g.PATCH / 512)
        baeume.append(np.c_[e - Ec, n - Nc, bild[zz, ss]])
    B = np.vstack(baeume)
    # Höhe des Bodens unter jedem Baum (bilinear aus dem Geländeraster)
    i = (B[:, 0] - E0) / ZELLE; j = (B[:, 1] - N0) / ZELLE
    i0 = np.clip(i.astype(int), 0, H.shape[1] - 2); j0 = np.clip(j.astype(int), 0, H.shape[0] - 2)
    fi, fj = i - i0, j - j0
    z = (H[j0, i0] * (1 - fi) * (1 - fj) + H[j0, i0 + 1] * fi * (1 - fj) + H[j0 + 1, i0] * (1 - fi) * fj + H[j0 + 1, i0 + 1] * fi * fj) - alt
    np.save(os.path.join(ZIEL, "baeume.npy"), np.c_[B[:, :2], z, B[:, 2]].astype(np.float32))
    json.dump(daten, open(os.path.join(ZIEL, "szene.json"), "w"), indent=1)
    print(f"Vorschau-Daten: Gelände {H.shape}, {len(objekte)} Objekte, {len(B)} Waldzellen -> {ZIEL}")


if __name__ == "__main__":
    main()
