# Condor 3: EastGermany3 und EDAZ Schönhagen

Stand: 17.11.2026

## Ziel

1. EDAZ Schönhagen in Condor 3 deutlich schöner und genauer machen: eigene 3D-Gebäude, echte Häuser in der Umgebung, besseres Bodenluftbild.
2. Die Landschaft EastGermany2 schrittweise als **EastGermany3** erneuern. Die Methode wird zuerst an EDAZ erprobt und danach Kachel für Kachel ausgeweitet.

## Was geht und was nicht

1. **Photogrammetrie ist grundsätzlich möglich, aber nicht mit dem offiziellen Toolkit.** Das Toolkit kann nur Höhenmodelle und Luftbilder. Mit einem eigenen Compiler lässt sich Photogrammetrie (z. B. aus 3D Tiles) in eine native Condor-Landschaft umwandeln. Gebäude und Bäume sind dann echte 3D-Meshes. Voraussetzung ist, dass die Dateiformate des Spiels bekannt sind, die wichtigsten sind inzwischen entschlüsselt (siehe Erkenntnisse 8). Das Urheberrecht der Quelldaten begrenzt die Weitergabe.
2. **Möglich ist eine moderne Fotolandschaft.** Dazu gehören ein genaues Gelände (DGM1), aktuelle Luftbilder, Wald und Gebäude aus OSM- bzw. Katasterdaten und Thermikkarten.
3. **Echte Häuser um EDAZ:** Die freien LoD2-Gebäudemodelle aus Brandenburg haben richtige Grundrisse, Höhen und Dachformen. Die Dächer werden aus dem Luftbild texturiert, die Fassaden generisch. Realistischer Umkreis: 5–10 km.
4. **Performance:** Gebäude müssen pro Patch zu wenigen Objekten zusammengefasst werden, mit einer gemeinsamen Textur und vereinfachter Geometrie. Tausende Einzelobjekte bremsen Condor aus.
5. **Bäume:** Wälder erzeugt Condor selbst aus den Waldkarten. Die Baumtextur lässt sich pro Landschaft austauschen (bestätigt am 17.11.2026). Baumreihen, Alleen und Hecken lassen sich als eigene Objekte setzen.
6. **Innenräume weglassen:** Turmkanzel, Foyer und Hangar innen sieht man in Condor nie.

## Analyse EastGermany2

1. **Raster:** Ursprung (rechts unten) bei UTM 33N, Rechtswert 605160, Hochwert 5558120. Spalten zählen von Ost nach West, Zeilen von Süd nach Nord. Patch-Dateien heißen `tSSZZ` (Spalte, Zeile).
2. **EDAZ** liegt im Patch **t4039** am Ostrand. Der Flugplatz reicht in **t3939** hinein, beide Patches müssen erneuert werden. Flugplatzeintrag in `.apt`: 52,2032 N, 13,16 E, 40 m Höhe (in EG3 auf 41 m gesetzt), Pistenlänge 1500 m.
3. **Texturen:** echte Luftbilder mit 2,8 m pro Pixel, aus der Höhe stimmig. Laut Skript stammen sie aus einem SAS.Planet-Cache, also vermutlich von einem kommerziellen Kachel-Dienst. Die Lizenz ist damit unklar.
4. **Gelände:** USGS-Höhendaten (vermutlich SRTM), 30-m-Raster, 193 × 193 Punkte pro Patch in ganzen Metern. Um EDAZ liegen die Werte zwischen 30 und 85 m. SRTM enthält Baumhöhen teilweise mit, deshalb wirken Wälder leicht erhöht. DGM1 wäre ein deutlicher Gewinn.
5. **Wald:** aus OSM, 11,25 m pro Pixel, nur zwei Klassen (Nadelwald und sonstiger Wald).
6. **Herkunft:** Die Landschaft wurde ursprünglich für Condor 2 gebaut, von Felix Hupfeld (Drh, condor-club.eu), Michel Bernard und Claude Simonneaud. Gelände, Texturen und Wald hat das Skript `create_landscape.py` erzeugt, Strommasten und Windräder `osm_to_objects.py`. Beide liegen unter github.com/flxhu/condor2.
7. **Format und Größe:** Die Dateien sind schon im Condor-3-Format (`.tr3`, `.tm3`). Ein Condor-3-Update heißt also, die Inhalte zu erneuern, nicht das Format zu konvertieren. 14 × 22 Kacheln zu 23,04 km, also etwa 320 × 500 km, das sind 4928 Patches zu 5,76 km. Texturen 2048 × 2048 px (DXT1) pro Patch, etwa 2,8 m pro Pixel.
8. **EDAZ im Original:** `Airports\SchoenhagenO.c3d` (1,5 KB) enthält nur Windsäcke, die Hallen standen als Objekte in der Objektliste. `SchoenhagenG.c3d` (4 KB) enthält Piste und Bodenflächen.
9. **Fazit:** brauchbare Grundlage, darauf aufbauen. EDAZ selbst hat keine Gebäude und ein grobes Gelände. Die Analysebilder liegen in `Referenz\EG2-Analyse`.

## Offizielle Arbeitsabläufe (laut Doku)

1. **Flugplatz** (siehe `AirportsInV3.pdf`):
   1. Die G-Datei enthält die Flächen (Grass3D, Asphalt, Markierungen, Gravel) auf einem feineren 22,5-m-Geländeraster mit Kommazahlen (TR3F).
   2. Die O-Datei enthält die Gebäude und funktioniert wie in Condor 2.
   3. Für Patches mit Flugplatz darf die Textur größer als 2048 px sein, also 4096 oder 8192 px. Bei 8192 px sind das 0,7 m pro Pixel.
   4. Ablauf: Der Landscape Editor exportiert das Gelände als 22,5-m-OBJ. Das wird in Blender geglättet, wir setzen stattdessen DGM1 direkt ein. Der Landscape Editor wandelt es in TR3F zurück. Danach Pistenausrichtung, Flugplatz-Eigenschaften, Flächen als OBJ, ObjectEditor und am Ende C3D.
