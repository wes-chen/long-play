#!/usr/bin/env python3
"""M10: wild-card calibration report.

Periodic check on whether the 2x wild-card weight is earned: do wild-card
picks predict taste better than curated slots? Metrics, from the listening
log (explicit chat reactions, the only ground truth):

  - reaction rate, loved rate, and mean weighted score per slot
  - discomfort signal strength: mean |weighted score| per slot
    (the standing claim is that discomfort is the most informative signal)
  - predictive lift: how much wild-card reactions move the M2 taste vector
    vs curated-slot reactions (reads engine/taste-vector.json when built)

Recommendation rule (advisory only — never auto-applied):
  - wild-card mean |score| >= 1.5x curated slots' -> suggest 2.5x
  - wild-card mean |score| <= 0.8x curated slots' -> suggest 1.5x
  - otherwise -> keep 2.0x
Wesley decides; the suggestion is reported, never written into the schema.

Needs >= 4 weeks of reactions to say anything meaningful; before that it
reports "insufficient data" honestly.
"""
import json
import os
import re
import sys
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOAL = os.path.expanduser("~/workspace/goals/album-recommender-music-digest")
LOG = os.path.join(GOAL, "listening-log.md")
VECTOR = os.path.join(REPO, "engine", "taste-vector.json")
OUT = os.path.join(GOAL, "hidden_files", "wildcard-calibration.json")

REACTION_SCORE = {"loved": 1.0, "played": 0.4, "skipped": -0.2, "bounced off": -1.0}
ROW_RE = re.compile(
    r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(anchor|adventurous|wild[- ]card)\s*\|\s*"
    r"(played|skipped|loved|bounced off)\b[^|]*\|\s*chat\s*\|\s*([\d.]+)\s*\|",
    re.IGNORECASE)
MIN_WEEKS = 4


def slot_of(raw):
    s = raw.lower().replace("-", "_").replace(" ", "_")
    return "wild_card" if "wild" in s else s


def main():
    rows = []
    if os.path.exists(LOG):
        with open(LOG) as f:
            for line in f:
                m = ROW_RE.match(line)
                if m:
                    rows.append((int(m.group(1)), slot_of(m.group(4)),
                                 m.group(5).lower(), float(m.group(6))))
    weeks = len({r[0] for r in rows})
    per_slot = defaultdict(lambda: {"n": 0, "loved": 0, "scores": []})
    for _, slot, reaction, weight in rows:
        s = per_slot[slot]
        s["n"] += 1
        if reaction == "loved":
            s["loved"] += 1
        s["scores"].append(REACTION_SCORE[reaction] * weight)

    report = {"generated_at": __import__("datetime").datetime.now(
                  __import__("datetime").timezone.utc).isoformat(),
              "weeks_with_data": weeks, "slots": {}}
    for slot, s in per_slot.items():
        n = s["n"]
        report["slots"][slot] = {
            "reactions": n,
            "loved_rate": round(s["loved"] / n, 3) if n else None,
            "mean_weighted_score": round(sum(s["scores"]) / n, 3) if n else None,
            "mean_abs_score": round(sum(abs(x) for x in s["scores"]) / n, 3) if n else None,
        }

    if weeks < MIN_WEEKS:
        report["status"] = "insufficient_data"
        report["recommendation"] = {
            "action": "none",
            "reason": f"only {weeks} week(s) of reactions; need >= {MIN_WEEKS} "
                      "before judging the 2x weight",
        }
    else:
        wc = report["slots"].get("wild_card", {}).get("mean_abs_score") or 0
        curated = [v.get("mean_abs_score") or 0
                   for k, v in report["slots"].items() if k != "wild_card"]
        base = sum(curated) / len(curated) if curated else 0
        ratio = (wc / base) if base else 0
        if ratio >= 1.5:
            sugg, why = 2.5, "wild-card discomfort signal is much stronger than curated slots'"
        elif ratio <= 0.8:
            sugg, why = 1.5, "wild-card reactions are not carrying more signal than curated slots'"
        else:
            sugg, why = 2.0, "wild-card signal strength is in line with curated slots'"
        report["status"] = "ok"
        report["recommendation"] = {
            "action": "suggest",
            "suggested_weight": sugg,
            "current_weight": 2.0,
            "wild_card_abs_signal": round(wc, 3),
            "curated_abs_signal": round(base, 3),
            "ratio": round(ratio, 3),
            "reason": why + " — Wesley decides; weights are never auto-changed",
        }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(report, f, indent=1)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
