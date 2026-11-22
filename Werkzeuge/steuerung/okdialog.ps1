# Schließt Info-/Meldungsfenster von Landscape Editor und ObjectEditor per BM_CLICK auf den OK-Knopf (ohne Maus).
# Ja/Nein-Rückfragen (z. B. Überschreiben, Speichern) bleiben offen, die muss ein Mensch beantworten.
# Aufruf: powershell -File okdialog.ps1
. "$PSScriptRoot\win.ps1"
$pid_ = (Get-Process LandscapeEditor, ObjectEditor -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$n = 0
foreach ($id in $pid_) { foreach ($w in [U]::Tops($id)) {
  $c = [U]::Cls($w); if ($c -eq "TMessageForm" -or $c -eq "#32770") {
    $txt = ([U]::Kids($w) | ForEach-Object { [U]::Txt($_) }) -join " | "
    $ok = [U]::Kids($w) | Where-Object { [U]::Txt($_) -match '^&?OK$' } | Select-Object -First 1
    if ($ok) { [U]::SendMessage($ok, 0x00F5, [IntPtr]::Zero, [IntPtr]::Zero) | Out-Null; $n++; "geschlossen: [$([U]::Txt($w))] $txt" }
  } } }
if ($n -eq 0) { "kein Dialog offen" }