2. **Autogen-Gebäude:** Mit dem Condor OSM Exporter (Blender + blosm) entstehen pro Patch automatisch OSM-Gebäude mit Texturen. Der Landscape Editor wandelt sie mit „Export autogen C3D from OBJ“ um, sie landen in `<Landschaft>\Autogen`. EG2 hat **keinen** Autogen-Ordner, also keine Gebäude in der Fläche. EG3 hat Autogen für die Patches 40/39 und 39/39 (siehe „Autogen und Dörfer“).
3. **Eigene Einzelobjekte** wie markante Punkte: Patch im PatchViewer in Blender laden, Objekt einsetzen, als Autogen exportieren.
4. **Arbeitsteilung:** Daten, Python und Blender laufen per Skript. Den Landscape Editor steuern die Skripte in `Werkzeuge\steuerung` über Win32-Nachrichten (`landscape_editor.py`, `autogen_einbauen.py`). Getestet wird in Condor.

## Entschlüsselte Formate und eigene Werkzeuge (`Werkzeuge\`)

1. **Koordinaten:** Die Condor-Position zählt PosX = 605160 − Rechtswert (nach Westen) und PosY = Hochwert − 5558120. Der Patch ist floor(Pos/5760). Gegen die Statusleiste des Landscape Editors geprüft, Lat/Lon stimmen exakt.
2. **`.tr3`:** 193 × 193 Werte als int16 (30-m-Raster, ganze Meter).
3. **22,5-m-OBJ des Editors:** 257 × 257 Punkte, Ursprung in der Patch-Mitte, x nach Osten, y nach Norden. Gegen DGM1 geprüft, die Korrelation liegt bei 0,87 gegenüber höchstens 0,43 bei allen anderen Achsrichtungen.
4. **`.tr3f`:** 257 × 257 float32 ohne Kopf, entspricht `np.rot90(raster[y, x], 1)`. Gegen die Ausgabe des Editors geprüft, exakt gleich. Die Skripte schreiben es deshalb selbst.
5. **Patch-Texturen:** DDS mit DXT1 und vollständiger Mipmap-Kette. `dds_dxt1.py` erzeugt einen Kopf, der Byte für Byte dem Original entspricht, mit gleicher Dateigröße.
6. **`.c3d` (Objekte, Flughafen-G/O-Dateien):** `'C3D'` + uint32 1, 0, n, n (n = Objektanzahl). Pro Objekt: Name (Pascal-String), uint32 VertexStart, VertexAnzahl, IndexStart, IndexAnzahl, Textur (Pascal-String, relativ zum Ordner der C3D, also `Airports` bzw. `Autogen`), 6 float Material (R, G, B, A, Spec, Shiny), uint32 0. Danach uint32 Vertexanzahl, je Vertex 8 float (x, y, z, nx, ny, nz, u, v), dann uint32 Indexanzahl und uint32-Indizes. Gelesen und geschrieben mit `c3d.py`; die Rundreise über 128 Dateien ist byteidentisch.
7. **G-Datei-Koordinaten:** Ursprung ist der Flugplatzpunkt aus der `.apt`, +y zeigt in Pistenrichtung (Gitter-Nord), +x nach Richtung −90°, das System ist also gespiegelt. z bezieht sich auf die Flugplatzhöhe. UV nach DirectX-Konvention (v nach unten). Abgeleitet aus der Eisenhüttenstadt-G-Datei mit Luftbild-UV.
8. **`.apt`-Datensatz (72 Byte):** Name (Pascal-String, 36 Byte), float lat, lon, Höhe, uint32 Richtung (100000 + Grad × 100), uint32 Länge, uint32 Breite, uint32 Asphalt, float Frequenz, uint32 Flags.
9. **Skripte:** `patch_textur.py` baut Patch-Texturen aus DOP20, `gelaende.py` und `edaz_gelaende.py` bauen das Gelände aus DGM1 mit Überblendung am Rand, `dds_dxt1.py` schreibt die Texturen.
10. **Steuerung der Editoren und von Condor:** Skripte in `Werkzeuge\steuerung`, siehe `ARBEITSABLAUF.md`, Abschnitt 6. Die Toolkit-Programme müssen im Condor-Ordner liegen.

## Stand EDAZ (17.11.2026)

