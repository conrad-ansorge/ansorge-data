#!/usr/bin/env python3
"""
Abgleich der Orte (<settlement>) und Veranstaltungsorte (<placeName type="venue">)
in data/indices/listevent.xml mit dem PMB-Export listplace.xml.

Ausgabe:  pmb-orte.csv               Ort im Kalender -> pmb-ID
          pmb-veranstaltungsorte.csv  (Ort, Veranstaltungsort) -> pmb-ID
          pmb-neue-orte.csv           alles ohne Treffer, zum Anlegen in der PMB

Veranstaltungsorte werden nur unter den PMB-Orten gesucht, die (auch über
Zwischenstufen wie Bezirk oder Straße) in der zugeordneten Stadt liegen.
Zeilen mit manuell=ja bleiben bei einem neuen Lauf erhalten. Danach
html-to-listevent.py laufen lassen, das setzt die ref="#pmb…".

Aufruf:
  python3 pmb-orte.py [listplace.xml]
"""
import csv
import difflib
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
LISTEVENT = HERE.parent / "data" / "indices" / "listevent.xml"
ORT_CSV = HERE / "pmb-orte.csv"
VENUE_CSV = HERE / "pmb-veranstaltungsorte.csv"
NEW_CSV = HERE / "pmb-neue-orte.csv"
N = "{http://www.tei-c.org/ns/1.0}"
XID = "{http://www.w3.org/XML/1998/namespace}id"

ORT_FIELDS = ["ort", "anzahl", "pmb", "pmb_name", "pmb_typ", "liegt_in", "sicherheit",
              "methode", "kandidaten", "manuell"]
VENUE_FIELDS = ["ort", "veranstaltungsort", "anzahl", "pmb", "pmb_name", "pmb_typ",
                "sicherheit", "methode", "kandidaten", "manuell"]
NEW_FIELDS = ["pmb", "name", "liegt_in_pmb", "liegt_in", "im_kalender", "anzahl",
              "konzerte", "anmerkung"]  # im_kalender: alle Schreibweisen, durch ' | ' getrennt

# Siedlungen und Verwaltungseinheiten (GeoNames-Klassen P und A, PMB-Typen)
SETTLEMENT_TYPE = re.compile(r"^(?:P\.|A\.ADM|A\.PCL)|Besiedelter Ort|Teil eines besiedelten|"
                             r"Bezirk|Stadt|Gemeinde|^$")
# Gebäude, Säle, Institutionen: alles, was keine Siedlung, Straße, Landschaft ist
NOT_VENUE_TYPE = re.compile(r"^(?:P\.|A\.|T\.|H\.|L\.|N\.|V\.)|Straße|Platz|Bezirk|Besiedelt|"
                            r"Bahnhof|Wohngebäude|Postamt|Berg|Tal|Insel|Land")
