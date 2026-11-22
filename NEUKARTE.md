# Neue Karte: Übergabe (Stand 22.11.2026)

Dieser Ordner ist eine Kopie der Werkzeuge und der Doku aus `Claude Projects\Condor3` (EDAZ in EastGermany3, GitHub intercipere/Condor-EastGer3-EDAZ). Ziel hier: ausprobieren, wie aufwendig eine komplett eigene Condor-3-Landschaft aus offenen Daten ist. Als Pilot soll erst nur der Bereich um EDAZ neu entstehen. Diese Arbeit geht nicht ins EDAZ-Repo, sondern nach GitHub intercipere/Condor3-Brandenburg.

## Warum

1. EastGermany2/GerE gehört einem Dritten. Für eine Weitergabe an den Club bräuchten Änderungen die Zustimmung des Autors. Eine eigene Karte aus LGB-Daten (dl-de/by-2-0) und eigenem Material hätte dieses Problem nicht.
2. Grobe Hochrechnung für ganz Brandenburg (~29.700 km², ~900 Patches): etwa 250 GB DOP und 35 GB DGM als Rohdaten (gemessen: 8,4 MB DOP und 1,2 MB DGM pro km²). Auf C: sind nur etwa 64 GB frei. Darum zuerst ein kleiner Pilot.

## Stand Pilot „Brandenburg“ (22.11.2026)

1. Entschieden: 1 Kachel (4 × 4 Patches, 23,04 km, laut Landscape Guide bestätigt), Name `Brandenburg`, Ordner `C:\Spiele\Condor3\Landscapes\Brandenburg`. Raster in `Werkzeuge\neukarte.py`: rechte untere Ecke UTM 33 E 388660 / N 5770840, EDAZ mittig in Patch 2/2.
2. Gebaut, ohne Landscape Editor: Gelände (`bb_gelaende.py`: `.trn`, 16 `.tr3`, 16 `.tr3f` aus DGM1), Luftbilder 8192 px (`bb_textur.py`), Waldkarten (`bb_wald.py`, Laub/Nadel-Schwelle gegen EG3 kalibriert), `.apt` mit EDAZ, `.ini`, `.obj`, `.air` (`bb_grunddateien.py`).
3. Geprüft: Gelände im EDAZ-Kern gegen EG3 im Mittel 4 cm Abweichung, Patchränder bitgleich, Texturlage gegen EG3 Korrelation 0,95–0,98 ohne Versatz, Wald 95,7 % gleich wie EG3.
4. Daten: neue LGB-Kacheln in `Daten\LGB_BB` (DGM, DOP, bDOM, LoD2), vorhandene werden aus `..\Condor3\Daten` gelesen.
5. Im Editor erzeugt: Flightplanner-Karte `.bmp`, `.tha`, `.fha`, `.aha` (zu leerer `.air`), `.oha` (ohne Autogen). „Check for missing files“: alles vorhanden.
6. Thermik (`bb_thermik.py`): `Working\ThermalMap\ThermalMap.bmp` (dort sucht der Editor), `.tdm` und `.tm3` selbst geschrieben. Der Editor legt keine erste `.tm3` an („Thermal map not loaded“), die Umwandlung im Condor Updater braucht Premium. `.tm3` = 3 Byte je 90-m-Zelle, Zeilen Süd→Nord, Spalten Ost→West: Kanal 0 = `.tdm`, Kanal 1 = 2,578 × Höhenstreuung über 27 × 27 Zellen, Kanal 2 = 127 + 0,2537 × (Höhe − Mittel über 27 × 27). Kanäle 1/2 an EG2 angepasst (Rest 0,96 bzw. 0,32 Stufen), Bedeutung in Condor ungeklärt.
7. `bb_grunddateien.py` schreibt jetzt auch `.obj` (ein `WindsackA.c3d` aus Condors `World\Objects` bei EDAZ), leere `.air`, `.ini` mit `Version=1.0` und wandelt die `.bmp` in 32 Bit wie EG3. Nach jedem Editor-Export der Flightplanner-Karte erneut laufen lassen.

### Was Condor zum Laden einer Landschaft braucht (getestet 22.11.2026)

1. Condor prüft beim Start alle Ordner in `Landscapes`. Fällt eine Landschaft durch oder lässt sie sich nicht laden, scheitert der Flugplan mit „Load flight plan error / Probably landscape not installed“, und Condor setzt den Flugplan des Piloten auf eine Standardlandschaft zurück, die womöglich nicht installiert ist. Dann öffnet der Flugplaner nicht mehr. Abhilfe: `Documents\Condor3\Pilots\<Pilot>\Flightplan.fpl` durch einen gespeicherten Plan einer installierten Landschaft ersetzen.
2. Im Landschaftsordner: `.trn`, `.bmp` (32 Bit, gleiche Maße wie die `.trn`), `.tm3`, `.tdm`, `.obj`, `.apt`, `.cup`, `.air`, `.aha`, `.tha`, `.fha`, `.oha`, `.ini`. Ohne `<Name>.cup` meldet Condor beim Auswählen „<Name> landscape not installed / corrupted.“ Weder `scenerycheck3` noch der Landscape Guide nennen die `.cup`. Condor liest sie ab der zweiten Zeile, darum schreibt `bb_grunddateien.py` eine Kopfzeile.
3. `Version` in der `.ini` ist nur eine Anzeigenummer (Landscape Guide).
4. Objekte der `.obj` sucht Condor in `Landscapes\<Name>\World\Objects`. Zu jedem Flugplatz der `.apt` erwartet `scenerycheck3` `Airports\<Name>G.c3d`, `<Name>O.c3d` und `<Name>.grs` (die erzeugt Condor beim ersten Laden selbst). `Textures\empty.dds` muss vorhanden sein.
5. `.tdm`: 8 Byte Kopf mit Breite und Höhe in Zellen wie die `.trn`, danach 1 Byte je Zelle.