1. **Erledigt:** Neue Texturen t4039 und t3939 mit 8192 px (0,7 m pro Pixel), Farben an die Umgebung angeglichen. Sie liegen in EG3\Textures.
2. **Erledigt:** Neues Gelände aus DGM1 als TR3F für beide Patches, in EG3\HeightMaps\22.5m. Zur Sicherheit liegt jede Datei sowohl mit 6-stelligem als auch mit 4-stelligem Namen dort.
3. **Erkenntnis:** Die alte Textur war 6–13 m versetzt. Das alte Gelände lag im Wald bis zu 21 m zu hoch, weil SRTM die Baumkronen mitmisst.
4. **Erkenntnis:** DGM1 am Flugplatz-Bezugspunkt ergibt 41,3 m, die `.apt` sagt 40 m.
5. **Erledigt:** Neue G-Datei (`edaz_flaechen.py`) mit Asphalt aus OSM für Piste, Rollwege und Vorfelder. Die Breiten der Rollwege sind aus dem Luftbild gemessen. Grass3D bedeckt das restliche Flugplatzgelände, die Unter-Textur `Airports\Textures\Schoenhagen.dds` hat 4096 px auf 2560 m mit Alpha für die Grashöhe (kurz an Pisten und Rollwegen). Die Flugplatzhöhe in der `.apt` ist von 40 auf 41 m gesetzt (DGM1). In Condor geladen und angesehen: kein Fehler, 3D-Gras sichtbar, Asphaltpiste grau mit Markierungen aus dem Luftbild.
6. **Farbangleich der Luftbilder:** Die DOP-Kacheln stammen aus mehreren Bildflügen (südlich von Hochwert 5784 km vom 29.04.2025, sonst vom 30.04.2024). `patch_textur.py` gleicht deshalb jeden Bildflug für sich an die alte Textur derselben Fläche an. Zusätzlich blendet `rand_angleich` die Farben auf 1,5 km zum Außenrand hin weich auf die alten Nachbar-Patches über. Ohne diesen Schritt war südlich von EDAZ (Ahrensdorf) ein dunklerer, grünerer Streifen mit harter Kante sichtbar.
7. **Wald (`waldkarte.py`):** Wo der Wald steht, ergibt sich aus der Baumhöhe (bDOM 0,2 m, auf 1 m gemittelt, minus DGM1) von mindestens 3 m und einem Flächenanteil von mindestens 35 % pro Zelle (11,25 m). LoD2-Gebäude (um 2 m vergrößert) sind ausgeschlossen. Laub oder Nadel wird über die Helligkeit im April-Luftbild bestimmt: Nadel bis 58. Das Sommer-Infrarot vom WMS trennt die beiden nicht. EastGermany2 hatte fast alles als Laubwald geführt, weil OSM-Wald ohne `leaf_type` als „other“ gezählt wurde. Danach `LandscapeEditor.exe -hash EastGermany3` ausführen, sonst meldet Condor eine Manipulation.
8. **`.for`:** 512 × 512 uint8, 1 = Nadel (s), 2 = Laub (b), 3 = beides. Datei = Bild[::-1, ::-1].T.
9. **Baumtextur pro Landschaft:** siehe Punkt 11.
10. **Gebäude (`edaz_gebaeude.py`):** 62 LoD2-Gebäude im Flugplatzumriss (+60 m) stehen als `SchoenhagenO.c3d` mit den Objekten Daecher und Waende, dazu der Windsack aus dem Original. Die Dachtextur ist das DOP mit 0,4 m (`Schoenhagen_Daecher.dds`), zu den Wänden siehe Abschnitt „Fassaden“.
11. **Baumtextur pro Landschaft: bestätigt (17.11.2026).** Die rote Test-Textur in `EastGermany3\World\Textures\Drevesa.dds` wurde in Condor angezeigt. Danach wieder entfernt. Ein eigenes Kiefernmodell ist also möglich.
    1. Eingebaut: `kiefer_blender.py` rendert prozedural (eigene Arbeit, ohne Lizenzfragen) eine Kieferngruppe: drei Altkiefern (22 m, astfreier Stamm, Krone etwa die obere Hälfte) und zwei Jungkiefern im Unterstand. Eine Einzelkiefer deckte nur 6 % des Billboards und wirkte in Condor wie lichter Wald. Die Gruppe deckt 27 % (Original-Fichte 18 %) und ist in Condor abgenommen.
    2. `baumtextur.py` ersetzt den Nadelbaum-Quadranten oben rechts. Der Stammfuß liegt wie bei der Fichte auf (346, 501), skaliert wird fest: 940 px im Render = 470 px = 22 m. Die Gruppe ist nach links versetzt, weil rechts vom Fuß nur etwa 7,5 m Platz bleiben. Das Skript prüft, dass nichts am Quadrantenrand abgeschnitten wird, auch kein halbtransparenter Rand. Der Laubbaum bleibt das Original. Format DXT3 mit 11 Mip-Ebenen, Kopf byteidentisch zum Original. Die globale `World\Textures\drevesa.dds` ist unverändert.
    3. Die Nadelbüschel baut `kiefer_blender.py` als ein einziges numpy-Netz; einzelne `bmesh.ops`-Aufrufe wären bei 35.000 Büscheln quadratisch langsam. TreesDensity steht im Pilotprofil schon auf dem Maximum 4.
12. **Objektliste `<Landschaft>.obj`:** 152-Byte-Datensätze: float PosX (605160 − E), PosY (N − 5558120), z absolut, Skalierung, Drehung (rad), Pascal-String Objektname. `objektliste.py` entfernt die alten Hallen und Büsche um EDAZ (24 Stück) und setzt 22 Flugzeuge und Anhänger auf die neue Geländehöhe. `-hash` ändert die `.oha` nicht, sie betrifft offenbar den Autogen-Ordner.
13. **Blender-Vorschau:** `vorschau_daten.py` liest die eingebauten EG3-Dateien (TR3F-Quelle, DDS, G/O-c3d, .for) nach `Daten\Vorschau`. `vorschau_blender.py` baut daraus die Szene, Bäume sind Platzhalter. Interaktiv öffnet `Vorschau.bat` die Szene. Für Bilder ohne Fenster: `blender -b --python vorschau_blender.py -- --render <ordner> [--nur kamera1,kamera2]`. Kameras: anflug_25, hallen_nah, vorfeld, uebersicht, boden_piste. Die Alphamaske der Grastextur muss in Blender auf CHANNEL_PACKED stehen, sonst wird die Fläche dunkel.
14. **Fassaden erledigt (17.11.2026):** Hallen Trapezblech mit Toren, übrige Gebäude Putz mit Fenstern, siehe Abschnitt „Fassaden“. In Condor angesehen und abgenommen.
15. **Sicherung** vor allen Änderungen: `Backup\EG3_vor_EDAZ_20261117_1847`.

## Fassaden

1. **Texturen:** `fassaden.py` erzeugt alle Wandtexturen prozedural (Rauschen und Formen, keine Fotos), je 1024 px, DXT1: `Schoenhagen_Waende.dds` (glatter Putz mit Sockel), `Schoenhagen_Fassade.dds` (gleicher Putz mit Fensterreihen alle 3 m), `Schoenhagen_Blech.dds` (Trapezblech, 16 × 16 m, Betonsockel), `Schoenhagen_Tore.dds` (Torflügel mit Fensterband). Farben und Struktur von Blech, Toren und Putz wurden später überarbeitet, siehe „Autogen und Dörfer“, Punkt 12. `python fassaden.py <ordner>` schreibt sie als PNG.
2. **Gebäudetyp** (`gebaeudetyp` in `edaz_gebaeude.py`) aus LoD2: Halle bei Funktion 2431 (Flugzeughalle) oder 2430 (Betriebsgebäude Flugverkehr) ab 500 m² ohne Walmdach. Nebengebäude bei Garagen, Schuppen, Ställen, Versorgung und 9998 unter 100 m². Alles andere ist Fassade. Ergebnis: 18 Hallen, 27 Fassaden, 17 Nebengebäude. Alle 17 OSM-Hangars sind als Halle erkannt.
3. **Tore:** Eine Hallenwand bekommt ein Tor, wenn sie am Boden steht, mindestens 6 m lang und 4 m hoch ist, 2 m davor kein Gebäude steht und 4–40 m vor der Wandmitte Vorfeld oder Rollweg aus OSM liegt. Ergebnis: 32 Wände an allen 18 Hallen. Die Torhöhe beträgt 75 % der Traufhöhe, zwischen 3,5 und 7 m und mindestens 0,8 m unter der Traufe. Die Flügel sind etwa 4 m breit, je Wand passt eine ganze Zahl.
4. **Fenster:** Nur ganze Fensterreihen unter der Traufe. Die Wand wird an der Geschossgrenze waagerecht geteilt, darüber (Giebel) glatter Putz mit derselben UV, also ohne Naht. Die Fensterachsen sind etwa 3 m breit, je Wand ganzzahlig, damit an den Ecken keine halben Fenster entstehen.
5. **Objekte in `SchoenhagenO.c3d`:** Daecher, Waende, Fassaden, Hallen, Tore, dazu Windsack und Mast aus dem Original. v zählt immer ab der Bodenhöhe des Gebäudes, auch bei Wänden, die auf einem Dach beginnen, sodass dort kein Sockel mehr erscheint. Die 1,5-m-Schürze unter dem Boden ist abgetrennt und hat ein festes v auf der Sockelzeile, sonst würden Torschiene oder Fenster vom oberen Kachelrand unter der Bodenlinie erscheinen. Wandstücke unter 2 m bekommen keine Fenster. Geprüft: Normale gleich Kreuzprodukt, Wandfläche und Normalensumme gleich wie vorher, alle 1111 bodennahen Wanddreiecke zeigen nach außen (Test gegen die Grundrisse), v passt bei allen Ecken über dem Boden zur LoD2-Bodenhöhe, kein v außerhalb von 0–1.
6. **Sicherung** des Stands davor: `Backup\vor_fassaden`.

