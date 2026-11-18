#!/usr/bin/env python3
"""
Abgleich der <rs type="person"> und <rs type="work"> in listevent.xml mit PMB.

Eingabe:  listevent.xml, PMB-Exporte listPerson.xml und listBibl.xml
Ausgabe:  pmb-personen.csv  (Name im Programm -> pmb-ID)
          pmb-werke.csv     (Komponist(en) + Werktitel -> pmb-ID)

Die CSV-Dateien sind zum Nachbearbeiten gedacht: html-to-listevent.py liest sie
und setzt daraus ref="#pmb…" (bei sicherheit=unsicher zusätzlich cert="low").
Ein leeres pmb-Feld heißt: kein Treffer. Zeilen mit manuell=ja werden bei einem
neuen Lauf nicht überschrieben.

Aufruf:
  python3 pmb-match.py [listPerson.xml] [listBibl.xml]
"""
import csv
import difflib
import math
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
N = "{http://www.tei-c.org/ns/1.0}"
XID = "{http://www.w3.org/XML/1998/namespace}id"
PERSON_CSV = HERE / "pmb-personen.csv"
WORK_CSV = HERE / "pmb-werke.csv"
PERSON_FIELDS = ["name", "anzahl", "pmb", "pmb_name", "lebensdaten", "sicherheit",
                 "methode", "kandidaten", "manuell"]
WORK_FIELDS = ["komponisten", "werk", "anzahl", "pmb", "pmb_titel", "sicherheit",
               "methode", "kandidaten", "manuell"]

# Kürzel und Namen, die ohne Kontext nicht eindeutig sind (pmb-ID)
PERSON_OVERRIDES = {
    "CA": "28247",            # Conrad Ansorge
    "Franz": "205779",        # Robert Franz
    "R. Franz": "205779",
    "Robert Franz": "205779",
    "Scarlatti": "359968",    # Domenico (Klavier), nicht Alessandro
    "Tausig": "194676",       # Carl Tausig
    "C. P. E. Bach": "259195",  # in PMB als 'Bach, Carl' (1714–1788)
    "Ph. Em. Bach": "259195",
    "Lalo": "203069",         # Édouard Lalo
    "Strauss": "12870",       # im Programm meist R. Strauss (Lieder)
    "Strauß": "12870",
    "Bronsart": "355071",     # Hans Bronsart von Schellendorff
    "Mendelssohn": "12228",   # Felix Mendelssohn Bartholdy
    "Bruch": "193925",        # Max Bruch
    "Beriot": "354545",       # Charles-Auguste de Bériot
    "Palestrina": "155140",   # Giovanni Pierluigi da Palestrina
    "J. L. Roeckel": "305410",  # Joseph Leopold Röckel
}
MUSIC_OCC = re.compile(r"Kompon|Musik|Pianist|Dirigent|Geiger|Organist|Cellist|Sänger|"
                       r"Kapellmeister|Violinist|Liederdicht|Harfen|Flötist|Cembal", re.I)
COMPOSER_OCC = re.compile(r"Kompon")
MUSIC_KINDS = re.compile(r"Klavier|Lied|Oper|Konzert|Sinfonie|Quartett|Kammermusik|Chor|"
                         r"Orchester|Ouvertüre|Messe|Oratorium|Orgel|Ballett|Operette|"
                         r"Kantate|Musik|Requiem|Melodram|Singspiel")
PARTICLES = {"v", "von", "van", "de", "d", "der", "le", "la", "di", "da", "du", "mr"}
FIRST_NAME_VARIANTS = [("c", "k"), ("ph", "f"), ("th", "t"), ("y", "i"), ("w", "v"),
                       ("j", "i"), ("ks", "x")]
# so häufige Nachnamen, dass ohne Vornamen nicht geraten wird
COMMON_SURNAMES = {"meyer", "meier", "neumann", "sommer", "hermann", "hoffmann", "hofmann",
                   "schmidt", "walter", "fuchs", "wolff", "becker", "muller", "schulz"}


