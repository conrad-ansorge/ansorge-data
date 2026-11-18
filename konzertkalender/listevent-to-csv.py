#!/usr/bin/env python3
"""
listevent.xml -> CSV (z. B. für Google Sheets).

Eine Zeile pro Konzert bzw. Kommentar, in Dokumentreihenfolge.
Mehrere Programmpunkte/Quellen stehen innerhalb einer Zelle auf eigenen Zeilen.

Aufruf:
  python3 listevent-to-csv.py [listevent.xml] [konzertkalender.csv]
"""
import csv
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).parent
N = "{http://www.tei-c.org/ns/1.0}"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"

COLUMNS = [
    "id", "typ", "abschnitt", "datum", "when", "notBefore", "notAfter", "unsicher",
    "zeit", "ort", "fluegel", "anlass", "programm", "quellen", "kommentar",
]


def text(el):
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip() if el is not None else ""


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "data" / "indices" / "listevent.xml"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "konzertkalender.csv"
    body = ET.parse(src).getroot().find(f"{N}text/{N}body")

    rows = []
    for section in body.iter(N + "listEvent"):
        head = section.find(N + "head")
        if head is None:
            continue
        abschnitt = text(head)
        for ev in section.findall(N + "event"):
            row = dict.fromkeys(COLUMNS, "")
            row["id"] = ev.get(XML_ID, "")
            row["abschnitt"] = abschnitt
            bibls = [text(b) for b in ev.iter(N + "bibl")]
            row["quellen"] = "\n".join(bibls)
            if ev.get("type") == "kommentar":
                row["typ"] = "Kommentar"
                row["kommentar"] = "\n".join(text(p) for p in ev.findall(N + "p"))
            else:
                row["typ"] = "Konzert"
                desc = ev.find(N + "desc")
                date = desc.find(N + "date")
                row["datum"] = text(date)
                for k in ("when", "notBefore", "notAfter"):
                    row[k] = ev.get(k, "")
                row["unsicher"] = "ja" if date is not None and date.get("cert") == "low" else ""
                row["zeit"] = text(desc.find(N + "time"))
                row["ort"] = text(desc.find(N + "placeName"))
                row["fluegel"] = text(desc.find(f"{N}rs[@type='fluegel']"))
                row["anlass"] = text(desc.find(f"{N}desc[@type='anlass']"))
                row["programm"] = "\n".join(
                    text(i) for i in desc.iter(N + "item"))
            rows.append(row)

    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerows(rows)
    n_k = sum(r["typ"] == "Konzert" for r in rows)
    print(f"{out}: {len(rows)} Zeilen ({n_k} Konzerte, {len(rows) - n_k} Kommentare)")


if __name__ == "__main__":
    main()