## Autogen und Dörfer (17.11.2026)

1. **Format:** pro Patch `<Landschaft>\Autogen\o<SSSZZZ>.c3d` (6-stellig, z. B. `o040039.c3d`), die Texturen in `Autogen\Textures`. Die C3D hat das bekannte Format, mit Ursprung in der Patch-Mitte, x nach Westen, y nach Norden und z als absoluter Höhe, also wie Condors PosX/PosY. Eigene Modelle sind ohne Einschränkung möglich.
2. **Erzeugen:** Wie der Condor OSM Exporter (`CondorOSMImporter.py`) eine OBJ mit MTL nach `Working\Autogen\o<Patch>.obj` schreiben. In der OBJ zeigt x nach Norden und y nach Westen (der Exporter dreht um 90°). Der Landscape Editor wandelt sie mit „File > Export autogen C3D from OBJ“ um (Menü-ID 23). Dabei tauscht er x und y, kehrt die Indexreihenfolge um, fasst gleiche Vertices zusammen und spiegelt v (v_C3D = 1 − vt). Das Material kommt aus `Kd`, die Textur wird zu `Textures\<map_Kd>`. Geprüft durch Rücklesen der umgewandelten C3D.
3. **Hash:** Die Zeile eines Patches in der `.oha` lautet `<Patch> <MD5 der C3D>`, Patches ohne Autogen stehen ohne Hash darin. Erzeugt wird die Datei mit „File > Export autogen hash (OHA)“ (Menü-ID 14), `-hash` erzeugt sie nicht. Die Texturen gehen nicht in den Hash ein.
4. **Steuerung ohne Maus:** Den Landscape Editor minimiert starten, die Landschaft über CB_SETCURSEL auf die Combobox plus WM_COMMAND/CBN_SELCHANGE wählen. Die Menüpunkte als WM_COMMAND mit der Menü-ID schicken, Dialoge per BM_CLICK schließen.
5. **Dörfer (`doerfer_autogen.py`, `autogen.py`):** LoD2-Gebäude außerhalb des Flugplatzes (gleicher Test wie in `edaz_gebaeude.py`, also keine doppelten Gebäude) werden mit 40-m-Puffer zu Siedlungen zusammengefasst. Ein Dorf sind alle Siedlungen bis 600 m um den OSM-Ortspunkt. Ergebnis: Schönhagen 302 Gebäude, Ahrensdorf 194 (eines davon in t3939). Das ergab etwa 30.400 Dreiecke in `o040039` und 26 in `o039039`; der Geflügelhof kam später in `o039039` dazu (Punkt 14).
6. **Aussehen:** Die Dächer zeigen das DOP20 je Dorf (`EG3Dorf_<Dorf>_Daecher.dds`, 4096 px, 0,28 bzw. 0,20 m pro Pixel). Die Wände nutzen die Texturen aus `fassaden.py` (`EG3Dorf_Putz/Fassade.dds`, für Hallen siehe Punkt 13). Typ (`dorftyp`): Garagen bekommen Putz ohne Fenster. Landwirtschaft, Gewerbe und Unbekanntes ab 250 m² werden Halle mit Blech, unter 100 m² und Landwirtschaft bis 250 m² Putz ohne Fenster. Alles andere bekommt Putz mit Fenstern (unter 25 m² ohne).
7. **Bodenanschluss:** Gebäude, deren LoD2-Boden unter dem 22,5-m-Gelände liegt, werden angehoben, in Ahrensdorf bis 3,8 m (eine Senke, die das Raster glättet). Jede Wand reicht gleichmäßig bis mindestens 0,5 m unter das Condor-Gelände, entlang der ganzen Unterkante gemessen, und mindestens 1,5 m unter den LoD2-Boden. Die Geländehöhe wird auf denselben Dreiecken wie in Condor berechnet, geprüft gegen `edaz_flaechen.gelaende_dreiecke` (Abweichung < 1e-9 m). 6 falsch orientierte LoD2-Wände und alle nach unten zeigenden Dächer werden umgedreht.
8. **Geprüft:** Gelesen wurde die OBJ, zurück nach UTM gerechnet. Die Normale stimmt mit dem Kreuzprodukt überein, kein Dach zeigt nach unten. Von 21.316 bodennahen Wanddreiecken zeigen 16.613 eindeutig nach außen, 10 nach innen; das sind kleine Stücke an Anschlüssen zwischen Gebäuden. Die übrigen sind Trennwände. Der Wandfuß liegt an 2743 von 2760 Grundrissecken unter dem Gelände, die übrigen 17 sind Wände, die laut LoD2 auf einem Dach beginnen. In der Blender-Ansicht, wie im PatchViewer importiert, sitzen die Häuser genau auf ihren Dächern im Patch-Luftbild.
9. **Test in Condor (bestanden):** Drei Testmasten in `o040039.c3d`: weiß (40 m) am Flugplatzbezugspunkt, rot 500 m nördlich, blau 400 m westlich. In Condor steht der weiße Mast in der Mitte der Segelflugbahn. Das stimmt, denn der Bezugspunkt der `.apt` liegt 7 m neben der Mittellinie der OSM-Graspiste. Rot steht nördlich, blau westlich jenseits der Asphaltpiste, alle stehen auf dem Boden. Die Achsen sind also weder gedreht noch gespiegelt. Danach wurden die Masten durch die Dörfer ersetzt (`o040039.c3d`, `o039039.c3d`), die Testtexturen gelöscht und die OHA neu exportiert. „Tools > Check autogen files and hashlist“ meldet „Autogen c3d files and hashlist OK“.
10. **Sicherung:** `Backup\vor_autogen_20261117_2108` (`.oha`, `edaz_gebaeude.py`, `PROJEKT.md`). Die Ordner `Autogen` und `Working\Autogen` waren vorher leer.
11. **In Condor angesehen, Ergebnis gut.** Große Hallen wirkten aber aus der Ferne fast weiß. Die Ursache sind nicht die Mip-Stufen (`dds_dxt1` mittelt mit INTER_AREA, die Helligkeit bleibt gleich). Die Blechtextur war mit 190 zu hell (offizielle Condor-Autogen-Texturen: Metall um 130, Putz 165–190), und ihre feinen 0,25-m-Rippen verschwinden in den kleinen Mips.
12. **Hallen und Tore neu (`fassaden.py`):** Blech in drei Varianten: `hangar` hellgrau, `stall` graubeige mit einer Reihe Zuluftklappen auf 1,9–2,3 m, `gewerbe` mittelgrau. Dazu kommt grobe Struktur, die auch in den Mips sichtbar bleibt: Tafelstöße alle 1 m, Wetterspuren 2–5 m breit, Spritzwasser unten. Helligkeit 122–135, der Kontrast bei 1/64 liegt bei 11 statt 5. Die Hangartore sind olivgrau wie die Falttore der Hangarzeilen A und C (FS-Screenshots nur zur Orientierung), mit abwechselnd hellen und dunklen Flügeln und breiten Rahmen. Die Tore liefen schon vorher über die ganze Torseite, hoben sich in Hellgraugrün aber kaum von der Wand ab. Der Flugplatz-Putz ist cremefarben wie die Putzbauten am Platz (`PUTZ_FLUGPLATZ`). `SchoenhagenO.c3d` ist dabei byteidentisch geblieben, nur die vier Wandtexturen in `Airports\Textures` sind neu.
13. **Dörfer:** Landwirtschaftshallen ab 250 m² bekommen `EG3Dorf_Stall.dds`, Gewerbehallen `EG3Dorf_Gewerbe.dds`. `EG3Dorf_Blech.dds` ist entfernt.
14. **Löwendorfer Geflügelhof und Landwerk Ahrensdorf** (Gruppe `Loewendorf` in `GRUPPEN`, Patch 39/39, 27 Gebäude): Die Piloten teilen danach ihre Landung ein. Das DOP20 zeigt drei lange Ställe (LoD2: 12 × 94,5 m, Traufe 3 m, First 4,7 m, zwei davon als Doppelstall mit Verbindungsbau), helle Dächer mit Firstlüftern, eine große Halle mit Solardach und an jedem Nordwest-Giebel Futtersilos mit langen Schatten. Umgesetzt: Die Ställe bekommen die Stallwand mit Zuluftklappen. Am Südgiebel sitzen Abluftventilatoren (`EG3Dorf_Luefter.dds`), und zwar auf Giebelstücken, die mindestens 4 m hoch reichen, sodass die flachen Verbindungsbauten keine bekommen. Vor jedem Nordgiebel stehen drei Futtersilos (r = 1,2 m, 7,5 m + 1,8 m Kegel, `EG3Dorf_Silo.dds`). LoD2 teilt die Giebel in Hälften, deshalb fügt `stallgiebel` die Stücke erst zusammen. Silos kommen nur an Giebel von 9–16 m Breite. Anzahl und Maße der Silos sind aus Schatten und Draufsicht geschätzt. Eigene Fotos vom Hof würden helfen (Silos, Giebel, Farbe der Längswände).
15. **Geprüft:** Unabhängiges Rücklesen der OBJ wie oben. Patch 40/39 ist unverändert (gleiche Zahlen). In Patch 39/39 zeigt kein Dach nach unten und keine bodennahe Wand eindeutig nach innen. Der Wandfuß liegt an 178 von 180 Grundrissecken unter dem Gelände. Blender-Bilder zeigen den Hof aus Nord, Süd und Anflugrichtung. Dabei fiel ein Fehler auf und ist behoben: Die Variable `breite` war überschrieben, wodurch die Dach-UVs falsch wurden. Danach OHA neu exportiert, „Autogen c3d files and hashlist OK“. Behobene Review-Funde:
    1. Die Außenrichtung der Giebel kommt aus der Stallachse und wird gegen den Grundriss geprüft. Silos, die ein Gebäude berühren, werden verworfen (bisher keiner).
    2. Die Silo-UV läuft über ganze Kacheln, und die Silotextur hat 6 Bahnen je Kachel, damit keine Naht entsteht.
    3. Geteilte Giebelstücke haben einen gemeinsamen u-Ursprung, damit die Lüfter an der Fuge durchlaufen.
    4. Nord und Süd werden entlang der Stallachse bestimmt, nicht nach dem Hochwert.