def norm(s):
    s = s.replace("ß", "ss").replace("’", "'").translate(str.maketrans("łŁøØđĐ", "lLoOdD"))
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9' -]", "", s).strip()


def skey(s):
    """Schlüssel für Nachnamen: Löwe = Loewe, Händel = Haendel."""
    s = norm(s)
    for a, b in (("ae", "a"), ("oe", "o"), ("ue", "u")):
        s = s.replace(a, b)
    return s


def loose(s):
    """Für Vornamen: Carl=Karl, Rudolph=Rudolf, Josef=Joseph …"""
    s = norm(s)
    for a, b in FIRST_NAME_VARIANTS:
        s = s.replace(a, b)
    return s


# ----------------------------------------------------------------- PMB laden --

def load_pmb(person_file, bibl_file):
    persons = {}
    for _, el in ET.iterparse(person_file):
        if el.tag != N + "person":
            continue
        pid = el.get(XID).split("__")[1]
        names = []
        for pn in el.findall(N + "persName"):
            sn = (pn.findtext(N + "surname") or "").strip()
            fn = (pn.findtext(N + "forename") or "").strip()
            if not (sn or fn) and pn.text and pn.text.strip():
                if pn.get("type", "").endswith("vorname"):
                    fn = pn.text.strip()
                else:
                    sn = pn.text.strip()
            if sn or fn:
                names.append((fn, sn))

        def year(tag):
            d = el.find(f"{N}{tag}/{N}date")
            if d is None:
                return None
            v = d.get("when-iso") or d.get("notBefore-iso") or d.text or ""
            m = re.search(r"-?\d{3,4}", v)
            return int(m.group()) if m else None

        idno = {i.get("subtype"): i.text for i in el.findall(N + "idno")}
        persons[pid] = {
            "names": names, "b": year("birth"), "d": year("death"),
            "occ": [o.text or "" for o in el.findall(N + "occupation")],
            "ansorge": "ansorge" in idno, "wd": bool(idno.get("wikidata")),
        }
        el.clear()
    works = {}
    for _, el in ET.iterparse(bibl_file):
        if el.tag != N + "bibl" or not el.get(XID, "").startswith("work__"):
            continue
        wid = el.get(XID).split("__")[1]
        works[wid] = {
            "titles": [t.text or "" for t in el.findall(N + "title")
                       if t.text and not t.text.startswith("http")],
            "auth": [a.get("key", "").replace("person__", "") for a in el.findall(N + "author")],
            "kind": [n.text or "" for n in el.findall(N + "note") if n.get("type") == "work_kind"],
        }
        el.clear()
    return persons, works


def display_name(p):
    fn, sn = p["names"][0] if p["names"] else ("", "?")
    return f"{sn}, {fn}".strip(", ")


def life(p):
    return f"{p['b'] or '?'}–{p['d'] or '?'}"


# ------------------------------------------------------------ Personen-Match --

