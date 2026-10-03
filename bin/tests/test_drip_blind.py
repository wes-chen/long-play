#!/usr/bin/env python3
"""Regression tests for blind-week drip redaction (issue #20).

The drip never checked predictions.json's blind flag, so on a blind week it
would print the artist/album/year in chat — the exact thing the blind is
meant to withhold. Contract now: on a blind week drip_pick.py redacts at
the JSON source (the only user-facing surface), so the drip cron body
needs no matching guard.

- blind week: pick JSON carries "blind": true, the A-E file-order label
  (matching the digest's blind labeling) in artist/album, empty year,
  null listen_for, null guided_cue — and no artist/album name appears
  anywhere in the serialized pick.
- blind labels follow FILE order, not drip order (week 8 skips file
  index 2: Tuesday drips file index 0 = "Album A", Friday drips file
  index 4 = "Album E").
- missing predictions file or missing week entry fails closed to
  not-blind.
- non-blind week: names flow through unchanged.

Run: python3 bin/tests/test_drip_blind.py  (stdlib only)
"""
import datetime
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import drip_pick

ARTISTS = ["Alpha Band", "Beta Project", "Gamma Trio", "Delta Sound",
           "Epsilon Club"]
ALBUMS = ["First Light", "Second Wave", "Third Stone", "Fourth Wind",
          "Fifth Dawn"]

WEEK_MD = """# Week {n}

## Anchor — {a0} — *{al0}* (1991)
**Listen for:** the famous cue text.

## Adventurous — {a1} — *{al1}* (1992)
**Listen for:** another famous cue.

## Adventurous — {a2} — *{al2}* (1993)
**Listen for:** a third famous cue.

## Adventurous — {a3} — *{al3}* (1994)
**Listen for:** a fourth famous cue.

## Wild card — {a4} — *{al4}* (1995)
**Listen for:** a fifth famous cue.
"""


def make_repo(tmp, week, blind):
    weeks = os.path.join(tmp, "weeks")
    os.makedirs(weeks)
    with open(os.path.join(weeks, "week-%02d.md" % week), "w") as f:
        f.write(WEEK_MD.format(n=week, a0=ARTISTS[0], al0=ALBUMS[0],
                               a1=ARTISTS[1], al1=ALBUMS[1],
                               a2=ARTISTS[2], al2=ALBUMS[2],
                               a3=ARTISTS[3], al3=ALBUMS[3],
                               a4=ARTISTS[4], al4=ALBUMS[4]))
    delivered = os.path.join(tmp, "digest-delivered.json")
    with open(delivered, "w") as f:
        json.dump([week], f)
    sent = os.path.join(tmp, "drip-sent.json")
    with open(sent, "w") as f:
        json.dump({}, f)
    predictions = os.path.join(tmp, "predictions.json")
    with open(predictions, "w") as f:
        json.dump({"weeks": {str(week): {"blind": blind,
                                         "predictions": []}}}, f)
    return delivered, sent, predictions


def run_pick(week, blind, day):
    """Run main() against a scratch repo; return the parsed pick JSON."""
    tmp = tempfile.mkdtemp()
    delivered, sent, predictions = make_repo(tmp, week, blind)
    drip_pick.REPO = tmp
    drip_pick.DELIVERED = delivered
    drip_pick.DRIP_SENT = sent
    drip_pick.PREDICTIONS = predictions
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        assert drip_pick.main(today=day) == 0
    finally:
        sys.stdout = old
    return json.loads(buf.getvalue()), sent


TUE = datetime.date(2026, 10, 6)   # Tuesday
FRI = datetime.date(2026, 10, 9)  # Friday


def test_blind_week_redacts_names():
    pick, _ = run_pick(week=8, blind=True, day=TUE)
    assert pick["blind"] is True, pick
    blob = json.dumps(pick)
    for name in ARTISTS + ALBUMS:
        assert name not in blob, (name, blob)
    assert pick["listen_for"] is None, pick
    assert pick["guided_cue"] is None, pick
    assert pick["year"] == "", pick


def test_blind_labels_follow_file_order():
    # week 8 skips file index (8-1)%5 = 2; Tuesday -> file index 0
    pick, _ = run_pick(week=8, blind=True, day=TUE)
    assert pick["artist"] == "Album A", pick
    assert pick["album"] == "Album A", pick
    # Friday -> file index 4
    pick, _ = run_pick(week=8, blind=True, day=FRI)
    assert pick["artist"] == "Album E", pick
    assert pick["album"] == "Album E", pick


def test_missing_predictions_fails_closed():
    tmp = tempfile.mkdtemp()
    delivered, sent, _ = make_repo(tmp, 8, True)
    drip_pick.REPO = tmp
    drip_pick.DELIVERED = delivered
    drip_pick.DRIP_SENT = sent
    drip_pick.PREDICTIONS = os.path.join(tmp, "no-such-file.json")
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        assert drip_pick.main(today=TUE) == 0
    finally:
        sys.stdout = old
    pick = json.loads(buf.getvalue())
    assert pick["blind"] is False, pick
    assert pick["artist"] == "Alpha Band", pick


def test_non_blind_week_passes_names_through():
    pick, _ = run_pick(week=2, blind=False, day=TUE)
    assert pick["blind"] is False, pick
    assert pick["artist"] == "Alpha Band", pick
    assert pick["album"] == "First Light", pick
    assert pick["year"] == "1991", pick
    assert "famous cue text" in (pick["listen_for"] or ""), pick


def test_blind_mark_sent_stores_label():
    tmp = tempfile.mkdtemp()
    delivered, sent, predictions = make_repo(tmp, 8, True)
    drip_pick.REPO = tmp
    drip_pick.DELIVERED = delivered
    drip_pick.DRIP_SENT = sent
    drip_pick.PREDICTIONS = predictions
    old_argv = sys.argv
    sys.argv = ["drip_pick.py", "--mark-sent"]
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        assert drip_pick.main(today=TUE) == 0
    finally:
        sys.stdout = old
        sys.argv = old_argv
    marked = json.loads(buf.getvalue())
    assert marked["album"] == "Album A", marked
    stored = json.load(open(sent))
    for name in ARTISTS + ALBUMS:
        assert name not in json.dumps(stored), stored


if __name__ == "__main__":
    tests = (test_blind_week_redacts_names,
             test_blind_labels_follow_file_order,
             test_missing_predictions_fails_closed,
             test_non_blind_week_passes_names_through,
             test_blind_mark_sent_stores_label)
    for t in tests:
        t()
        print("ok", t.__name__)
    print(f"blind drip regression tests: {len(tests)}/{len(tests)} passed")