# Ortsangaben im Kalender, die anders heißen als in der PMB (Kalender -> PMB-Name)
ORT_ALIASES = {
    "cassel": "kassel", "coblenz": "koblenz", "cothen": "kothen", "buenos-aires": "buenos aires",
    "kristiania": "oslo", "petersburg": "sankt petersburg", "lodz": "łódź",
    "teplitz": "teplice", "teplitz-schonau": "teplice", "graz a": "graz",
    "frankenstein schlesien": "ząbkowice śląskie", "pressburg": "bratislava",
    "bratislava / pressburg": "bratislava", "hirschberg in schlesien": "jelenia góra",
    "landeshut in schlesien": "kamienna góra", "landeshut schlesien": "kamienna góra",
    "landeshut": "kamienna góra", "liegnitz schlesien": "legnica",
    "halle saale": "halle (saale)", "hamborn am rhein": "hamborn", "den haag": "den haag",
    "freiberg in sachsen": "freiberg", "annaberg- buchholz": "annaberg-buchholz",
    "berlin-westend": "westend", "berlin westend": "westend", "berlin pankow": "pankow",
    "brandenburg a d h": "brandenburg an der havel", "blankenburg/harz": "blankenburg (harz)",
    "arnau a d elbe": "arnau", "belgard pommern": "białogard",
}
# feste Zuordnungen (normalisierter Kalendertext -> pmb-ID), wo der Name allein irreführt
ORT_IDS = {
    "liebau": "304872",          # Lubawka (Schlesien), nicht Libau/Liepāja
    "koslin": "335758",          # Koszalin
    "marburg": "59021",          # Marburg an der Lahn, nicht Maribor
    "eger": "90565",             # Cheb, nicht Eger in Ungarn
    "mullheim": "405058",        # Müllheim im Markgräflerland
    "new york": "44053",         # New York City, nicht der Bundesstaat
    "lemberg": "46224",          # Lviv (Stadt), nicht die Oblast
    "moskau": "91304",           # Stadt
    "salt lake city": "120274",
    "langenbielau": "403949",    # Bielawa
    "morchenstern": "349509",    # Smržovka
    "oberleutensdorf": "299035",  # Litvínov
    "blankenburg/harz": "54027",
    "pankow": "17871",           # Berlin-Pankow
    "berlin pankow": "17871",
    "berlin": "168",
    "orange": "8028",            # Orange, New Jersey (Llewellyn Park)
    "graz a": "860",             # der in der PMB übliche Graz-Eintrag
}
# Hinweise für die Liste der fehlenden Orte
ORT_NOTES = {
    "halberstadt u blankenburg": "zwei Orte, beide in der PMB: Halberstadt 50762, Blankenburg 54027",
    "berlin blankenburg": "vermutlich Blankenburg (Harz) 54027, vgl. „Blankenburg/Harz, Fürstenhof-Saal“",
    "berlin westend": "Ortsteil von Charlottenburg (9925)",
    "munchener volkstheater": "kein Ort, sondern Veranstaltungsort in München (45258)",
    "aula des lyzeums": "kein Ort, sondern Veranstaltungsort; Ort fehlt in der Vorlage",
    "dur": "unklar, wohl verlesen",
    "hirschberg": "unklar, welches Hirschberg",
    "hirschberg erzgebirge": "in der Vorlage selbst unsicher",
}
# kein Treffer erzwingen (ähnliche PMB-Namen meinen etwas anderes)
ORT_NONE = {"berlin westend", "berlin-westend", "berlin blankenburg", "dur", "aula des lyzeums",
            "munchener volkstheater", "halberstadt u blankenburg"}
# Wörter, die für den Vergleich von Saalnamen nichts bedeuten
VENUE_STOP = set("""im in der des dem den die das zu zum zur am an auf und bei vom von
saal saale sale salen grosser grosse grossen gr kleiner kleine kleinen
of the at""".split())


GENERIC_VENUES = set("""schloss theater stadttheater kurhaus aula rathaus museum konzerthaus
stadthalle fest casino kasino hotel harmonie schutzenhaus gesellschaftshaus konzert musik
tonhalle kursaal stadt neues alte alten deutsches deutsche""".split())