class PersonMatcher:
    def __init__(self, persons, works):
        self.P = persons
        self.music_works = Counter()
        self.all_works = Counter()
        for w in works.values():
            music = any(MUSIC_KINDS.search(k) for k in w["kind"])
            for a in set(w["auth"]):
                self.all_works[a] += 1
                if music:
                    self.music_works[a] += 1
        # Suchstufen: 0 Hauptname exakt, 1 alle Namen/Umlautvarianten, 2 Namensteile
        self.tiers = [defaultdict(set), defaultdict(set), defaultdict(set)]
        for pid, p in persons.items():
            for i, (fn, sn) in enumerate(p["names"]):
                if not sn:
                    continue
                n = norm(sn)
                parts = [x for x in n.split() if x not in PARTICLES]
                plain_sn = " ".join(parts)  # 'van Beethoven' -> 'beethoven'
                if i == 0:
                    self.tiers[0][n].add(pid)
                    self.tiers[0][plain_sn].add(pid)
                for k in (n, plain_sn, skey(n), skey(plain_sn)):
                    self.tiers[1][k].add(pid)
                if len(parts) > 1:  # 'Mendelssohn Bartholdy' -> 'mendelssohn'
                    for x in (parts[0], parts[-1]):
                        self.tiers[2][x].add(pid)
                        self.tiers[2][skey(x)].add(pid)
        self.known_keys = set(self.tiers[1]) | set(self.tiers[2])
        self.musician_surnames = sorted({skey(sn) for pid, p in persons.items()
                                         if self.music_score(pid) >= 2
                                         for fn, sn in p["names"] if sn})

    def ident(self, pid):
        """Für PMB-Dubletten: gleicher Name, gleiches Geburtsjahr."""
        p = self.P[pid]
        fn = p["names"][0][0] if p["names"] else ""
        return (loose(fn.split()[0]) if fn.split() else "", p["b"], p["d"])

    def music_score(self, pid):
        p = self.P[pid]
        s = 0
        if any(COMPOSER_OCC.search(o) for o in p["occ"]):
            s += 3
        elif any(MUSIC_OCC.search(o) for o in p["occ"]):
            s += 2
        mw = self.music_works[pid]
        if mw:
            s += 2 + math.log2(1 + mw)
        if p["ansorge"]:   # im Ansorge-Register: fast immer Musiker
            s += 2.5
        return s

    def plausible_dates(self, pid):
        b, d = self.P[pid]["b"], self.P[pid]["d"]
        return (b is None or b <= 1925) and (d is None or d >= 1500)

    @staticmethod
    def split_name(name):
        """'C. M. v. Weber' -> (['c', 'm'], 'weber'); 'Niels W. Gade' -> (['niels', 'w'], 'gade')."""
        name = re.sub(r"\s*\[.*", "", name).strip()
        toks = name.replace(".", ". ").split()
        # Nachname: letztes Token, Partikel davor gehören dazu ('d’Albert')
        surname = toks[-1]
        given = toks[:-1]
        given = [g for g in given if g not in ("Mr.", "v.")
                 and (g.endswith(".") or norm(g) not in PARTICLES)]
        return given, surname

    def forename_ok(self, given, pid):
        if not given:
            return True
        forenames = []
        for fn, _ in self.P[pid]["names"]:
            forenames += [loose(f) for f in re.split(r"[\s\-.]+", fn) if f]
        if not forenames:
            return False
        for i, g in enumerate(given):
            if i > 0 and len(set(forenames)) < len(given):
                break  # 'C. P. E. Bach' ~ 'Carl Bach': nur erste Initiale prüfen
            gl = loose(g.rstrip("."))
            if not gl:
                continue
            if g.endswith(".") or len(gl) <= 2:   # Initiale/Abkürzung: 'Ph.', 'Jos.', 'C.'
                if not any(f.startswith(gl) for f in forenames):
                    return False
            elif not any(f == gl or f.startswith(gl) or gl.startswith(f) and len(f) > 3
                         or difflib.SequenceMatcher(None, f, gl).ratio() >= 0.8
                         for f in forenames):   # 'Kostantin' ~ 'Constantin'
                return False
        return True

    def candidates(self, surname, given):
        n = norm(surname)
        keys = {n, " ".join(x for x in n.split() if x not in PARTICLES)}
        names = ["Nachname", "Nachname (Variante)", "Namensteil"]
        first_found = None
        for t, tier in enumerate(self.tiers):
            tkeys = keys | {skey(k) for k in keys} if t else keys
            found = {c for k in tkeys for c in tier.get(k, ())
                     if self.plausible_dates(c) and self.forename_ok(given, c)}
            if t == 2:   # Namensteile nur für Musiker ('Arnold von Lübeck' nein)
                found = {c for c in found if self.music_score(c) >= 2}
            if any(self.music_score(c) >= 2 for c in found):
                return found, names[t]
            if found and first_found is None:
                first_found = (found, names[t])
        if first_found:
            return first_found
        if any(k in self.known_keys or skey(k) in self.known_keys for k in keys):
            return set(), "Nachname bekannt, Vorname passt nicht"
        found = set()
        close = difflib.get_close_matches(skey(n), self.musician_surnames, n=3, cutoff=0.86)
        for c in close:
            found |= {pid for pid in self.tiers[1][c] if self.music_score(pid) >= 2
                      and self.plausible_dates(pid) and self.forename_ok(given, pid)}
        ratio = max((difflib.SequenceMatcher(None, skey(n), c).ratio() for c in close), default=0)
        return found, f"ähnlich {ratio:.2f} (" + ", ".join(close) + ")"

    def match(self, name):
        if name in PERSON_OVERRIDES:
            return PERSON_OVERRIDES[name], "sicher", "Vorgabe", []
        given, surname = self.split_name(name)
        cands, method = self.candidates(surname, given)
        if not cands and "-" in surname:   # Doppelname, nur erster Teil in PMB
            cands, method = self.candidates(surname.split("-")[0], given)
            method += " (erster Teil)"
        if not cands:
            return "", "", method if "bekannt" in method else "kein Treffer", []
        ranked = sorted(cands, key=lambda c: (-self.music_score(c), -self.all_works[c],
                                               not self.P[c]["wd"], int(c)))
        top = ranked[0]
        rivals = [c for c in ranked[1:] if self.ident(c) != self.ident(top)]
        s1 = self.music_score(top)
        s2 = self.music_score(rivals[0]) if rivals else -1
        if s1 < 2:
            # kein Musiker bekannt: nur bei einem einzigen Kandidaten übernehmen
            if rivals:
                return "", "", "kein Musiker, mehrdeutig", ranked[:5]
            cert = "unsicher"
        elif s2 < 2 or s1 - s2 >= 4:
            cert = "sicher"
        elif s1 - s2 >= 1.5:
            cert = "wahrscheinlich"
        else:
            cert = "unsicher"
        top_fn = {f for fn, _ in self.P[top]["names"] for f in fn.split()}
        if len(given) > 1 and len(top_fn) < len(given) and cert != "unsicher":
            cert = "unsicher"   # nicht alle Initialen prüfbar ('H. C. Schmidt')
        if method == "Namensteil":
            cert = "unsicher"
        if method.startswith("ähnlich"):
            cert = "wahrscheinlich" if float(method.split()[1]) >= 0.9 and cert != "unsicher" \
                else "unsicher"
        elif method != "Nachname" and cert == "sicher":
            cert = "wahrscheinlich"
        if cert == "unsicher" and not given and (
                skey(surname) in COMMON_SURNAMES
                or sum(1 for c in rivals if self.music_score(c) >= max(2, s1 - 1.5)) >= 2):
            return "", "", "zu mehrdeutig", ranked[:5]
        return top, cert, method, ranked[:5]


