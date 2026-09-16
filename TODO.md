# Roadmap

Diese Datei ist die gemeinsame Arbeitsliste fuer den SOOMFON Controller. Wir
arbeiten die Phasen der Reihe nach ab; nach jeder Phase muss der Controller
weiterhin benutzbar sein.

## Bereits vorhanden

- [x] HID-Kommunikation mit dem SOOMFON CN002
- [x] vollstaendiger Hardware-Funktionstest
- [x] automatische Profile nach aktivem Windows-Fenster
- [x] einzelne Profilmodule fuer Desktop, Browser, VS Code, Explorer und Spotify
- [x] getrennte Bildschirmmodule fuer Profilanzeige und Screensaver
- [x] Idle-Animation mit drei eigenen Pixelwesen
- [x] manuelle Profilwahl und Profilsperre
- [x] grundlegende Medien- und Lautstaerkeaktionen
- [x] automatisierte Kern- und Renderingtests

## Phase 1 – Laufzeit stabilisieren und messen (abgeschlossen)

- [x] Konfiguration beim Start vollstaendig validieren
- [x] USB-Trennung erkennen und automatisch neu verbinden
- [x] Schreibfehler behandeln, ohne den Dienst zu beenden
- [x] LCD-Cache einfuehren: nur veraenderte Bilder uebertragen
- [x] Fensterwechsel entprellen und unbrauchbare Hilfsfenster ignorieren
- [x] Mock-Deck fuer Tests ohne echte Hardware bereitstellen
- [x] Messskript fuer CPU, RAM, Startzeit und HID-Schreiblast erstellen
- [x] Wiederverbindung einmal durch physisches Abziehen/Anstecken bestaetigen

Zielwerte, die wir auf dem echten PC messen und gegebenenfalls anpassen:

- Idle ohne Animation: durchschnittlich unter 0,5 Prozent CPU
- aktive Animation: durchschnittlich unter 2 Prozent CPU
- Arbeitsspeicher: moeglichst unter 100 MB
- keine GPU-Abhaengigkeit
- keine dauerhaften Netzwerkabfragen unter einer Sekunde

Fertig, wenn Abziehen/Anstecken und schnelle Fensterwechsel keinen manuellen
Neustart erfordern und ein reproduzierbarer Ressourcenbericht vorliegt.

Aktueller Mock-Benchmark auf dem Entwicklungs-PC (16.09.2026; die kurze
Windows-CPU-Messung ist wegen der Timeraufloesung als Obergrenze zu lesen):

- Idle-Dauerlast: unter 0,7 Prozent eines CPU-Kerns, ca. 24,5 MB RAM
- Screensaver-Dauerlast: unter 0,7 Prozent eines CPU-Kerns, ca. 25 MB RAM
- einmaliges Vorbereiten der Animation: ca. 0,13 Sekunden
- gemessene Spitzenbelegung inklusive Quelldateien: ca. 43 MB RAM

## Phase 2 – Profil- und Bildschirm-API (abgeschlossen)

- [x] einheitlichen Profil-Lebenszyklus definieren:
  `on_activate`, `on_deactivate`, `on_button`, `on_encoder`, `on_tick`
- [x] Profile automatisch aus `streamdeck_app/profiles/` entdecken
- [x] Profilzustand sauber von der zentralen Service-Schleife trennen
- [x] dynamische LCD-Inhalte und zeitlich begrenzte Overlays ermoeglichen
- [x] geaenderte Profile im Entwicklungsmodus ohne Neustart laden
- [x] Tests fuer Aktivierung, Deaktivierung und Profilwechsel ergaenzen

Fertig, wenn ein neues Programm nur eine eigene Profildatei benoetigt.

## Phase 3 – Screensaver-Steuerung (abgeschlossen)

- [x] langes Druecken direkt auf dem Streamdeck erkennen
- [x] Standardbelegung: grossen Encoder fuenf Sekunden druecken
- [x] Taste und Haltedauer ueber die Konfiguration aenderbar machen
- [x] langes Druecken aktiviert und beendet den Screensaver
- [x] kurze Stumm-Funktion des grossen Encoders erhalten
- [x] erste andere Deck-Eingabe beendet den Screensaver ohne Folgeaktion
- [x] weitere Screensaver als austauschbare Module vorbereiten
- [x] langes Druecken einmal am echten Deck bestaetigen

Die Haltedauer wird in der ohnehin laufenden HID-Schleife geprueft und erzeugt
daher keinen zusaetzlichen Polling-Thread.

## Phase 4 – Windows Audio Cockpit (implementiert, Handtest offen)

- [x] Encoder 1: Systemlautstaerke und Mute
- [x] Encoder 2: Lautstaerke der aktiven Anwendung und Mute
- [x] Encoder 3: Mikrofonlautstaerke und Mute
- [x] kurzzeitiges Lautstaerke-Overlay auf den LCDs
- [x] Audiogeraet zwischen Headset und Lautsprechern wechseln
- [x] fehlende oder neu gestartete Audio-Sessions automatisch behandeln
- [ ] System-, App-, Mikrofon- und Geraetefunktionen am echten Deck bestaetigen

Fertig, wenn Browser, Spiel, Spotify und Discord unabhaengig geregelt werden
koennen und jede Aenderung sichtbar bestaetigt wird.

## Phase 5 – Kurse im Screensaver auf den unteren drei LCDs (implementiert, Handtest offen)

