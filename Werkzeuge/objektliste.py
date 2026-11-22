"""Bearbeitet die Objektliste der Landschaft (<Landschaft>.obj) rund um EDAZ.

Format (aus der Datei ermittelt): Datensätze zu je 152 Byte:
  float PosX (= 605160 - Rechtswert), float PosY (= Hochwert - 5558120), float z (absolute Höhe),
  float Skalierung, float Drehung (rad), Pascal-String Objektdatei (in World/Objects), Rest unverändert übernehmen.

- Alte Hallen/Hangars und Büsche im Flugplatzgebiet werden entfernt (ersetzt durch LoD2-Gebäude und die neue Waldkarte).
- Flugzeuge/Anhänger bleiben, ihre Höhe wird auf das neue 22,5-m-Gelände gesetzt; stehen sie in einem neuen Gebäude, fliegen sie raus.
"""
import os
import struct
import sys

import numpy as np
import shapely
from shapely.geometry import Point, Polygon

import edaz_gebaeude as eg
from edaz_flaechen import lade_raster, GRID_W, GRID_N0, ZELLE, osm_elemente, utm, ist_geschlossen

from config import LAND
DATEI = os.path.join(LAND, "EastGermany3.obj")
SATZ = 152
ERSETZT = {"hangarlongroa.c3d", "hangar2p.c3d", "hangar2.c3d", "kerken halle.c3d", "buisson1_ns.c3d", "buisson2_ns.c3d"}


def lies(pfad):
    d = open(pfad, "rb").read()
    assert len(d) % SATZ == 0
    saetze = []
    for k in range(len(d) // SATZ):
        r = bytearray(d[k * SATZ:(k + 1) * SATZ])
        x, y, z, s, rot = struct.unpack_from("<5f", r, 0)
        name = r[21:21 + r[20]].decode("latin1")
        saetze.append(dict(roh=r, x=x, y=y, z=z, name=name))
    return saetze


def gelaende_hoehe(H, E, N):
    i = (E - GRID_W) / ZELLE
    j = (N - GRID_N0) / ZELLE
    i0, j0 = int(i), int(j)
    fi, fj = i - i0, j - j0
    return (H[j0, i0] * (1 - fi) * (1 - fj) + H[j0, i0 + 1] * fi * (1 - fj)
            + H[j0 + 1, i0] * (1 - fi) * fj + H[j0 + 1, i0 + 1] * fi * fj)


def main():
    nur_pruefen = "--pruefen" in sys.argv
    saetze = lies(DATEI)
    flugplatz = [Polygon(utm(e["geometry"])) for e in osm_elemente("edaz_aeroway.json")
                 if e.get("tags", {}).get("aeroway") == "aerodrome" and ist_geschlossen(e["geometry"])][0]
    gebiet = flugplatz.buffer(eg.PUFFER)
    flaechen, _, _ = eg.lies_gebaeude(gebiet)
    grundrisse = shapely.union_all([Polygon(r[:, :2]).buffer(0) for a, r, i, g in flaechen if a == "RoofSurface"]).buffer(1.0)
    H = lade_raster()
    raus, angepasst, behalten = [], [], []
    for k, s in enumerate(saetze):
        E, N = 605160.0 - s["x"], 5558120.0 + s["y"]
        p = Point(E, N)
        if not gebiet.contains(p):
            behalten.append(s)
            continue
        if s["name"].lower() in ERSETZT or grundrisse.contains(p):
            raus.append(s)
            continue
        z = float(gelaende_hoehe(H, E, N))
        print(f"  {s['name']:<18} z {s['z']:.1f} -> {z:.1f}")
        struct.pack_into("<f", s["roh"], 8, z)
        angepasst.append(s)
        behalten.append(s)
    print(f"{len(saetze)} Objekte: {len(raus)} entfernt, {len(angepasst)} Höhe angepasst")
    print("  entfernt:", sorted({s['name'] for s in raus}))
    if not nur_pruefen:
        open(DATEI, "wb").write(b"".join(bytes(s["roh"]) for s in behalten))
        assert len(lies(DATEI)) == len(saetze) - len(raus)
        print("geschrieben:", DATEI)


if __name__ == "__main__":
    main()
