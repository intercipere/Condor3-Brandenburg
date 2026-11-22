# Arbeitsablauf EastGermany3 / EDAZ

Diese Datei beschreibt, was man installieren muss und in welcher Reihenfolge die Skripte laufen. Sie richtet sich an Menschen und an KI-Agents, die an der Landschaft mitarbeiten. Hintergrund, Dateiformate und Messwerte stehen in `PROJEKT.md`.

Stand: 17.11.2026. Die Reihenfolge ist aus den Abhängigkeiten der Skripte abgeleitet und wurde nicht als Ganzes auf einem frischen Rechner durchlaufen. Wo etwas ungeprüft ist, steht es dabei.

## 1. Voraussetzungen

1. **Windows.** Getestet wurde unter Windows 11. Die Editoren des Condor-Toolkits laufen nur dort.
2. **Condor 3** mit dem **Landscape Toolkit** (`LandscapeEditor.exe`, `ObjectEditor.exe`, `scenerycheck3.exe`). Die Toolkit-Programme müssen im Condor-Ordner liegen, sonst starten sie nicht. Den Download-Link bitte beim Condor-Team erfragen, er steht noch nicht in dieser Doku.
3. **Eine unveränderte Landschaft `EastGermany2`** in `Landscapes\`. Sie wird nie verändert, nur als Vorlage gelesen.
4. **Python 3.12** und die Pakete aus `requirements.txt`: `pip install -r requirements.txt`.
5. **Blender 5.3** nur für `Vorschau.bat` und `kiefer_blender.py`.
6. **Platz:** Die Rohdaten brauchen gepackt etwa 2,9 GB und entpackt noch einmal so viel, zusammen etwa 6 GB (`Daten\LGB`). Die Arbeitskopie `EastGermany3` braucht etwa 16 GB, wenn man sie kopiert.

## 2. Einrichten

1. **Projekt holen:** Repo klonen, die Skripte liegen in `Werkzeuge\`.
2. **Condor-Pfad:** Die Skripte erwarten Condor unter `C:/Spiele/Condor3`. Anderer Ort: Umgebungsvariable `CONDOR_DIR` setzen, zum Beispiel `set CONDOR_DIR=D:/Games/Condor3`. Alle Pfade stehen in `Werkzeuge\config.py`.
3. **Arbeitskopie anlegen:** Den Ordner `Landscapes\EastGermany2` nach `Landscapes\EastGermany3` kopieren und alle Dateien `EastGermany2.*` im Hauptordner in `EastGermany3.*` umbenennen. Einmal in Condor laden und prüfen, dass die Landschaft startet. Ein Installer mit Hardlinks statt Kopie ist geplant, aber nicht gebaut.
4. **Rohdaten:** Es gibt noch kein Download-Skript. Die Dateien lädt man von https://data.geobasis-bb.de/geobasis/daten/ (Lizenz dl-de/by-2-0, Quellenangabe „© GeoBasis-DE/LGB, dl-de/by-2-0“) nach `Daten\LGB`:
   1. `dop\dop_33<Rechts>-<Hoch>.zip` (Luftbild), `dgm\dgm_...zip` (Gelände), `bdom\bdom_...zip` (Oberflächenmodell), `lod2\lod2_...zip` (Gebäude, auf dem Server im Ordner `3d_gebaeude/lod2_gml/`). Die Zahlen sind Rechtswert und Hochwert der 1-km-Kachel, zum Beispiel `dop_33368-5782.zip`.
   2. Abgedeckt sein muss Rechtswert 368–380, Hochwert 5782–5788 (UTM 33). Die Skripte entpacken selbst nach `dop_jpg`, `dgm_tif` und `bdom_tif`.
   3. `Daten\OSM\` enthält vier JSON-Auszüge von OpenStreetMap. Die Skripte lesen nur `edaz_aeroway.json` und `edaz_bauten.json`. `doerfer_landuse.json` und `places.json` liest kein Skript im Repo, sie sind Hilfsdaten. Die Dateien sind noch **nicht** im Repo, siehe Abschnitt 7.

## 3. Reihenfolge der Skripte

Alle Aufrufe im Ordner `Werkzeuge\`. Die Patches 40/39 und 39/39 (EDAZ und Ahrensdorf) stehen fest in den Skripten (`PATCHES`).

1. **Luftbild:** `python patch_textur.py <pixel> <ausgabeordner> <spalte,zeile> [<spalte,zeile> ...]`, zum Beispiel `python patch_textur.py 8192 ..\Daten\Arbeit 40,39 39,39`. Alle Patches müssen in derselben Reihe liegen. Das Skript liest die alten Texturen aus `EastGermany2`, schreibt `t4039_8192.png` und `t3939_8192.png` und dazu `mosaik.npy` und `mosaik_flug.npy`. Diese beiden Dateien müssen im Ordner `Daten\Arbeit` landen, weil `edaz_flaechen.py` und `waldkarte.py` sie dort lesen. Danach `python dds_dxt1.py <png> <dds>` und die DDS nach `EastGermany3\Textures\t<SS><ZZ>.dds` legen.
2. **Gelände:** Im Landscape Editor das 22,5-m-Gelände als OBJ exportieren (nach `Working\HeightMaps\22.5m`). Dann `python edaz_gelaende.py` (schreibt nach `...\22.5m\Modified`). Anschließend wandelt der Landscape Editor die OBJ in `.tr3f` um. Die `.tr3f` liegen in `HeightMaps\22.5m`, jede Datei mit 6-stelligem und 4-stelligem Namen (siehe `PROJEKT.md`, Stand EDAZ, Punkt 2).
3. **Wald:** `python waldkarte.py` (schreibt `ForestMaps\<SS><ZZ>.for`). Danach `LandscapeEditor.exe -hash EastGermany3`, das aktualisiert die Hashes in `.fha` und `.tha`.
4. **Flugplatzflächen:** `python edaz_flaechen.py` (liest Flugplatzpunkt, Höhe und Richtung aus `EastGermany3.apt`, schreibt `Daten\Arbeit\EDAZ\SchoenhagenG.c3d`, die Unter-Textur und `kontrolle_flaechen.png`). Die Dateien kommen nach `EastGermany3\Airports`. Flugplatzhöhe in der `.apt` laut `PROJEKT.md` setzen. Die Grasdatei `Airports\Schoenhagen.grs` (40 MB) erzeugt keines unserer Skripte. Wie sie entstanden ist, ist nicht dokumentiert (vermutlich ein Export im Editor), das muss noch geklärt werden.
5. **Flugplatzgebäude:** `python edaz_gebaeude.py` (schreibt `SchoenhagenO.c3d`, die Dach- und Wandtexturen und `kontrolle_daecher.png` nach `Daten\Arbeit\EDAZ`). Die Texturen kommen nach `Airports\Textures`.
6. **Objektliste:** `python objektliste.py --pruefen` prüft nur, ohne `--pruefen` schreibt es `EastGermany3.obj`.
7. **Dörfer (Autogen):** `python doerfer_autogen.py` (schreibt `Working\Autogen\o<Patch>.obj/.mtl` und Texturen nach `Daten\Arbeit\Autogen`). Dann `python steuerung/autogen_einbauen.py ../Daten/Arbeit/Autogen`. Das Skript steuert den Landscape Editor: „File > Export autogen C3D from OBJ“, C3D nach `EastGermany3\Autogen` und Texturen nach `Autogen\Textures` kopieren, „File > Export autogen hash (OHA)“ und die Prüfung „Check autogen files and hashlist“. Danach vergleicht es die `.oha` mit dem Autogen-Ordner und bricht bei jeder Abweichung ab. Vorher die Landschaft sichern.
8. **Baumtextur:** Kieferngruppe rendern mit `blender -b --python kiefer_blender.py -- <kiefer.png> [seed]` (Standard und eingebaut: Seed 7, etwa 10 Sekunden), dann `python baumtextur.py <kiefer.png> <Condor-Ordner>\Landscapes\EastGermany3\World\Textures\Drevesa.dds`. Das Ziel liegt im Landschaftsordner, nicht im globalen `World`. Das Skript liest die globale `<Condor-Ordner>\World\Textures\drevesa.dds` nur als Vorlage für den Laubbaum und ändert sie nicht, solange das Ziel ein anderer Pfad ist. Nie das Ziel auf die globale Datei legen.
9. **Fassadentexturen:** `python fassaden.py <ordner>` schreibt Beispielbilder zur Kontrolle. Die Gebäudeskripte rufen `fassaden.py` selbst auf.
10. **Vorschau:** `Vorschau.bat` baut eine Blender-Szene aus den eingebauten Dateien (Blender-Pfad in der Datei anpassen).
11. **Ring um EDAZ** (die 7 Patches um den Kern, stehen fest in `ring_textur.py`): `python lgb_laden.py 363 380 5777 5794 ..\Daten\LGB_Ring` lädt DOP, DGM, bDOM und LoD2. Für Gebäude, die von außen hineinragen, zusätzlich `python lgb_laden.py 362 381 5776 5795 ..\Daten\LGB_Ring lod2`. Dann `python ring_textur.py` (etwa 1,5 Minuten, beim ersten Lauf etwas länger; die Rohbilder liegen dann als Zwischenspeicher in `Daten\Arbeit\Ring\Cache`, nach Änderungen an `roh_bauen` oder neu geladenen DOP-Kacheln den Ordner löschen; schreibt `t<SS><ZZ>.dds` und `flug_<SS><ZZ>.npy` nach `Daten\Arbeit\Ring`) und `python ring_wald.py` (schreibt `<SS><ZZ>.for` dorthin). Die Dateien nach `Textures` und `ForestMaps` kopieren, danach `-hash`.

## 4. Prüfen

1. **Toolkit:** `scenerycheck3.exe` prüft die Landschaft. Ein Ergebnis dazu ist hier noch nicht festgehalten.
2. **In Condor:** Flug auf EDAZ starten. Zum Neuladen reicht „Flug beenden, im Flugplaner neu starten“, Condor muss nicht neu gestartet werden.
3. **Skriptkontrollen:** Die Gebäude- und Flächenskripte schreiben `kontrolle_*.png` nach `Daten\Arbeit\EDAZ`.
4. **Automatische Tests gibt es nicht.** Jede Änderung an einem Format oder einer Geometrie bitte gegen Originaldateien oder Messwerte prüfen, nicht nur gegen den eigenen Code.

## 5. Regeln für alle, die mitarbeiten

1. `EastGermany2` und die Dateien im Condor-Ordner bleiben unverändert. Gearbeitet wird nur in `EastGermany3`. Vor größeren Änderungen eine Sicherung anlegen.
2. Nach jeder Änderung an Wald oder Gelände `LandscapeEditor.exe -hash EastGermany3` ausführen, nach Autogen-Änderungen den OHA-Export. Nach Änderungen an den `.tr3f` zusätzlich im Editor „Export terrain hash (THA)“ (`python steuerung/landscape_editor.py menue "Export terrain hash (THA)"`), sonst springt der Knüppel. Condor prüft die Hashes auch im Freiflug.
3. Keine fremden Texturen oder Modelle verwenden, auch nicht aus FS2024-Screenshots. Erlaubt sind eigene Fotos, offene Daten mit Quellenangabe (LGB dl-de/by-2-0) und prozedural erzeugte Inhalte.
4. Keine Landschaftsdateien von EastGermany2, keine Condor-Dateien und keine Rohdaten ins Repo. Gebaute Ergebnisse gehören in ein Release, nicht in die Git-Historie (Dateien über 100 MB nimmt GitHub nicht).
5. Neue Erkenntnisse zu Dateiformaten mit Messwert in `PROJEKT.md` eintragen.

## 6. Hinweise für KI-Agents

1. Lies zuerst `PROJEKT.md` und dann diese Datei. Frage nach, bevor du Condor, den Landscape Editor oder den ObjectEditor startest, sie öffnen Fenster auf dem Rechner der Person.
2. Die Editoren lassen sich nur über Fensternachrichten und Mausklicks steuern, es gibt keine Kommandozeile außer `-hash`. Die Hilfsskripte liegen in `Werkzeuge\steuerung`:
   1. `landscape_editor.py`: Landscape Editor ohne Maus starten, Landschaft wählen, Menüpunkte über ihre Beschriftung auslösen (`start`, `liste`, `pruefen`, `menue "<Menüpunkt>"`). Ja/Nein-Rückfragen beantwortet es nie automatisch.
   2. `autogen_einbauen.py`: Autogen-Export samt Hash und Gegenprobe (siehe Abschnitt 3, Schritt 7).
   3. PowerShell für Condor und Sonderfälle: `shot.ps1` (Screenshot), `taste.ps1` (Taste als Scancode), `click.ps1` (Mausklick), `front.ps1` (Fenster nach vorn), `okdialog.ps1` (OK-Meldungen schließen) und `win.ps1` (gemeinsame Funktionen, z. B. `Dump-Menu` für die Menü-IDs).
3. Condor ignoriert simulierte Mausbewegungen, Tasten müssen als Scancodes gesendet werden (Details in `PROJEKT.md`, Erkenntnis 7).
4. Behaupte nicht, dass etwas funktioniert, ohne es ausgeführt zu haben. Prüfwerte aus Originaldateien oder Messungen herleiten, nicht aus dem getesteten Code.
5. Setze keine Pfade im Code fest, sondern nutze `config.py`.

## 7. Offene Punkte

Was noch fehlt, steht in `TODO.md`.
