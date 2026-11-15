"""Baut die Kartendaten für die Testseite aus einem OpenStreetMap-Auszug.

Eingabe: ein .osm.pbf (vorher mit osmium tags-filter auf Supermärkte und Postleitzahl-Grenzen reduziert).
Ausgabe (im Zielordner):
  meta.json                 Stand der Daten, Anzahl Märkte und Postleitzahlen
  plz/<NN>.json             Postleitzahl -> [Breite, Länge, Ort], aufgeteilt nach den ersten zwei Ziffern
  maerkte/<B>_<L>.json      Märkte der App-Ketten je 1°x1°-Kachel: [kette, Breite, Länge, Straße, Ort, Webseite]

Daten: © OpenStreetMap-Mitwirkende, Lizenz ODbL (abgeleitete Datenbank, ebenfalls ODbL).
Aufruf: python tools/daten_bauen.py auszug.osm.pbf data
"""
import datetime
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

import osmium
import shapely.wkb

# Gleiche Regeln wie in index.html (KETTEN). Reihenfolge ist wichtig.
KETTEN = [
    ("aldi-nord", ["Q41171373"], r"aldi\s*nord", r"aldi-nord\.de"),
    ("aldi-sued", [], r"aldi\s*s(ü|ue|u)d", r"aldi-sued\.de"),
    ("aldi", [], r"^aldi\b", None),
    ("lidl", ["Q151954"], r"lidl", r"lidl\.de"),
    ("kaufland", [], r"kaufland", r"kaufland\.de"),
    ("marktkauf", [], r"marktkauf", r"marktkauf\.de"),
    ("edeka", ["Q701755"], r"edeka|e[\s-]?center", r"(^|\.|//)edeka\.de"),
    ("netto", ["Q879858"], r"netto", r"netto-online\.de"),
    ("nahkauf", [], r"nahkauf", r"nahkauf\.de"),
    ("rewe", ["Q16968817"], r"rewe", r"rewe\.de"),
    ("penny", ["Q284688"], r"penny", r"penny\.de"),
    ("norma", [], r"\bnorma\b", r"norma-online\.de"),
]
KETTEN = [(k, wd, re.compile(m, re.I), re.compile(d, re.I) if d else None) for k, wd, m, d in KETTEN]
NETTO_DAENISCH = "Q552652"


def kette_von(tags) -> str | None:
    text = " | ".join(v for v in (tags.get("brand"), tags.get("name"), tags.get("brand:de")) if v)
    wd = tags.get("brand:wikidata", "")
    web = tags.get("website") or tags.get("contact:website") or tags.get("url") or ""
    if wd == NETTO_DAENISCH:
        return None
    for k, wds, muster, domain in KETTEN:
        if wd in wds or (text and muster.search(text)) or (domain and web and domain.search(web)):
            if k == "aldi":
                if re.search(r"aldi-sued\.de", web, re.I):
                    return "aldi-sued"
                if re.search(r"aldi-nord\.de", web, re.I) or wd == "Q41171373":
                    return "aldi-nord"
            return k
    return None


def webseite(k: str, tags) -> str:
    web = tags.get("website") or tags.get("contact:website") or ""
    for kid, _, _, domain in KETTEN:
        if kid == k and domain and web and domain.search(web):
            return web
    return ""  # fremde Seiten (z. B. Prospekt-Portale) werden nicht übernommen


class Sammler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.wkb = osmium.geom.WKBFactory()
        self.maerkte = []
        self.plz = {}

    def _markt(self, tags, lat, lon):
        k = kette_von(tags)
        if not k:
            return
        strasse = " ".join(v for v in (tags.get("addr:street"), tags.get("addr:housenumber")) if v)
        ort = tags.get("addr:city") or tags.get("addr:place") or tags.get("addr:suburb") or ""
        self.maerkte.append([k, round(lat, 5), round(lon, 5), strasse, ort, webseite(k, tags)])

    def node(self, n):
        if n.tags.get("shop") == "supermarket" and n.location.valid():
            self._markt(n.tags, n.location.lat, n.location.lon)

    def area(self, a):
        t = a.tags
        ist_markt = t.get("shop") == "supermarket"
        code = t.get("postal_code", "")
        ist_plz = t.get("boundary") == "postal_code" and re.fullmatch(r"\d{5}", code or "")
        if not (ist_markt or ist_plz):
            return
        try:
            geom = shapely.wkb.loads(self.wkb.create_multipolygon(a), hex=True)
        except Exception:  # kaputte Geometrie in OSM: überspringen
            return
        p = geom.representative_point()
        if ist_markt:
            self._markt(t, p.y, p.x)
        elif code not in self.plz:
            ort = t.get("note") or t.get("name") or ""
            ort = re.sub(r"^\s*\d{5}\s*", "", ort).strip()
            self.plz[code] = [round(p.y, 5), round(p.x, 5), ort]


def main(eingabe: str, ziel: str) -> None:
    ziel = Path(ziel)
    s = Sammler()
    s.apply_file(eingabe, locations=True)

    # Doppelte Einträge (gleiche Kette, < 30 m auseinander, z. B. Punkt + Gebäude) zusammenfassen
    gesehen, maerkte = set(), []
    for m in s.maerkte:
        schluessel = (m[0], round(m[1], 3), round(m[2], 3))
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        maerkte.append(m)

    for alt in list(ziel.glob("maerkte/*.json")) + list(ziel.glob("plz/*.json")):
        alt.unlink()
    (ziel / "maerkte").mkdir(parents=True, exist_ok=True)
    (ziel / "plz").mkdir(parents=True, exist_ok=True)

    kacheln = defaultdict(list)
    for m in maerkte:
        kacheln[f"{math.floor(m[1])}_{math.floor(m[2])}"].append(m)
    for name, liste in kacheln.items():
        (ziel / "maerkte" / f"{name}.json").write_text(json.dumps(liste, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    gruppen = defaultdict(dict)
    for code, wert in s.plz.items():
        gruppen[code[:2]][code] = wert
    for vorne, d in gruppen.items():
        (ziel / "plz" / f"{vorne}.json").write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")

    je_kette = defaultdict(int)
    for m in maerkte:
        je_kette[m[0]] += 1
    meta = {
        "erstellt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        "quelle": "OpenStreetMap (Geofabrik-Auszug Deutschland)",
        "lizenz": "© OpenStreetMap-Mitwirkende, ODbL",
        "maerkte": len(maerkte),
        "postleitzahlen": len(s.plz),
        "kacheln": len(kacheln),
        "je_kette": dict(sorted(je_kette.items())),
    }
    (ziel / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