def norm(s):
    s = s.replace("ß", "ss").replace("’", "'")
    s = s.translate(str.maketrans("łŁøØđĐ", "lLoOdD"))
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[\[\]()?.,;:„“\"»«]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def ort_key(s):
    """'Landeshut [Schlesien]' -> 'landeshut schlesien'; '[Leipzig]' -> 'leipzig'."""
    return norm(s)


# ----------------------------------------------------------------- PMB laden --

def load_places(path):
    places = {}
    for _, el in ET.iterparse(path):
        if el.tag != N + "place":
            continue
        pid = el.get(XID).split("__")[1]
        names = [(p.text or "").strip() for p in el.findall(N + "placeName") if (p.text or "").strip()]
        within = [l.find(N + "placeName").get("key", "").replace("place__", "")
                  for l in el.findall(f"{N}location[@type='located_in_place']")
                  if l.find(N + "placeName") is not None]
        idno = {i.get("subtype"): i.text for i in el.findall(N + "idno")}
        places[pid] = {
            "names": list(dict.fromkeys(names)),
            "typ": el.findtext(f"{N}desc[@type='entity_type']") or "",
            "within": [w for w in within if w],
            "ansorge": "ansorge" in idno,
            "ids": sum(1 for k in idno if k != "pmb"),
        }
        el.clear()
    return places


class PlaceIndex:
    def __init__(self, places):
        self.P = places
        self.by_name = defaultdict(set)
        self.children = defaultdict(set)
        for pid, p in places.items():
            for n in p["names"]:
                self.by_name[norm(n)].add(pid)
                # 'Halle (Saale)' auch als 'halle'; 'Josefov [Prag]' nicht als Stadt
                base = norm(re.sub(r"\s*[(\[].*", "", n))
                if base and SETTLEMENT_TYPE.search(p["typ"]):
                    self.by_name[base].add(pid)
            for w in p["within"]:
                self.children[w].add(pid)
        self.settlement_names = sorted(k for k, v in self.by_name.items()
                                       if any(SETTLEMENT_TYPE.search(places[x]["typ"]) for x in v))

    def descendants(self, pid, depth=4):
        out, front = set(), {pid}
        for _ in range(depth):
            front = {c for f in front for c in self.children.get(f, ())} - out
            out |= front
        return out

    def label(self, pid):
        p = self.P[pid]
        within = ", ".join(self.P[w]["names"][0] for w in p["within"][:1] if w in self.P)
        return f"{pid} {p['names'][0]} [{p['typ'] or '–'}]" + (f" in {within}" if within else "")

    # ---------------------------------------------------------------- Orte --
    def settlement_rank(self, pid):
        p = self.P[pid]
        t = p["typ"]
        r = 0
        if re.match(r"P\.PPL(?:C|G|A)$", t):
            r += 4.5   # Haupt- und Verwaltungssitze
        elif re.match(r"P\.PPLA\d", t):
            r += 4
        elif t == "A.ADM1":
            r += 3
        elif t.startswith("P.PPL") or "Besiedelter Ort" in t:
            r += 3.5   # Stadt vor gleichnamiger Verwaltungseinheit
        elif t.startswith("A.ADM"):
            r += 1.5
        elif t == "":
            r += 0.5
        return r + min(p["ids"], 4) * 0.5 + min(len(self.children.get(pid, ())), 20) * 0.1 \
            + (1 if p["ansorge"] else 0)

    def match_ort(self, text):
        key = ort_key(text)
        if not key or key in ("o o",):
            return "", "", "kein Ort", []
        keys = [key]
        if key in ORT_ALIASES:
            keys.insert(0, norm(ORT_ALIASES[key]))
        # 'Königgrätz (Böhmen)', 'Landshut (Bayern)', 'Graz (A)': Zusatz weglassen
        short = norm(re.sub(r"\s*[(\[].*?[)\]]\s*", " ", text))
        if short and short not in keys:
            keys.append(short)
            if short in ORT_ALIASES:
                keys.append(norm(ORT_ALIASES[short]))
        if key in ORT_NONE:
            return "", "", "kein Treffer", []
        for k in keys:
            if k in ORT_IDS:
                return ORT_IDS[k], "sicher", "Vorgabe", []
        method = "Name"
        cands = set()
        for k in keys:
            cands = {c for c in self.by_name.get(k, ()) if SETTLEMENT_TYPE.search(self.P[c]["typ"])}
            if cands:
                if k != key:
                    method = "Variante"
                break
        if not cands:
            close = difflib.get_close_matches(key, self.settlement_names, n=2, cutoff=0.88)
            for c in close:
                cands |= {x for x in self.by_name[c] if SETTLEMENT_TYPE.search(self.P[x]["typ"])}
            method = "ähnlich (" + ", ".join(close) + ")"
        if not cands:
            return "", "", "kein Treffer", []
        ranked = sorted(cands, key=lambda c: (-self.settlement_rank(c), int(c)))
        top = ranked[0]
        # Konkurrenz: gleichnamige Siedlungen mit Typ ('Frankfurt am Main' / '(Oder)' bei
        # 'Frankfurt'), nicht 'Ost-Berlin' oder typlose Dubletten
        def base(c):
            return norm(re.sub(r"\s*[(\[].*", "", self.P[c]["names"][0]))
        rivals = [c for c in ranked[1:] if self.P[c]["typ"]
                  and (base(c) == base(top) or base(c) in keys or norm(self.P[c]["names"][0]) in keys)
                  and base(c) not in ("",)]
        rivals = [c for c in rivals if base(c) == base(top) or base(c).split()[0] == base(top).split()[0]]
        r1 = self.settlement_rank(top)
        if any(self.settlement_rank(c) >= r1 - 1 for c in rivals):
            cert = "unsicher"
        elif rivals:
            cert = "wahrscheinlich"
        else:
            cert = "sicher"
        if method.startswith("ähnlich"):
            cert = "unsicher"
        if "?" in text and cert == "sicher":
            cert = "wahrscheinlich"   # '[Hannover?]': Ort im Kalender selbst unsicher
        return top, cert, method, [self.label(c) for c in ranked[:4]]

    # ---------------------------------------------------- Veranstaltungsorte --
    @staticmethod
    def venue_tokens(s, pmb=False):
        if pmb:
            s = re.sub(r"\[[^\]]*\]", " ", s)    # PMB-Zusatz 'Stadttheater [Lübeck]'
        s = re.sub(r"\[(?:sic|\?)\]", " ", s)     # '[sic]', '[?]'; '[Rudolphinum]' bleibt
        s = norm(s.replace("-", " ").replace("’", "").replace("'", "")).replace("ph", "f")
        toks = [t for t in s.split() if t not in VENUE_STOP and not t.isdigit() and len(t) > 1]
        out = []
        for t in toks:   # 'blüthnersaal' -> 'bluthner'; 'kaisersaal' bleibt als ganzes
            for suf in ("saale", "saal", "sale", "salen"):
                if t.endswith(suf) and len(t) > len(suf) + 3:
                    t = t[:-len(suf)]
            out.append(t)
        return out

    @staticmethod
    def contains(x, y):
        """Teilwort nur, wenn das kürzere Wort lang genug ist ('blüthner' ~ 'blüthnersaal',
        aber nicht 'de' in 'deutschlandsender' oder 'museum' in 'museumsbrücke')."""
        if x == y:
            return True
        short, long_ = sorted((x, y), key=len)
        return len(short) >= 5 and short in long_ and len(short) / len(long_) >= 0.7

    def venue_score(self, vt, name, text=""):
        nt = self.venue_tokens(name, pmb=True)
        if not vt or not nt:
            return 0
        # verschiedene Hausnummern: 'Köthener Str. 32' ist nicht 'Köthener Straße 44'
        n1, n2 = set(re.findall(r"\d+", text)), set(re.findall(r"\d+", name))
        if n1 and n2 and not n1 & n2:
            return 0
        a, b = "".join(vt), "".join(nt)
        if a == b:
            return 1.0
        if all(t in GENERIC_VENUES for t in vt):
            return 0   # 'Schloss', 'Stadttheater' allein: nur bei gleichem Namen
        if self.contains(a, b):
            return 0.9
        hits = sum(1 for t in vt if any(self.contains(t, u) for u in nt))
        back = sum(1 for u in nt if any(self.contains(t, u) for t in vt))
        cover = hits / len(vt)
        ratio = difflib.SequenceMatcher(None, a, b).ratio()
        score = max(cover * 0.85 if hits else 0, ratio if ratio >= 0.9 else 0)
        if hits and back == len(nt) and not all(u in GENERIC_VENUES for u in nt):
            score = max(score, 0.8)   # alle Wörter des PMB-Namens kommen vor
        return score

    def match_venue(self, city_ids, text):
        vt = self.venue_tokens(text)
        if not vt:
            return "", "", "zu allgemein", []
        pool = set()
        for c in city_ids:
            pool |= self.descendants(c)
        pool = {p for p in pool if not NOT_VENUE_TYPE.search(self.P[p]["typ"])}
        scored = []
        for p in pool:
            s = max(self.venue_score(vt, n, text) for n in self.P[p]["names"])
            if s >= 0.6:
                scored.append((s, p))
        if not scored:
            return "", "", "kein Treffer", []
        scored.sort(key=lambda x: (-x[0], int(x[1])))
        s1, top = scored[0]
        cands = [f"{self.label(p)} ({s:.2f})" for s, p in scored[:4]]
        if s1 < 0.75:
            return "", "", "zu schwach", cands
        same = [p for s, p in scored[1:] if s >= s1 - 0.05
                and norm(self.P[p]["names"][0]) != norm(self.P[top]["names"][0])]
        cert = "sicher" if s1 >= 0.9 and not same else "wahrscheinlich" if not same else "unsicher"
        return top, cert, "Name in Stadt", cands


# ------------------------------------------------------------------ Ablauf --

def collect():
    root = ET.parse(LISTEVENT).getroot()
    orte, venues = Counter(), Counter()
    konzerte = defaultdict(list)
    for ev in root.iter(N + "event"):
        desc = ev.find(N + "desc")
        if desc is None:
            continue
        date = (desc.findtext(N + "date") or "").strip()
        for pn in desc.findall(N + "placeName"):
            st = pn.find(N + "settlement")
            ve = pn.find(f"{N}placeName[@type='venue']")
            city = "".join(st.itertext()) if st is not None else ""
            if city:
                orte[city] += 1
                konzerte[("ort", city, "")].append(date)
            if ve is not None:
                v = "".join(ve.itertext())
                venues[(city, v)] += 1
                konzerte[("venue", city, v)].append(date)
    return orte, venues, konzerte


def read_manual(path, keyf):
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return {keyf(r): r for r in csv.DictReader(f) if r.get("manuell") == "ja"}


def write(path, fields, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def apply_new_numbers():
    """In pmb-neue-orte.csv eingetragene Nummern auf alle Schreibweisen übertragen
    (als manuell=ja in pmb-orte.csv / pmb-veranstaltungsorte.csv). Zeilen ohne
    liegt_in/liegt_in_pmb sind Orte, die anderen Veranstaltungsorte."""
    if not NEW_CSV.exists():
        return
    with open(NEW_CSV, encoding="utf-8") as f:
        new = [r for r in csv.DictReader(f) if r.get("pmb", "").strip()]
    if not new:
        return
    with open(ORT_CSV, encoding="utf-8") as f:
        orte = list(csv.DictReader(f))
    with open(VENUE_CSV, encoding="utf-8") as f:
        venues = list(csv.DictReader(f))
    ort_pmb = {r["ort"]: r["pmb"] for r in orte}
    n = 0
    for nr in new:
        pid = re.sub(r"\D", "", nr["pmb"])
        variants = {v.strip() for v in nr["im_kalender"].split(" | ")}
        is_ort = not nr.get("liegt_in", "").strip() and not nr.get("liegt_in_pmb", "").strip() \
            and nr.get("art", "Ort") == "Ort"
        targets = ([r for r in orte if r["ort"] in variants] if is_ort else
                   [r for r in venues if r["veranstaltungsort"] in variants
                    and ((nr["liegt_in_pmb"] and ort_pmb.get(r["ort"]) == nr["liegt_in_pmb"])
                         or (not nr["liegt_in_pmb"] and r["ort"] == nr["liegt_in"]))])
        for r in targets:
            r.update(pmb=pid, pmb_name=nr["name"], sicherheit="sicher",
                     methode="manuell (neu in PMB)", manuell="ja", kandidaten="")
            n += 1
    write(ORT_CSV, ORT_FIELDS, orte)
    write(VENUE_CSV, VENUE_FIELDS, venues)
    print(f"aus {NEW_CSV.name} übernommen: {len(new)} Nummern für {n} Schreibweisen")


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "listplace.xml"
    apply_new_numbers()
    idx = PlaceIndex(load_places(src))
    orte, venues, konzerte = collect()

    manual = read_manual(ORT_CSV, lambda r: r["ort"])
    ort_rows, ort_id = [], {}
    for o, n in sorted(orte.items(), key=lambda x: (-x[1], x[0])):
        if o in manual:
            r = manual[o] | {"anzahl": n}
        else:
            pid, cert, method, cands = idx.match_ort(o)
            p = idx.P.get(pid, {})
            r = {"ort": o, "anzahl": n, "pmb": pid, "pmb_name": p.get("names", [""])[0],
                 "pmb_typ": p.get("typ", ""),
                 "liegt_in": ", ".join(idx.P[w]["names"][0] for w in p.get("within", [])[:1]
                                       if w in idx.P),
                 "sicherheit": cert, "methode": method,
                 "kandidaten": " | ".join(c for c in cands if not c.startswith(pid + " ")) if pid
                 else " | ".join(cands), "manuell": ""}
        ort_id[o] = r["pmb"]
        ort_rows.append(r)
    write(ORT_CSV, ORT_FIELDS, ort_rows)

    manual = read_manual(VENUE_CSV, lambda r: (r["ort"], r["veranstaltungsort"]))
    venue_rows = []
    for (o, v), n in sorted(venues.items(), key=lambda x: (x[0][0], x[0][1])):
        if (o, v) in manual:
            r = manual[(o, v)] | {"anzahl": n}
        else:
            city = ort_id.get(o)
            if city and city not in idx.P:   # Ort neu in der PMB, noch nicht im Export
                pid, cert, method, cands = "", "", "Ort neu in PMB", []
            elif city:
                # alle PMB-Einträge gleichen Namens (Dubletten) als Stadt zulassen
                same = {c for c in idx.by_name.get(norm(idx.P[city]["names"][0]), ())}
                pid, cert, method, cands = idx.match_venue({city} | same, v)
            else:
                pid, cert, method, cands = "", "", "Ort ohne PMB", []
            p = idx.P.get(pid, {})
            r = {"ort": o, "veranstaltungsort": v, "anzahl": n, "pmb": pid,
                 "pmb_name": p.get("names", [""])[0], "pmb_typ": p.get("typ", ""),
                 "sicherheit": cert, "methode": method, "kandidaten": " | ".join(cands),
                 "manuell": ""}
        venue_rows.append(r)
    write(VENUE_CSV, VENUE_FIELDS, venue_rows)

    # Liste zum Anlegen: Schreibvarianten desselben Saals (gleiche Stadt, gleiche
    # Kernwörter) werden zu einer Zeile zusammengefasst
    groups = []   # [art, stadt-pmb, stadt-text, schlüssel, {variante: anzahl}, daten]
    def add(art, city_pmb, city, key, variant, n, dates):
        for g in groups:
            if g[0] == art and (g[1] or g[2]) == (city_pmb or city) and \
                    (g[3] == key or (key and g[3] and idx.contains(g[3], key))):
                g[4][variant] = g[4].get(variant, 0) + n
                g[5] += dates
                return
        groups.append([art, city_pmb, city, key, {variant: n}, list(dates)])
    for r in ort_rows:
        if not r["pmb"] and r["methode"] != "kein Ort":
            add("Ort", "", "", ort_key(re.sub(r"\s*\(.*?\)|,\s*[A-Z]{2}\b", "", r["ort"])).replace("-", " "), r["ort"],
                int(r["anzahl"]), konzerte[("ort", r["ort"], "")])
    for r in venue_rows:
        if not r["pmb"]:
            add("Veranstaltungsort", ort_id.get(r["ort"], ""), r["ort"],
                "".join(idx.venue_tokens(r["veranstaltungsort"])), r["veranstaltungsort"],
                int(r["anzahl"]), konzerte[("venue", r["ort"], r["veranstaltungsort"])])
    new = []
    for art, city_pmb, city, key, variants, dates in groups:
        name = max(variants, key=lambda v: (variants[v], -len(v)))
        new.append({"name": re.sub(r"^(?:im|in der|in)\s+", "", name),
                    "liegt_in_pmb": city_pmb,
                    "liegt_in": idx.P[city_pmb]["names"][0] if city_pmb in idx.P else city,  # Anzeige
                    "im_kalender": " | ".join(sorted(variants)),
                    "anzahl": sum(variants.values()),
                    "konzerte": ", ".join(sorted(set(dates))[:6]),
                    "anmerkung": ORT_NOTES.get(ort_key(name).replace("-", " "), "")})
    new.sort(key=lambda r: (bool(r["liegt_in"]), r["liegt_in"], -r["anzahl"], r["name"]))
    write(NEW_CSV, NEW_FIELDS, new)

    def stats(rows):
        c = Counter(r["sicherheit"] for r in rows if r["pmb"])
        return (f"{sum(1 for r in rows if r['pmb'])}/{len(rows)} Formen, "
                f"{sum(int(r['anzahl']) for r in rows if r['pmb'])}/"
                f"{sum(int(r['anzahl']) for r in rows)} Nennungen, {dict(c)}")
    print(f"{ORT_CSV.name}: {stats(ort_rows)}")
    print(f"{VENUE_CSV.name}: {stats(venue_rows)}")
    print(f"{NEW_CSV.name}: {len(new)} Einträge ohne PMB-Nummer")


if __name__ == "__main__":
    main()
