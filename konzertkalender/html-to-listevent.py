#!/usr/bin/env python3
"""
Konzertkalender Conrad Ansorge: HTML-Export (aus PDF) -> TEI listEvent.

Warum nicht einfach td[1]..td[5]?
  Das HTML stammt aus einem PDF-Export. Die Tabellen haben logisch immer
  5 Spalten (Datum | Ort | Anlass | Programm | Quelle), physisch aber:
    - 4-Spalten-Tabellen: Programm und Quelle sind zu einer Spalte verschmolzen
      (155pt = 99pt + 56pt), Quelle fehlt dort.
    - colspan: Programm-Zelle über Programm+Quelle, Kommentarzeilen über 4/5
      Spalten, Kommentar+Quelle (colspan=4 + 1).
    - rowspan: Datum/Ort-Zellen über mehrere Zeilen -> in den Folgezeilen
      fehlen td's, alle weiteren td's rutschen nach links.
    - Ein Ereignis kann über viele <tr> verteilt sein (eine <tr> pro Druckzeile)
      und über Seiten-/Tabellengrenzen hinweg weiterlaufen.
  Daher: jede Tabelle wird zuerst in ein echtes Raster aufgelöst (colspan und
  rowspan berücksichtigt), dann werden die Zeilen zu Ereignissen zusammengeführt.

Programmpunkte: <rs type="person"> / <rs type="work"> mit ref="#pmb…" aus
pmb-personen.csv und pmb-werke.csv (siehe pmb-match.py; dort von Hand korrigieren).

Aufruf:
  python3 html-to-listevent.py [eingabe.html] [ausgabe.xml]
"""
import csv
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).parent
DEFAULT_IN = HERE / "conrad-ansorge-1862-1930-ein-pianist-des-fin-de-siecle-in-berlin-und-wien (verschoben).html"
DEFAULT_OUT = HERE.parent / "data" / "indices" / "listevent.xml"

XH = "{http://www.w3.org/1999/xhtml}"
TEI_NS = "http://www.tei-c.org/ns/1.0"
T = "{%s}" % TEI_NS
ET.register_namespace("", TEI_NS)

FIELDS = ["datum", "ort", "anlass", "programm", "quelle"]

MONTHS = {
    "jan": 1, "jän": 1, "feb": 2, "märz": 3, "mär": 3, "apr": 4, "april": 4,
    "mai": 5, "juni": 6, "jun": 6, "juli": 7, "jul": 7, "aug": 8, "sept": 9,
    "sep": 9, "okt": 10, "nov": 11, "dez": 12,
}
WEEKDAYS = r"(?:Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonnabend|Sonntag)"
DATE_START = re.compile(
    r"^\s*(?:" + WEEKDAYS + r",?\s*)?\[?\s*\??\s*(?:"
    r"\d{1,2}\.\s*(?:\d{1,2}\.|oder|u\.|und|/|–|-)"  # 12.03. / 12. oder 13.03.
    r"|(?:Jan|Jän|Feb|März|Mär|Apr|Mai|Juni|Juli|Aug|Sep|Okt|Nov|Dez)"
    r"|(?:Anfang|Ende|Mitte|Sommer|Herbst|Winter|Frühjahr|Frühling|Saison)"
    r"|\d{4}"
    r")"
    r"|^\s*" + WEEKDAYS + r",?\s*$"
)
YEAR_SECTION = re.compile(r"^\s*(\d{4})(?:\s*[–-]\s*(\d{4}))?\s*$")
# Wörter, vor denen ein Zeilenend-Bindestrich ein echter Ergänzungsstrich ist
KEEP_HYPHEN_BEFORE = {"und", "oder", "bis", "u.", "sowie", "bzw.", "als", "noch", "wie"}

LOG = []


def log(msg):
    LOG.append(msg)


# ---------------------------------------------------------------- Text/Runs --
# Eine "Zeile" ist eine Liste von Runs (text, italic). Eine Zeile entspricht
# einem <p> im HTML (bei <li> mit vorangestellter Nummer).

def italic_classes(root):
    css = "".join(s.text or "" for s in root.iter(XH + "style"))
    ital, normal = set(), set()
    for m in re.finditer(r"\.([\w-]+)\s*\{([^}]*)\}", css):
        if re.search(r"font-style:\s*italic", m.group(2)):
            ital.add(m.group(1))
        else:
            normal.add(m.group(1))
    return ital, normal


def runs_of(el, italic, ital_cls, norm_cls, out):
    cls = el.get("class")
    if cls in ital_cls:
        italic = True
    elif cls in norm_cls:
        italic = False
    if el.tag in (XH + "i", XH + "em"):
        italic = True
    if el.tag == XH + "br":
        out.append((" ", italic))
    if el.text:
        out.append((el.text, italic))
    for ch in el:
        runs_of(ch, italic, ital_cls, norm_cls, out)
        if ch.tail:
            out.append((ch.tail, italic))


def normalize_runs(runs):
    """Whitespace normalisieren, gleiche Formatierung verschmelzen."""
    merged = []
    for text, it in runs:
        text = re.sub(r"\s+", " ", text)
        if not text:
            continue
        if merged and merged[-1][1] == it:
            merged[-1] = (merged[-1][0] + text, it)
        else:
            merged.append((text, it))
    # führende/abschließende Leerzeichen der ganzen Zeile entfernen
    if merged:
        merged[0] = (merged[0][0].lstrip(), merged[0][1])
        merged[-1] = (merged[-1][0].rstrip(), merged[-1][1])
    merged = [r for r in merged if r[0]]
    # innerzeilige Trennungen aus dem PDF: "Einbeschee- rung" -> "Einbescherung"
    return [(fix_text(dehyphen_inline(t)), it) for t, it in merged]


# Fehler des PDF-Exports (verlorene Zeichen, falsche Umbrüche)
TEXT_FIXES = {
    "Beetho ven": "Beethoven",
    "M ynarski": "Młynarski",
}


def fix_text(text):
    for a, b in TEXT_FIXES.items():
        text = text.replace(a, b)
    return text


def dehyphen_inline(text):
    def repl(m):
        nxt = m.group(2)
        if nxt in KEEP_HYPHEN_BEFORE:
            return m.group(0)
        return m.group(1) + nxt
    text = re.sub(r"([a-zäöüß])- ([a-zäöüß][\w.]*)", repl, text)
    # römische Zahlen: "LX- VII" -> "LXVII"
    text = re.sub(r"\b([IVXLC]+)- ([IVXLC]+)\b", r"\1\2", text)
    # "Bösendorfer- Saal" -> "Bösendorfer-Saal"
    return re.sub(r"([A-Za-zäöüß])- ([A-ZÄÖÜ])", r"\1-\2", text)


def cell_lines(td, ital_cls, norm_cls):
    lines = []
    ps = list(td.iter(XH + "p"))
    if not ps:  # Text direkt im td
        runs = []
        runs_of(td, False, ital_cls, norm_cls, runs)
        r = normalize_runs(runs)
        return [r] if r else []
    li_of = {}
    for li in td.iter(XH + "li"):
        first = next(li.iter(XH + "p"), None)
        if first is not None:
            li_of[first] = li.get("data-list-text", "")
    for p in ps:
        runs = []
        runs_of(p, False, ital_cls, norm_cls, runs)
        r = normalize_runs(runs)
        if not r:
            continue
        if p in li_of and li_of[p]:
            r = [(li_of[p] + " ", False)] + r
        lines.append(r)
    return lines