# --------------------------------------------------------------- Werk-Match --

GENRE = [  # (Muster, Normalform)
    (r"klaviersonate|sonate|sonata|sonaten|sonatine", "sonate"),
    (r"klavierkonzert|violinkonzert|cellokonzert|konzert|concert|concerto|konzerte", "konzert"),
    (r"symphonie|sinfonie|symphony", "sinfonie"),
    (r"klavierfantasie|fantasie|phantasie|fantaisie|fantasia", "fantasie"),
    (r"etude|etuden|etudes|etuede|etueden|konzertetude|konzertetuden", "etude"),
    (r"rhapsodie|rhapsodien|rapsodie", "rhapsodie"),
    (r"nocturne|nocturnes|notturno", "nocturne"),
    (r"walzer|valse|valses|waltz", "walzer"),
    (r"prelude|preludes|praludium|praeludium|preludium|praludien", "praludium"),
    (r"variationen|variations|variation|veranderungen", "variationen"),
    (r"ouverture|ouvertuere|overture|ouvertur", "ouverture"),
    (r"polonaise|polonaisen", "polonaise"), (r"mazurka|mazurkas|mazurken", "mazurka"),
    (r"ballade|balladen", "ballade"), (r"scherzo|scherzi", "scherzo"),
    (r"impromptu|impromptus", "impromptu"), (r"fuge|fugue|fuga", "fuge"),
    (r"lied|lieder|gesang|gesange", "lied"), (r"rondo|rondos", "rondo"),
    (r"trio|trios|klaviertrio", "trio"), (r"quartett|streichquartett|quartet", "quartett"),
    (r"quintett|klavierquintett", "quintett"), (r"bagatelle|bagatellen", "bagatelle"),
    (r"romanze|romance|romanzen", "romanze"), (r"berceuse", "berceuse"),
    (r"barkarole|barcarolle", "barkarole"), (r"tarantella|tarantelle", "tarantella"),
    (r"toccata|toccaten", "toccata"), (r"suite|suiten", "suite"),
    (r"chaconne|ciaccona", "chaconne"), (r"menuett|menuet|minuetto", "menuett"),
]
GENRE_RE = [(re.compile(r"^(?:" + p + r")$"), n) for p, n in GENRE]
STOP = set("""fur und in aus der die das des den dem op opp nr no a fur klavier pianoforte
piano orchester mit von zu zum zur fuer et de la le les sur un une for and the of
grosse grosses grosser grande grand zwei drei vier funf sechs sieben acht neun zehn
zwolf two three four five six""".split())
KEYS = re.compile(r"\b([A-Ha-h])(is|es|s)?[-\s]?(Dur|Moll|dur|moll)\b")