16. **Sicherung:** `Backup\vor_blech_20261117_2151` (`SchoenhagenO.c3d`, alte Flugplatz- und Autogen-Texturen, Autogen-C3D, `.oha`, Skripte, `PROJEKT.md`).

## Erkenntnisse vom 17.11.2026 (Zusammenfassung)

Condor und Toolkit:
1. Condor 3 lädt bei jedem Flugstart alle Landschaftsdateien neu. Zum Testen reicht es, den Flug zu beenden und im Flugplaner neu zu starten, ein Neustart von Condor ist nicht nötig.
2. Die Toolkit-Programme (LandscapeEditor, ObjectEditor, scenerycheck3) funktionieren nur im Condor-Ordner.
3. Es gibt keine API und keine Kommandozeile außer `LandscapeEditor.exe -hash <Landschaft>`. Die Editoren lassen sich per Screenshot, Mausklick und Win32-Nachrichten steuern. Dialoge schließt BM_CLICK auf den OK-Knopf.
4. Die Hashes (`.tha` für Gelände, `.fha` für Wald) prüft Condor auch im Freiflug. Nach jeder Änderung an Wald oder Gelände `-hash` ausführen. Die O-/G-Dateien des Flugplatzes laufen ohne neuen Hash. Die `.tr3f` dagegen stehen in der `.tha`: Nach jeder Änderung an `HeightMaps\22.5m` im Landscape Editor „File > Export terrain hash (THA)“ ausführen (`python steuerung/landscape_editor.py menue "Export terrain hash (THA)"`). Ohne neuen Hash springt der Knüppel im Cockpit (Cheat-Schutz, gefunden am 22.11., siehe TODO.md 2a). Condor liest nur die 6-stelligen Namen `h%0.3d%0.3d.tr3f`. `-hash` ändert die `.oha` nicht.
5. Pro Landschaft austauschbar: die Baumtextur unter `<Landschaft>\World\Textures\Drevesa.dds`, mit roter Testtextur bestätigt. Die globale Datei bleibt unangetastet.
6. Patch-Texturen mit 8192 px (0,7 m pro Pixel) funktionieren auch auf einem Patch ohne Flugplatzmittelpunkt (t3939).
7. Zoom in der Außenkamera: rechte Maustaste plus Maus hoch/runter. Simulierte Mausbewegungen ignoriert Condor. Tasten müssen als Scancodes gesendet werden: P = Pause, F2 = Außenansicht, Pfeiltasten = Kamera.

