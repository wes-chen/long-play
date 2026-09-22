#!/usr/bin/env python3
"""M3: guided-listening cues — build engine/guided_cues.json.

For each syllabus week and album, produce:
  timed: {track_n, track_title, starts_at, cue} — a real track boundary
         from the Spotify tracklist cache, paired with the week's curated
         "Listen for" cue. If the listen-for text names a specific track,
         the cue points at it; otherwise it points at the opener.
  liner: a one-line context drop taken VERBATIM from the album's curated
         week-file prose (first sentence of the section body). No new
         facts — the week file is the source of truth.

Intra-track moments ("listen at 2:14 on track 4") are deliberately NOT
generated: they need manual curation and would be invented otherwise.
A cue carries "curated_moment": false until a human adds one.

Usage: python3 bin/build_guided_cues.py [--week N]
Regenerates engine/guided_cues.json from weeks.json + tracklist cache.
"""
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "engine", "guided_cues.json")
TRACKLIST_DIR = os.path.join(REPO, "engine", "tracklists")

SECTION_RE = re.compile(
    r"^##\s+(Anchor|Adventurous|Wild card)\s+[—–-]\s+(.+?)\s+[—–-]\s+\*(.+?)\*\s*(\(\d{4}\))?",
    re.IGNORECASE)
LISTEN_FOR_RE = re.compile(r"\*\*Listen for:\*\*\s*(.+)", re.IGNORECASE)


def norm(s):
    return re.sub(r"[^a-z0-9]+", "-", s.strip().lower()).strip("-")


def slug(artist, album):
    return f"{norm(artist)}--{norm(album)}"


def load_tracklist(artist, album):
    path = os.path.join(TRACKLIST_DIR, slug(artist, album) + ".json")
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def parse_week_file(path):
    """Return list of {slot, artist, album, listen_for, prose}."""
    try:
        with open(path) as f:
            text = f.read()
    except FileNotFoundError:
        return None
    albums, current, in_cue, prose_lines, body_done = [], None, False, [], False
    for line in text.splitlines():
        stripped = line.strip()
        m = SECTION_RE.match(stripped)
        if m:
            if current:
                current["prose"] = " ".join(prose_lines).strip()
                albums.append(current)
            slot, artist, album, year = m.groups()
            current = {"slot": slot.strip().lower().replace(" ", "_"),
                       "artist": artist.strip(), "album": album.strip(),
                       "year": (year or "").strip("()"), "listen_for": "",
                       "prose": ""}
            in_cue, prose_lines, body_done = False, [], False
            continue
        if current is None or body_done:
            continue
        m2 = LISTEN_FOR_RE.search(line)
        if m2:
            # prose may precede the marker on the same line ("Same band... **Listen for:** ...")
            before = line[:m2.start()].strip()
            if before:
                prose_lines.append(before)
            current["listen_for"] = m2.group(1).strip()
            in_cue = True
            continue
        if in_cue:
            if stripped == "":
                in_cue = False
            else:
                current["listen_for"] += " " + stripped
        elif stripped and not stripped.startswith("**Log it"):
            if stripped == "---":
                # footer separator reached; drop it and stop collecting this body
                prose_lines = [p for p in prose_lines if p != "---"]
                body_done = True
            else:
                prose_lines.append(stripped)
    if current:
        current["prose"] = " ".join(prose_lines).strip()
        albums.append(current)
    return albums if len(albums) == 5 else None


def pick_track(listen_for, tracks):
    """Point the cue at a track named in the listen-for text, else the opener."""
    lf = listen_for.lower()
    for t in tracks:
        clean = (t.get("clean_title") or "").lower()
        full = (t.get("title") or "").lower()
        if clean and len(clean) > 3 and (clean in lf or full in lf):
            return t, True
    return (tracks[0], False) if tracks else (None, False)


def first_sentence(text):
    m = re.match(r"^(.+?[.!?])(\s|$)", text.strip())
    return m.group(1).strip() if m else text.strip()[:160]


def build_week(week_n):
    with open(os.path.join(REPO, "engine", "weeks.json")) as f:
        weeks = json.load(f)["weeks"]
    week = next(w for w in weeks if w["n"] == week_n)
    sections = parse_week_file(os.path.join(REPO, "weeks", f"week-{week_n:02d}.md"))
    by_key = {}
    if sections:
        for sec in sections:
            by_key[f"{norm(sec['artist'])}|{norm(sec['album'])}"] = sec
    cues = {}
    plan_picks = ([("anchor", week["anchor"])] +
                  [("adventurous", a) for a in week["adventurous"]] +
                  [("wild_card", week["wild_card"])])
    for slot, p in plan_picks:
        artist, album = p["artist"], p["album"]
        key = f"{norm(artist)}|{norm(album)}"
        sec = by_key.get(key, {})
        listen_for = sec.get("listen_for", "")
        placeholder = "(set by the digest)" in listen_for
        prose = sec.get("prose", "")
        tl = load_tracklist(artist, album)
        tracks = tl["tracks"] if tl else []
        search_text = (prose + " " + listen_for) if not (placeholder or not listen_for.strip()) else ""
        track, named = pick_track(search_text, tracks)
        if placeholder or not listen_for.strip():
            cue_sent = "[the week's listen-for lands with the Monday digest]"
            cue_pending = True
        else:
            cue_sent = first_sentence(listen_for)
            cue_pending = False
        liner = first_sentence(prose) if prose and not placeholder else None
        cues[key] = {
            "artist": artist, "album": album, "slot": slot,
            "timed": ({
                "track_n": track["n"],
                "track_title": track["clean_title"] or track["title"],
                "starts_at": track["starts_at"],
                "named_in_cue": named,
                "cue": (f"Track {track['n']} — “{track['clean_title'] or track['title']}” "
                        f"starts at {track['starts_at']}. {cue_sent}"),
                "curated_moment": False,  # intra-track moments need a human
                "cue_text_pending": cue_pending,
            } if track else None),
            "liner": liner,
            "liner_source": (f"weeks/week-{week_n:02d}.md (verbatim, first sentence)"
                             if liner else None),
            "tracklist": "spotify" if tl else "pending",
        }
    return cues


def main():
    only = None
    if "--week" in sys.argv:
        only = int(sys.argv[sys.argv.index("--week") + 1])
    with open(os.path.join(REPO, "engine", "weeks.json")) as f:
        weeks = json.load(f)["weeks"]
    out = {}
    built, missing_tl = 0, []
    for w in weeks:
        n = w["n"]
        if only and n != only:
            continue
        cues = build_week(n)
        if cues:
            out[str(n)] = cues
            built += 1
            for key, c in cues.items():
                if c["tracklist"] == "pending":
                    missing_tl.append((n, c["artist"], c["album"]))
    if not only:
        with open(OUT, "w") as f:
            json.dump(out, f, indent=1, ensure_ascii=False)
    else:
        # merge single week into existing file
        try:
            with open(OUT) as f:
                existing = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            existing = {}
        existing.update(out)
        with open(OUT, "w") as f:
            json.dump(existing, f, indent=1, ensure_ascii=False)
    print(json.dumps({"weeks_built": built, "missing_tracklists": missing_tl}, indent=1))


if __name__ == "__main__":
    main()
