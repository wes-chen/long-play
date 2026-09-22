#!/usr/bin/env python3
"""M8: monthly taste-blend — DRAFTING MECHANISM ONLY.

Blends his recent listening with a friend's or artist's playlist into a
shared 10-track mix. DRAFT ONLY — nothing is sent, no playlist is created;
the draft is surfaced in chat for Wesley's approval, and he sends it
himself.

His side (real data): top tracks from the last 4 sampler rollups +
loved albums from the listening log.
Their side: a source playlist named in
~/workspace/goals/album-recommender-music-digest/hidden_files/taste-blend-source.json
{"type": "friend"|"artist", "name": "...", "playlist_uri": "spotify:playlist:..."}.
STUBBED until Wesley names a friend's playlist or picks an artist —
the draft says so plainly.

Overlap: shared artists between his recent listening and the source feed
hidden_files/taste-blend-overlap.json, which the M2 taste vector reads as
a weak artist-affinity signal.
"""
import glob
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

GOAL = os.path.expanduser("~/workspace/goals/album-recommender-music-digest")
ROLLUPS = os.path.join(GOAL, "hidden_files", "sampler", "rollups")
SOURCE = os.path.join(GOAL, "hidden_files", "taste-blend-source.json")
DRAFTS = os.path.join(GOAL, "hidden_files", "taste-blend-drafts.md")
OVERLAP = os.path.join(GOAL, "hidden_files", "taste-blend-overlap.json")


def his_recent_tracks(n=5):
    """Top completed tracks across the last 4 rollups."""
    seen, out = {}, []
    for path in sorted(glob.glob(os.path.join(ROLLUPS, "*.json")), reverse=True)[:4]:
        try:
            with open(path) as f:
                roll = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        for t in roll.get("top_tracks", []):
            key = (t.get("track") or "").lower()
            if not key or key in seen:
                continue
            seen[key] = True
            out.append({"title": t["track"], "artists": t.get("artists", []),
                        "max_progress_pct": t.get("max_progress_pct"),
                        "source": "his recent listening (sampler)"})
            if len(out) >= n:
                return out
    return out


def source_tracks(uri, n=5):
    """Fetch up to n tracks from the source playlist via spotify-api."""
    r = subprocess.run(["spotify-api", "experience", "--id", uri],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return None, f"spotify-api failed: {r.stderr.strip()[:150]}"
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return None, "non-JSON response"
    out = []
    for section in data.get("sections", []):
        for it in section.get("items", []):
            if it.get("title") and it.get("spotify_uri", "").startswith("spotify:track:"):
                out.append({"title": it["title"],
                            "artists": [it.get("subtitle")] if it.get("subtitle") else [],
                            "spotify_uri": it["spotify_uri"],
                            "source": "source playlist"})
            if len(out) >= n:
                break
        if len(out) >= n:
            break
    return out, None


def main():
    his = his_recent_tracks()
    try:
        with open(SOURCE) as f:
            src = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        src = None
    theirs, their_note = [], None
    if src and src.get("playlist_uri"):
        theirs, err = source_tracks(src["playlist_uri"])
        if err:
            their_note = err
            theirs = []
    overlap_artists = set()
    if his and theirs:
        his_artists = {a.lower() for t in his for a in t["artists"]}
        their_artists = {a.lower() for t in theirs for a in t["artists"] if a}
        overlap_artists = his_artists & their_artists
        if overlap_artists:
            with open(OVERLAP, "w") as f:
                json.dump({"ts": datetime.now(timezone.utc).isoformat(),
                           "artists": sorted(overlap_artists),
                           "note": "weak artist-affinity signal for the M2 taste vector"},
                          f, indent=1)
    blend = his + theirs
    lines = [f"{i+1}. “{t['title']}” — {', '.join(t['artists']) or 'unknown artist'} "
             f"({t['source']})" for i, t in enumerate(blend)]
    src_line = (f"{src['type']}: {src['name']}" if src
                else "[source not set — Wesley, name a friend's playlist or pick an artist]")
    draft_text = (
        f"Taste blend — {datetime.now(timezone.utc).date().isoformat()}\n"
        f"His side: recent listening. Their side: {src_line}.\n\n"
        + ("\n".join(lines) if lines else "[not enough listening data yet — blend pending]")
        + (f"\n\nOverlap artists (taste-vector signal): {', '.join(sorted(overlap_artists))}"
           if overlap_artists else "")
        + "\n\nDRAFT ONLY — nothing sent, no playlist created. Wesley approves/sends."
    )
    if their_note:
        draft_text += f"\n[source fetch issue: {their_note}]"
    os.makedirs(os.path.dirname(DRAFTS), exist_ok=True)
    with open(DRAFTS, "a") as f:
        f.write(f"\n## {datetime.now(timezone.utc).date().isoformat()}\n{draft_text}\n")
    print(json.dumps({
        "draft": draft_text,
        "his_tracks": len(his), "their_tracks": len(theirs),
        "overlap_artists": sorted(overlap_artists),
        "source": src or "STUBBED",
        "note": "DRAFT ONLY — nothing was sent.",
    }, indent=1))


if __name__ == "__main__":
    main()
