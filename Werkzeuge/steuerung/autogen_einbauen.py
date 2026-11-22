"""Baut fertige Autogen-OBJ in die Landschaft ein: Landscape Editor "Export autogen C3D from OBJ", die C3D aus
Working/Autogen nach <Landschaft>/Autogen und die Texturen nach Autogen/Textures kopieren, "Export autogen hash (OHA)"
und "Check autogen files and hashlist". Danach muss jede C3D in <Landschaft>/Autogen mit ihrem MD5 in der .oha
stehen und umgekehrt. Pfade aus Werkzeuge/config.py (LAND). Vorher die OBJ erzeugen (z. B. doerfer_autogen.py) und
die Landschaft sichern.

Aufruf (aus Werkzeuge/):
    python steuerung/autogen_einbauen.py <Texturordner> [<weitere Texturordner> ...]
    z. B. python steuerung/autogen_einbauen.py ../Daten/Arbeit/Autogen
"""
import glob
import hashlib
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
from steuerung.landscape_editor import Editor  # noqa: E402


def erwarte(text, muss):
    if muss not in text:
        raise SystemExit(f"unerwartete Meldung des Editors (erwartet „{muss}“): {text!r}")
    return text


def main(texturordner):
    land = config.LAND
    name = os.path.basename(land)
    work = os.path.join(land, "Working", "Autogen")
    objs = {os.path.basename(f)[:-4] for f in glob.glob(os.path.join(work, "o*.obj"))}
    if not objs:
        raise SystemExit(f"keine Autogen-OBJ in {work}")
    texturen = []
    for ordner in texturordner:
        dds = glob.glob(os.path.join(ordner, "*.dds"))
        if not dds:
            raise SystemExit(f"keine .dds in {ordner}")
        texturen += dds
    ed = Editor(name)
    for f in glob.glob(os.path.join(work, "o*.c3d")):  # alte Ergebnisse weg, damit nichts Veraltetes eingebaut wird
        os.remove(f)
    print("C3D:", erwarte(ed.ausfuehren("Export autogen C3D from OBJ"), "C3D files exported"))
    c3d = sorted(glob.glob(os.path.join(work, "o*.c3d")))
    if {os.path.basename(f)[:-4] for f in c3d} != objs:
        raise SystemExit(f"C3D passen nicht zu den OBJ: {sorted(objs)} -> {[os.path.basename(f) for f in c3d]}")
    os.makedirs(os.path.join(land, "Autogen", "Textures"), exist_ok=True)
    for f in c3d:
        shutil.copy2(f, os.path.join(land, "Autogen"))
    for f in texturen:
        shutil.copy2(f, os.path.join(land, "Autogen", "Textures"))
    print(f"kopiert: {len(c3d)} C3D, {len(texturen)} Texturen")
    print("OHA:", erwarte(ed.ausfuehren("Export autogen hash (OHA)"), "OHA exported"))
    print("Prüfung:", erwarte(ed.ausfuehren("Check autogen files and hashlist"), "hashlist OK"))
    # Gegenprobe: .oha-Einträge mit Hash und eingebaute C3D müssen genau übereinstimmen
    oha = dict(z.split() for z in open(os.path.join(land, name + ".oha")).read().splitlines() if len(z.split()) == 2)
    eingebaut = {os.path.basename(f)[1:-4]: f for f in glob.glob(os.path.join(land, "Autogen", "o*.c3d"))}
    fehler = sorted(set(oha) ^ set(eingebaut))
    for patch, f in sorted(eingebaut.items()):
        md5 = hashlib.md5(open(f, "rb").read()).hexdigest()
        ok = oha.get(patch, "").lower() == md5
        fehler += [] if ok else [patch]
        print(f"  {patch}: {'OK' if ok else 'FALSCH'} {md5}")
    if fehler:
        raise SystemExit(f".oha und Autogen-Ordner passen nicht zusammen: {sorted(set(fehler))}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
    else:
        main(sys.argv[1:])
