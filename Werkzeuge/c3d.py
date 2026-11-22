"""Lesen und Schreiben von Condor-C3D-Dateien (Format durch Vergleich bekannter Dateien entschlüsselt).

Aufbau:
  'C3D' + uint32 Version(1) + uint32 (0) + uint32 Anzahl Objekte + uint32 Anzahl Objekte (in allen 151 Originaldateien gleich)
  je Objekt: Name (Pascal-String), uint32 VertexStart, VertexAnzahl, IndexStart, IndexAnzahl,
             Textur (Pascal-String), 6 x float32 Material, uint32 (LOD?)
  uint32 Vertexanzahl gesamt, je Vertex 8 x float32 (x, y, z, nx, ny, nz, u, v)
  uint32 Indexanzahl gesamt, je Index uint32 (global)
"""
import struct
import numpy as np


def _pstr(d, o):
    n = d[o]
    return d[o + 1:o + 1 + n].decode("latin1"), o + 1 + n


def lies(pfad):
    d = open(pfad, "rb").read()
    assert d[:3] == b"C3D", "kein C3D"
    kopf = struct.unpack_from("<4I", d, 3)
    o = 19
    objekte = []
    for _ in range(kopf[3]):
        name, o = _pstr(d, o)
        vs, vn, is_, in_ = struct.unpack_from("<4I", d, o); o += 16
        tex, o = _pstr(d, o)
        mat = struct.unpack_from("<6f", d, o); o += 24
        rest = struct.unpack_from("<I", d, o)[0]; o += 4
        objekte.append(dict(name=name, vstart=vs, vanz=vn, istart=is_, ianz=in_, textur=tex, material=mat, rest=rest))
    nv = struct.unpack_from("<I", d, o)[0]; o += 4
    vert = np.frombuffer(d, "<f4", nv * 8, o).reshape(nv, 8); o += nv * 32
    ni = struct.unpack_from("<I", d, o)[0]; o += 4
    idx = np.frombuffer(d, "<u4", ni, o); o += ni * 4
    assert o == len(d), f"Restbytes: {len(d) - o}"
    return kopf, objekte, vert, idx


def schreibe(pfad, objekte, vert, idx, kopf=None):
    kopf = kopf or (1, 0, len(objekte))
    out = bytearray(b"C3D" + struct.pack("<4I", *kopf, len(objekte)))
    for ob in objekte:
        n = ob["name"].encode("latin1"); t = ob["textur"].encode("latin1")
        out += bytes([len(n)]) + n + struct.pack("<4I", ob["vstart"], ob["vanz"], ob["istart"], ob["ianz"])
        out += bytes([len(t)]) + t + struct.pack("<6f", *ob["material"]) + struct.pack("<I", ob["rest"])
    out += struct.pack("<I", len(vert)) + np.asarray(vert, "<f4").tobytes()
    out += struct.pack("<I", len(idx)) + np.asarray(idx, "<u4").tobytes()
    open(pfad, "wb").write(out)


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        k, obs, v, i = lies(p)
        print(p.split("/")[-1], "Kopf", k, "Vertices", len(v), "Indizes", len(i))
        for ob in obs:
            print("  ", ob["name"], ob["vanz"], ob["ianz"], repr(ob["textur"]), [round(x, 3) for x in ob["material"]], ob["rest"])
