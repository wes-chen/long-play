#!/usr/bin/env python3
"""Regression tests for long-play issue #23.

The listening log's old format comment documented a different column layout
than the canonical feedback schema (reference/feedback-schema.md); rows
written to that layout silently matched zero parser rows across the grower /
streak / predictions / wild-card loops. Parsers now warn on stderr when the
Weekly-log section contains table rows that look like reaction records but
match nothing.

Run: python3 bin/tests/test_log_format_drift.py  (stdlib only)
"""
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import grower
import predictions
import streak
import wildcard_calibration

# Rows in the OLD (comment-documented, wrong) column layout:
# | Album | Slot | Concepts taught | Listened | Plays | Reaction | Notes |
WRONG_FORMAT_LOG = """\
# long-play listening log

## Pre-course canon

| Album | Status | Notes |
|---|---|---|
| Pink Floyd — Wish You Were Here (1975) | Known canon | Island #1. |

## Weekly log
<!-- old comment format -->
### Week of 2026-10-05
| Abbey Road | anchor | harmony | 2026-10-05 | 3 | loved | great closer |
| Let It Be | anchor | melody | 2026-10-05 | 2 | played | fine |
"""

RIGHT_FORMAT_LOG = """\
# long-play listening log

## Pre-course canon

| Album | Status | Notes |
|---|---|---|
| Pink Floyd — Wish You Were Here (1975) | Known canon | Island #1. |

## Weekly log
### Week of 2026-10-05
| 01 | Abbey Road | The Beatles | anchor | loved | chat | 1.0 | 2026-10-05 |
| 01 | Let It Be | The Beatles | anchor | bounced off; meandering | chat | 1.0 | 2026-10-05 |
"""

CANON_ONLY_LOG = """\
# long-play listening log

## Pre-course canon

| Album | Status | Notes |
|---|---|---|
| Pink Floyd — Wish You Were Here (1975) | Known canon | Island #1. |

## Weekly log
"""


def _scratch_log(text):
    d = tempfile.mkdtemp(prefix="lp-drift-")
    p = os.path.join(d, "listening-log.md")
    with open(p, "w") as f:
        f.write(text)
    return p


def _capture(fn):
    out, err = io.StringIO(), io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out, err
    try:
        result = fn()
    finally:
        sys.stdout, sys.stderr = old_out, old_err
    return result, out.getvalue(), err.getvalue()


def _run_all_parsers(log_path):
    """Run all four parsers against log_path; return (results, stderr)."""
    grower.LOG = log_path
    grower.STATE = os.path.join(os.path.dirname(log_path), "grower-state.json")
    streak.LOG = log_path
    predictions.LOG = log_path
    wildcard_calibration.LOG = log_path
    wildcard_calibration.OUT = os.path.join(os.path.dirname(log_path),
                                            "wildcard-calibration.json")

    def run():
        g = json.loads(_json_stdout(grower.scan))
        s = streak.week_reactions()
        p = predictions.log_reactions(1)
        _json_stdout(wildcard_calibration.main)
        with open(wildcard_calibration.OUT) as f:
            w = json.load(f)
        return g, s, p, w

    (g, s, p, w), _, err = _capture(run)
    return (g, s, p, w), err


def _json_stdout(fn):
    out, err = io.StringIO(), io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out, err
    try:
        fn()
    finally:
        sys.stdout, sys.stderr = old_out, old_err
    return out.getvalue()


def check_wrong_format_warns():
    """Old-format reaction rows: empty results AND a drift warning."""
    (g, s, p, w), err = _run_all_parsers(_scratch_log(WRONG_FORMAT_LOG))
    assert g["added"] == 0 and g["queue_size"] == 0, g
    assert s == {}, s
    assert p == {}, p
    assert w["weeks_with_data"] == 0, w
    assert "WARNING" in err and "format drift" in err, repr(err)
    print("PASS wrong-format log: empty results + drift warning on stderr")


def check_right_format_no_warning():
    """Canonical rows: parsed normally, no warning."""
    (g, s, p, w), err = _run_all_parsers(_scratch_log(RIGHT_FORMAT_LOG))
    assert g["added"] == 1, g            # one bounced-off row re-queued
    assert s[1], s                        # streak sees week 1
    assert p == {("the beatles", "abbey road"): "loved",
                 ("the beatles", "let it be"): "bounced off"}, p
    assert w["weeks_with_data"] == 1, w
    assert "WARNING" not in err, repr(err)
    print("PASS right-format log: rows parsed, no warning")


def check_canon_only_silent():
    """No feedback rows yet: canon table must not trip the warning."""
    (g, s, p, w), err = _run_all_parsers(_scratch_log(CANON_ONLY_LOG))
    assert s == {} and p == {}, (s, p)
    assert "WARNING" not in err, repr(err)
    print("PASS canon-only log: no warning")


def main():
    check_wrong_format_warns()
    check_right_format_no_warning()
    check_canon_only_silent()
    print("3/3 drift tests passed")


if __name__ == "__main__":
    main()