### Weiter offen

1. Erledigt 22.11.: `bb_flugplatz.py` kopiert G-Datei und Gebäudetexturen aus EG3 und schreibt die O-Datei ohne Windsack-Markierung und Mast aus EG2, dafür mit eigenen an derselben Stelle (70 m links der Piste vom Flugplatzpunkt). Noch nicht in Condor angesehen.
2. Farbkante an der Bildfluggrenze 2024/2025 (Hochwert 5784 km, direkt südlich von EDAZ, Screenshot 22.11., 18:51). `bb_textur.py` gleicht die Flüge jetzt per Quantil-Tabelle je Kanal an statt linear (Verstärkung bis 1,9 hatte helle Felder fast weiß gemacht: 0,81 % → 0,01 % fast weiße Pixel in 2023/2025). Die Stufe direkt an der Grenze bleibt (Median 27 Stufen, roh wie linear wie Quantil; davon nur 4–5 Stufen systematisch, Rest sind andere Feldinhalte 2024/2025), darum kein weicher Übergang. Neu gebaut 22.11. (Texturen, Flugplatz-Untertextur, Wald: im Mittel 0,97 % der Waldkarten-Bytes geändert, max 3,3 %; Thermik 0,23 %). Danach im Editor Flightplanner-Karte und FHA, dann `bb_grunddateien.py`.
2a. Harte Kante am Rand der Grass3D-Fläche von EDAZ (Screenshot 22.11., 18:26): Die Unter-Textur aus EG3 war an die EG3-Farben angeglichen. `bb_flugplatz.py` baut sie jetzt aus DOP20 mit der Farbumrechnung von `bb_textur.py` (0,625 m/px, so scharf wie in EG3), Alpha (Grashöhe) aus EG3. Farbe gegen die Patch-Textur im Mittel 1,2 Stufen, Versatz gegen EG3 0 px. Kante laut Screenshot 18:34 weg (damals noch aus der Patch-Textur abgetastet, Piste unschärfer); DOP-Fassung noch nicht in Condor angesehen.
2b. Dörfer (22.11.): `doerfer_autogen.py` und `autogen.py` rechnen jetzt im Brandenburg-Raster (Gelände aus den TR3F, Patch aus `neukarte`). Schönhagen 302, Ahrensdorf 194, Löwendorf 27 Gebäude, alle in Patch 2/2 → `Working\Autogen\o002002.obj`. Texturen `BBDorf_*.dds` liegen in `Autogen\Textures`. Geprüft: Gelände minus LoD2-Boden Median 0,14 m, Streuung 0,40 m (bei 22,5 m Versatz 0,54–0,80 m), Anhebung max 3,6 m wie in EG3 (3,8 m). Eingebaut mit `steuerung/autogen_einbauen.py ../Daten/Arbeit_BB/Autogen` (Editor mit Brandenburg offen): `Autogen\o002002.c3d` (32.966 Dreiecke), OHA-Zeile `002002 c9d633f8…`, „Autogen c3d files and hashlist OK“. Sicherung vorher in `Daten\Arbeit_BB\Sicherung_vor_Autogen_20261122`. In Condor noch nicht angesehen. Trebbin (22.11.): Gruppe in `doerfer_autogen.GRUPPEN` (OSM node 60122712, Radius 800 m), LoD2 aus allen `nk.LGB_ORDNER` (`edaz_gebaeude.lies_gebaeude(gebiet, ordner)`). Erster Einbau hatte nur 3.218 Gebäude: LoD2 wurde nur bis Radius + 400 m gelesen, der Osten Trebbins fehlte. Jetzt `LESE_PUFFER` 3 km und eine Prüfung, die abbricht, wenn eine Siedlung bis an den Leserand reicht (Bruchtest mit 400 m greift). Neu: 3.820 Gebäude, 3.564 in Patch 1/2 (`o001002.obj`, 201.552 Dreiecke), 256 in 2/2; die übrigen Dörfer unverändert. Gelände minus LoD2-Boden Median 0,08 m, Streuung 0,21 m. Noch nicht eingebaut (Editor nötig). Bildrate lässt sich in Condor nicht anzeigen.
3. `config.LAND` zeigt auf Brandenburg. Die alten EDAZ-Skripte (`waldkarte.py`, `objektliste.py`, `edaz_*.py`, `ring_*.py`; nicht mehr `doerfer_autogen.py`) rechnen im EG2-Raster und dürfen hier nicht laufen (nicht im Code gesperrt).
4. Reihenfolge zum Neubauen: `bb_gelaende.py`, `bb_textur.py`, `bb_wald.py`, `bb_thermik.py`, Editor (Flightplanner-Karte, THA, FHA, AHA, OHA), `bb_grunddateien.py`, `bb_flugplatz.py`.

