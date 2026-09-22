#!/usr/bin/env python3
"""M5: Course Wrapped finale — end-of-24-weeks personal review.

Fires once, after week 24 delivers (runonce cron). The course is still
underway at year-end — this is separate from the NL-04 year-end reckoning.

Sections (all from real data; anything uncomputable is marked pending):
  - Totals: weeks completed, albums assigned/played/loved/bounced, full-listen weeks
  - Biggest growers: M1 second-chance albums that flipped to played/loved
  - Genre map of taste movement: genre affinity from weeks 1-4 vs 21-24
    (explicit reactions only — ground truth)
  - Prediction accuracy: M4 record across the course, blind weeks called out
  - Wild-card verdict: the final M10 read on the 2x weight

Writes a private working copy to hidden_files/wrapped.md and prints the
chat report. Usage: python3 bin/course_wrapped.py [--save]
"""
import json
import os
import re
import sys
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOAL = os.path.expanduser("~/workspace/goals/album-recommender-music-digest")
LOG = os.path.join(GOAL, "listening-log.md")
GROWER = os.path.join(GOAL, "hidden_files", "grower-state.json")
PREDICTIONS = os.path.join(GOAL, "hidden_files", "predictions.json")
STREAK = os.path.join(GOAL, "hidden_files", "streak.json")
OUT = os.path.join(GOAL, "hidden_files", "wrapped.md")

REACTION_SCORE = {"loved": 1.0, "played": 0.4, "skipped": -0.2, "bounced off": -1.0}
ROW_RE = re.compile(
    r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(anchor|adventurous|wild[- ]card)\s*\|\s*"
    r"(played|skipped|loved|bounced off)\b[^|]*\|\s*chat\s*\|\s*([\d.]+)\s*\|",
    re.IGNORECASE)


def norm(s):
    return " ".join(s.strip().lower().split())


def load_tags():
    with open(os.path.join(REPO, "engine", "album_tags.json")) as f:
        return json.load(f)


def rows():
    out = []
    if os.path.exists(LOG):
        with open(LOG) as f:
            for line in f:
                m = ROW_RE.match(line)
                if m:
                    out.append({"week": int(m.group(1)), "album": m.group(2).strip(),
                                "artist": m.group(3).strip(),
                                "slot": m.group(4).strip().lower(),
                                "reaction": m.group(5).lower(),
                                "weight": float(m.group(6))})
    return out


def genre_affinity(rows, tags, weeks):
    scores, weights = defaultdict(float), defaultdict(float)
    for r in rows:
        if r["week"] not in weeks:
            continue
        tag = tags.get(f"{norm(r['artist'])}|{norm(r['album'])}")
        if not tag:
            continue
        s = REACTION_SCORE[r["reaction"]] * r["weight"]
        scores[tag["genre"]] += s
        weights[tag["genre"]] += r["weight"]
    return {g: round(scores[g] / weights[g], 3) for g in scores if weights[g]}


def main():
    save = "--save" in sys.argv
    tags = load_tags()
    rs = rows()
    weeks_done = sorted({r["week"] for r in rs})
    by_reaction = defaultdict(int)
    for r in rs:
        by_reaction[r["reaction"]] += 1

    # full-listen weeks: 5 reactions, >=3 played/loved
    per_week = defaultdict(list)
    for r in rs:
        per_week[r["week"]].append(r["reaction"])
    full_weeks = [w for w, rxs in per_week.items()
                  if len(rxs) >= 5 and sum(x in ("played", "loved") for x in rxs) >= 3]

    # growers
    growers = []
    try:
        with open(GROWER) as f:
            gq = json.load(f)["queue"]
        growers = [e for e in gq if e.get("grower")]
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # prediction accuracy
    pred_line = "pending — no scored prediction weeks"
    try:
        with open(PREDICTIONS) as f:
            pw = json.load(f)["weeks"]
        scored = {w: d for w, d in pw.items() if d.get("accuracy") is not None}
        if scored:
            acc = sum(d["accuracy"] for d in scored.values()) / len(scored)
            blind = [w for w, d in scored.items() if d.get("blind")]
            pred_line = (f"{round(acc*100)}% mean accuracy across {len(scored)} scored weeks"
                         + (f"; blind weeks: {', '.join(sorted(blind))}" if blind else
                            "; no blind weeks run"))
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # genre movement: weeks 1-4 vs 21-24
    early = genre_affinity(rs, tags, set(range(1, 5)))
    late = genre_affinity(rs, tags, set(range(21, 25)))
    movement = []
    for g in sorted(set(early) | set(late)):
        e, l = early.get(g, 0), late.get(g, 0)
        movement.append((g, e, l, round(l - e, 3)))
    movement.sort(key=lambda x: -abs(x[3]))

    best_streak = None
    try:
        with open(STREAK) as f:
            best_streak = json.load(f).get("best")
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    L = []
    L.append("# Course Wrapped — the 24-week long-play\n")
    L.append("## Totals")
    L.append(f"- Weeks with logged feedback: {len(weeks_done)}")
    L.append(f"- Album reactions: {len(rs)} "
             f"(loved {by_reaction['loved']}, played {by_reaction['played']}, "
             f"skipped {by_reaction['skipped']}, bounced off {by_reaction['bounced off']})")
    L.append(f"- Full-listen weeks: {len(full_weeks)}")
    if best_streak is not None:
        L.append(f"- Best streak: {best_streak} consecutive full-listen weeks")
    L.append("")
    L.append("## Biggest growers (M1 second chances that flipped)")
    if growers:
        for g in growers:
            L.append(f"- {g['artist']} — {g['album']} (bounced week {g['week']}, "
                     f"{g['second_reaction']} on the second chance)")
    else:
        L.append("- None yet — no second-chance album has flipped to played/loved.")
    L.append("")
    L.append("## Genre map: taste movement (weeks 1–4 → weeks 21–24)")
    L.append("Explicit reactions only; score = mean weighted reaction per genre.")
    if movement:
        for g, e, l, d in movement[:12]:
            arrow = "→"
            L.append(f"- {g}: {e:+.2f} {arrow} {l:+.2f} (Δ {d:+.2f})")
    else:
        L.append("- Pending — not enough reactions in the comparison windows.")
    L.append("")
    L.append("## Prediction accuracy (M4)")
    L.append(f"- {pred_line}")
    L.append("")
    L.append("## Wild-card verdict (M10)")
    L.append("- Final read: run `bin/wildcard_calibration.py` for the closing "
             "judgment on the 2× weight — the numbers above are its inputs.")
    L.append("")
    L.append("_Note: the 24-week arc completed before the calendar year ended; "
             "the NL-04 year-end reckoning is a separate report._")
    report = "\n".join(L)
    if save:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w") as f:
            f.write(report + "\n")
    print(report)


if __name__ == "__main__":
    main()
