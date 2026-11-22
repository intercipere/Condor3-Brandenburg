"""Lädt LGB-Kacheln (DOP20, DGM1, bDOM, LoD2) für ein Gebiet in UTM-33-Kilometern.

Aufruf: python lgb_laden.py <ost_von> <ost_bis> <nord_von> <nord_bis> <zielordner> [datensatz,datensatz]
Beispiel Ring um EDAZ: python lgb_laden.py 363 380 5777 5794 ..\\Daten\\LGB_Ring
Gebäude, die von außen in das Gebiet ragen: python lgb_laden.py 362 381 5776 5795 ..\\Daten\\LGB_Ring lod2

Die Grenzen zählen mit. Kacheln, die schon in Daten\\LGB, in neukarte.LGB_ORDNER oder im Zielordner liegen, werden übersprungen.
Für LoD2 ist 404 normal (Kachel ohne Gebäude), bei den anderen Datensätzen ist es ein Fehler.
Lizenz der Daten: dl-de/by-2-0, © GeoBasis-DE/LGB.
"""
import http.client
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from neukarte import LGB_ORDNER

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASIS = "https://data.geobasis-bb.de/geobasis/daten"
# Ordner lokal: (Pfad auf dem Server, Namensanfang)
DATENSAETZE = {
    "dop": ("dop/rgb_jpg", "dop"),
    "dgm": ("dgm/tif", "dgm"),
    "bdom": ("bdom/tif", "bdom"),
    "lod2": ("3d_gebaeude/lod2_gml", "lod2"),
}
VERSUCHE = 4
# Kacheln, die hier schon liegen, werden nicht neu geladen
VORHANDEN = [os.path.join(PROJ, "Daten", "LGB")] + LGB_ORDNER


def lade(aufgabe):
    """Gibt (Name, Status) zurück: geladen, fehlt (404) oder Fehler."""
    url, pfad = aufgabe
    name = os.path.basename(pfad)
    teil = pfad + ".part"
    for versuch in range(1, VERSUCHE + 1):
        try:
            anfrage = urllib.request.Request(url, headers={"User-Agent": "lgb-kachel-download"})
            with urllib.request.urlopen(anfrage, timeout=120) as antwort, open(teil, "wb") as f:
                while block := antwort.read(1 << 20):
                    f.write(block)
            with zipfile.ZipFile(teil) as zf:
                kaputt = zf.testzip()
            if kaputt:
                raise zipfile.BadZipFile(f"defekt: {kaputt}")
            os.replace(teil, pfad)
            return name, "geladen"
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return name, "fehlt"
            fehler = e
        except (OSError, http.client.HTTPException, zipfile.BadZipFile) as e:
            fehler = e
        if os.path.exists(teil):
            os.remove(teil)
        time.sleep(5 * versuch)
    return name, f"Fehler: {fehler}"


def main():
    ost_von, ost_bis, nord_von, nord_bis = (int(a) for a in sys.argv[1:5])
    ziel = os.path.abspath(sys.argv[5])
    auswahl = sys.argv[6].split(",") if len(sys.argv) > 6 else list(DATENSAETZE)
    aufgaben = {}
    for ordner in auswahl:
        server, anfang = DATENSAETZE[ordner]
        os.makedirs(os.path.join(ziel, ordner), exist_ok=True)
        aufgaben[ordner] = []
        for ost in range(ost_von, ost_bis + 1):
            for nord in range(nord_von, nord_bis + 1):
                name = f"{anfang}_33{ost}-{nord}.zip"
                if any(os.path.exists(os.path.join(o, ordner, name)) for o in VORHANDEN + [ziel]):
                    continue
                aufgaben[ordner].append((f"{BASIS}/{server}/{name}", os.path.join(ziel, ordner, name)))
    fehler = []
    for ordner, liste in aufgaben.items():
        zaehler = {"geladen": 0, "fehlt": 0}
        with ThreadPoolExecutor(4) as pool:
            for name, status in pool.map(lade, liste):
                if status in zaehler:
                    zaehler[status] += 1
                if status.startswith("Fehler") or (status == "fehlt" and ordner != "lod2"):
                    fehler.append(f"{name}: {status}")
        print(f"{ordner}: {zaehler['geladen']} geladen, {zaehler['fehlt']} ohne Daten, {len(liste)} angefragt", flush=True)
    for f in fehler:
        print("FEHLER", f)
    sys.exit(1 if fehler else 0)


if __name__ == "__main__":
    main()
