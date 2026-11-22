# Condor 3 Brandenburg

Werkzeuge für eine eigene Condor-3-Landschaft „Brandenburg“ aus offenen Geodaten des Landes Brandenburg. Pilot: eine Kachel (23,04 × 23,04 km, 4 × 4 Patches) um den Flugplatz EDAZ Schönhagen mit Trebbin und den umliegenden Dörfern. Der Stand ist ein Arbeitsstand, noch kein Release.

Die Werkzeuge stammen aus dem Projekt [Condor-EastGer3-EDAZ](https://github.com/intercipere/Condor-EastGer3-EDAZ) (EDAZ in EastGermany3). Anders als dort baut dieses Repo die Landschaft komplett neu und braucht keine Dateien von EastGermany2.

## Inhalt

1. `NEUKARTE.md`: Stand der Brandenburg-Karte, Reihenfolge der Skripte, Erkenntnisse über die Dateien, die Condor verlangt. Hier anfangen.
2. `Werkzeuge/bb_*.py`: Gelände (DGM1 → `.trn`, `.tr3`, `.tr3f`), Luftbild-Texturen (DOP20), Waldkarten, Thermik, Grunddateien (`.apt`, `.cup`, `.ini`, `.obj`, `.air`), Flugplatz EDAZ.
3. `Werkzeuge/doerfer_autogen.py`: alle Siedlungen der Karte als Autogen aus LoD2. `Werkzeuge/steuerung/autogen_einbauen.py` baut sie über den Landscape Editor ein und erzeugt den Hash.
4. `ARBEITSABLAUF.md`, `PROJEKT.md`, `TODO.md`: Doku aus dem EDAZ-Projekt (Dateiformate, Datenquellen, Arbeitsweise). Gilt in weiten Teilen auch hier, beschreibt aber EastGermany3.
5. `Daten/OSM/`: OpenStreetMap-Auszüge, die die Skripte lesen (Flugplatz, Gebäude, Ortsnamen).
6. `requirements.txt` (Python-Pakete) und `Vorschau.bat` (Blender-Vorschau).

Der Condor-Pfad steht in `Werkzeuge/config.py` (Standard `C:/Spiele/Condor3`, änderbar über die Umgebungsvariable `CONDOR_DIR`), das Raster der Karte in `Werkzeuge/neukarte.py`.

## Nicht enthalten

1. Keine Condor-Dateien und kein Condor Landscape Toolkit. Gebraucht werden Condor 3 und das Toolkit (Landscape Editor).
2. Keine Rohdaten und keine gebaute Landschaft. Die Geodaten (DOP20, DGM1, bDOM, LoD2) kommen vom Server der LGB (`Werkzeuge/lgb_laden.py`). Eine Kachel braucht etwa 20 GB Platz.

## Quellen und Rechte

1. Geodaten: © GeoBasis-DE/LGB, dl-de/by-2-0.
2. `Daten/OSM/`: © OpenStreetMap-Mitwirkende, ODbL 1.0.
3. Die gebaute Landschaft wird derzeit nur intern genutzt. Für Code und Doku ist noch keine Lizenz festgelegt.
