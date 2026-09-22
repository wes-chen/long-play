#!/usr/bin/env python3
"""One-off generator: parse syllabus.md into engine/weeks.json.

engine/weeks.json is the machine-readable 24-week plan: build_watchlist.py
reads it (ADV-LP-01 rollover), and bin/rollover.py scaffolds week files from
it. Re-run after any syllabus edit; verify the printed weeks by eye.

Usage: python3 bin/syllabus_to_weeks.py
"""
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYLLABUS = os.path.join(REPO, "syllabus.md")
OUT = os.path.join(REPO, "engine", "weeks.json")


def clean_album(s):
    # strip trailing parenthetical notes: "(known)", "(his save; ...)"
    s = (s or "").strip().rstrip(".")
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s).strip()
    return s


def parse_album_pair(s):
    # "Artist — Album" -> (artist, album)
    parts = re.split(r"\s*[—–-]\s*", s.strip(), maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), clean_album(parts[1])
    return s.strip(), ""


def parse_week(n, title, block):
    t = re.sub(r"\s+", " ", block)
    week = {"n": n, "title": title}

    m = re.search(r"Objective:\s*(.+?)\.\s*Anchor:", t)
    week["objective"] = m.group(1).strip() if m else ""

    m = re.search(r"Anchor:\s*(.+?)(?:Adventurous:|Wild card:|Concept:|$)", t)
    anchor = parse_album_pair(m.group(1)) if m else ("", "")
    week["anchor"] = {"artist": anchor[0], "album": anchor[1]}

    m = re.search(r"Adventurous:\s*(.+?)(?:Wild card:|Concept:|$)", t)
    adv = []
    if m:
        pieces = re.split(r",\s*(?![^()]*\))", m.group(1))
        # merge fragments that lack an "Artist — Album" separator back into
        # the previous piece (e.g. "Ravedeath, 1972" splits at the comma)
        merged = []
        for piece in pieces:
            if re.search(r"\s[—–-]\s", piece) or not merged:
                merged.append(piece)
            else:
                merged[-1] += ", " + piece
        for piece in merged:
            a, al = parse_album_pair(piece)
            if a and al:
                adv.append({"artist": a, "album": al})
    week["adventurous"] = adv

    m = re.search(r"Wild card:\s*(.+?)(?:Concept:|$)", t)
    wc = parse_album_pair(m.group(1)) if m else ("", "")
    week["wild_card"] = {"artist": wc[0], "album": wc[1]}

    m = re.search(r"Concept:\s*\*\*(.+?)\*\*\s*[—–-]\s*(.+?)(?:Technique:|$)", t)
    week["concept"] = m.group(1).strip() if m else ""
    week["concept_note"] = m.group(2).strip().rstrip(".") if m else ""

    m = re.search(r"Technique:\s*\*\*(.+?)\*\*\s*[—–-]\s*(.+)$", t)
    week["technique"] = m.group(1).strip() if m else ""
    week["technique_note"] = m.group(2).strip() if m else ""
    return week


def main():
    with open(SYLLABUS) as f:
        text = f.read()
    # split on **Week N — Title.** headers
    parts = re.split(r"\*\*Week (\d+) — (.+?)\.\*\*", text)
    weeks = []
    for i in range(1, len(parts), 3):
        n = int(parts[i])
        title = parts[i + 1].strip()
        block = parts[i + 2]
        # cut at the next week header remnant or section break is handled
        # by the split itself; trim trailing unit headers
        block = re.split(r"\n## |\n---\n", block)[0]
        weeks.append(parse_week(n, title, block))
    weeks.sort(key=lambda w: w["n"])
    with open(OUT, "w") as f:
        json.dump({"weeks": weeks, "source": "syllabus.md (parse at generation time)"},
                  f, indent=1, ensure_ascii=False)
    for w in weeks:
        adv = ", ".join(f"{a['artist']} — {a['album']}" for a in w["adventurous"])
        print(f"W{w['n']:02d} {w['title']}\n"
              f"  anchor: {w['anchor']['artist']} — {w['anchor']['album']}\n"
              f"  adv: {adv}\n"
              f"  wild: {w['wild_card']['artist']} — {w['wild_card']['album']}\n"
              f"  concept: {w['concept']} / technique: {w['technique']}")
    missing = [w["n"] for w in weeks if not (w["anchor"]["album"] and
              len(w["adventurous"]) == 3 and w["wild_card"]["album"])]
    if missing:
        print(f"WARNING: incomplete parse for weeks {missing}", file=sys.stderr)
        return 1
    print(f"wrote {OUT}: {len(weeks)} weeks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
