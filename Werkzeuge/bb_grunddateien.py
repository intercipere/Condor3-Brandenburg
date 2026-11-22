"""Schreibt die kleinen Grunddateien der Landschaft Brandenburg: <Name>.ini, <Name>.apt (nur EDAZ), <Name>.obj und
<Name>.air (leer, kein Luftraum), und wandelt die Flightplanner-Karte <Name>.bmp in 32 Bit wie bei EG3.

.apt-Datensatz (72 Byte, siehe PROJEKT.md): Pascal-String (36 Byte), float lat, lon, Höhe, uint32 Richtung
(100000 + Grad × 100), uint32 Länge, Breite, Asphalt, float Frequenz, uint32 Flags.
Die EDAZ-Werte stammen aus der EG3-Arbeit (Höhe 41 m aus DGM1, Piste 257,18°, 1500 × 100 m).
.obj (siehe objektliste.py): 152 Byte je Satz, float PosX (= E0 - Rechtswert), PosY (= Hochwert - N0), z (absolut),
Skalierung, Drehung (rad), Pascal-String Objektdatei. Condor und scenerycheck3 suchen sie in
Landscapes/<Name>/World/Objects, darum wird der Windsack aus Condors eigenem World/Objects dorthin kopiert.
Aufruf: python bb_grunddateien.py (nach bb_gelaende.py und dem Editor-Export der Flightplanner-Karte)
"""
import os
import shutil
import struct
import numpy as np
from PIL import Image
import neukarte as nk
from config import CONDOR_DIR

FLUGPLAETZE = [
    # Name, lat, lon, Höhe, Richtung °, Länge, Breite, Asphalt, Frequenz, Flags
    ("Schoenhagen", 52.2032, 13.16, 41.0, 257.18, 1500, 100, 0, 123.5, 0),
]
ICAO = {"Schoenhagen": "EDAZ"}


def apt_satz(name, lat, lon, hoehe, richtung, laenge, breite, asphalt, frequenz, flags):
    n = name.encode("latin1")
    assert len(n) <= 35
    return (bytes([len(n)]) + n.ljust(35, b"\0")
            + struct.pack("<3f4If I", lat, lon, hoehe, 100000 + round(richtung * 100), laenge, breite, asphalt, frequenz, flags))


OBJEKTE = [
    # Objekt, Rechtswert, Hochwert, Skalierung, Drehung (rad): Windsack 150 m nördlich des Flugplatzpunkts
    ("WindsackA.c3d", 374261.0, 5785385.0, 1.0, 0.0),
]


