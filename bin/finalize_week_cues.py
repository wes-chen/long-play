#!/usr/bin/env python3
"""Issue #24: persist the Monday digest's finalized listen-for cues.

The digest composes five listen-for sentences while writing the week's
digest page, but nothing wrote them back into weeks/week-NN.md — the
scaffold's "**Listen for:** (set by the digest)" placeholders survived
into the published week. Consequences, all verified before this script
existed:

- drip_pick parsed the placeholder and printed it verbatim as the day's
  cue ("Listen for: (set by the digest)") for every Tue–Fri drip;
- build_guided_cues saw the placeholder, marked cue_text_pending: true,
  got empty search text so pick_track blindly pointed every cue at
  track 1, and liner stayed null (scaffolded files have no prose).

This script is the digest's missing write-back step. Run it after the
write-ups are composed, replacing the old manual edit of the week file
and the separate build_guided_cues.py --week N call — both now happen
atomically here:

    python3 bin/finalize_week_cues.py --week 2 --cues /tmp/week-02-cues.json

cues.json is either a list of 5 strings in week-file section order
(anchor, adventurous x3, wild card), or
{"anchor": s, "adventurous": [s, s, s], "wild_card": s}.

Fail-closed contract:
- Exactly 5 "(set by the digest)" placeholders must be present. Fewer
  means the file is already finalized (or not a scaffold) — the script
  refuses to overwrite a finalized cue. Rerunning with the SAME cues is
  an idempotent no-op.
- The 5 sentences must be non-empty and free of the placeholder text.
- After the write-back, the guided cues for week N are rebuilt and the
  script verifies every week-N timed cue has cue_text_pending == False.

Usage: python3 bin/finalize_week_cues.py --week N --cues cues.json
"""
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "bin"))
import build_guided_cues  # noqa: E402

PLACEHOLDER_RE = re.compile(
    r"^\*\*Listen for:\*\*\s*\(set by the digest\)\s*$")
LISTEN_FOR_RE = re.compile(r"^\*\*Listen for:\*\*\s*(.+?)\s*$")
N_SECTIONS = 5


def load_cues(path):
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        cues = data
    elif isinstance(data, dict):
        cues = ([data["anchor"]] + list(data["adventurous"]) +
                [data["wild_card"]])
    else:
        raise ValueError("cues.json must be a list of 5 or "
                         "{anchor, adventurous[3], wild_card}")
    if len(cues) != N_SECTIONS or not all(
            isinstance(c, str) and c.strip() for c in cues):
        raise ValueError("need exactly 5 non-empty cue sentences")
    if any("(set by the digest)" in c for c in cues):
        raise ValueError("cue sentences must not contain the placeholder")
    return [c.strip() for c in cues]


def finalize(repo_root, week_n, cues):
    """Write cues into weeks/week-NN.md and rebuild guided cues.

    Returns a summary dict. Raises SystemExit-free ValueError/RuntimeError
    on any contract violation; the week file is only rewritten when every
    check passes first.
    """
    week_path = os.path.join(repo_root, "weeks", "week-%02d.md" % week_n)
    if not os.path.exists(week_path):
        raise RuntimeError(f"week file missing: {week_path}")

    with open(week_path) as f:
        lines = f.read().splitlines()

    ph_idx = [i for i, ln in enumerate(lines)
              if PLACEHOLDER_RE.match(ln)]

    if len(ph_idx) != N_SECTIONS:
        existing = [m.group(1) for ln in lines
                    if (m := LISTEN_FOR_RE.match(ln))]
        if not ph_idx and len(existing) == N_SECTIONS:
            if existing == cues:
                return {"week": week_n, "finalized": True,
                        "changed": False,
                        "note": "cues already match; no-op"}
            raise RuntimeError(
                "week file already has finalized listen-fors; refusing "
                "to overwrite (finalized cues are the assignment of "
                "record)")
        raise RuntimeError(
            f"expected {N_SECTIONS} '(set by the digest)' placeholders, "
            f"found {len(ph_idx)} — not a fresh scaffold")

    for i, cue in zip(ph_idx, cues):
        lines[i] = f"**Listen for:** {cue}"

    with open(week_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    # Verify no placeholder survived, then rebuild guided cues for week N.
    with open(week_path) as f:
        after = f.read()
    if "(set by the digest)" in after:
        raise RuntimeError("placeholder still present after write-back")

    out_path = os.path.join(repo_root, "engine", "guided_cues.json")
    old_repo, old_out, old_tl = (build_guided_cues.REPO,
                                 build_guided_cues.OUT,
                                 build_guided_cues.TRACKLIST_DIR)
    try:
        build_guided_cues.REPO = repo_root
        build_guided_cues.OUT = out_path
        build_guided_cues.TRACKLIST_DIR = os.path.join(
            repo_root, "engine", "tracklists")
        cues_map = build_guided_cues.build_week(week_n)
        try:
            with open(out_path) as f:
                existing = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            existing = {}
        existing[str(week_n)] = cues_map
        with open(out_path, "w") as f:
            json.dump(existing, f, indent=1, ensure_ascii=False)
    finally:
        (build_guided_cues.REPO, build_guided_cues.OUT,
         build_guided_cues.TRACKLIST_DIR) = old_repo, old_out, old_tl

    with open(out_path) as f:
        week_cues = json.load(f)[str(week_n)]
    pending = [k for k, c in week_cues.items()
               if c.get("timed") and c["timed"].get("cue_text_pending")]
    if pending:
        raise RuntimeError(
            f"cue rebuild left cue_text_pending on: {pending}")

    return {"week": week_n, "finalized": True, "changed": True,
            "week_file": week_path, "guided_cues": len(week_cues),
            "cue_text_pending": 0}


def main():
    if "--week" not in sys.argv or "--cues" not in sys.argv:
        print("usage: finalize_week_cues.py --week N --cues cues.json",
              file=sys.stderr)
        return 2
    week_n = int(sys.argv[sys.argv.index("--week") + 1])
    cues = load_cues(sys.argv[sys.argv.index("--cues") + 1])
    try:
        summary = finalize(REPO, week_n, cues)
    except (ValueError, RuntimeError) as e:
        print(f"finalize_week_cues: {e}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