def genre_of(w):
    for rx, n in GENRE_RE:
        if rx.match(w):
            return n
    return None


def work_features(title):
    t = title.replace("„", " ").replace("“", " ").replace("»", " ").replace("«", " ") \
        .replace('"', " ")
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", t)   # Anmerkungen
    f = {"op": None, "sub": None, "cat": None, "nr": None, "key": None}
    m = re.search(r"\bop(?:us)?\.?\s*(\d+)\s*(?:[/,]\s*|\s+)?(?:(?:Nr|No)\.?\s*)?(\d+|[IVX]+\b)?", t, re.I)
    if m:
        f["op"] = m.group(1)
        sub = m.group(2)
        if sub and re.fullmatch(r"[IVX]+", sub):
            sub = str("I II III IV V VI VII VIII IX X XI XII".split().index(sub) + 1)
        if sub and (re.search(r"/|Nr|No", m.group(0)) or "," not in m.group(0)):
            f["sub"] = sub
        t = t[:m.start()] + " " + t[m.end():]
    m = re.search(r"\b(KV|BWV|WoO|S|R|Hob\.?)\s*\.?\s*(\d+\w?)", t)
    if m:
        f["cat"] = (m.group(1).rstrip(".").upper(), m.group(2))
        t = t[:m.start()] + " " + t[m.end():]
    m = KEYS.search(t)
    if m:
        f["key"] = (m.group(1).lower() + (m.group(2) or "")).replace("as", "as") + \
            ("-dur" if m.group(3).lower() == "dur" else "-moll")
        t = t[:m.start()] + " " + t[m.end():]
    m = re.search(r"(?:\bNr\.?|\bNo\.?|^\s*)\s*(\d+)\b\.?", t)
    if m:
        f["nr"] = m.group(1)
        t = t[:m.start()] + " " + t[m.end():]
    words = set()
    genres = set()
    for w in re.findall(r"[a-z0-9']+", norm(t.replace("-", " "))):
        if w in STOP or w.isdigit() or len(w) < 2:
            continue
        g = genre_of(w)
        if g:
            genres.add(g)
        else:
            words.add(w[:-1] if len(w) > 5 and w.endswith(("n", "s")) else w)
    f["words"], f["genres"] = words, genres
    return f