def plain(line):
    return "".join(t for t, _ in line)


def join_lines(lines, sep=" "):
    """Zeilen zu Fließtext (Runs) verbinden, Silbentrennung am Zeilenende auflösen."""
    out = []
    for line in lines:
        if not line:
            continue
        if not out:
            out.extend(line)
            continue
        prev_text = out[-1][0]
        nxt_text = line[0][0]
        first_word = nxt_text.split(" ", 1)[0]
        if re.search(r"[A-Za-zÄÖÜäöüß]-$", prev_text):
            if re.match(r"[a-zäöüß]", nxt_text) and first_word not in KEEP_HYPHEN_BEFORE:
                out[-1] = (prev_text[:-1], out[-1][1])  # An-|sorge -> Ansorge
            # sonst: Weihnachts-|Bescheerung, d-|Moll -> Bindestrich bleibt
        elif re.search(r"/$", prev_text):
            pass  # 1913/|14
        else:
            out[-1] = (prev_text + sep, out[-1][1])
        out.extend(line)
    # gleiche Formatierung verschmelzen
    merged = []
    for t, it in out:
        if merged and merged[-1][1] == it:
            merged[-1] = (merged[-1][0] + t, it)
        else:
            merged.append((t, it))
    return [(fix_text(t), it) for t, it in merged]


# ------------------------------------------------------------------- Raster --

class Cell:
    __slots__ = ("lines", "row", "col", "colspan", "rowspan", "table")

    def __init__(self, lines, row, col, colspan, rowspan, table):
        self.lines, self.row, self.col = lines, row, col
        self.colspan, self.rowspan, self.table = colspan, rowspan, table

    @property
    def text(self):
        return " ".join(plain(l) for l in self.lines).strip()


def table_grid(tbl, tno, ital_cls, norm_cls):
    """Liefert (ncols, rows); rows = Liste von Listen der Länge ncols mit
    (Cell, origin: bool) oder None."""
    trs = list(tbl.iter(XH + "tr"))
    occupied = {}  # (r, c) -> Cell
    origin = {}
    ncols = 0
    for r, tr in enumerate(trs):
        c = 0
        for td in tr.findall(XH + "td"):
            while (r, c) in occupied:
                c += 1
            cs = int(td.get("colspan") or 1)
            rs = int(td.get("rowspan") or 1)
            cell = Cell(cell_lines(td, ital_cls, norm_cls), r, c, cs, rs, tno)
            for dr in range(rs):
                for dc in range(cs):
                    occupied[(r + dr, c + dc)] = cell
            origin[(r, c)] = cell
            c += cs
        ncols = max(ncols, c)
    rows = []
    for r in range(len(trs)):
        row = []
        for c in range(ncols):
            cell = occupied.get((r, c))
            row.append(None if cell is None else (cell, origin.get((r, c)) is cell))
        rows.append(row)
    return ncols, rows


def logical_field(ncols, cell):
    """Physische Startspalte -> logisches Feld."""
    col = cell.col
    field = FIELDS[min(col, 4)] if ncols >= 5 else FIELDS[min(col, 3)]
    # Programm+Quelle verschmolzen (4-Spalten-Tabelle oder colspan), Inhalt ist
    # aber nur eine Quellenangabe ("A in: Almanach …, S. 119")
    merged = field == "programm" and (ncols == 4 or cell.colspan >= 2)
    if merged and cell.lines:
        txt = cell.text
        if re.match(r"^[AR] in:", txt) or (
                cell.lines[0][0][1] and len(txt) < 150
                and re.search(r"S\.\s*\d+\S*\s*$", txt)):
            log(f"T{cell.table}: Quelle in Programm+Quelle-Zelle erkannt: {txt[:80]!r}")
            return "quelle"
    return field


# ---------------------------------------------------------------- Datensätze --

class Record:
    def __init__(self, kind):
        self.kind = kind  # event | kommentar | section
        self.cells = {f: [] for f in FIELDS}  # Feld -> Liste von Cells
        self.text_cells = []  # für Kommentare/Sections

    def date_text(self):
        return " ".join(c.text for c in self.cells["datum"]).strip()


def date_complete(text):
    if not re.search(r"\d", text):
        return False
    if text.count("[") > text.count("]"):
        return False
    if text.count("(") > text.count(")"):
        return False
    if re.search(r"[-/]$", text.strip()):
        return False
    return True


def build_records(root):
    ital_cls, norm_cls = italic_classes(root)
    records = []
    section = None
    current = None  # letzter Datensatz (event oder kommentar)

    for tno, tbl in enumerate(root.iter(XH + "table")):
        ncols, rows = table_grid(tbl, tno, ital_cls, norm_cls)
        for rno, row in enumerate(rows):
            origins = []
            seen = set()
            for c, slot in enumerate(row):
                if slot and slot[1] and id(slot[0]) not in seen:
                    seen.add(id(slot[0]))
                    origins.append(slot[0])
            if not any(o.lines for o in origins):
                continue  # leere Zeile (z. B. Kopfzeile ohne Inhalt)

            first = row[0][0] if row[0] else None
            spanning = first is not None and first.colspan >= ncols - 1 and first.col == 0

            # --- Abschnittsüberschrift / Kommentar (Zelle über alle Spalten) ---
            if spanning:
                head_line = plain(first.lines[0]) if first.lines else ""
                if YEAR_SECTION.match(head_line) and row[0][1]:
                    section = Record("section")
                    section.text_cells.append(first)
                    records.append(section)
                    current = None
                    continue
                if not row[0][1]:
                    continue  # rowspan-Fortsetzung einer Kommentarzelle
                text = first.text
                rest = [o for o in origins if o is not first]
                if (current is not None and current.kind == "kommentar" and rno == 0
                        and re.match(r"[a-zäöüß]", text)):
                    # Kommentar läuft über Seitenumbruch weiter
                    current.text_cells.append(first)
                    current.cells["quelle"].extend(rest)
                    log(f"T{tno}R{rno}: Kommentar-Fortsetzung über Tabellengrenze: {text[:60]!r}")
                    continue
                rec = Record("kommentar")
                rec.text_cells.append(first)
                rec.cells["quelle"].extend(rest)  # colspan=4 + Quelle-Spalte
                records.append(rec)
                current = rec
                continue

            # --- Ereigniszeile oder Fortsetzung ---
            date_slot = row[0]
            date_cell = date_slot[0] if date_slot and date_slot[1] else None
            date_txt = date_cell.text if date_cell else ""

            # Eine Zelle dieser Zeile ist per rowspan aus einer früheren Zeile
            # fortgesetzt -> gleiches Ereignis (z. B. Alternativdatum "[08.10.?]")
            # Nur Ort/Anlass/Programm zählen: eine geteilte Quellen-Zelle kann
            # mehrere getrennte Konzerte belegen (Den Haag 18./19./25.04.1911).
            shared_from_above = any(
                s is not None and not s[1] and s[0].row < rno
                and logical_field(ncols, s[0]) in ("ort", "anlass", "programm")
                for s in row[1:])

            new_event = False
            if date_txt and DATE_START.match(date_txt):
                if shared_from_above and current is not None and current.kind == "event":
                    log(f"T{tno}R{rno}: rowspan verbindet mit vorigem Ereignis, kein neues: "
                        f"{current.date_text()!r} + {date_txt!r}")
                elif current is not None and current.kind == "event" and not date_complete(current.date_text()):
                    log(f"T{tno}R{rno}: Datum unvollständig, Fortsetzung: "
                        f"{current.date_text()!r} + {date_txt!r}")
                else:
                    new_event = True
            elif date_txt and current is None:
                new_event = True
                log(f"T{tno}R{rno}: Ereignis ohne erkennbares Datum begonnen: {date_txt!r}")

            if new_event:
                current = Record("event")
                records.append(current)
                # per rowspan geteilte Zellen (meist Quelle) auch diesem Ereignis geben
                for s in row[1:]:
                    if s is not None and not s[1] and s[0].row < rno and s[0] not in origins:
                        origins.append(s[0])  # wird unten dem Ereignis zugeordnet
                        log(f"T{tno}R{rno}: geteilte Zelle übernommen ({date_txt!r}): {s[0].text[:50]!r}")
            elif current is None:
                log(f"T{tno}R{rno}: Fortsetzungszeile ohne Vorgänger verworfen: "
                    f"{[o.text[:40] for o in origins]}")
                continue
            elif current.kind == "kommentar":
                # Mehrspaltige Zeile ohne Datum direkt nach einem Kommentar:
                # gehört zum letzten Ereignis davor
                prev_ev = next((r for r in reversed(records) if r.kind == "event"), None)
                log(f"T{tno}R{rno}: Fortsetzungszeile nach Kommentar -> letztes Ereignis "
                    f"({prev_ev.date_text() if prev_ev else None!r}): {[o.text[:40] for o in origins]}")
                if prev_ev is None:
                    continue
                target = prev_ev
                for o in origins:
                    target.cells[logical_field(ncols, o)].append(o)
                continue

            for o in origins:
                current.cells[logical_field(ncols, o)].append(o)

    # Überschriftstexte außerhalb von Tabellen (Bildunterschriften etc.) werden
    # ignoriert; sie stehen im HTML als <p class="s7"> zwischen den Tabellen.
    return records