Dateiformate (alle selbst entschlüsselt und mit Originaldateien geprüft):
8. `.tr3f`, `.c3d`, `.apt`, `.obj` (Objektliste), `.for` und das Koordinatensystem der Flugplatzdateien sind oben beschrieben.
9. `.c3d`: Dreiecke sind so gewickelt, dass das Kreuzprodukt (v1−v0)×(v2−v0) nach außen zeigt, und die gespeicherte Normale ist genau dieses Kreuzprodukt. Das dritte Kopffeld ist die Objektanzahl (in allen 151 Originaldateien).
10. Die Baumtextur `Drevesa.dds` ist 1024 px groß, DXT3, mit 11 Mip-Ebenen. Oben rechts liegt der Nadelbaum (Stammfuß bei (346, 501), Höhe etwa 470 px), unten links der Laubbaum (Stammfuß bei (214, 511)). Die anderen beiden Quadranten sind leer.

Daten:
11. Die LGB stellt DOP20 (RGB-JPG, RGBI-TIF), DGM1, bDOM (0,2 m), nDOM (LAZ) und LoD2 frei zum Download, Lizenz dl-de/by-2-0.
12. Die DOP-Kacheln stammen aus verschiedenen Bildflügen. Um EDAZ: südlich von Hochwert 5784 km vom 29.04.2025, sonst vom 30.04.2024. Das Datum steht in der Metadatei jeder Kachel. Den Farbton kann man angleichen, die unterschiedlich bestellten Felder nicht. Daher bleibt bei Ahrensdorf ein schwacher Streifen. Der Server hat für jede Kachel nur den neuesten Flug.
13. Das Farbinfrarot vom WMS stammt aus einem Sommerflug und trennt Laub- und Nadelwald nicht. Das April-RGB tut es: Kiefer ist dunkel (Helligkeit 40–57), Laub heller.
14. EastGermany2 führte fast den gesamten Wald als Laubwald, weil OSM-Wald ohne `leaf_type` als „other“ gezählt wurde. Das alte SRTM-Gelände lag im Wald bis zu 21 m zu hoch, die alte Textur war 6–13 m versetzt.
15. Die LoD2-Ringe sind zuverlässig von außen gesehen gegen den Uhrzeigersinn orientiert (139 von 139 Dächern, 349 von 354 Außenwänden). Die Wandausrichtung kommt deshalb aus dem Ring, nicht aus dem Schwerpunkt.
16. Die alten EDAZ-Hangars standen in der Objektliste `EastGermany3.obj`, nicht in der Flugplatzdatei.

Werkzeuge und Ergebnisse:
17. Gebaut wurden: scharfe Luftbilder (2 Patches), DGM1-Gelände, Flugplatzflächen mit Asphalt und Grass3D, 62 LoD2-Gebäude mit Dach-Luftbild und typgerechten Fassaden (von der zweiten Session), neue Waldkarten, bereinigte Objektliste, Kiefern-Baumtextur, die Dörfer Schönhagen und Ahrensdorf als Autogen, der Löwendorfer Geflügelhof als Landmarke und die Blender-Vorschau (`Vorschau.bat`).
18. Jeder Arbeitsschritt wurde vom adversarial-reviewer geprüft. Echte Funde waren unter anderem: Gras und Asphalt überlappten am Rand, Wände an L-förmigen Hallen zeigten nach innen, die Bodenerkennung war falsch, Waldklassen wurden auf randangeglichenen Farben bestimmt, die Krone der Kiefer konnte abgeschnitten werden, am Kronenrand entstand ein schwarzer Saum. Alle sind behoben. Zweimal lag der Prüfer falsch (C3D-Kopf, Dachorientierung) und wurde an Originaldaten widerlegt.

Stand Abend 17.11.2026:
19. Alles Gebaute ist in Condor angesehen und abgenommen: Kieferngruppe (Stand EDAZ 11), Fassaden, Dörfer, Hallen, Tore und Geflügelhof („sieht alles sehr gut aus, können wir erstmal so lassen“).
20. Offen: Ring aus scharfen Luftbildern und neuem Wald um EDAZ (3 × 3 Patches), dadurch rücken die Bildflug- und Patchkanten vom Platz weg.
21. Offen: Weitere Flugplatzgebäude nach Fotos (Tower-Komplex in Kalksandstein, Hangar P1 mit Rolltoren).

