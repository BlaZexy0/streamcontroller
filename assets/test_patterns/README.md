# LCD-Testmuster

Zu jedem Muster gibt es zwei Dateien:

- `.png`: das erzeugte 60-x-60-Quellbild in der beabsichtigten Ausrichtung
- `.device.jpg`: exakt die um 270 Grad gedrehte JPEG-Datei, die per HID an das
  SOOMFON-Display geschickt wird

Die JPEG-Dateien sehen am PC gedreht aus. Das ist beabsichtigt, weil das Panel
die Bilder in dieser Orientierung erwartet.

Im Unterordner `dimension_sweep` liegen Schachbretter mit 57 bis 62 Pixeln.
Sie pruefen, ob der interne JPEG-Decoder des Panels eine bestimmte Bildgroesse
auf die sichtbaren 60 x 60 Pixel skaliert.

Eine andere Startgroesse kann mit `--dimension-start` getestet werden. Das
Geraet scheint JPEGs unter 60 x 60 Pixeln zu ignorieren.