# --------------------------------------------------------------- Datumslogik --

def iso(y, m=None, d=None):
    s = f"{int(y):04d}"
    if m:
        s += f"-{int(m):02d}"
        if d:
            s += f"-{int(d):02d}"
    return s


def month_num(word):
    w = word.lower().rstrip(".")
    for k, v in MONTHS.items():
        if w.startswith(k):
            return v
    return None


def parse_date(text, last_year):
    """-> dict mit when / notBefore / notAfter / cert, oder {}."""
    t = text.strip()
    attrs = {}
    if "?" in t:
        attrs["cert"] = "low"
    t_clean = t.replace("[", "").replace("]", "").replace("?", "")
    t_clean = re.sub(r"^\s*" + WEEKDAYS + r",?\s*", "", t_clean)
    t_clean = re.sub(r"\s+", " ", t_clean).strip()

    # 12. oder 13.03.1904
    m = re.match(r"(\d{1,2})\.\s*(?:oder|u\.|und|/|–|-)\s*(\d{1,2})\.(\d{1,2})\.(\d{4})", t_clean)
    if m:
        d1, d2, mo, y = m.groups()
        attrs.update(notBefore=iso(y, mo, d1), notAfter=iso(y, mo, d2))
        return attrs
    # 12.03.1904 (auch 12.03.[1904])
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.\s*(\d{4})", t_clean)
    if m:
        d, mo, y = m.groups()
        attrs["when"] = iso(y, mo, d)
        return attrs
    # 12.03. ohne Jahr -> Jahr aus Kontext
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.", t_clean)
    if m and last_year:
        d, mo = m.groups()
        attrs["when"] = iso(last_year, mo, d)
        attrs["cert"] = "low"
        log(f"Jahr ergänzt aus Kontext: {t!r} -> {attrs['when']}")
        return attrs
    # Nov./Dez. 1899
    m = re.match(r"([A-Za-zäöüÄÖÜ]+)\.?\s*/\s*([A-Za-zäöüÄÖÜ]+)\.?\s*(\d{4})", t_clean)
    if m and month_num(m.group(1)) and month_num(m.group(2)):
        y = m.group(3)
        attrs.update(notBefore=iso(y, month_num(m.group(1))), notAfter=iso(y, month_num(m.group(2))))
        return attrs
    # März 1904, Nov. 1904
    m = re.match(r"([A-Za-zäöüÄÖÜ]+)\.?\s*(\d{4})", t_clean)
    if m and month_num(m.group(1)):
        attrs["when"] = iso(m.group(2), month_num(m.group(1)))
        return attrs
    # Saison 1913/14, 1913/14
    m = re.search(r"(\d{4})\s*/\s*(\d{2,4})", t_clean)
    if m:
        y1, y2 = m.groups()
        if len(y2) == 2:
            y2 = y1[:2] + y2
        attrs.update(notBefore=iso(y1), notAfter=iso(y2))
        return attrs
    # Ende 1907, Sommer 1905, 1899
    m = re.search(r"(\d{4})", t_clean)
    if m:
        attrs["when"] = iso(m.group(1))
        return attrs
    return {}


def split_date_time(lines):
    """Datum-Zellen enthalten oft auch Uhrzeit/Tageszeit in Folgezeilen."""
    date_part, time_part = [], []
    for line in lines:
        txt = plain(line)
        if time_part or (date_part and date_complete(" ".join(plain(l) for l in date_part))
                         and not DATE_START.match(txt)):
            time_part.append(line)
        else:
            date_part.append(line)
    return date_part, time_part


# ------------------------------------------------------------- TEI-Ausgabe --

def add_runs(parent, runs):
    """Runs als gemischten Inhalt mit <hi rend="italic"> anhängen."""
    last = None
    for text, it in runs:
        if it:
            hi = ET.SubElement(parent, T + "hi", rend="italic")
            hi.text = text
            last = hi
        else:
            if last is None:
                parent.text = (parent.text or "") + text
            else:
                last.tail = (last.tail or "") + text


def lines_of(cells):
    out = []
    for c in cells:
        out.extend(c.lines)
    return out


def field_runs(cells):
    """Alle Zeilen eines Feldes; Zellen mit mehreren <p> -> Zeilen mit Leerzeichen
    (das PDF bricht ohnehin innerhalb von Absätzen um)."""
    return join_lines(lines_of(cells))


def is_line_mode(cells):
    """Ereignis ist im Export in eine <tr> pro Druckzeile zerlegt."""
    cells = [c for c in cells if c.lines]
    single = [c for c in cells if len(c.lines) == 1]
    return len(cells) >= 3 and len(single) >= len(cells) - 1


COMPOSER_START = re.compile(r"^(?:[IVX]+\.\s|\d+\.\s|außerdem\b|u\. a\.|[^\s„“\"(][^:„“\"()]{0,45}:\s?)")


