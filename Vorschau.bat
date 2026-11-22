@echo off
echo Bereite die Vorschau-Daten vor, das dauert etwa eine Minute ...
cd /d "%~dp0Werkzeuge"
python vorschau_daten.py
if errorlevel 1 (
  echo Fehler beim Vorbereiten.
  pause
  exit /b 1
)
echo Starte Blender, die Szene baut sich in etwa 30 Sekunden auf ...
start "" "C:\Program Files\Blender Foundation\Blender 5.3\blender.exe" --python vorschau_blender.py