def work_score(pf, wf, ptitle, wtitle):
    """Punktzahl (None = Widerspruch)."""
    for k in ("key", "cat"):
        if pf[k] and wf[k] and pf[k] != wf[k]:
            return None
    if pf["op"] or wf["op"]:
        if pf["op"] and wf["op"]:
            if pf["op"] != wf["op"]:
                return None
            if pf["sub"] and wf["sub"] and pf["sub"] != wf["sub"]:
                return None
            if pf["sub"] and not wf["sub"]:
                return None  # Programm nennt Einzelstück, PMB nur die Sammlung
            score = 6
            if wf["sub"] and not pf["sub"]:
                score -= 3     # PMB-Einzelstück, Programm meint die ganze Opuszahl
        else:
            score = 0
    else:
        score = 0
    if pf["nr"] and wf["nr"] and pf["nr"] != wf["nr"] and not (pf["op"] and wf["op"]):
        return None
    if pf["cat"] and wf["cat"]:
        score += 6
    if pf["genres"] and wf["genres"]:
        if pf["genres"] & wf["genres"]:
            score += 2
        elif score < 6:
            return None
    if pf["key"] and wf["key"]:
        score += 2
    if pf["nr"] and pf["nr"] == wf["nr"]:
        score += 1
    pw, ww = pf["words"], wf["words"]
    if pw or ww:
        inter = len(pw & ww)
        jac = inter / len(pw | ww)
        if pw and not inter and score < 6:
            return None
        score += 4 * jac
        if pw and ww and pw <= ww or ww <= pw and ww:
            score += 1
    elif not pf["genres"] and not pf["op"]:
        return None
    a, b = norm(ptitle), norm(wtitle)
    if a == b:
        score += 4
    return score


class WorkMatcher:
    def __init__(self, works):
        self.by_author = defaultdict(list)
        for wid, w in works.items():
            for t in w["titles"]:
                for a in set(w["auth"]):
                    self.by_author[a].append((wid, t, work_features(t)))

    def match(self, composer_ids, title):
        if re.search(r"\bopp\.|^(?:Sonaten|Lieder|Werke|Stücke)\b|\bop\.\s*\d+\w*,\s*\d", title):
            return "", "", "Sammelangabe", []
        res = self.match_title(composer_ids, title)
        if res[0]:
            return res
        # Teil eines größeren Werks: 'Arie des Sextus aus „Titus“' -> Titus
        m = re.search(r"\b(?:aus|a\. d\.)\s+(?:de[rmns]\s+)?(?:Oper\s+|Musik zu\s+|Oratorium\s+)?"
                      r"„?([^“,(]+)“?", title)
        if m and len(m.group(1)) > 3:
            part = self.match_title(composer_ids, m.group(1).strip())
            if part[0]:
                return part[0], "unsicher", "Teil aus: " + part[3][0] if part[3] else "Teil aus", part[3]
        return res

    def match_title(self, composer_ids, title):
        pf = work_features(title)
        if not (pf["op"] or pf["cat"] or pf["words"] or pf["genres"]):
            return "", "", "zu unspezifisch", []
        scored = {}
        for cid in composer_ids:
            for wid, t, wf in self.by_author.get(cid, ()):
                s = work_score(pf, wf, title, t)
                if s is not None and s > scored.get(wid, (-1,))[0]:
                    scored[wid] = (s, t)
        if not scored:
            return "", "", "kein Treffer", []
        ranked = sorted(scored.items(), key=lambda x: (-x[1][0], len(x[1][1])))
        (wid, (s1, t1)) = ranked[0]
        s2 = ranked[1][1][0] if len(ranked) > 1 else 0
        cands = [f"{w} {t} ({s:.1f})" for w, (s, t) in ranked[:4]]
        if s1 < 3:
            return "", "", "zu schwach", cands
        if s1 - s2 < 1:
            # gleichwertige Kandidaten; identische Titel (Doppeleinträge) sind egal
            if norm(ranked[1][1][1]) != norm(t1):
                return wid, "unsicher", "mehrdeutig", cands
        cert = "sicher" if s1 >= 8 else "wahrscheinlich" if s1 >= 5 else "unsicher"
        return wid, cert, "Titel/Opus/Tonart", cands


