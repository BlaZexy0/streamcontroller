# SOOMFON Stream Controller SE – Python-Controller

Die geplanten Arbeitspakete und ihr aktueller Stand stehen in `TODO.md`.

## Controller starten

Die offizielle SOOMFON-Anwendung muss geschlossen sein. Danach:

```powershell
.\start_controller.ps1
```

Alternativ ohne PowerShell-Skript:

```powershell
.\.venv\Scripts\python.exe .\controller.py --config .\config.json
```

Der Controller erkennt das aktive Vordergrundprogramm monitoruebergreifend und
wechselt automatisch zwischen Profilen fuer Desktop, Browser, VS Code,
Explorer und Spotify. Globale Hardware- und Zeiteinstellungen liegen in
`config.json`. Jedes Programmprofil hat eine eigene Python-Datei unter
`streamdeck_app/profiles/`.

- LCD-Tasten 1–6: Aktionen des aktuellen Profils
- Zusatztasten 1/2: vorheriges/naechstes Profil
- Zusatztaste 3: automatische Erkennung sperren/entsperren
- grosser Encoder: Systemlautstaerke, kurz druecken = stumm; mit LCD-Overlay
- linker kleiner Encoder: Lautstaerke der aktiven Anwendung, druecken = stumm
- rechter kleiner Encoder: Mikrofonlautstaerke, kurz druecken = stumm
- rechten kleinen Encoder zwei Sekunden druecken: Audioausgabe wechseln
- Screensaver, untere drei LCDs: konfigurierbare Aktienkurse mit Tagesveraenderung

Die Kursanzeige ist in `config.json` ueber `market_enabled`,
`market_refresh_seconds`, `market_closed_refresh_seconds`,
`market_stale_seconds` und `market_watchlist`
konfigurierbar. Die Kurse ersetzen keine Programmtasten, sondern erscheinen
ausschliesslich im Screensaver. Die Watchlist enthaelt genau drei Yahoo-Symbole, zum Beispiel
`AAPL`, `MSFT` und `NVDA`; `label` ist der kurze Anzeigename auf dem LCD.
Passende Symbole lassen sich ueber die Yahoo-Finance-Suche finden. Deutsche
Boersenplaetze tragen meist ein Suffix, beispielsweise `SAP.DE`. Waehrend der
regulaeren Handelszeit wird alle 15 Sekunden aktualisiert, ausserhalb nur alle
30 Minuten. `~` kennzeichnet
veraltete beziehungsweise zuletzt nur aus dem Cache geladene Daten, `C` einen
geschlossenen Markt und `FEHLER` einen Abruf ohne vorhandenen Cache.

Die Datenquelle ist eine inoffizielle, rein lesende Yahoo-Kursabfrage. Sie
braucht weder Trade-Republic-Zugangsdaten noch Zugriff auf Depot oder Orders.
Die Anzeige kann verzoegert oder zeitweise nicht verfuegbar sein und ist nur
zur Information gedacht, nicht als Grundlage fuer Handelsentscheidungen.

Nach 300 Sekunden ohne Eingabe am Deck startet auf den oberen drei LCDs eine
Offline-Pixelanimation. Die erste Eingabe weckt nur das Deck und loest keine
Aktion aus. Fuer eine sofortige Vorschau:

```powershell
.\.venv\Scripts\python.exe .\controller.py --screensaver-now --run-seconds 10
```

Im laufenden Betrieb schaltet fuenf Sekunden langes Druecken des grossen
Encoders den Screensaver ein oder wieder aus. Ein kurzer Druck behaelt seine
normale Stumm-Funktion und wird beim Loslassen ausgefuehrt. Taste und Haltedauer
sind ueber `screensaver_hold_key` und `screensaver_hold_seconds` in
`config.json` konfigurierbar.

`audio_output_devices` kann Namensbestandteile der gewuenschten Ausgabegeraete
enthalten, beispielsweise `Sennheiser` und `Arctis Pro Wireless Game`. Eine
leere Liste wechselt durch alle momentan aktiven Windows-Ausgabegeraete.

Mit `Strg+C` wird der Dienst beendet.

## Windows-EXE bauen