def gelaende_hoehe(e, n):
    """Höhe aus der TR3F des Patches (nächster Rasterpunkt, Layout wie bb_gelaende.py)."""
    c, r = int((nk.E0 - e) // nk.PATCH), int((n - nk.N0) // nk.PATCH)
    _, ost, sued, _ = nk.patch_ecken(c, r)
    f = np.fromfile(f"{nk.LAND}/HeightMaps/22.5m/h{c:03d}{r:03d}.tr3f", np.float32).reshape(257, 257)
    return float(f[round((ost - e) / 22.5), round((n - sued) / 22.5)])


def obj_satz(name, e, n, skalierung, drehung):
    satz = bytearray(152)
    struct.pack_into("<5f", satz, 0, nk.E0 - e, n - nk.N0, gelaende_hoehe(e, n), skalierung, drehung)
    b = name.encode("latin1")
    satz[20] = len(b)
    satz[21:21 + len(b)] = b
    return bytes(satz)


def bmp_32bit(pfad):
    """Schreibt die BMP als 32 Bit BGRA (Kopf 54 Byte, Zeilen von unten), wie EastGermany3.bmp."""
    rgb = np.asarray(Image.open(pfad).convert("RGB"))
    h, w = rgb.shape[:2]
    daten = np.dstack([rgb[::-1, :, ::-1], np.zeros((h, w), np.uint8)]).tobytes()
    kopf = struct.pack("<2sIHHIIiiHHIIiiII", b"BM", 54 + len(daten), 0, 0, 54, 40, w, h, 1, 32, 0, len(daten), 0, 0, 0, 0)
    with open(pfad, "wb") as f:
        f.write(kopf + daten)


def cup_zeile(name, lat, lon, hoehe, richtung, laenge, breite, asphalt, frequenz, flags):
    """Wendepunkt im SeeYou-Format wie EastGermany3.cup (Stil 5 = Asphalt, 2 = Gras)."""
    def grad_min(wert, stellen, pos, neg):
        g, m = divmod(round(abs(wert) * 60000), 60000)  # erst runden, damit nie „60.000“ Minuten entstehen
        return f"{g:0{stellen}d}{m / 1000:06.3f}{pos if wert >= 0 else neg}"
    return (f'"{name}","{ICAO.get(name, "")}",DE,{grad_min(lat, 2, "N", "S")},{grad_min(lon, 3, "E", "W")},'
            f'{hoehe:.1f}m,{5 if asphalt else 2},{round(richtung) % 360 or 360:03d},{laenge:.1f}m,{frequenz:.3f},'
            f'"Flugplatz"\n')


def empty_dds(pfad):
    """Schreibt Textures/empty.dds: 256 × 256 DXT3 mit 9 Mipmaps, einfarbig, Aufbau wie in EG2/EG3
    (scenerycheck3 meldet die Landschaft ohne diese Datei als KO)."""
    block = b"\x33" * 8 + struct.pack("<HHI", 0x222A, 0x222A, 0)  # Alpha 3/15, Farbe RGB565, alle Indizes 0
    n_bloecke = sum(max(1, (256 >> i) // 4) ** 2 for i in range(9))
    kopf = struct.pack("<4s7I44x2I4s20xI16x", b"DDS ", 124, 0xA1007, 256, 256, 256 * 256, 0, 9,
                       32, 4, b"DXT3", 0x401008)
    with open(pfad, "wb") as f:
        f.write(kopf + block * n_bloecke)


def main():
    with open(f"{nk.LAND}/{nk.NAME}.apt", "wb") as f:
        for fp in FLUGPLAETZE:
            f.write(apt_satz(*fp))
    # Ohne <Name>.cup meldet Condor beim Auswählen „landscape not installed / corrupted“ (eine eigene .cup in
    # Documents\Condor3\Turnpoints hat Vorrang). Condor liest ab der zweiten Zeile, darum eine Kopfzeile.
    # Zeilenende LF wie EastGermany3.cup.
    with open(f"{nk.LAND}/{nk.NAME}.cup", "w", encoding="latin1", newline="") as f:
        f.write("name,code,country,lat,lon,elev,style,rwdir,rwlen,freq,desc\n")
        for fp in FLUGPLAETZE:
            f.write(cup_zeile(*fp))
    with open(f"{nk.LAND}/{nk.NAME}.ini", "w", newline="\r\n") as f:
        f.write("[General]\nVersion=1.0\nRealtimeShading=1\n")
    with open(f"{nk.LAND}/{nk.NAME}.obj", "wb") as f:
        for o in OBJEKTE:
            f.write(obj_satz(*o))
    os.makedirs(f"{nk.LAND}/World/Objects", exist_ok=True)
    for name in {o[0] for o in OBJEKTE}:
        shutil.copy2(f"{CONDOR_DIR}/World/Objects/{name}", f"{nk.LAND}/World/Objects/{name}")
    open(f"{nk.LAND}/{nk.NAME}.air", "wb").close()
    bmp_32bit(f"{nk.LAND}/{nk.NAME}.bmp")
    empty_dds(f"{nk.LAND}/Textures/empty.dds")
    print(f"{nk.NAME}.apt: {len(FLUGPLAETZE)} Flugplatz, .ini, .obj ({len(OBJEKTE)} Objekte), .air, .bmp 32 Bit, "
          "Textures/empty.dds geschrieben")


if __name__ == "__main__":
    main()
