"""Zentrale Pfade. Alle Skripte lesen den Condor-Ordner von hier.

Anderer Installationsort: Umgebungsvariable CONDOR_DIR setzen, zum Beispiel
    set CONDOR_DIR=D:/Games/Condor3
Standard ist C:/Spiele/Condor3.
"""
import os

CONDOR_DIR = os.environ.get("CONDOR_DIR", "C:/Spiele/Condor3").replace("\\", "/")

LAND = CONDOR_DIR + "/Landscapes/Brandenburg"             # neue Karte, hier wird geschrieben (EG2/EG3 nie verändern)
LAND_ORIGINAL = CONDOR_DIR + "/Landscapes/EastGermany2"   # unveränderte Vorlage, wird nur gelesen
GLOBAL_BAUMTEXTUR = CONDOR_DIR + "/World/Textures/drevesa.dds"