Die reproduzierbaren PyInstaller-Builds werden so erstellt:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\build_controller.ps1 all
```

Ergebnisse:

- `dist\SoomfonController\SoomfonController.exe`: diagnostizierbarer
  `onedir`-Build mit Konsole
- `dist\SoomfonController.exe`: einzelne `onefile --windowed`-EXE ohne
  Konsolenfenster

Beim ersten normalen EXE-Start wird die mitgelieferte Konfiguration nach
`%LOCALAPPDATA%\SoomfonController\config.json` kopiert. Diese Datei bleibt bei
neuen Builds erhalten und ist danach die zu bearbeitende Konfiguration der
EXE. Die begrenzten Logdateien liegen als `controller.log` sowie maximal drei
Backups im selben Ordner. Der Quellcode-Start ueber `start_controller.ps1`
verwendet weiterhin die `config.json` im Projektverzeichnis.

Nur einen Buildtyp erzeugen:

```powershell
.\build_controller.ps1 onedir
.\build_controller.ps1 onefile
```

Messung der gebauten Onefile-EXE:

```powershell
.\.venv\Scripts\python.exe -m tools.benchmark_build --duration 5
```

Beim Entwickeln neuer Profile koennen Aenderungen ohne Neustart geladen werden:

```powershell
.\.venv\Scripts\python.exe .\controller.py --dev-reload --verbose
```

Dieser Modus prueft den Profilordner einmal pro Sekunde. Bei Syntax- oder
Konfigurationsfehlern bleibt der zuletzt funktionierende Stand aktiv. Im
normalen Startmodus findet keine Dateipruefung statt.

USB-Unterbrechungen werden automatisch erkannt. Der Dienst versucht die
Verbindung standardmaessig alle zwei Sekunden wiederherzustellen. Unveraenderte
LCD-Bilder werden nicht erneut ueber USB uebertragen.

Ressourcenmessung ohne angeschlossenes Deck:

```powershell
.\.venv\Scripts\python.exe -m tools.benchmark --duration 5
```

Das Ergebnis wird zusaetzlich als `benchmark_report.json` gespeichert.

Statisches LCD-Kalibriermuster fuer Rotation und Pixelbreite:

```powershell
.\.venv\Scripts\python.exe -m tools.display_calibration
```

Das Muster zeigt oben Rotation, vertikale und horizontale 1-Pixel-Streifen;
unten folgen 1/2/3-Pixel-Streifen, ein 1-Pixel-Schachbrett und ein 5-Pixel-Raster.
Es bleibt bis zum naechsten Controller-Start auf dem Deck sichtbar.
Die unveraenderten PNGs und die tatsaechlich uebertragenen, gedrehten JPEGs
werden gleichzeitig unter `assets/test_patterns/` gespeichert. Nur exportieren:

```powershell
.\.venv\Scripts\python.exe -m tools.display_calibration --export-only
```

## Projektstruktur

```text
streamdeck_app/
|-- core/
|   |-- device.py          # USB/HID-Protokoll
|   |-- foreground.py      # aktives Windows-Fenster
|   `-- actions.py         # Hotkeys, Medien- und Startaktionen
|-- profiles/
|   |-- desktop.py
|   |-- browser.py
|   |-- vscode.py
|   |-- explorer.py
|   |-- spotify.py
|   |-- helpers.py         # lesbare Aktionskonstruktoren
|   |-- model.py           # Profile, Buttons und Lebenszyklus-Hooks
|   |-- reload.py          # optionales Neuladen im Entwicklungsmodus
|   `-- runtime.py         # Profilzustand und Wechselsteuerung
|-- market/
|   |-- model.py           # anbieterunabhaengige Kursmodelle
|   |-- provider.py        # read-only Marktdatenadapter
|   `-- worker.py          # langsamer Hintergrundabruf, Cache und Backoff
|-- paths.py               # Bundle-Ressourcen und LOCALAPPDATA
|-- logging_setup.py       # begrenzte Datei- und Konsolenlogs
|-- screens/
|   |-- display.py         # dynamische LCD-Inhalte und Overlay-Stapel
|   |-- market.py          # Kurskacheln im Screensaver
|   |-- profile_screen.py  # normale LCD-Tasten
|   `-- screensaver.py     # Idle-Animation
`-- service.py             # verbindet Ereignisse, Profile und Anzeigen
```

Ein neues Programm bekommt eine eigene Datei in `streamdeck_app/profiles/`.
Diese muss lediglich ein `PROFILE` exportieren und wird beim Start automatisch
gefunden. Das Feld `order` bestimmt die Reihenfolge bei der manuellen
Profilwahl. Bildschirmdarstellungen bleiben davon getrennt in
`streamdeck_app/screens/`.

Fuer dynamische Profile kann die Profildatei eine Unterklasse von
`ProfileLifecycle` als `lifecycle_factory` eintragen. Verfuegbar sind
`on_activate`, `on_deactivate`, `on_button`, `on_encoder` und `on_tick`.

## Hardware-Funktionstest

Interaktiver Hardware-Funktionstest fuer den SOOMFON CN002 (`1500:3001`):

- USB-Erkennung und exklusives Oeffnen des Steuer-Interfaces
- alle sechs 60-x-60-LCDs (Farbe, Rahmen, Nummer und Ausrichtung)
- Helligkeitssteuerung
- Druecken und Loslassen aller sechs LCD-Tasten
- Druecken und Loslassen der drei Zusatztasten
- Druecken und Loslassen aller drei Drehencoder
- Links- und Rechtsdrehung aller drei Encoder

## Start unter Windows

Die offizielle SOOMFON-Software zuerst vollstaendig beenden und das Geraet per
USB-Datenkabel verbinden. Dann in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python .\test.py
```

Falls die PowerShell-Ausfuehrungsrichtlinie die Aktivierung blockiert, geht es
ohne Aktivierung:

```powershell
.\.venv\Scripts\python.exe .\test.py
```

Der Test schreibt am Ende `function_test_report.json`. Die LCDs werden beim
Beenden geleert und auf 60 Prozent Helligkeit gesetzt.

Weitere Modi:

```powershell
# Nur erkennen, ohne Schreibzugriff
.\.venv\Scripts\python.exe .\test.py --diagnose

# Displays und Helligkeit ansteuern, ohne interaktive Eingabepruefung
.\.venv\Scripts\python.exe .\test.py --smoke

# Eingabetest mit fuenf Minuten Zeitlimit
.\.venv\Scripts\python.exe .\test.py --timeout 300
```

## Venv neu erstellen

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