Stand 18.11.2026 (Ring um EDAZ):
22. Die 7 Patches um den Kern (Spalten 41 bis 39, Reihen 40 bis 38) haben neue 8192-px-Texturen aus DOP20 und neue Waldkarten. Kern-Texturen und Kern-Waldkarten sind unverändert. Eingebaut mit `-hash`, in der `.fha` haben sich genau die 7 Ring-Zeilen geändert. Sicherung: `Backup\vor_ring_20261118_210636`. Noch nicht in Condor angesehen.
23. Im Ring liegen drei Bildflüge (30.04.2024, 27.04.2025, 29.04.2025). Der Flug von 2025 im Südwesten ist dunstig. Deshalb gleicht `ring_textur.py` die Farben je Flug örtlich an die alte Textur an (Fenster 1,5 km) und zieht an den Kernkanten die Farbe des Kerns nach außen.
24. Laub/Nadel läuft im Ring auf dem örtlich angeglichenen Bild. Die Schwelle 58 passt auch dort: Am Kern stimmen damit 96 % der Waldzellen mit den abgenommenen Karten überein (54: 90 %, 62: 92 %).

## Wolken und Shader (17.11.2026)

Stand: untersucht und getestet, noch nichts geändert. Die Wolken-Variation ist vorerst zurückgestellt.

1. **Aufbau der Wolken:** In `<Condor>\World\Clouds` liegen nur 9 Wolkenmodelle (`S1`–`S3`, `M1`–`M3`, `W1`–`W3` jeweils `Cloud.c3d`) und ein gemeinsamer Textur-Atlas `Clouds.tga`. Das erklärt, warum die Wolken gleich aussehen. Dazu kommen `Cirrus0`–`Cirrus3.tga` (hohe Wolken), `RainDrop`, `RainShaft`, `RainTrail` und die Blitzmodelle.
2. **Format `Clouds.tga`:** 4096 × 256 px, 32 Bit, unkomprimiert (BGRA, 18 Byte Kopf, 26 Byte Fuß). Eine Ersatzdatei muss dieselbe Größe und denselben Aufbau haben.
3. **Nicht pro Landschaft austauschbar:** Eine rot eingefärbte `Clouds.tga` in `Landscapes\EastGermany3\World\Clouds` wurde ignoriert, die Wolken blieben weiß (Test mit Cumulus-Wetter). Im Gegensatz zur Baumtextur (Erkenntnis 5) wirken Wolken also nur global, über `World\Clouds` im Condor-Ordner. Offen: ob die `.c3d`-Modelle pro Landschaft laden (unwahrscheinlich, nicht getestet). Eine globale Änderung gilt in jeder Landschaft und trifft Online-Flüge und Wettbewerbe, Verhalten der Dateiprüfung ungetestet.
4. **Shader:** Die Effekte liegen kodiert in `Effects\*.fxc` (u. a. `EffectCloud`, `EffectCloudFog`, `EffectCloudShadows`, `EffectHighClouds`, `EffectMiddleClouds`, `EffectSky`, `EffectLand`). Der Algorithmus ist unbekannt (keine Periodizität erkennbar), der Originaltext liegt nicht vor.
5. **Klartext-Override:** Condor kompiliert HLSL (`fx_5_0`, über `D3DX11CompileFromMemory`) und sucht zuerst `Effects\fx\<Name>.fx`. Bestätigt mit einer absichtlich ungültigen `Effects\fx\EffectCloudFog.fx`: Condor lädt sie und stürzt beim Flugstart bei „Creating CloudFog“ mit einer Access Violation ab (`Logs\ErrorLog.txt`). Die Testdatei ist gelöscht, `Effects\fx` existiert nicht mehr. Shader wirken immer global.
6. **Weg zum Original-Shadertext, falls nötig:** Proxy für `d3dx11_43.dll`, der den an `D3DX11CompileFromMemory` übergebenen Text lokal mitschreibt. Das braucht einen C++-Compiler (Visual Studio 2022 Community ist installiert, ob die C++-Workload dabei ist, ist ungeprüft). Der Text wäre nur zur lokalen Nutzung, nicht zur Weitergabe.
7. **Wenn Wolken verbessert werden sollen:** Zuerst `World\Clouds` komplett sichern (außerhalb von `World`). Dann `Clouds.tga` mit mehr Variation ersetzen, danach neue Wolkenmeshes im ObjectEditor. Dafür braucht es Beispiele oder eine Analyse des Atlas.

## EDAZ-Patches

1. t4039: UTM 33 Rechtswert 369000–374760, Hochwert 5782760–5788520.
2. t3939: Rechtswert 374760–380520, gleicher Hochwert.
3. LGB-Kacheln (1 km): Rechtswert 368–380, Hochwert 5782–5788. Download nach `Daten\LGB\dop`, `dgm`, `bdom` und `lod2`, gepackt etwa 2,9 GB (davon bDOM 2,0 GB und DOP 0,8 GB). Die Skripte entpacken noch einmal etwa so viel.

## Datenquellen und Lizenzen