def continues_previous(prev, txt):
    """Ist eine Programmzeile nur der Umbruch der vorigen (PDF-Zeilenumbruch)?"""
    if txt.startswith("außerdem"):
        return False
    if re.match(r"[a-zäöüß„“(\[/]|op\.|Nr\.|No\.|[A-H](?:is|es|s)?-?\s?(?:Dur|Moll)\b", txt):
        return True
    if re.search(r"(?:[-,/:&]|\b(?:und|aus|from|in|zu|von|des|der|die|das|mit|für|über|nach|of|and|the))$", prev):
        return True
    if prev.count("„") > prev.count("“") or prev.count("(") > prev.count(")") \
            or prev.count("[") > prev.count("]"):
        return True  # offene Klammer/Anführung
    return False


def program_items(cells):
    """Programm-Spalte -> Liste von Items (je Item Runs)."""
    items = []
    line_mode = is_line_mode(cells)
    for c in cells:
        for i, line in enumerate(c.lines):
            txt = plain(line)
            starts_new = (not items or not line_mode or COMPOSER_START.match(txt))
            # erst zusammenfügen, split_composers() trennt danach wieder sauber
            if items and continues_previous(plain(items[-1][-1]), txt):
                starts_new = False
            if starts_new:
                items.append([line])
            else:
                items[-1].append(line)
    out = []
    for it in items:
        out.extend(split_composers(join_lines(it)))
    return out


# Komponistenpräfix mitten in einer Zeile: "… Novellette Chopin: Polonaise …"
# Ein Name ist: [Vorname] [Initialen/Partikel]* Nachname[/Bearbeiter]. Vornamen
# nur aus einer festen Liste, weil sonst Tonarten und Gattungswörter („As-Dur
# Liszt:", „Fuge Beethoven:") als Vorname durchgehen.
FIRST_NAMES = (
    "Adolf Alfred Ambroise Anton Armin Arthur August Bruno Carl Christian Conradin "
    "Constantin Edgar Edouard Eduard Erich-Walter Franz Friedrich Fritz Georg George "
    "Gustav Hans Heinrich Heinz Henri Hermann Hubert Hugo Johann Johannes Josef Joseph "
    "Joachim Julius Kostantin Kurt Leo Leopold Louise Luca Ludwig Luigi Maria Max Niels "
    "Otto Ottokar Paul Reinhold Richard Robert Rudolf Rudolph Stephan Tomaso Victor "
    "Vitezslav Vitézlaw Volkmar Wilhelm"
).split()
_FIRST = r"(?:" + "|".join(map(re.escape, FIRST_NAMES)) + r")"
_INIT = r"(?:[A-ZÄÖÜ][a-zäöü]{0,2}\.|v\.|von|van|de|d’)"
_SURNAME = r"(?![A-H](?:is|es|s)?-(?:Dur|Moll))(?:d’)?[A-ZÄÖÜ][\w’'\-]*"
_PERSON = r"(?:" + _INIT + r" ?)*" + _SURNAME
_COMPOSER = r"(?:" + _FIRST + r" )?" + _PERSON + r"(?:/" + _PERSON + r")*"
_NAME = r"(?:[A-ZÄÖÜ][\w’'\-]*\.?|v\.|von|van|de|d’[A-ZÄÖÜ]\w*)"  # für Namensreste
MID_COMPOSER = re.compile(r"(?<=[\w)\]“.,;]) (?=(?P<name>" + _COMPOSER + r"):\s)")


def split_runs(runs, offsets):
    """Runs an Zeichenpositionen (im Klartext) aufteilen."""
    parts, cur, pos = [], [], 0
    offsets = list(offsets)
    for text, it in runs:
        start = 0
        while offsets and pos + len(text) > offsets[0] >= pos:
            k = offsets.pop(0) - pos
            if text[start:k]:
                cur.append((text[start:k], it))
            parts.append(cur)
            cur, start = [], k
        if text[start:]:
            cur.append((text[start:], it))
        pos += len(text)
    parts.append(cur)
    cleaned = []
    for p in parts:
        if not p:
            continue
        p[0] = (p[0][0].lstrip(), p[0][1])
        p[-1] = (p[-1][0].rstrip(), p[-1][1])
        p = [r for r in p if r[0]]
        if p:
            cleaned.append(p)
    return cleaned


def split_composers(runs):
    txt = plain(runs)
    cuts = []
    name_end = -1
    for m in MID_COMPOSER.finditer(txt):
        if m.start() < name_end:
            continue  # " Wagner:" innerhalb von " R. Wagner:"
        name_end = m.end("name")
        before = txt[:m.start()]
        # "R. Wagner:", "Niels W. Gade:" – davor stehen nur Namensteile
        segment = txt[(cuts[-1] if cuts else 0):m.start()].strip()
        if re.fullmatch(r"(?:" + _NAME + r"(?:/" + _NAME + r")*\s?)+", segment):
            continue
        # nicht innerhalb von Anführungszeichen oder Klammern trennen
        if before.count("„") > before.count("“") or before.count("(") > before.count(")") \
                or before.count("[") > before.count("]"):
            continue
        # "Werke von Caryl Florio:" – Präfix steht nach Präposition, nicht trennen
        if re.search(r"\b(?:von|aus|nach|mit|für|über)$", before):
            continue
        if re.fullmatch(r"\S+ CA", m.group("name")):
            # '… Lieder von Schubert und Franz CA: Ballade' – Vorname gehört zum
            # vorigen Punkt, CA (Conrad Ansorge) beginnt einen neuen
            cuts.append(m.end("name") - 2)
            continue
        cuts.append(m.end())
    return split_runs(runs, cuts) if cuts else [runs]


# ------------------------------------------------- Personen/Werke im Programm --
# Ein Programmpunkt hat meist die Form „Komponist[/Bearbeiter]: Werk, Werk …“.
# Ausgezeichnet wird heuristisch:
#   <rs type="person"> für jeden Namen vor dem Doppelpunkt (Bach/Liszt -> zwei),
#                      für Namenslisten („außerdem X, Y“, „Lieder von X, Y“)
#   <rs type="work">   für jedes durch Komma getrennte Werk nach dem Doppelpunkt;
#                      Ausführende am Ende („(CA)“, „[hs: …]“) bleiben draußen.
# Unsichere Fälle landen im Protokoll.

_NAME_TOKEN = r"(?:[A-ZÄÖÜ][\w’'ëéèáóúäöüçšřčý\-]*\.?|[a-z]{1,3}\.|von|van|de|d’[A-Z]\w*|[A-Z]\.)"
NAME_RE = re.compile(r"^" + _NAME_TOKEN + r"(?: " + _NAME_TOKEN + r")*$")
NOT_A_NAME = re.compile(
    r"\b(?:Zugabe|Volkslieder|Clavichord|Cembalo|Hammerklavier|Flügel|Verfasser|"
    r"Ständchen|Spinnrad|Jhd|Konzert|Sonaten?|Stunde|Pause|Lieder|Werke|Theil|Teil|"
    r"Musik|Texten|Programm|Chöre|Arien|Stücke)\b|-Flügel")
# Bindestrich verbindet zwei Personen nur bei diesen Namen (sonst Saint-Saëns …)
HYPHEN_PERSONS = {"Schubert", "Liszt", "Paganini", "Chopin", "Gluck", "Wagner", "CA",
                  "Mozart", "Beethoven", "Bach"}