## Vorsicht beim Start

1. `Werkzeuge\config.py` zeigt mit `LAND` seit 22.11.2026 auf `Landscapes/Brandenburg`. EastGermany2 und EastGermany3 hier nicht verändern.
2. Viele Skripte haben Patches und Gitterursprünge fest eingebaut, für EG2 (`gelaende.E0, N0`, `PATCHES`, `GRID_W/GRID_N0` in `edaz_flaechen.py`, `ring_textur.py`). In einer neuen Landschaft gelten andere Ursprünge.
3. Die Rohdaten sind **nicht** mitkopiert (26 GB). Sie liegen in `Claude Projects\Condor3\Daten\`: `LGB` (EDAZ-Kern), `LGB_Ring` (DOP, DGM, bDOM, LoD2 für Rechtswert 363–380, Hochwert 5777–5794, UTM 33), `Arbeit` (Zwischenstände). Die Skripte lesen `Daten\` relativ zum Projektordner. Entweder Pfade umstellen oder gezielt kopieren. Keine Verzeichnis-Junctions anlegen, ein `rm -rf` darauf löscht die Originale. Mitkopiert ist nur `Daten\OSM`.
4. Den Landscape Editor und Condor nur nach Rückfrage starten. Sie öffnen Fenster, getestet wird in Condor von Hand. Die Landschaft im Editor nie per Skript umschalten.

## Was wir über Condor 3 wissen (gemessen, nicht nur gelesen)

1. **Grobes Gelände** `HeightMaps\hCCRR.tr3`: 193×193 uint16 in ganzen Metern, ohne Kopf, `np.rot90(raster[y, x], 3)`. 30-m-Raster, Patch 5760 m.
2. **Feines Gelände** `HeightMaps\22.5m\hCCCRRR.tr3f`: 257×257 float32, ohne Kopf, `np.rot90(raster[y, x], 1)`. Bitgenau gegen die Editor-Ausgabe geprüft. Condor liest nur 6-stellige Namen (`h%0.3d%0.3d.tr3f`).
3. **Hashes:** Nach jeder Änderung an `.tr3`/`.tr3f` im Editor „Export terrain hash (THA)“ ausführen. Nach Wald `FHA`, nach Autogen `OHA`. Ein falscher Hash zeigt sich nicht als Fehlermeldung. Der Cheat-Schutz lässt dann den Knüppel im Cockpit springen (am 22.11. so gefunden, siehe `TODO.md` 2a).
4. **Flugplätze:** Geneigte Pisten sind erlaubt (`AirportsInV3.pdf`). Die G-Datei bezieht sich auf die `.apt`-Höhe. Condor erzeugt `Airports\<Name>.grs` (Gras-Cache) beim Start selbst aus der Grass3D-Fläche. Format von `.apt`, `.c3d`, G-Datei-Koordinaten: siehe `PROJEKT.md`.
5. **Editor-Menü** (`python Werkzeuge\steuerung\landscape_editor.py liste`): New landscape, Save landscape, Export forest maps (FOR), Export thermal map (TM3), Export flightplanner map (BMP), Export textures to DDS, Export TRN from TR3, Export terrain OBJ from TR3, Export TR3 from modified terrain OBJ, Import tile size textures, Import tile size forest maps, Import V2 albedo map (TDM), Export field map to tile size tiles, die vier Hash-Exporte, Check for missing files, Check autogen files and hashlist. Wie „New landscape“ funktioniert (Eingaben, Größen), ist noch nicht ausprobiert.
6. **Was schon funktioniert und übertragbar ist:** Luftbild-Patches aus DOP (`patch_textur.py`, `ring_textur.py`, etwa 13 s pro Patch), Waldkarten aus Luftbild und bDOM (`waldkarte.py`, `ring_wald.py`), DGM1 nach TR3F (`edaz_gelaende.py`), Flugplatzflächen und Gebäude aus OSM und LoD2, Dörfer als Autogen, Baumtextur, Blender-Vorschau.

## Regeln aus dem EDAZ-Projekt, die weiter gelten

1. Nur offene Daten mit Quellenangabe („© GeoBasis-DE/LGB, dl-de/by-2-0“), eigene Fotos oder prozedural erzeugte Inhalte. `EDAZ Fotos\` sind Screenshots einer kommerziellen FS2024-Szenerie, nur zur Orientierung, nie als Textur oder Modell.
2. Erst Doku lesen: diese Datei, dann `PROJEKT.md`, `ARBEITSABLAUF.md`, `LOKAL.md` und die beiden PDFs.
