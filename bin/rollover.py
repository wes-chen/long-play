#!/usr/bin/env python3
"""ADV-LP-01: idempotent week rollover for the long-play course.

Called as step 0 of the Monday digest. Reads weeks/CURRENT (e.g. "01") and
the delivery marker hidden_files/digest-delivered.json (list of delivered
week numbers). Only when the current week is already marked delivered does
it advance: writes CURRENT = N+1, scaffolds weeks/week-NN.md from
engine/weeks.json, and rebuilds the sampler watchlist for the new week.

Idempotent: running twice without a new delivery changes nothing — the
marker file is the single source of truth for "delivered", and CURRENT is
never advanced past a delivered week. Never alters a published week's
picks; it only creates the *next* week's file.

M1 grower wiring: when the next week is scaffolded, albums due for their
one scheduled second chance (grower.due_entries) are slotted into the new
week file's "Second chance" section and marked re-queued — each album
exactly once, ever. If the week file already existed, nothing is inserted
and nothing is marked (the Monday grower chat announcement covers those).

Usage: python3 bin/rollover.py
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "bin"))
import grower  # noqa: E402  (M1 second-chance wiring)
CURRENT_PATH = os.path.join(REPO, "weeks", "CURRENT")
WEEKS_JSON = os.path.join(REPO, "engine", "weeks.json")
DELIVERED = os.path.expanduser(
    "~/workspace/goals/album-recommender-music-digest/hidden_files/"
    "digest-delivered.json"
)
MAX_WEEK = 24


def read_current():
    with open(CURRENT_PATH) as f:
        return int(f.read().strip())


def read_delivered():
    try:
        with open(DELIVERED) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def week_plan(n):
    with open(WEEKS_JSON) as f:
        data = json.load(f)
    for w in data.get("weeks", []):
        if w["n"] == n:
            return w
    return None


def scaffold_week_file(n, plan, second_chances=None):
    """Build the week file. second_chances is a list of grower queue
    entries (see grower.due_entries); each is inserted as a bonus
    "Second chance" re-listen — never a replacement pick.

    Returns (path, created): created is False when the file already
    existed and was left untouched.
    """
    path = os.path.join(REPO, "weeks", f"week-{n:02d}.md")
    if os.path.exists(path):
        print(f"week file exists, leaving it: {path}")
        return path, False
    lines = [
        f"# Week {n} — {plan['title']}",
        "",
        f"**Objective:** {plan['objective']}",
        "",
        f"**Concept — {plan['concept']}.** {plan['concept_note']}",
        "",
        f"**Technique — {plan['technique']}.** {plan['technique_note']}",
        "",
        "---",
        "",
        f"## Anchor — {plan['anchor']['artist']} — "
        f"*{plan['anchor']['album']}*",
        "",
        "**Listen for:** (set by the digest)",
        "",
    ]
    for a in plan["adventurous"]:
        lines += [f"## Adventurous — {a['artist']} — *{a['album']}*", "",
                  "**Listen for:** (set by the digest)", ""]
    wc = plan["wild_card"]
    lines += [f"## Wild card — {wc['artist']} — *{wc['album']}*", "",
              "**Listen for:** (set by the digest)", ""]
    if second_chances:
        lines += ["", "## Second chance — grower re-queue", ""]
        for e in second_chances:
            lines += [f"- **{e['artist']}** — *{e['album']}* — bounced off "
                      f"in week {e['week']}; re-queued for one second listen.",
                      ""]
        lines += ["**Log it:** second-chance reactions use the same four "
                  "reactions — a played/loved here marks a grower.", ""]
    lines += ["---", "",
              "**Log it:** played / skipped / loved / bounced off — one line "
              "per album. Wild card reactions count double.", ""]
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"scaffolded {path}")
    return path, True


def main():
    n = read_current()
    delivered = read_delivered()
    if n not in delivered:
        print(f"week {n} not marked delivered; staying on week {n:02d}")
        return 0
    m = n + 1
    if m > MAX_WEEK:
        print(f"all {MAX_WEEK} weeks delivered; course complete")
        return 0
    plan = week_plan(m)
    if not plan:
        print(f"no plan for week {m} in engine/weeks.json; not advancing")
        return 1
    # M1: slot any due grower second-chances into the week being built,
    # then mark each re-queued (exactly once per album, ever).
    second_chances = grower.due_entries(m)
    for e in second_chances:
        print(f"grower second chance due in week {m}: "
              f"{e['artist']} — {e['album']} (bounced week {e['week']})")
    path, created = scaffold_week_file(m, plan, second_chances)
    if created:
        for e in second_chances:
            grower.mark_requeued(e["week"], e["artist"], e["album"])
    r = subprocess.run([sys.executable,
                        os.path.join(REPO, "sampler", "build_watchlist.py"),
                        str(m)], capture_output=True, text=True, timeout=300)
    print(r.stdout.strip())
    if r.returncode != 0:
        print(f"watchlist rebuild failed for week {m}; not advancing",
              file=sys.stderr)
        print(r.stderr.strip(), file=sys.stderr)
        return 1
    with open(CURRENT_PATH, "w") as f:
        f.write(f"{m:02d}\n")
    print(f"rolled over: CURRENT is now week {m:02d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