KEY_START = re.compile(r"[A-Ha-h](?:is|es|s)?-?\s?(?:Dur|Moll|dur|moll)\b")
NO_SPLIT_START = re.compile(
    r"(?:op\.|opp\.|Op\.|Nr\.|No\.|KV|BWV|\d|[a-zäöüß]|"
    r"(?:Andante|Adagio|Allegro|Allegretto|Largo|Presto|Scherzo|Finale|Menuett|"
    r"Satz|Thema|Variation|Rondo-Finale|Intermezzo|Trio)\b)")
_GENRE_PL = r"[A-ZÄÖÜ]?\w*(?:[Ll]ieder|[Ww]erke|[Ss]tücke|[Cc]höre|[Aa]rien|[Gg]esänge|[Dd]uette|[Kk]ompositionen)"
NAMELIST_INTRO = re.compile(
    r"(?:(?<=\s)|^)(?:außerdem|u\. a\.|(?:" + _GENRE_PL + r"(?: und \w+)? von))\s+")
GENRE_VON = re.compile(r"^" + _GENRE_PL + r"(?: und \w+)? von\s+")
# Namen, die irgendwo als 'Name:' vor einem Programmpunkt stehen (Vorlauf in write_tei)
KNOWN_PERSONS = set()
GENRE_START = re.compile(
    r"^(?:„|(?:Gro(?:ss|ß)e |Drei |Zwei |Vier |Fünf |Sechs |\d+ )?(?:Sonate|Sonaten|Rondo|Rondos|"
    r"Bagatelle|Bagatellen|Klavierkonzert|Konzert|Concert|Ouvertüre|Symphonie|Sinfonie|"
    r"Quartett|Streichquartett|Trio|Quintett|Variationen|Eroica|Impromptu|Fantasie|"
    r"Phantasie|Ballade|Etüde|Etüden|Nocturne|Polonaise|Walzer|Valse|Mazurka|Prélude|"
    r"Präludium|Fuge|Toccata|Suite|Partita|Rhapsodie|Scherzo|Traumbilder|Coriolan|"
    r"Waldstein|Appassionata|Mondschein|Kreisleriana|Carnaval|Novellette))")


def _balanced(s):
    return (s.count("„") <= s.count("“") and s.count("(") <= s.count(")")
            and s.count("[") <= s.count("]"))


def _strip_span(txt, a, b):
    while a < b and txt[a] in " ,;:–-":
        a += 1
    while b > a and txt[b - 1] in " ,;:":
        b -= 1
    return a, b


def _person_spans(txt, a, b):
    """Namen in txt[a:b] (z. B. 'Bach/Liszt', 'F. Fiorilli [wahrsch. …]')."""
    seg = txt[a:b]
    m = re.search(r"\s*\[", seg)  # redaktionelle Anmerkung abtrennen
    if m:
        seg = seg[:m.start()]
    spans, pos = [], a
    for part in re.split(r"(/)", seg):
        if part == "/":
            pos += 1
            continue
        pa, pb = _strip_span(txt, pos, pos + len(part))
        pos += len(part)
        name = txt[pa:pb]
        if not name:
            continue
        hy = name.split("-")
        if len(hy) == 2 and all(h.strip() in HYPHEN_PERSONS for h in hy):
            spans.append((pa, pa + len(hy[0].rstrip()), "person"))
            off = pa + len(hy[0]) + 1
            off += len(hy[1]) - len(hy[1].lstrip())
            spans.append((off, pb, "person"))
        elif NAME_RE.match(name) and not NOT_A_NAME.search(name):
            spans.append((pa, pb, "person"))
        else:
            return None
    return spans or None


def _namelist_spans(txt, a, b):
    """'Vieuxtemps, Mendelssohn, F. von Holstein, u. a.' -> Personen."""
    spans, pos = [], a
    for part in re.split(r"(,|\bund\b|&)", txt[a:b]):
        pa, pb = _strip_span(txt, pos, pos + len(part))
        pos += len(part)
        name = txt[pa:pb]
        if part in (",", "und", "&") or not name or name in ("u. a.", "u.a.", "a."):
            continue
        m = GENRE_VON.match(name)  # 'außerdem Gesangsstücke von Weber'
        if m:
            pa += m.end()
            name = txt[pa:pb]
        name_b = pb
        m = re.search(r"\s*[(\[]", name)  # 'Brahms (Sonate)'
        if m:
            name_b = pa + m.start()
        ps = _person_spans(txt, pa, name_b)
        if ps:
            spans.extend(ps)
    return spans


def _top_level_splits(txt, a, b):
    """Positionen von ', ' außerhalb von Anführungen/Klammern."""
    out = []
    for m in re.finditer(r",\s+|;\s+", txt[a:b]):
        if _balanced(txt[a:a + m.start()]):
            out.append((a + m.start(), a + m.end()))
    return out


def _work_spans(txt, a, b):
    a, b = _strip_span(txt, a, b)
    if a >= b:
        return []
    # Namensliste mitten im Werkteil: '… op. 111 Werke von Schubert', '… außerdem X, Y'
    for m in NAMELIST_INTRO.finditer(txt, a, b):
        if _balanced(txt[a:m.start()]):
            return _work_spans(txt, a, m.start()) + _namelist_spans(txt, m.end(), b)
    # weiterer Komponist mitten im Werkteil: '… Ouvertura Liszt : Klavierkonzert'
    for m in re.finditer(r"(?<=\s)(" + _COMPOSER + r")\s?:\s", txt[a:b]):
        s = a + m.start(1)
        if _balanced(txt[a:s]) and not re.search(r"\b(?:von|aus|nach|mit|für|über)\s*$", txt[a:s]):
            ps = _person_spans(txt, s, a + m.end(1))
            if ps:
                return _work_spans(txt, a, s) + ps + _work_spans(txt, a + m.end(), b)
    # Ausführende/Anmerkungen am Ende: '(CA)', '(EA)', '[hs: …]', '(„vorgetragen …“)'
    while True:
        seg = txt[a:b]
        m = re.search(r"\s*(?:\([^()]*\)|\[hs[^\]]*\]?)\s*$", seg)
        if not m or m.start() == 0:
            break
        b = a + m.start()
    pieces = [(a, b)]
    if not re.search(r"\saus\s", txt[a:b]):  # 'Ouvertüre, Finale … aus der Oper …'
        pieces, start = [], a
        for s, e in _top_level_splits(txt, a, b):
            nxt = txt[e:b]
            if NO_SPLIT_START.match(nxt) or KEY_START.match(nxt):
                continue
            pieces.append((start, s))
            start = e
        pieces.append((start, b))
    spans = []
    for pa, pb in pieces:
        pa, pb = _strip_span(txt, pa, pb)
        if pa < pb and re.search(r"\w", txt[pa:pb]):
            spans.append((pa, pb, "work"))
    return spans


