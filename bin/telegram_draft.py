#!/usr/bin/env python3
"""M7: one-track telegram — DRAFTING MECHANISM ONLY.

Each week, pick the standout track and draft a short message Wesley can
copy/send to 1–2 friends himself. NEVER sends anything — there is no send
path in this script, by design. The draft is surfaced in chat for his
approval; lightweight friend reactions can be logged later with
--log-reaction.

Standout selection (honest, no invention):
  1. The current week's album with the strongest logged reaction
     (loved > played; ties break toward the wild card).
  2. Its standout track = the album's most-completed sampler track that
     week; fallback = the opener from the Spotify tracklist cache.
  3. The one-line "why" comes verbatim from the week's Listen-for cue.

Recipients: ~/workspace/goals/album-recommender-music-digest/hidden_files/
telegram-recipients.json {"friends": ["name", ...]}. STUBBED until Wesley
names 1–2 friends — the draft says so plainly.

Drafts append to hidden_files/telegram-drafts.md (private).
"""
import glob
import json
import os
import re
import sys
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOAL = os.path.expanduser("~/workspace/goals/album-recommender-music-digest")
LOG = os.path.join(GOAL, "listening-log.md")
ROLLUPS = os.path.join(GOAL, "hidden_files", "sampler", "rollups")
RECIPIENTS = os.path.join(GOAL, "hidden_files", "telegram-recipients.json")
DRAFTS = os.path.join(GOAL, "hidden_files", "telegram-drafts.md")
DELIVERED = os.path.join(GOAL, "hidden_files", "digest-delivered.json")
TRACKLIST_DIR = os.path.join(REPO, "engine", "tracklists")

ROW_RE = re.compile(
    r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(anchor|adventurous|wild[- ]card)\s*\|\s*"
    r"(played|skipped|loved|bounced off)\b([^|]*)\|\s*chat\s*\|",
    re.IGNORECASE)
REACTION_RANK = {"loved": 3, "played": 2, "skipped": 1, "bounced off": 0}


def norm(s):
    return re.sub(r"[^a-z0-9]+", "-", s.strip().lower()).strip("-")


def current_week():
    try:
        with open(DELIVERED) as f:
            delivered = json.load(f)
        return max(delivered) if delivered else None
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def week_reactions(week):
    out = []
    if os.path.exists(LOG):
        with open(LOG) as f:
            for line in f:
                m = ROW_RE.match(line)
                if m and int(m.group(1)) == week:
                    out.append({"album": m.group(2).strip(), "artist": m.group(3).strip(),
                                "slot": m.group(4).strip().lower(),
                                "reaction": m.group(5).lower(), "note": m.group(6).strip()})
    return out


def standout_track(artist, album):
    """Most-completed sampler track for the album, else the opener."""
    key = f"{norm(artist)}--{norm(album)}"
    tl_path = os.path.join(TRACKLIST_DIR, key + ".json")
    opener = None
    if os.path.exists(tl_path):
        with open(tl_path) as f:
            tl = json.load(f)
        if tl.get("tracks"):
            opener = tl["tracks"][0]
    # sampler: newest rollup, album rows keyed "Artist — Album"
    best, best_prog = None, -1
    for path in sorted(glob.glob(os.path.join(ROLLUPS, "*.json")), reverse=True)[:4]:
        try:
            with open(path) as f:
                roll = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        for t in roll.get("top_tracks", []):
            # track-level completion data lives in top_tracks
            pass
        break
    # rollup.py exposes per-track max progress in top_tracks; match by artist
    for path in sorted(glob.glob(os.path.join(ROLLUPS, "*.json")), reverse=True)[:4]:
        try:
            with open(path) as f:
                roll = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        for t in roll.get("top_tracks", []):
            artists = [a.lower() for a in t.get("artists", [])]
            if artist.lower() in artists and (t.get("max_progress_pct") or 0) >= 85:
                if (t.get("max_progress_pct") or 0) > best_prog:
                    best, best_prog = t, t["max_progress_pct"]
        if best:
            break
    if best:
        return {"title": best["track"], "artists": best.get("artists", []),
                "source": "sampler: most-completed track this month"}
    if opener:
        return {"title": opener.get("clean_title") or opener["title"],
                "source": "tracklist cache: opener (fallback)"}
    return {"title": None, "source": "pending: no tracklist, no sampler data"}