- [x] allgemeine, read-only `MarketDataProvider`-Schnittstelle erstellen
- [x] drei Symbole/ISINs in einer eigenen Watchlist konfigurieren
- [x] pro LCD Name, Preis, Waehrung und Tagesveraenderung anzeigen
- [x] gruen/rot sowie Plus/Minus verwenden, damit Farbe nicht die einzige Information ist
- [x] Abruf in einem Hintergrund-Worker mit Cache und Backoff ausfuehren
- [x] Aktualisierung waehrend des Handels alle 15 Sekunden, sonst alle 30 Minuten
- [x] Markt geschlossen, veraltete Daten und Netzwerkfehler anzeigen
- [x] Tests mit aufgezeichneten Beispieldaten statt Live-Netzwerk erstellen
- [ ] Anzeige und Aktualisierung einmal am echten Deck bestaetigen

### Trade-Republic-Entscheidung

Trade Republic bietet derzeit keine oeffentlich dokumentierte Entwickler-API.
Vorhandene Python-Bibliotheken verwenden eine private, reverse-engineerte API
und brauchen Kontozugang beziehungsweise wiederkehrende Anmeldung. Daher:

- [x] zuerst einen unabhaengigen Marktdatenanbieter implementieren
- [x] keine Handels-, Order- oder Depotfunktionen in den Controller aufnehmen
- [x] Zugangsdaten niemals in `config.json`, Logs oder der EXE speichern
- [ ] optionalen Trade-Republic-Adapter nur nach separater Zustimmung bauen
- [ ] einen solchen Adapter strikt read-only und als optionales Zusatzmodul halten

Das erste sichere Ergebnis zeigt die gewuenschten Aktienkurse, ist aber nicht
mit dem Depotkonto verbunden. Exakt dieselben Trade-Republic-Handelsplatzkurse
waeren ein spaeterer, bewusst optionaler Schritt.

## Phase 6 – Onefile-EXE und Ressourcen (implementiert, Fremdsystemtest offen)

- [x] PyInstaller als Build-Abhaengigkeit hinzufuegen
- [x] zuerst einen leichter zu diagnostizierenden `onedir`-Build erstellen
- [x] danach einen `onefile --windowed`-Build erstellen
- [x] `.spec`-Datei fuer Bilder und native HID-Bibliothek pflegen
- [x] Assetzugriff fuer Quellcode und gepackte EXE vereinheitlichen
- [x] beschreibbare Konfiguration nach `%LOCALAPPDATA%\SoomfonController` legen
- [x] Logs ebenfalls ausserhalb der EXE speichern und begrenzen
- [x] unbenutzte Pakete, Module und Assets aus dem Bundle ausschliessen
- [x] Startzeit, EXE-Groesse, RAM und CPU des Builds messen
- [ ] Build auf einem Windows-System ohne Python testen

Onefile entpackt seine Bestandteile beim Start temporaer. Das macht den Start
etwas langsamer, veraendert aber die laufende Controller-Last nicht wesentlich.
Optionale schwere Integrationen werden deshalb lazy geladen und nicht pauschal
in den Hauptprozess eingebaut.

Messung auf dem Entwicklungs-PC (16.09.2026): Onefile 17,68 MB, Start bis
Controller bereit ca. 0,70 Sekunden, Spitzenbelegung des Entpack- und
Controller-Prozessbaums ca. 45,11 MB.

## Phase 7 – Autostart und Einzelinstanz

- [ ] sicherstellen, dass nur eine Controller-Instanz laufen kann
- [ ] `--install-autostart` und `--remove-autostart` bereitstellen
- [ ] Autostart nur fuer den aktuellen Benutzer unter `HKCU` einrichten
- [ ] Pfad zur EXE korrekt quoten
- [ ] verzögerten Start beziehungsweise USB-Wartephase unterstuetzen
- [ ] Autostartstatus ueber CLI und spaeter Tray-Menue anzeigen
- [ ] Eintrag bei Verschieben oder Entfernen der EXE sauber reparieren

Fertig, wenn die Onefile-EXE nach der Windows-Anmeldung ohne Konsole startet,
sich mit dem Deck verbindet und im Task-Manager deaktiviert werden kann.

## Phase 8 – Programmprofile ausbauen

- [ ] Spotify: Titel, Interpret, Cover und Wiedergabestatus
- [ ] Discord: Mikrofon, Deafen und Lautstaerke
- [ ] OBS: Szenen, Aufnahme, Stream und Quellenstatus
- [ ] Browser: Webseiten-spezifische Unterprofile
- [ ] VS Code: Tests, Debugger, Terminal und Git-Status

## Phase 9 – Bedienkomfort

- [ ] Windows-Tray-App fuer Status, Pause, Profilwahl und Screensaver
- [ ] Autostart im Tray-Menue ein-/ausschalten
- [ ] Konfiguration ohne Neustart neu laden
- [ ] Logdatei und Diagnosebericht aus dem Tray oeffnen
- [ ] lokaler Profil-Editor als spaeteres Teilprojekt

## Empfohlene Abarbeitungsreihenfolge

1. Phase 1: Stabilitaet und Ressourcenmessung
2. Phase 3: Screensaver-Tastenkombination als schneller sichtbarer Gewinn
3. Phase 2: dynamische Profil- und Bildschirm-API
4. Phase 4: vollstaendiges Audio Cockpit
5. Phase 5: sichere Kursanzeige auf der unteren Reihe
6. Phase 6: reproduzierbare Onefile-EXE
7. Phase 7: Autostart und Einzelinstanz
8. Phasen 8 und 9: weitere Integrationen und Bedienoberflaeche

## Definition of Done fuer jede Phase

- bestehende automatisierte Tests bleiben gruen
- neue Logik besitzt eigene Tests
- echter Kurztest auf dem angeschlossenen Deck wurde durchgefuehrt
- CPU-/RAM-Verhalten hat sich nicht unbeabsichtigt verschlechtert
- README und diese Roadmap sind aktualisiert