def tag_program_item(runs):
    """Spannen (start, end, typ) für Personen und Werke in einem Programmpunkt."""
    txt = plain(runs)
    # führende Nummerierung / Füllwörter: 'IV. CA:', 'u. a. CA :', 'von CA:'
    lead = re.match(r"^(?:[IVX]+\.\s+|\d+\.\s+|u\. a\.\s+|von\s+|Stunde Pause\s+|Maria\s+(?=\S+\s?:))*", txt)
    a = lead.end()
    rest = txt[a:]
    if re.match(r"^(?:außerdem|u\. a\.)\s", txt) or NAMELIST_INTRO.match(rest):
        m = NAMELIST_INTRO.match(txt, a) or NAMELIST_INTRO.match(txt)
        return _namelist_spans(txt, m.end(), len(txt))
    m = re.match(r"^([^:„“\"()]{1,60}?)\s?:\s", rest)
    if m:
        ps = _person_spans(txt, a, a + m.end(1))
        if ps:
            return ps + _work_spans(txt, a + m.end(), len(txt))
        label = m.group(1)
        if NOT_A_NAME.search(label) and "erwähnt" not in label or label.endswith("Jhd."):
            # Etikett vor dem eigentlichen Punkt: 'Zugabe: Liszt: …', 'Volkslieder: „…“'
            b = a + m.end()
            inner = tag_program_item(runs_from(runs, b))
            if inner:
                return [(s + b, e + b, t) for s, e, t in inner]
            return _work_spans(txt, b, len(txt))
        log(f"Programm: kein Personenname vor ':': {txt[:80]!r}")
        return []
    # ohne Komponist: reine Namensliste 'Liszt, Haydn, Reinecke'
    parts = [re.sub(r"\s*\(.*", "", p).strip() for p in rest.split(",")]
    parts = [p for p in parts if p and p not in ("u. a.", "u.a.")]
    if len(parts) >= 2 and all(n in KNOWN_PERSONS for p in parts for n in p.split("/")):
        return _namelist_spans(txt, a, len(txt))
    # ohne Komponist: Werkliste 'Sonaten opp. 53, 13, Rondo op. 51' / '3. Das Trinklied'
    if (GENRE_START.match(rest) or (lead.group(0) and re.match(r"\d", txt)
                                    and not rest.startswith("Satz"))):
        return _work_spans(txt, a, len(txt))
    # ohne Doppelpunkt: 'Ital. Arien, Lieder von Schubert und Franz'
    m = NAMELIST_INTRO.search(txt)
    if m and m.group(0).strip() not in ("außerdem", "u. a.") and _balanced(txt[:m.start()]):
        return _namelist_spans(txt, m.end(), len(txt))
    return []


def collect_known_persons(records):
    """Vorlauf: alle Namen vor 'Name:' sammeln (für reine Namenslisten)."""
    for rec in records:
        if rec.kind not in ("section", "kommentar"):
            for it in program_items(rec.cells["programm"]):
                txt = plain(it)
                m = re.match(r"^([^:„“\"()]{1,60}?)\s?:\s", txt)
                if m:
                    for s, e, _ in _person_spans(txt, 0, m.end(1)) or []:
                        KNOWN_PERSONS.add(txt[s:e])


def runs_from(runs, offset):
    """Runs ab Klartext-Position offset."""
    out, pos = [], 0
    for text, it in runs:
        if pos + len(text) > offset:
            out.append((text[max(0, offset - pos):], it))
        pos += len(text)
    return out


def fully_quoted(t):
    """'„Erlkönig“' -> True; '„Waldesnacht“ und „All’ meine …“' -> False."""
    return (len(t) > 2 and t[0] in "„\"" and t[-1] in "“\""
            and not any(c in t[1:-1] for c in "„“\""))


def requote(text):
    """Anführungszeichen in Werktiteln: „…“ / "…" -> »…«."""
    text = text.replace("„", "»").replace("“", "«")
    out, opening = [], True
    for ch in text:
        if ch == '"':
            ch = "»" if opening else "«"
            opening = not opening
        out.append(ch)
    return "".join(out)


def add_runs_spans(parent, runs, spans):
    """Runs als gemischten Inhalt anhängen, Spannen als <rs type="…"> (darin <hi>).
    In Werktiteln werden umschließende Anführungszeichen entfernt, innere zu »…«."""
    spans = sorted(spans)
    txt = plain(runs)
    strip_quotes = {sp for sp in spans if sp[2] == "work" and fully_quoted(txt[sp[0]:sp[1]])}
    # Runs an Spannengrenzen (und um zu entfernende Anführungszeichen) zerschneiden
    cuts = sorted({p for s, e, _ in spans for p in (s, e)}
                  | {p for s, e, _ in strip_quotes for p in (s + 1, e - 1)})
    pieces = split_runs_keep(runs, cuts)
    pos, si, cur_rs, holder = 0, 0, None, parent
    last = None  # letztes Kind im aktuellen Halter
    created = []
    for text, it in pieces:
        while si < len(spans) and spans[si][1] <= pos:
            si += 1
        in_span = si < len(spans) and spans[si][0] <= pos < spans[si][1]
        if in_span and cur_rs is not spans[si]:
            rs = ET.SubElement(parent, T + "rs", type=spans[si][2])
            created.append(rs)
            cur_rs, holder, last = spans[si], rs, None
        elif not in_span and cur_rs is not None:
            last = holder
            cur_rs, holder = None, parent
        start = pos
        pos += len(text)
        if in_span and cur_rs[2] == "work":
            if cur_rs in strip_quotes and (start == cur_rs[0] or pos == cur_rs[1]):
                continue  # das umschließende „ bzw. “
            text = requote(text)
        if it:
            hi = ET.SubElement(holder, T + "hi", rend="italic")
            hi.text = text
            last = hi
        elif last is None:
            holder.text = (holder.text or "") + text
        else:
            last.tail = (last.tail or "") + text
    set_pmb_refs(created)


# ---------------------------------------------------------- PMB-Referenzen --
# Aus pmb-personen.csv / pmb-werke.csv (erzeugt von pmb-match.py, von Hand
# korrigierbar). sicherheit: sicher -> kein @cert, wahrscheinlich -> medium,
# unsicher -> low.

CERT = {"wahrscheinlich": "medium", "unsicher": "low"}


def load_pmb_table(path, key):
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return {key(r): (r["pmb"].strip(), r.get("sicherheit", "")) for r in csv.DictReader(f)
                if r.get("pmb", "").strip()}


PMB_PERSONS = load_pmb_table(HERE / "pmb-personen.csv", lambda r: r["name"])
PMB_WORKS = load_pmb_table(HERE / "pmb-werke.csv", lambda r: (r["komponisten"], r["werk"]))
PMB_STATS = {"person": [0, 0], "work": [0, 0]}


CURRENT_EVENT = [""]  # xml:id des gerade geschriebenen Ereignisses


def set_pmb_refs(rs_elements):
    """ref="#pmb…" setzen; Werke werden über ihre(n) Komponisten im selben Punkt gesucht.
    Eine Zeile 'Name#ansorge_e_0059' in pmb-personen.csv gilt nur für dieses Ereignis
    (für Namen, die je nach Konzert verschiedene Personen meinen)."""
    composers, seen_work = [], False
    for rs in rs_elements:
        txt = "".join(rs.itertext())
        typ = rs.get("type")
        if typ == "person":
            if seen_work:
                composers, seen_work = [], False
            composers.append(txt)
            hit = PMB_PERSONS.get(f"{txt}#{CURRENT_EVENT[0]}") or PMB_PERSONS.get(txt)
        else:
            seen_work = True
            hit = PMB_WORKS.get(("/".join(composers), txt))
        PMB_STATS[typ][1] += 1
        if hit:
            PMB_STATS[typ][0] += 1
            rs.set("ref", "#pmb" + re.sub(r"\D", "", hit[0]))
            if hit[1] in CERT:
                rs.set("cert", CERT[hit[1]])


