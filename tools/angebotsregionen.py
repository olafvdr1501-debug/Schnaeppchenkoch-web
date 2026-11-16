"""Angebotsregion je Markt: zu welcher EDEKA-Regionalgesellschaft gehört ein EDEKA-Markt?

Die Angebote von EDEKA unterscheiden sich je Region (Nord, Minden-Hannover, Rhein-Ruhr, Hessenring,
Nordbayern-Sachsen-Thüringen, Südbayern, Südwest). Viele Märkte tragen ihre Region selbst in der Webseiten-Adresse
der Kartendaten, z. B. „https://www.edeka.de/eh/südbayern/edeka-…/index.jsp“ – das sind die Anker.
Für die übrigen Märkte gilt: Haben die drei nächstgelegenen Anker dieselbe Region, gilt sie auch hier; sonst
bleibt die Region offen (der Markt bekommt dann nur bundesweite Angebote). Geprüft mit dem Auszug vom 15.11.2026,
jeder Anker gegen seine Nachbarn: 886 von 891 richtig (99,4 %), 47 an Grenzen offen.

Daten: © OpenStreetMap-Mitwirkende, ODbL. Es wird keine Seite abgerufen – nur die Adressen in den Kartendaten gelesen.
Aufruf (vorhandene Kacheln nachrüsten): python tools/angebotsregionen.py data
"""
import json
import math
import re
import sys
import urllib.parse
from collections import Counter
from pathlib import Path

# Region in der edeka.de-Adresse → Kennung der Angebotsregion (so heißt sie auch in angebote/aktuell.json)
EDEKA = {"nord": "edeka-nord", "minden-hannover": "edeka-minden-hannover", "rhein-ruhr": "edeka-rhein-ruhr",
         "hessenring": "edeka-hessenring", "nordbayern-sachsen-thüringen": "edeka-nst",
         "südbayern": "edeka-suedbayern", "südwest": "edeka-suedwest"}
ADRESSE = re.compile(r"edeka\.de/eh/([^/]+)/", re.I)
NACHBARN = 3


def anker_region(web: str) -> str | None:
    m = ADRESSE.search(urllib.parse.unquote(web or ""))
    return EDEKA.get(m.group(1).lower()) if m else None


def km(a, b) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[1], a[2], b[1], b[2]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def zuordnen(maerkte: list[list]) -> Counter:
    """Hängt an jeden Markt [kette, Breite, Länge, Straße, Ort, Webseite, PLZ] als 8. Feld die Angebotsregion an
    ("" = keine). Gibt die Anzahl je Region zurück."""
    anker = [(m, anker_region(m[5])) for m in maerkte if m[0] == "edeka" and anker_region(m[5])]
    zahl = Counter()
    for m in maerkte:
        del m[7:]
        region = ""
        if m[0] == "edeka":
            region = anker_region(m[5]) or ""
            if not region and anker:
                nah = sorted(anker, key=lambda a: km(m, a[0]))[:NACHBARN]
                regionen = {r for _, r in nah}
                region = regionen.pop() if len(regionen) == 1 else ""
            zahl[region or "offen"] += 1
        m.append(region)
    return zahl


def main(ordner: str) -> None:
    ordner = Path(ordner)
    kacheln = {p: json.loads(p.read_text(encoding="utf-8")) for p in sorted(ordner.glob("maerkte/*.json"))}
    zahl = zuordnen([m for liste in kacheln.values() for m in liste])
    for p, liste in kacheln.items():
        p.write_text(json.dumps(liste, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    meta_datei = ordner / "meta.json"
    meta = json.loads(meta_datei.read_text(encoding="utf-8"))
    meta["angebotsregionen"] = dict(sorted(zahl.items()))
    meta_datei.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(meta["angebotsregionen"], ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1])