# ------------------------------------------------------------------ Ablauf --

def collect(listevent):
    """Personen- und Werknennungen (mit Komponisten des Programmpunkts) zählen."""
    root = ET.parse(listevent).getroot()
    persons, works = Counter(), Counter()
    for item in root.iter(N + "item"):
        composers = []
        seen_work = False
        for rs in item.findall(N + "rs"):
            txt = "".join(rs.itertext())
            if rs.get("type") == "person":
                if seen_work:      # neuer Komponist mitten im Punkt
                    composers, seen_work = [], False
                composers.append(txt)
                persons[txt] += 1
            elif rs.get("type") == "work":
                seen_work = True
                works[("/".join(composers), txt)] += 1
    return persons, works


def read_manual(path, keyf):
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return {keyf(r): r for r in csv.DictReader(f) if r.get("manuell") == "ja"}


def main():
    person_file = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "listPerson.xml"
    bibl_file = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE.parent / "listBibl.xml"
    persons, works = load_pmb(person_file, bibl_file)
    pm, wm = PersonMatcher(persons, works), WorkMatcher(works)
    p_count, w_count = collect(HERE.parent / "data" / "indices" / "listevent.xml")

    manual_p = read_manual(PERSON_CSV, lambda r: r["name"])
    rows, pid_of = [], {}
    for name, n in sorted(p_count.items(), key=lambda x: (-x[1], x[0])):
        if name in manual_p:
            r = manual_p[name]
            r["anzahl"] = n
        else:
            pid, cert, method, ranked = pm.match(name)
            r = {"name": name, "anzahl": n, "pmb": pid, "sicherheit": cert, "methode": method,
                 "pmb_name": display_name(persons[pid]) if pid else "",
                 "lebensdaten": life(persons[pid]) if pid else "",
                 "kandidaten": " | ".join(f"{c} {display_name(persons[c])} {life(persons[c])}"
                                          for c in ranked if c != pid),
                 "manuell": ""}
        pid_of[name] = r["pmb"]
        rows.append(r)
    with open(PERSON_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=PERSON_FIELDS)
        w.writeheader()
        w.writerows(rows)

    manual_w = read_manual(WORK_CSV, lambda r: (r["komponisten"], r["werk"]))
    wrows = []
    for (comp, title), n in sorted(w_count.items(), key=lambda x: (x[0][0], x[0][1])):
        if (comp, title) in manual_w:
            r = manual_w[(comp, title)]
            r["anzahl"] = n
        else:
            cids = [pid_of.get(c) for c in comp.split("/") if pid_of.get(c)] if comp else []
            wid, cert, method, cands = wm.match(cids, title) if cids else ("", "", "kein Komponist", [])
            r = {"komponisten": comp, "werk": title, "anzahl": n, "pmb": wid,
                 "pmb_titel": works[wid]["titles"][0] if wid else "", "sicherheit": cert,
                 "methode": method, "kandidaten": " | ".join(cands), "manuell": ""}
        wrows.append(r)
    with open(WORK_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=WORK_FIELDS)
        w.writeheader()
        w.writerows(wrows)

    def stats(rs, cnt):
        c = Counter(r["sicherheit"] or "–" for r in rs if r["pmb"])
        hit = sum(int(r["anzahl"]) for r in rs if r["pmb"])
        tot = sum(int(r["anzahl"]) for r in rs)
        return f"{sum(1 for r in rs if r['pmb'])}/{len(rs)} Formen, {hit}/{tot} Nennungen, {dict(c)}"
    print(f"{PERSON_CSV.name}: {stats(rows, p_count)}")
    print(f"{WORK_CSV.name}: {stats(wrows, w_count)}")


if __name__ == "__main__":
    main()
