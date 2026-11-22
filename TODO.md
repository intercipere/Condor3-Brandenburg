# TODO: was noch zu tun ist

Sammelliste für alle, die mitarbeiten wollen. Stand: 17.11.2026. Details zu den einzelnen Punkten stehen in `PROJEKT.md` (Bauliste, Offene Punkte, Erkenntnisse) und `ARBEITSABLAUF.md` (Reihenfolge der Skripte). Wer einen Punkt anfängt, trägt das bitte hier ein (Name und Datum), damit niemand doppelt arbeitet.

## 1. Lücken im Repo

1. Download-Skript für die LGB-Kacheln (Dateinamen siehe `ARBEITSABLAUF.md`).
2. Die OSM-Auszüge (`Daten\OSM`) ins Repo, mit ODbL-Quellenangabe.
3. Klären und beschreiben, wie `Airports\Schoenhagen.grs` (40 MB) entsteht.
4. Link zum Condor Landscape Toolkit in `ARBEITSABLAUF.md` ergänzen.
5. Prüfen, was `scenerycheck3.exe` zur Landschaft meldet, und das Ergebnis festhalten.
6. Blender-Vorschau: Die Kamera „vorfeld“ sitzt auf Dachhöhe und muss tiefer.

## 2. In Condor ansehen und prüfen

1. Klären, ob Condor die Höhenkacheln `.tr3f` mit 6- oder 4-stelligem Namen liest, dann die doppelten Dateien entfernen.
2. Prüfen, ob Condor eigene Meshes (z. B. aus DOM und DOP20) als Landschaftsobjekte akzeptiert, und ob die Dateiprüfung bei Online-Flügen geänderte Spieldateien bemängelt.
3. Den Start des Landscape Editors durch `steuerung/landscape_editor.py start` testen, wenn der Editor noch nicht läuft (bisher nur mit laufendem Editor getestet).

## 2a. Knüppelzittern um EDAZ: behoben (22.11.2026)

Symptom: Der Knüppel im Cockpit springt schnell zwischen Ausschlag und Mitte, nur um EDAZ in EG3.

Ursache: Der Gelände-Hash `EastGermany3.tha` war noch der von EG2 (bytegleich). Condors Cheat-Schutz prüft auch die `.tr3f` in `HeightMaps\22.5m` und reagiert mit springendem Knüppel. Bisektion: Jede `.tr3f` löst es aus, auch mit EG2-Inhalt. Ohne `.tr3f`, aber ohne Autogen bei passender `.oha`, zitterte es aus demselben Grund. Die offizielle Anleitung (Condor V3 Airport Construction, downloads3.condorsoaring.com/CLT/AirportsInV3.pdf) verlangt nach TR3F „Export Terrain hash (THA)“. Geneigte Pisten sind dort ausdrücklich erlaubt, Einebnen ist nicht nötig.

Stand: Alles ist zurück auf dem Stand vom 17.11. (DGM1-Gelände, `.apt` 41 m, eigene G-/O-Dateien, Autogen). Nur die 4-stelligen `.tr3f`-Kopien sind entfernt. Die THA ist im Editor neu exportiert, die Autogen-Prüfung ist OK.

Bestätigt: Mit neuer THA ist das Zittern weg (Testflug 22.11.). Die Testsicherungen sind gelöscht.

## 3. Inhalte für EDAZ

Die vollständige Liste steht im Abschnitt „Bauliste EDAZ“ in `PROJEKT.md`. Offen sind unter anderem:

1. Weitere Gebäudearten: Tower-Komplex in Kalksandstein, Hangar P1 mit Rolltoren.
2. Denkmäler (Do 27 im Zebra-Look, Schulgleiter auf Mast) und Umgebung (Baumreihen, Teich, Zäune).
3. Eigene Fotos vom Platz (frontal, bedeckter Himmel). Sie sind die beste Quelle für Fassaden. Dazu Fotos vom Geflügelhof Löwendorf (Giebel, Silos), dessen Silos und Lüfter bisher geschätzt sind.
4. Die Commons-Fotos zum Flugplatz von Hand laden (der automatische Download scheiterte am Rate-Limit), mit Urheber und Lizenz.
5. Vorfeldmarkierungen ins Bodenluftbild.

## 4. Orientierungspunkte und Umgebung

Wunschliste für die Landschaft rund um EDAZ, vor allem Dinge, die man aus dem Segelflugzeug zur Orientierung nutzt:

1. Mehr Orientierungspunkte als 3D-Objekte: Sandgrube, Aussichtsturm, Windräder mit korrekten Positionen und weitere markante Punkte.
2. Mehr Dörfer als LoD2-Autogen, vor allem südlich von EDAZ sowie Luckenwalde und Trebbin (bisher nur Schönhagen, Ahrensdorf und der Geflügelhof Löwendorf).
3. Straßen besser darstellen.
4. Solarfelder.
5. Sanddüne westlich von Luckenwalde.
6. Sperenberg. Was dort genau dargestellt werden soll, ist noch festzulegen.

## 5. Karte erweitern

1. Ring aus scharfen Luftbildern und neuem Wald um EDAZ (3 × 3 Patches): gebaut und eingebaut am 18.11.2026, in Condor noch ansehen.
2. Datenaufbereitung automatisieren (laden, nach UTM umrechnen, Farben angleichen, Patches erzeugen), dann Kachel für Kachel erneuern. Die Patches stehen bisher fest in den Skripten.

## 6. Ideen, bisher zurückgestellt

1. **Mehr Wolkenvariation:** Es gibt nur 9 Wolkenmodelle und einen Textur-Atlas, und Wolken wirken nur global (nicht pro Landschaft). Siehe „Wolken und Shader“ in `PROJEKT.md`.
2. **Shader-Änderungen:** Condor lädt `Effects\fx\<Name>.fx` im Klartext, der Originalquelltext liegt aber nicht vor.
3. **Weitergabe der gebauten Daten:** Ein Release-Paket mit den eigenen Dateien (Texturen, Höhenkacheln, Flugplatz-, Autogen-Dateien, Waldkarten) und ein Installer, der `EastGermany3` neben `EastGermany2` anlegt (Hardlinks, ungetestet) und die abgeleiteten Dateien (`.obj`, `.apt`, Hash-Zeilen in `.fha` und `.oha`, `Drevesa.dds`) aus der EG2 des Mitglieds erzeugt. Aktuell nur in der Gruppe genutzt, daher zurückgestellt. Die Daten kämen in ein eigenes Repo oder ein Release, nicht in dieses Repo (Größe etwa 275 MB).