def listen_for(week, artist, album):
    path = os.path.join(REPO, "weeks", f"week-{week:02d}.md")
    try:
        with open(path) as f:
            text = f.read()
    except FileNotFoundError:
        return ""
    # find the album section and its Listen for line
    lines = text.splitlines()
    in_section = False
    for i, line in enumerate(lines):
        if line.startswith("##") and artist.lower() in line.lower() \
                and album.lower() in line.lower():
            in_section = True
            continue
        if in_section:
            if line.startswith("##"):
                break
            m = re.search(r"\*\*Listen for:\*\*\s*(.+)", line)
            if m:
                cue = m.group(1).strip()
                j = i + 1
                while j < len(lines) and lines[j].strip() and not lines[j].startswith("##"):
                    cue += " " + lines[j].strip()
                    j += 1
                return cue
    return ""


def draft():
    week = current_week()
    if not week:
        print(json.dumps({"draft": None,
                          "note": "no week delivered yet — nothing to telegram"}))
        return
    reactions = week_reactions(week)
    if not reactions:
        print(json.dumps({"draft": None,
                          "note": f"week {week}: no reactions logged yet"}))
        return
    # standout album: strongest reaction, ties -> wild card
    def rank(r):
        return (REACTION_RANK[r["reaction"]],
                1 if "wild" in r["slot"] else 0)
    pick = sorted(reactions, key=rank, reverse=True)[0]
    track = standout_track(pick["artist"], pick["album"])
    cue = listen_for(week, pick["artist"], pick["album"])
    try:
        with open(RECIPIENTS) as f:
            friends = json.load(f).get("friends", [])
    except (FileNotFoundError, json.JSONDecodeError):
        friends = []
    to_line = ", ".join(friends) if friends else \
        "[recipients not set — Wesley, tell me which 1–2 friends get these]"
    text = (
        f"To: {to_line}\n"
        f"Week {week} standout — “{track['title'] or '[track pending]'}”"
        f" — {pick['artist']} (from *{pick['album']}*).\n"
        f"Why: {cue[:180] + ('…' if len(cue) > 180 else '') if cue else '[cue pending]'}\n"
        f"— via the long-play course (week {week}, {pick['slot']}; "
        f"his reaction: {pick['reaction']})"
    )
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "week": week,
             "album": f"{pick['artist']} — {pick['album']}",
             "track": track["title"], "track_source": track["source"],
             "recipients": friends or "STUBBED",
             "text": text, "sent": False, "friend_reaction": None}
    os.makedirs(os.path.dirname(DRAFTS), exist_ok=True)
    with open(DRAFTS, "a") as f:
        f.write(f"\n## {entry['ts'][:10]} — week {week}\n{text}\n"
                f"\nSent: no. Friend reaction: —\n")
    print(json.dumps({"draft": text, "track_source": track["source"],
                      "recipients": entry["recipients"],
                      "note": "DRAFT ONLY — nothing was sent. Wesley approves/sends himself."},
                     indent=1))


def log_reaction(ts_prefix, reaction):
    """Record a lightweight friend reaction to a draft: --log-reaction YYYY-MM-DD <text>."""
    if not os.path.exists(DRAFTS):
        print(json.dumps({"error": "no drafts file"}))
        return
    with open(DRAFTS) as f:
        content = f.read()
    new = content.replace("Friend reaction: —",
                          f"Friend reaction: {reaction}", 1)
    with open(DRAFTS, "w") as f:
        f.write(new)
    print(json.dumps({"logged": reaction}))


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--log-reaction":
        log_reaction(sys.argv[2], " ".join(sys.argv[3:]))
    else:
        draft()


if __name__ == "__main__":
    main()
