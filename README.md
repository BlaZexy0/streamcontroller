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
- manuelle Seite `Dienste`: Status und Antwortzeit aus einer Uptime-Kuma-Statusseite

Im Spotify-Profil bleiben oben Zurueck, Play/Pause und Weiter erhalten. Die
mittlere obere Kachel zeigt das Cover samt Wiedergabestatus; unten laufen
Interpret und Titel ueber alle drei Displays. Die Beschriftungen `VOL-`,
`MUTE` und `VOL+` zeigen weiterhin die Aktionen der unteren Tasten. Die Daten
kommen alle zwei Sekunden aus der lokalen Windows-Mediensitzung. Es gibt
keinen Spotify-Login, keine Spotify-Web-API und keine Netzwerkabfrage durch
dieses Profil. Spotify muss mindestens einmal eine Wiedergabe gestartet haben,
damit Windows eine Sitzung samt Metadaten bereitstellt.

Das Discord-Profil wird fuer Discord Stable, PTB, Canary und Vesktop erkannt.
Oben liegen Mikrofon umschalten, Deafen umschalten und zum verbundenen
Sprachkanal springen. Unten liegen Discord leiser, Discord-Audio stummschalten
und Discord lauter. Mikrofon und Deafen verwenden die offiziellen
Windows-Kuerzel `Strg+Umschalt+M` und `Strg+Umschalt+D`; danach bestaetigt ein
kurzes Overlay die gesendete Aktion. Discord stellt den tatsaechlichen
Mute-Zustand ohne weitergehende Konto-/IPC-Anbindung nicht verlaesslich bereit,
daher behauptet das Overlay bewusst keinen Zustand.

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

## Uptime-Kuma-Dienste

Das manuell anwählbare Profil `Dienste` zeigt bis zu sechs veröffentlichte
Monitore gleichzeitig. Grün bedeutet online, Rot offline und Gelb Wartung.
Mit dem rechten kleinen Encoder wird bei mehr als sechs Diensten geblättert;
ein Druck auf eine LCD-Taste öffnet das Uptime-Kuma-Dashboard.

Die Integration nutzt ausschließlich die öffentlichen, lesenden Endpunkte
einer Uptime-Kuma-Statusseite. In Uptime Kuma zuerst unter `Statusseiten` eine
Seite erstellen, die gewünschten Monitore hinzufügen und deren Slug in
`uptime_kuma_status_page` in `config.json` eintragen. Beispiel für
`http://192.168.0.39:3001/status/homelab`: `"uptime_kuma_status_page": "homelab"`.
Es werden weder Benutzername noch Passwort im Controller gespeichert. Abruf,
Timeout und Abschalten lassen sich über die übrigen `uptime_kuma_*`-Werte
konfigurieren.

## Windows-Tray-Menue

Bei einem normalen Start erscheint der Controller im Windows-Infobereich. Das
Tray-Menue zeigt Verbindung, aktives Profil und Betriebszustand. Darueber kann
man den Controller pausieren oder fortsetzen, den Screensaver umschalten, ein
Profil fest auswaehlen und den Autostart ein- oder ausschalten.

`Konfiguration neu laden` uebernimmt Aenderungen an der aktiven `config.json`
ohne Neustart. Fehlerhafte Aenderungen werden ins Log geschrieben und der
zuletzt gueltige Stand bleibt aktiv. Das Menue kann Konfiguration und Logdatei
direkt oeffnen. `Diagnosebericht erstellen` schreibt und oeffnet
`%LOCALAPPDATA%\SoomfonController\diagnostic_report.json` mit Zustand und
Laufzeitpfaden, aber ohne Zugangsdaten.

`Profil-Editor öffnen` startet einen kleinen lokalen Editor im Standardbrowser.
Er ist nur ueber `127.0.0.1` und eine zufaellige Sitzungsadresse erreichbar.
Dort lassen sich Profilname, erkannte Prozessdateien, Reihenfolge sowie alle
sechs Beschriftungen, Farben und Aktionen bearbeiten. Neue Profile koennen
angelegt und vorhandene geloescht werden; mindestens ein Fallback-Profil ohne
Prozess muss bestehen bleiben. Beim Speichern entsteht neben der aktiven
Konfiguration eine `profiles.json`, und das Deck uebernimmt die Aenderungen
ohne Neustart. `Werkseinstellungen wiederherstellen` entfernt diese Datei.