def split_runs_keep(runs, cuts):
    """Wie split_runs, aber ohne Whitespace zu verändern; liefert flache Runs."""
    out, pos = [], 0
    cuts = list(cuts)
    for text, it in runs:
        start = 0
        for c in cuts:
            if pos < c < pos + len(text):
                out.append((text[start:c - pos], it))
                start = c - pos
        out.append((text[start:], it))
        pos += len(text)
    return [r for r in out if r[0]]


def source_items(cells):
    """Quelle-Spalte -> einzelne bibl. Neue Quelle, wenn eine Zeile kursiv
    beginnt (Zeitschriftentitel) oder die vorige mit einer Seitenangabe endet."""
    items = []
    for c in cells:
        for i, line in enumerate(c.lines):
            txt = plain(line)
            new = not items
            if items:
                prev = plain(join_lines(items[-1]))
                prev_ends_italic = items[-1][-1][-1][1]
                if line[0][1] and not prev_ends_italic and not (i == 0 and re.match(r"[a-zäöüß(]", txt)):
                    new = True
                elif re.search(r"S\.\s*[\dIVX]+[\w–\-]*\s*(?:f{1,2}\.)?\s*\.?$", prev) and \
                        not re.match(r"[(a-zäöüß]", txt):
                    new = True
                if re.search(r"[A-Za-zäöüß]-$", prev) or prev.rstrip().endswith(","):
                    new = False
            if new:
                items.append([line])
            else:
                items[-1].append(line)
    return [join_lines(it) for it in items]


def split_fluegel(runs):
    """'Leipzig, Gewandhaus Flügel: Blüthner' -> (Ort-Runs, Flügel-Text)."""
    txt = plain(runs)
    m = re.search(r"\s*Flügel\s*:\s*", txt)
    if not m:
        return runs, None
    cut = m.start()
    ort, pos = [], 0
    for t, it in runs:
        if pos + len(t) <= cut:
            ort.append((t, it))
        elif pos < cut:
            ort.append((t[:cut - pos], it))
        pos += len(t)
    if ort:
        ort[-1] = (ort[-1][0].rstrip(" ,"), ort[-1][1])
    return [r for r in ort if r[0]], txt[m.end():].strip()


# ------------------------------------------------------------------- Orte --
# 'Berlin, Beethovensaal' -> <placeName><settlement>Berlin</settlement>,
# <placeName type="venue">Beethovensaal</placeName></placeName>; ref="#pmb…" aus
# pmb-orte.csv / pmb-veranstaltungsorte.csv (siehe pmb-orte.py).

VENUE_WORDS = re.compile(r"^(?:im\s|in\s|„|\S*(?:saal|Saal|Verein|verein|haus|Haus|Aula|Theater)\b)")


def split_place(txt):
    """Spannen (start, end) für Ort und Veranstaltungsort (jeweils oder None)."""
    if txt.strip() in ("o. O.", ""):
        return None, None
    m = re.match(r"^\[[^\]]*\]", txt)
    if m and "," in m.group(0):           # '[Hirschberg, Erzgebirge?] Concerthause'
        city_end = m.end()
    else:
        i = txt.find(",")
        city_end = i if i >= 0 else len(txt)
        m = re.match(r",\s*[A-Z]{2}\b", txt[city_end:])   # 'Poughkeepsie, NY, …'
        if m:
            city_end += m.end()
        if i < 0:                          # 'Kiel im Saal …', 'Berlin Beethovensaal …'
            m = re.match(r"^(\S+)\s+(.+)$", txt)
            if m and VENUE_WORDS.match(m.group(2)):
                city_end = m.end(1)
    city = txt[:city_end].rstrip(" ,")
    rest_start = city_end
    while rest_start < len(txt) and txt[rest_start] in " ,":
        rest_start += 1
    city_span = (0, len(city)) if city else None
    venue_span = (rest_start, len(txt.rstrip())) if txt[rest_start:].strip() else None
    return city_span, venue_span


def load_place_table(path, key):
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return {key(r): (r["pmb"].strip(), r.get("sicherheit", "")) for r in csv.DictReader(f)
                if r.get("pmb", "").strip()}


PMB_ORTE = load_place_table(HERE / "pmb-orte.csv", lambda r: r["ort"])
PMB_VENUES = load_place_table(HERE / "pmb-veranstaltungsorte.csv",
                              lambda r: (r["ort"], r["veranstaltungsort"]))
PMB_STATS["ort"] = [0, 0]
PMB_STATS["venue"] = [0, 0]


# Ortsangaben ohne Ort, nur Veranstaltungsort
VENUE_ONLY = {"Münchener Volkstheater"}


def place_spans(txt):
    """[(start, end, 'ort'|'venue')]: 'Halberstadt u. Blankenburg, …' -> zwei Orte."""
    if txt.strip() in VENUE_ONLY:
        return [(0, len(txt.rstrip()), "venue")]
    city, venue = split_place(txt)
    spans = []
    if city:
        m = re.fullmatch(r"(\S+)( u\. | und )(\S+)", txt[city[0]:city[1]])
        if m:   # zwei Orte
            spans += [(city[0] + m.start(1), city[0] + m.end(1), "ort"),
                      (city[0] + m.start(3), city[0] + m.end(3), "ort")]
        else:
            spans.append((city[0], city[1], "ort"))
    if venue:
        spans.append((venue[0], venue[1], "venue"))
    return spans


def add_place(pn, runs):
    txt = plain(runs)
    spans = place_spans(txt)
    if not spans:
        add_runs(pn, runs)
        return
    pieces = split_runs_keep(runs, sorted({p for sp in spans for p in sp[:2]}))
    pos, last, holder, cur = 0, None, pn, None
    made = []
    for text, it in pieces:
        span = next((sp for sp in spans if sp[0] <= pos < sp[1]), None)
        if span is not cur:
            if span is None:
                last, holder = holder, pn
            else:
                if span[2] == "ort":
                    el = ET.SubElement(pn, T + "settlement")
                else:
                    el = ET.SubElement(pn, T + "placeName", type="venue")
                made.append((span, el))
                holder, last = el, None
            cur = span
        if it:
            hi = ET.SubElement(holder, T + "hi", rend="italic")
            hi.text = text
            last = hi
        elif last is None:
            holder.text = (holder.text or "") + text
        else:
            last.tail = (last.tail or "") + text
        pos += len(text)
    # Schlüssel für Veranstaltungsorte: der (erste) Ort im selben placeName
    city_txt = next((txt[s:e] for s, e, k in spans if k == "ort"), "")
    for (s, e, kind), el in made:
        if kind == "ort":
            hit = PMB_ORTE.get(txt[s:e])
        else:
            hit = PMB_VENUES.get((city_txt, txt[s:e]))
        PMB_STATS[kind][1] += 1
        if hit:
            PMB_STATS[kind][0] += 1
            el.set("ref", "#pmb" + re.sub(r"\D", "", hit[0]))
            if hit[1] in CERT:
                el.set("cert", CERT[hit[1]])