1. **Brandenburg (LGB):** Download-Server https://data.geobasis-bb.de/geobasis/daten/ mit den Ordnern `dop/` (Luftbilder), `dgm/` (Gelände), `bdom/` (Oberflächenmodell), `ndom/` (normalisiertes Oberflächenmodell, also Objekthöhen), `3d_gebaeude/` (LoD2) und `als/` (Laserscan-Rohdaten).
2. **Lizenz:** Datenlizenz Deutschland – Namensnennung 2.0 (dl-de/by-2-0) laut Download-Seite, Grundlage ist die BbgGeoNutzV. Vermutete Quellenangabe: „© GeoBasis-DE/LGB, dl-de/by-2-0“. Den genauen Wortlaut vor der Weitergabe in der Verordnung prüfen.
3. **Wikimedia Commons, Category:Flugplatz Schönhagen:** 23 Fotos unter CC BY-SA, darunter zwei Luftaufnahmen sowie Hauptgebäude und Tower. Der automatische Download ist am Rate-Limit von Wikimedia (HTTP 429) gescheitert. Die Fotos müssen von Hand geladen werden, mit Urheber und Lizenz. Texturen aus diesen Fotos müssen ebenfalls unter CC BY-SA stehen und den Urheber nennen.
4. **Eigene Fotos vom Platz:** die beste Quelle für Fassaden. Jede Hallenfront frontal aufnehmen, den Turm von allen vier Seiten und beide Denkmäler, am besten bei bedecktem Himmel.
5. **Nicht verwenden:** Google Maps, Google Earth, Bilder aus der Google-Suche und Bing- oder Google-3D-Daten. Die Nutzungsbedingungen bzw. das Urheberrecht verbieten das. Zum Anschauen sind sie in Ordnung.
6. **Freie Alternative zu Google 3D Tiles:** Das bDOM der LGB (0,2 m, dl-de/by-2-0) enthält Gebäude und Bäume und ist für EDAZ geladen, genutzt für die Waldkarte. Daraus ließe sich ein Mesh erzeugen und mit DOP20 texturieren, eine Art Photogrammetrie mit freien Daten. Noch nicht versucht. Offen ist, ob Condor solche Meshes als Objekte verkraftet.
7. **`EDAZ Fotos\`:** Screenshots der kommerziellen FS2024-Szenerie von Aviation-Sim-Design. Nur zur Orientierung, nichts daraus übernehmen.

## Detailstufen

1. **EDAZ:** von Hand modelliert, so originalgetreu wie möglich.
2. **Markante Punkte:** von Hand oder halbautomatisch modelliert, wichtig für die Orientierung im Segelflug. Kandidaten: Tropical Islands (ehemalige Cargolifter-Halle), die Kühltürme der Kraftwerke Jänschwalde, Schwarze Pumpe und Boxberg, das Mercedes-Werk Ludwigsfelde, auffällige Kirchtürme. Auswahl noch offen.
3. **Rest:** automatisch erzeugt. LoD2 liefert Grundriss, Höhe und Dachform, die Dachtextur kommt aus DOP20. Fassaden bekommen generische Texturen je Gebäudetyp. Weiter draußen nur Luftbild und Wald.

## Bauliste EDAZ (nach Priorität)

Stand 17.11.2026: Alle Gebäude des Platzes stehen als LoD2-Modelle mit Dach-Luftbild und prozeduralen Fassaden (Hallen mit olivgrauen Toren, Putzbauten mit Fenstern). Offen ist die Detaillierung nach Fotos (Punkte 1–5) sowie die Punkte 6–8.

1. Tower-Komplex: Turm mit blauer Glasfront und „EDAZ“, Restaurant mit flachem Walmdach, Terrasse, Fahnen.
2. Hangarzeile A1–A3 mit grünlichen Falttoren, Flachdach und Lichtkuppeln, dazu die CD-Aircraft-Halle.
3. Hangarzeile C1–C4 am Waldrand.
4. Einzelhallen P1, G, M, V, X und die Shed-Hallen. Ein Großteil kommt aus LoD2.
5. Historische Putzbauten mit Säulenportal und Solardächern. Dachform aus LoD2, Dachtextur aus dem Luftbild.
6. Vereinsecke: alte Wellblechhangars, Garagen, Anhänger.
7. Denkmäler: Do 27 im Zebra-Look (D-EDAZ) und Schulgleiter auf Mast.
8. Umgebung: Baumreihen, Teich, Windsack, Zäune. Die Vorfeldmarkierungen kommen ins Bodenluftbild.

## Vorgehen

1. **Erledigt. Arbeitskopie einrichten:** Ordner und alle `EastGermany2.*`-Dateien in `EastGermany3` umbenennen. Einmal in Condor laden und prüfen.
2. **Erledigt. Werkzeuge:** Blender und das Condor 3 Landscape Toolkit installieren. Danach das Objektformat (`.c3d`) und den Import-Weg klären.
3. **Erledigt. Pilot EDAZ:** DOP20 und DGM1 für 2 Patches um den Platz, scharfes Luftbild, Gelände, Piste und alle Gebäude aus LoD2. Der Tower ist noch nicht nach Fotos nachmodelliert.
4. **Teilweise erledigt. EDAZ ausbauen:** Gebäude nach Fotos laut Bauliste und die LoD2-Häuser im Umkreis von 5–10 km (bisher Schönhagen, Ahrensdorf, Geflügelhof).
5. **Karte erweitern:** Die Datenaufbereitung automatisieren (laden, nach UTM umrechnen, Farben angleichen, Patches erzeugen). Kachel für Kachel erneuern, zuerst Brandenburg um EDAZ, dann dort, wo der Verein fliegt.

Grobe Aufwandsschätzung:

| Teil | Aufwand |
| --- | --- |
| Automatische Umwandlung der Gebäudedaten | 1–2 Wochen |
| Flugplatzgebäude von Hand | Tage bis 1–2 Wochen |
| Ganze Karte | Monate, nebenher |

## Offene Punkte

Die Punkte 1 und 2 sind erst vor einer Weitergabe nötig. Die Landschaft wird derzeit nur intern genutzt (Stand 17.11.2026).

1. Vorgeschriebenen Wortlaut der Quellenangabe in der BbgGeoNutzV prüfen. Die Lizenz dl-de/by-2-0 ist bestätigt.
2. Mit Felix Hupfeld klären, ob EastGermany3 als offizielle Weiterentwicklung verteilt werden darf. Für Online-Flüge muss jeder exakt dieselbe Landschaft haben.
3. ~~Höhere Texturauflösung als 2048 px?~~ Ja, 8192 px laufen (siehe Erkenntnisse 6).
4. ~~Baummodelle pro Landschaft austauschbar?~~ Ja (siehe Erkenntnisse 5).
5. Eigene Fotos vom Platz organisieren.
6. Commons-Fotos von Hand im Browser herunterladen. Der automatische Download ist am Rate-Limit von Wikimedia (HTTP 429) gescheitert.
7. Prüfen, ob Condor eigene Meshes (z. B. aus DOM und DOP20) als Landschaftsobjekte akzeptiert, und ob die Dateiprüfung bei Online-Flügen geänderte Spieldateien (Shader, Wolken) bemängelt.
8. Wolken: mehr Variation (Atlas und Meshes) und eventuell Shader-Änderungen. Siehe Abschnitt „Wolken und Shader“. Zurückgestellt.
9. Klären, ob Condor die `.tr3f` mit 6- oder 4-stelligem Namen liest, dann die doppelten Dateien entfernen (Stand EDAZ 2).
10. Blender-Vorschau: Die Kamera „vorfeld“ sitzt auf Dachhöhe und muss tiefer.
