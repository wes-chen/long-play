#!/usr/bin/env python3
"""M11: streaks + finisher rituals.

Streak counter for consecutive full-listen weeks + the week-24 graduation
ritual. HARD RULE: this must never feel like nagging (the finish-the-album
nudge was vetoed). Celebrations fire ONLY for new records (>= 3 weeks) or
milestones (4/8/12/16/20/24); routine weeks stay silent.

Full-listen week: all 5 albums have a logged chat reaction AND at least 3
are played or loved. Data: the listening log (ground truth).

Kill switch: after a celebration, the next week's log is checked. If no
feedback was logged for the celebrated week (he's not engaging — streak
talk is noise), the celebration counts as ignored. Two consecutive ignored
celebrations -> reminders DISABLE themselves permanently in the state file;
the cron body exits silently while disabled. Wesley re-enables by saying
so (the parent agent flips "enabled" back to true).

State: ~/workspace/goals/album-recommender-music-digest/hidden_files/streak.json
  {"streak": int, "best": int, "last_full_week": int|null,
   "enabled": bool, "ignored": int, "celebrated_week": int|null}

Commands:
  --check      print {"celebrate": bool, "message": "..."} for the cron
  --graduate   the week-24 graduation ritual message
  --ack-ignored  (internal) evaluate the kill-switch after a celebration
"""
import json
import os
import re
import sys
from collections import defaultdict

GOAL = os.path.expanduser("~/workspace/goals/album-recommender-music-digest")
LOG = os.path.join(GOAL, "listening-log.md")
STATE = os.path.join(GOAL, "hidden_files", "streak.json")
MILESTONES = {4, 8, 12, 16, 20, 24}

ROW_RE = re.compile(
    r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(anchor|adventurous|wild[- ]card)\s*\|\s*"
    r"(played|skipped|loved|bounced off)\b[^|]*\|\s*chat\s*\|",
    re.IGNORECASE)


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"streak": 0, "best": 0, "last_full_week": None,
                "enabled": True, "ignored": 0, "celebrated_week": None}


def save_state(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(s, f, indent=1)


def week_reactions():
    weeks = defaultdict(list)
    if os.path.exists(LOG):
        with open(LOG) as f:
            for line in f:
                m = ROW_RE.match(line)
                if m:
                    weeks[int(m.group(1))].append(m.group(5).lower())
    return weeks


def is_full_listen(reactions):
    return len(reactions) >= 5 and sum(
        r in ("played", "loved") for r in reactions) >= 3


def compute_streak(weeks):
    full = sorted(w for w, rs in weeks.items() if is_full_listen(rs))
    streak, last = 0, None
    for w in full:
        streak = streak + 1 if (last is None or w == last + 1) else 1
        last = w
    return streak, last, full


def check():
    st = load_state()
    if not st["enabled"]:
        print(json.dumps({"celebrate": False, "reason": "disabled by kill switch"}))
        return
    weeks = week_reactions()
    streak, last_full, _ = compute_streak(weeks)
    st["streak"], st["best"] = streak, max(st["best"], streak)
    st["last_full_week"] = last_full
    celebrate, message = False, None
    if last_full and last_full != st.get("celebrated_week"):
        if streak in MILESTONES:
            celebrate = True
            message = (f"Streak ritual: {streak} consecutive full-listen weeks. "
                       f"Week {last_full} closed the set — that's the milestone. "
                       "No lecture, just the number.")
        elif streak >= 3 and streak == st["best"] and streak > 3:
            celebrate = True
            message = (f"New record: {streak} full-listen weeks in a row. "
                       "The course is compounding.")
        if celebrate:
            st["celebrated_week"] = last_full
    save_state(st)
    print(json.dumps({"celebrate": celebrate, "message": message,
                      "streak": streak, "best": st["best"],
                      "last_full_week": last_full}, indent=1))


def ack_ignored():
    """Kill-switch evaluation: run the week after a celebration.

    If the celebrated week has no logged reactions, the celebration was
    ignored. Two in a row -> disable permanently.
    """
    st = load_state()
    if not st.get("celebrated_week"):
        print(json.dumps({"ignored": st["ignored"], "note": "nothing celebrated"}))
        return
    weeks = week_reactions()
    engaged = bool(weeks.get(st["celebrated_week"]))
    if engaged:
        st["ignored"] = 0
        msg = "engaged — counter reset"
    else:
        st["ignored"] += 1
        msg = f"ignored ({st['ignored']}/2)"
        if st["ignored"] >= 2:
            st["enabled"] = False
            msg = ("kill switch tripped: streak reminders disabled permanently "
                   "until Wesley re-enables them")
    save_state(st)
    print(json.dumps({"ignored": st["ignored"], "enabled": st["enabled"], "note": msg}))


def graduate():
    weeks = week_reactions()
    streak, last_full, full = compute_streak(weeks)
    full_weeks = len(full)
    print(json.dumps({
        "ritual": (
            "Graduation. 24 weeks, five albums a week, 120 records — the course "
            "is complete. You listened to "
            f"{full_weeks} weeks all the way through; your longest streak was "
            f"{load_state()['best']} weeks. The capstone: re-read the week-1 dense "
            "write-ups. If they read clearly now, the course worked. The Wrapped "
            "has the numbers; this is just the handshake."
        ),
        "full_listen_weeks": full_weeks,
        "best_streak": load_state()["best"],
    }, indent=1))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "--check"
    if cmd == "--check":
        check()
    elif cmd == "--ack-ignored":
        ack_ignored()
    elif cmd == "--graduate":
        graduate()
    else:
        print("usage: streak.py [--check|--ack-ignored|--graduate]")


if __name__ == "__main__":
    main()