def write_tei(records, out_path):
    tei = ET.Element(T + "TEI")
    header = ET.SubElement(tei, T + "teiHeader")
    fd = ET.SubElement(header, T + "fileDesc")
    ts = ET.SubElement(fd, T + "titleStmt")
    ET.SubElement(ts, T + "title").text = "Conrad Ansorge Konzertkalender 1879-1943"
    ET.SubElement(ts, T + "author").text = "Christian Heitler"
    rs = ET.SubElement(ts, T + "respStmt")
    ET.SubElement(rs, T + "resp").text = "Mitwirkung"
    for n in ("Eike Rathgeber", "Manuela Schwartz", "Caroline Sibilak"):
        ET.SubElement(rs, T + "name").text = n
    ps = ET.SubElement(fd, T + "publicationStmt")
    ET.SubElement(ps, T + "p").text = "Konvertiert aus HTML zu TEI (html-to-listevent.py)"
    sd = ET.SubElement(fd, T + "sourceDesc")
    ET.SubElement(sd, T + "p").text = (
        "Erstellt aus dem HTML-Export des Konzertkalenders. Im Druck fett gesetzte "
        "Werke Ansorges sind im HTML-Export nicht ausgezeichnet und fehlen daher.")
    body = ET.SubElement(ET.SubElement(tei, T + "text"), T + "body")
    collect_known_persons(records)
    root_le = ET.SubElement(body, T + "listEvent")

    container = root_le
    n_ev = n_k = 0
    last_year = None
    stats = {"events": 0, "kommentare": 0, "sections": 0, "ohne_when": 0}

    for rec in records:
        if rec.kind == "section":
            stats["sections"] += 1
            container = ET.SubElement(root_le, T + "listEvent")
            head = ET.SubElement(container, T + "head")
            lines = rec.text_cells[0].lines
            years = plain(lines[0]).strip()
            m = YEAR_SECTION.match(years)
            d = ET.SubElement(head, T + "date")
            if m.group(2):
                d.set("from", m.group(1))
                d.set("to", m.group(2))
            else:
                d.set("when", m.group(1))
            d.text = years
            title = join_lines(lines[1:])
            if title:
                d.tail = " – "
                add_runs_after(head, d, title)
            continue

        if rec.kind == "kommentar":
            stats["kommentare"] += 1
            n_k += 1
            ev = ET.SubElement(container, T + "event", type="kommentar")
            ev.set("{http://www.w3.org/XML/1998/namespace}id", f"ansorge_k_{n_k:03d}")
            p = ET.SubElement(ev, T + "p")
            add_runs(p, join_lines(lines_of(rec.text_cells)))
            for b in source_items(rec.cells["quelle"]):
                bibl = ET.SubElement(ev, T + "bibl")
                add_runs(bibl, b)
            continue

        # --- Konzert-Ereignis ---
        stats["events"] += 1
        n_ev += 1
        ev = ET.SubElement(container, T + "event")
        ev.set("{http://www.w3.org/XML/1998/namespace}id", f"ansorge_e_{n_ev:04d}")
        CURRENT_EVENT[0] = f"ansorge_e_{n_ev:04d}"
        date_lines, time_lines = split_date_time(lines_of(rec.cells["datum"]))
        date_runs = join_lines(date_lines)
        dattrs = parse_date(plain(date_runs), last_year)
        if not dattrs.get("when") and not dattrs.get("notBefore"):
            stats["ohne_when"] += 1
            log(f"{n_ev}: Datum nicht normalisierbar: {plain(date_runs)!r}")
        for k in ("when", "notBefore", "notAfter"):
            if k in dattrs:
                ev.set(k, dattrs[k])
        y = (dattrs.get("when") or dattrs.get("notBefore") or "")[:4]
        if y:
            last_year = y

        desc = ET.SubElement(ev, T + "desc")
        de = ET.SubElement(desc, T + "date")
        for k, v in dattrs.items():
            de.set(k, v)
        add_runs(de, date_runs)
        if time_lines:
            de.tail = " "
            tm = ET.SubElement(desc, T + "time")
            add_runs(tm, join_lines(time_lines))

        ort_runs = field_runs(rec.cells["ort"])
        if ort_runs:
            ort, fluegel = split_fluegel(ort_runs)
            if ort:
                add_place(ET.SubElement(desc, T + "placeName"), ort)
            if fluegel:
                ET.SubElement(desc, T + "rs", type="fluegel").text = fluegel

        anlass = field_runs(rec.cells["anlass"])
        if anlass:
            d = ET.SubElement(desc, T + "desc", type="anlass")
            add_runs(d, anlass)

        prog = program_items(rec.cells["programm"])
        if prog:
            d = ET.SubElement(desc, T + "desc", type="programm")
            lst = ET.SubElement(d, T + "list")
            for it in prog:
                add_runs_spans(ET.SubElement(lst, T + "item"), it, tag_program_item(it))

        quellen = source_items(rec.cells["quelle"])
        if quellen:
            lb = ET.SubElement(ev, T + "listBibl")
            for b in quellen:
                add_runs(ET.SubElement(lb, T + "bibl"), b)

    indent_preserving_mixed(tei)
    ET.ElementTree(tei).write(out_path, encoding="UTF-8", xml_declaration=True)
    return stats


MIXED = {T + n for n in ("item", "bibl", "p", "head", "placeName", "settlement", "date", "time",
                         "rs", "hi")}


def indent_preserving_mixed(root):
    """ET.indent, ohne Whitespace in gemischten Inhalt (<item>, <bibl> …) zu schreiben."""
    saved = []
    for el in root.iter():
        if el.tag in MIXED or (el.tag == T + "desc" and el.get("type") == "anlass"):
            saved.append((el, "text", el.text))
            for d in el.iter():
                if d is not el:
                    saved.append((d, "text", d.text))
                    saved.append((d, "tail", d.tail))
    ET.indent(root, space="  ")
    for el, attr, val in saved:
        setattr(el, attr, val)


def add_runs_after(parent, after_el, runs):
    """Runs hinter einem bestehenden Kindelement anhängen."""
    for text, it in runs:
        if it:
            hi = ET.SubElement(parent, T + "hi", rend="italic")
            hi.text = text
            after_el = hi
        else:
            after_el.tail = (after_el.tail or "") + text


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_IN
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    raw = src.read_text(encoding="utf-8")
    raw = re.sub(r"<!DOCTYPE[^>]*>", "", raw, count=1)
    root = ET.fromstring(raw)
    records = build_records(root)
    stats = write_tei(records, out)
    log_path = out.with_suffix(".log")
    log_path.write_text("\n".join(LOG) + "\n", encoding="utf-8")
    print(f"{out}: {stats}")
    print("PMB-Referenzen (Treffer/Nennungen): "
          + ", ".join(f"{k} {v[0]}/{v[1]}" for k, v in PMB_STATS.items()))
    print(f"Protokoll ({len(LOG)} Einträge): {log_path}")


if __name__ == "__main__":
    main()
