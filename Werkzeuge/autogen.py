"""Schreibt Autogen-OBJ/MTL für einen Patch in Working/Autogen (Format wie der Condor OSM Exporter, CondorOSMImporter.py).

Der Landscape Editor wandelt sie mit "Export autogen C3D from OBJ" in Working/Autogen/o<Patch>.c3d um. Condor liest
<Landschaft>/Autogen/o<Patch>.c3d, die Texturen aus <Landschaft>/Autogen/Textures. Danach im Landscape Editor
"Export autogen hash (OHA)", sonst meldet Condor eine Manipulation.

Achsen der OBJ (Hypothese, siehe test_marker): Der Exporter lädt das Gelände h<Patch>.obj unverändert
(x Ost, y Nord, Ursprung Patch-Mitte) und schreibt Autogen mit axis_forward='X' -> OBJ x = Nord, y = West,
z = absolute Höhe.
"""
import os

import numpy as np

import neukarte as nk

from config import LAND
WORK = os.path.join(LAND, "Working", "Autogen")


def patchname(col, row):
    return f"{col:03d}{row:03d}"


def nach_obj(P, col, row):
    """UTM (E, N, z absolut) -> OBJ-Rahmen des Patches (x Nord, y West, z)."""
    west, ost, sued, nord = nk.patch_ecken(col, row)
    Ec, Nc = (west + ost) / 2, (sued + nord) / 2
    P = np.asarray(P, float)
    return np.c_[P[..., 1].ravel() - Nc, Ec - P[..., 0].ravel(), P[..., 2].ravel()].reshape(P.shape)


def schreibe(col, row, teile, ziel=WORK):
    """teile: Liste von (objektname, textur.dds, dreiecke[N,3,3] in UTM, uv[N,3,2] mit v nach unten wie DirectX).
    Dreiecke von außen gesehen gegen den Uhrzeigersinn; Normale = Flächennormale."""
    name = "o" + patchname(col, row)
    os.makedirs(ziel, exist_ok=True)
    with open(os.path.join(ziel, name + ".mtl"), "w", newline="\n") as f:
        for obj, tex, _, _ in teile:
            f.write(f"newmtl {obj}\nNs 0.000000\nKa 1.0 1.0 1.0\nKd 1.000000 1.000000 1.000000\n"
                    f"Ks 0.000000 0.000000 0.000000\nKe 0.000000 0.000000 0.000000\nNi 1.450000\nd 1.000000\n"
                    f"illum 2\nmap_Kd {tex}\n\n")
    i = 1
    with open(os.path.join(ziel, name + ".obj"), "w", newline="\n") as f:
        f.write(f"# Condor Autogen aus LoD2\nmtllib {name}.mtl\n")
        for obj, _, tris, uv in teile:
            L = nach_obj(np.asarray(tris, float), col, row)
            n = np.cross(L[:, 1] - L[:, 0], L[:, 2] - L[:, 0])
            n /= np.linalg.norm(n, axis=1, keepdims=True)
            f.write(f"o {obj}\nusemtl {obj}\n")
            zeilen = []
            for t in range(len(L)):
                for k in range(3):
                    zeilen.append("v %.4f %.4f %.4f\nvn %.6f %.6f %.6f\nvt %.6f %.6f\n"
                                  % (*L[t, k], *n[t], uv[t][k][0], 1.0 - uv[t][k][1]))
                zeilen.append(f"f {i}/{i}/{i} {i + 1}/{i + 1}/{i + 1} {i + 2}/{i + 2}/{i + 2}\n")
                i += 3
            f.write("".join(zeilen))
    return os.path.join(ziel, name + ".obj")
