#!/usr/bin/env python3
"""M4: pre-listen prediction scoring + blind-week bookkeeping.

Before the weekly picks, Wesley records his prediction for each album
(love / play / bounce — "play" = will listen through, no strong feeling).
Prediction accuracy is a calibration signal for the M2 taste vector.

State: ~/workspace/goals/album-recommender-music-digest/hidden_files/predictions.json
  {"weeks": {"3": {"asked_at": ..., "blind": false,
                   "predictions": [{"artist","album","slot","prediction"}],
                   "scored": false, "accuracy": null, "detail": [...]}}}

Prediction vocabulary: love / play / bounce.
Reaction vocabulary:  loved / played / skipped / bounced off.
Match rules: love<->loved, play<->played, bounce<->bounced off.
"skipped" counts as a half-miss against any prediction except bounce
(skipping a predicted bounce is a hit).

Commands:
  --record <week> <artist> <album> <slot> <love|play|bounce>
  --set-blind <week> true|false
  --score <week>     compare predictions vs the listening log
  --accuracy         overall accuracy across scored weeks
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

GOAL = os.path.expanduser("~/workspace/goals/album-recommender-music-digest")
STATE = os.path.join(GOAL, "hidden_files", "predictions.json")
LOG = os.path.join(GOAL, "listening-log.md")

MATCH = {("love", "loved"): 1.0, ("play", "played"): 1.0, ("bounce", "bounced off"): 1.0}
ROW_RE = re.compile(
    r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(anchor|adventurous|wild[- ]card)\s*\|\s*"
    r"(played|skipped|loved|bounced off)\b[^|]*\|\s*chat\s*\|",
    re.IGNORECASE)


def load():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"weeks": {}}


def save(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(s, f, indent=1)


def now():
    return datetime.now(timezone.utc).isoformat()


def record(week, artist, album, slot, prediction):
    prediction = prediction.lower()
    assert prediction in ("love", "play", "bounce"), "prediction must be love/play/bounce"
    s = load()
    w = s["weeks"].setdefault(str(week), {"asked_at": now(), "blind": False,
                                          "predictions": [], "scored": False,
                                          "accuracy": None})
    w["predictions"] = [p for p in w["predictions"]
                        if not (p["artist"].lower() == artist.lower()
                                and p["album"].lower() == album.lower())]
    w["predictions"].append({"artist": artist, "album": album,
                             "slot": slot, "prediction": prediction})
    save(s)
    print(json.dumps({"recorded": f"{artist} — {album}: {prediction}", "week": week}))


def set_blind(week, flag):
    s = load()
    w = s["weeks"].setdefault(str(week), {"asked_at": now(), "blind": False,
                                          "predictions": [], "scored": False,
                                          "accuracy": None})
    w["blind"] = flag.lower() == "true"
    save(s)
    print(json.dumps({"week": week, "blind": w["blind"]}))


def log_reactions(week):
    """Map (artist, album) -> reaction for a week from the log."""
    out = {}
    if not os.path.exists(LOG):
        return out
    with open(LOG) as f:
        for line in f:
            m = ROW_RE.match(line)
            if m and int(m.group(1)) == int(week):
                out[(m.group(3).strip().lower(), m.group(2).strip().lower())] = \
                    m.group(5).lower()
    return out


def score_week(week):
    s = load()
    w = s["weeks"].get(str(week))
    if not w or not w["predictions"]:
        print(json.dumps({"error": "no predictions recorded for week " + str(week)}))
        return
    reactions = log_reactions(week)
    detail, hits, total = [], 0.0, 0
    for p in w["predictions"]:
        key = (p["artist"].lower(), p["album"].lower())
        r = reactions.get(key)
        if not r:
            detail.append({**p, "reaction": None, "score": None})
            continue
        total += 1
        if (p["prediction"], r) in MATCH:
            sc = 1.0
        elif r == "skipped":
            sc = 0.5 if p["prediction"] == "bounce" else 0.0
        else:
            sc = 0.0
        hits += sc
        detail.append({**p, "reaction": r, "score": sc})
    w["scored"] = total > 0
    w["accuracy"] = round(hits / total, 3) if total else None
    w["scored_at"] = now()
    w["detail"] = detail
    save(s)
    print(json.dumps({"week": week, "accuracy": w["accuracy"],
                      "scored_predictions": total,
                      "detail": detail}, indent=1))


def accuracy():
    s = load()
    scored = [(wk, w) for wk, w in s["weeks"].items() if w.get("accuracy") is not None]
    if not scored:
        print(json.dumps({"weeks_scored": 0, "note": "no scored weeks yet"}))
        return
    acc = sum(w["accuracy"] for _, w in scored) / len(scored)
    print(json.dumps({
        "weeks_scored": len(scored),
        "mean_accuracy": round(acc, 3),
        "by_week": {wk: w["accuracy"] for wk, w in sorted(scored)},
        "blind_weeks": [wk for wk, w in sorted(scored) if w.get("blind")],
    }, indent=1))


def main():
    if len(sys.argv) < 2:
        print("usage: predictions.py [--record W ARTIST ALBUM SLOT love|play|bounce |"
              "--set-blind W true|false | --score W | --accuracy]")
        return
    cmd = sys.argv[1]
    if cmd == "--record" and len(sys.argv) == 7:
        record(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])
    elif cmd == "--set-blind" and len(sys.argv) == 4:
        set_blind(sys.argv[2], sys.argv[3])
    elif cmd == "--score" and len(sys.argv) == 3:
        score_week(sys.argv[2])
    elif cmd == "--accuracy":
        accuracy()
    else:
        print("bad args")


if __name__ == "__main__":
    main()
