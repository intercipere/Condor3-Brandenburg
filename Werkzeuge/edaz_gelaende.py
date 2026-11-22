"""Ersetzt das Gelände der EDAZ-Patches (22,5-m-OBJ) durch DGM1, mit weichem Übergang zum alten Gelände am Außenrand.

Ergebnis landet in Working/HeightMaps/22.5m/Modified, von dort wandelt der Landscape Editor es in TR3F um.
"""
import os
import cv2
import numpy as np
import gelaende as g

PATCHES = [(40, 39), (39, 39)]
UEBERGANG = 600.0  # Meter vom Außenrand des Gebiets, in denen von alt auf DGM1 überblendet wird

# Außenrand des Gesamtgebiets aus allen Patches
west = min(g.patch_mitte(c, r)[0] for c, r in PATCHES) - g.PATCH / 2
ost = max(g.patch_mitte(c, r)[0] for c, r in PATCHES) + g.PATCH / 2
sued = min(g.patch_mitte(c, r)[1] for c, r in PATCHES) - g.PATCH / 2
nord = max(g.patch_mitte(c, r)[1] for c, r in PATCHES) + g.PATCH / 2

dgm, tr = g.dgm_mosaik()
assert np.isfinite(dgm).all(), "DGM-Mosaik hat Lücken (fehlende Kachel oder nodata)"
assert tr.c <= west and tr.c + dgm.shape[1] >= ost and tr.f >= nord and tr.f - dgm.shape[0] <= sued, "DGM deckt das Gebiet nicht ab"
dgm_glatt = cv2.blur(dgm, (23, 23))  # Mittel über eine 22,5-m-Zelle, damit nichts flimmert

os.makedirs(os.path.join(g.WORK, "Modified"), exist_ok=True)
for c, r in PATCHES:
    name = f"h{c:03d}{r:03d}.obj"
    kopf, v, rest = g.lies_obj(os.path.join(g.WORK, name))
    ec, nc = g.patch_mitte(c, r)
    e, n = ec + v[:, 0], nc + v[:, 1]  # OBJ: x nach Osten, y nach Norden (gegen DGM1 geprüft)
    neu = g.taste_ab(dgm_glatt, tr, e, n)
    abstand = np.minimum.reduce([e - west, ost - e, n - sued, nord - n])
    t = np.clip(abstand / UEBERGANG, 0, 1)
    w = t * t * (3 - 2 * t)
    assert np.isfinite(neu).all(), f"{name}: ungültige Höhen"
    v2 = v.copy()
    v2[:, 2] = w * neu + (1 - w) * v[:, 2]
    g.schreibe_obj(os.path.join(g.WORK, "Modified", name), kopf, v2, rest)
    d = v2[:, 2] - v[:, 2]
    print(f"{name}: Änderung min {d.min():+.1f} / max {d.max():+.1f} / Mittel {d.mean():+.2f} m")
