#!/usr/bin/env python3
"""Regression tests: rollup.py must never clobber the canonical weekly file.

`python3 sampler/rollup.py 1` is the contract's health check. It used to
write its 1-day trailing aggregate straight over rollups/YYYY-Www.json --
the weekly aggregate the engine and capacity model read. Three weekly files
(2026-W39..W41) were found holding 1-day windows because of this.

Rule under test:
- a 7-day run writes the canonical `YYYY-Www.json`;
- any other window writes a sidecar `YYYY-Www.{N}d.json` and leaves the
  canonical file untouched;
- bin/course_wrapped.rollup_implicit() counts canonical files only.

Run: python3 bin/tests/test_rollup_window.py  (stdlib only)
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sampler"))

import rollup
import course_wrapped


def _sample(ts):
    # synthetic row: no real listening data in this repo's tests
    return {
        "ts": ts,
        "playing": True,
        "track_uri": "spotify:track:test000000000000000000001",
        "track": "Test Tone",
        "artists": ["Test Artist"],
        "progress_pct": 50.0,
        "item_type": "track",
    }


def _stage():
    tmp = tempfile.mkdtemp(prefix="rollup-window-")
    now = datetime.now(timezone.utc).isoformat()
    with open(os.path.join(tmp, "samples.jsonl"), "w") as f:
        f.write(json.dumps(_sample(now)) + "\n")
    with open(os.path.join(tmp, "watchlist.json"), "w") as f:
        json.dump({}, f)
    os.makedirs(os.path.join(tmp, "rollups"))
    return tmp


def _run(days, tmp):
    rollup.LOG_FILE = os.path.join(tmp, "samples.jsonl")
    rollup.WATCHLIST = os.path.join(tmp, "watchlist.json")
    rollup.ROLLUP_DIR = os.path.join(tmp, "rollups")
    rollup.CTX_JSON = os.path.join(tmp, "no-ctx.json")  # missing -> no session fit
    old = sys.argv
    sys.argv = ["rollup.py", str(days)]
    try:
        rollup.main()
    finally:
        sys.argv = old
    return sorted(os.listdir(rollup.ROLLUP_DIR))


def check_short_window_writes_sidecar():
    tmp = _stage()
    files = _run(1, tmp)
    assert any(f.endswith(".1d.json") for f in files), files
    canonical = [f for f in files
                 if f.endswith(".json") and not f.endswith("d.json")]
    assert not canonical, files
    print("ok - check_short_window_writes_sidecar")


def check_weekly_window_writes_canonical():
    tmp = _stage()
    files = _run(7, tmp)
    canonical = [f for f in files
                 if f.endswith(".json") and not f.endswith("d.json")]
    assert len(canonical) == 1, files
    print("ok - check_weekly_window_writes_canonical")


def check_short_window_does_not_clobber_canonical():
    tmp = _stage()
    _run(7, tmp)
    canonical = [f for f in os.listdir(os.path.join(tmp, "rollups"))
                 if f.endswith(".json") and not f.endswith("d.json")]
    assert len(canonical) == 1
    before = open(os.path.join(tmp, "rollups", canonical[0])).read()
    _run(1, tmp)
    after = open(os.path.join(tmp, "rollups", canonical[0])).read()
    assert before == after, "short-window run modified the canonical file"
    print("ok - check_short_window_does_not_clobber_canonical")


def check_wrapped_counts_canonical_only():
    tmp = _stage()
    course_wrapped.ROLLUPS_DIR = os.path.join(tmp, "rollups")
    files = _run(7, tmp)
    n_windows, completions = course_wrapped.rollup_implicit()
    assert n_windows == 1, (n_windows, files)
    _run(1, tmp)  # sidecar lands in the same dir
    n_windows, completions = course_wrapped.rollup_implicit()
    assert n_windows == 1, (n_windows, sorted(os.listdir(course_wrapped.ROLLUPS_DIR)))
    print("ok - check_wrapped_counts_canonical_only")


def main():
    for check in (check_short_window_writes_sidecar,
                  check_weekly_window_writes_canonical,
                  check_short_window_does_not_clobber_canonical,
                  check_wrapped_counts_canonical_only):
        check()
    return 0


if __name__ == "__main__":
    sys.exit(main())