Im Abschnitt `Bootlogo` kann ausserdem das Bild geaendert werden, das der
Controller direkt nach dem Einschalten zeigt. Die Vorschau wird mittig auf
320 x 240 Pixel zugeschnitten, ohne EXIF- oder sonstige Bildmetadaten neu als
JPEG erzeugt und erst nach einer Sicherheitsabfrage dauerhaft auf das Geraet
geschrieben. Die zuletzt gewaehlte Vorschau liegt als `boot_logo.jpg` neben
der aktiven Konfiguration. Das Bootlogo wird nicht bei jedem Programmstart
erneut geschrieben.

Aktionswerte im Editor:

- `key`: ein Tastenname wie `f5` oder `media_play_pause`
- `hotkey`: Tasten mit `+`, beispielsweise `ctrl+shift+p`
- `open`: URL, Datei oder Windows-Einstellungsadresse
- `launch`: Programm und Argumente mit `|`, etwa `notepad.exe | datei.txt`
- `internal`: eine vorhandene Controller-Aktion wie `system_volume_mute`
- `none`: nur Anzeige, keine Aktion

Fuer Diagnose- oder Konsolenbetrieb laesst sich das Tray abschalten:

```powershell
.\.venv\Scripts\python.exe .\controller.py --no-tray --verbose
```

## Windows-EXE bauen

Die reproduzierbaren PyInstaller-Builds werden so erstellt:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build_controller.ps1 all
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
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build_controller.ps1 onedir
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build_controller.ps1 onefile
```

Messung der gebauten Onefile-EXE:

```powershell
.\.venv\Scripts\python.exe -m tools.benchmark_build --duration 5
```

## Windows-Autostart

Der Controller ist fuer den aktuellen Benutzer im Windows-Autostart
eingerichtet. Standardmaessig wartet er nach der Anmeldung zehn Sekunden und
verbindet sich danach mit dem Deck. Ist das Deck noch nicht vorhanden, laeuft
die vorhandene USB-Wiederverbindung weiter.

Autostart installieren oder nach Verschieben/Neubauen der EXE reparieren:

```powershell
.\.venv\Scripts\python.exe .\controller.py --install-autostart
```

Andere Startverzoegerung, Status und Entfernen:

```powershell
.\.venv\Scripts\python.exe .\controller.py --install-autostart --autostart-delay 20
.\.venv\Scripts\python.exe .\controller.py --autostart-status
.\.venv\Scripts\python.exe .\controller.py --remove-autostart
```

Der Eintrag liegt ausschliesslich unter
`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`; Administratorrechte
sind nicht erforderlich. Ein benannter Windows-Mutex verhindert, dass durch
Autostart, Doppelklick oder Skript versehentlich zwei Controller gleichzeitig
auf dasselbe HID-Geraet zugreifen.

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
|-- media/
|   |-- model.py           # lokaler, anbieterunabhaengiger Medienzustand
|   `-- worker.py          # blockierungsfreier Spotify-Abruf alle zwei Sekunden
|-- integrations/
|   `-- windows_media.py   # lokale Windows-Mediensitzung fuer Spotify
|-- paths.py               # Bundle-Ressourcen und LOCALAPPDATA
|-- logging_setup.py       # begrenzte Datei- und Konsolenlogs
|-- autostart.py           # HKCU-Autostart installieren und pruefen
|-- control.py             # thread-sichere Befehle und Laufzeitstatus
|-- tray.py                # Windows-Infobereich und Bedienmenue
|-- single_instance.py     # zweite Controller-Instanz verhindern
|-- screens/
|   |-- display.py         # dynamische LCD-Inhalte und Overlay-Stapel
|   |-- discord.py         # Bestaetigung fuer Sprachaktionen
|   |-- market.py          # Kurskacheln im Screensaver
|   |-- spotify.py         # Cover, Status, Interpret und Titel
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
