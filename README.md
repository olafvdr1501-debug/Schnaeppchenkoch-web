# Schnäppchenkoch – Testseite

Postleitzahl eingeben und sehen, welche Supermärkte im Umkreis liegen – je Kette die nächste
Filiale mit Entfernung und einem Link zu den aktuellen Angeboten auf der Seite der Kette.

Testversion (Etappe 1). Die Seite läuft komplett im Browser mit vorberechneten Daten:
Jeden Sonntag lädt GitHub Actions (`.github/workflows/kartendaten.yml`) den
[Geofabrik-Auszug Deutschland](https://download.geofabrik.de/europe/germany.html), filtert die
Supermärkte der großen Ketten und die Postleitzahl-Gebiete heraus und legt sie als kleine Dateien
in `data/` ab (`tools/daten_bauen.py`). Die Suche dauert dadurch nur Sekundenbruchteile.
Nur wenn eine Postleitzahl in den Daten fehlt, fragt die Seite [Nominatim](https://nominatim.openstreetmap.org/).

Kartendaten: © [OpenStreetMap-Mitwirkende](https://www.openstreetmap.org/copyright), Lizenz ODbL.
Die Dateien in `data/` sind daraus abgeleitet und stehen ebenfalls unter der ODbL.
Angebote und Preise stehen auf den Seiten der Supermärkte; diese Seite verlinkt nur dorthin.
