#!/usr/bin/env python3
"""Regression tests for the #24 listen-for write-back (finalize_week_cues).

Before the fix, the Monday digest composed the five listen-for sentences
in chat but never wrote them into weeks/week-NN.md: the scaffold's
"(set by the digest)" placeholders survived, so drip_pick printed the
placeholder verbatim and build_guided_cues fell back to cue_text_pending
(timed cues aimed at track 1, liner null).

Contract under test:
- finalize() replaces all 5 placeholders with the provided sentences,
  rebuilds the week's guided cues, and every timed cue ends with
  cue_text_pending == False;
- rerunning with the same cues is a no-op (changed: False);
- a file whose cues are already finalized is never overwritten, even
  with different sentences;
- malformed cues.json (wrong count, empty sentence, placeholder text
  inside a sentence) is rejected before the week file is touched.

Run: python3 bin/tests/test_finalize_week_cues.py  (stdlib only)
"""
import json
import os
import shutil
import sys
import tempfile

BIN = os.path.join(os.path.dirname(__file__), "..")
REAL = os.path.join(BIN, "..")
sys.path.insert(0, BIN)
import finalize_week_cues  # noqa: E402
import rollover  # noqa: E402
import drip_pick  # noqa: E402

CUES = [
    "The room each song is in: compare the closet-sized clock shop of the "
    "opener against the hangar the band kicks in — reverb as set design.",
    "How much bigger and emptier the guitars sound than the anchor's — "
    "timbre doing narrative work, not the notes.",
    "The drums: real kick, real room, no samples. Bar-for-bar against any "
    "808 on the Four Tet record — same job, different species.",
    "Reverb as glue: dozens of tiny samples with no business sharing a "
    "track, smeared into one imaginary space so they belong together.",
    "The hi-hat barely changes timbre for the whole album, and that's "
    "the point — hypnosis through refusal to vary.",
]


def make_repo(tmp):
    """Scratch tree with real weeks.json + tracklist cache, week 2."""
    for d in ("weeks", "engine"):
        os.makedirs(os.path.join(tmp, d))
    shutil.copy(os.path.join(REAL, "engine", "weeks.json"),
                os.path.join(tmp, "engine", "weeks.json"))
    shutil.copytree(os.path.join(REAL, "engine", "tracklists"),
                    os.path.join(tmp, "engine", "tracklists"))
    with open(os.path.join(tmp, "engine", "guided_cues.json"), "w") as f:
        f.write("{}")
    old_repo, old_json = rollover.REPO, rollover.WEEKS_JSON
    try:
        rollover.REPO = tmp
        rollover.WEEKS_JSON = os.path.join(tmp, "engine", "weeks.json")
        plan = rollover.week_plan(2)
        rollover.scaffold_week_file(2, plan)
    finally:
        rollover.REPO, rollover.WEEKS_JSON = old_repo, old_json
    return os.path.join(tmp, "weeks", "week-02.md")


def read_week(path):
    with open(path) as f:
        return f.read()


def test_happy_path():
    tmp = tempfile.mkdtemp()
    try:
        path = make_repo(tmp)
        assert "(set by the digest)" in read_week(path)
        summary = finalize_week_cues.finalize(tmp, 2, CUES)
        assert summary["changed"] is True
        assert summary["cue_text_pending"] == 0
        text = read_week(path)
        assert "(set by the digest)" not in text
        # drip's own parser (line 2 of the drip) sees real text now
        albums = drip_pick.parse_week_file(path)
        assert albums is not None and len(albums) == 5
        for a, cue in zip(albums, CUES):
            assert a["listen_for"] == cue, a
        # guided cues rebuilt with real cue text
        with open(os.path.join(tmp, "engine", "guided_cues.json")) as f:
            week_cues = json.load(f)["2"]
        assert len(week_cues) == 5
        for key, c in week_cues.items():
            timed = c.get("timed")
            if timed:
                assert timed.get("cue_text_pending") is False, key
                assert "(set by the digest)" not in timed["cue"]
    finally:
        shutil.rmtree(tmp)
    print("ok happy_path")


def test_idempotent_noop():
    tmp = tempfile.mkdtemp()
    try:
        make_repo(tmp)
        finalize_week_cues.finalize(tmp, 2, CUES)
        summary = finalize_week_cues.finalize(tmp, 2, CUES)
        assert summary["changed"] is False
        assert summary["finalized"] is True
    finally:
        shutil.rmtree(tmp)
    print("ok idempotent_noop")


def test_refuses_overwrite_finalized():
    tmp = tempfile.mkdtemp()
    try:
        make_repo(tmp)
        finalize_week_cues.finalize(tmp, 2, CUES)
        other = ["different sentence %d" % i for i in range(5)]
        try:
            finalize_week_cues.finalize(tmp, 2, other)
        except RuntimeError as e:
            assert "refusing" in str(e)
        else:
            raise AssertionError("overwrite of finalized cues was allowed")
        # original cues untouched
        albums = drip_pick.parse_week_file(
            os.path.join(tmp, "weeks", "week-02.md"))
        assert [a["listen_for"] for a in albums] == CUES
    finally:
        shutil.rmtree(tmp)
    print("ok refuses_overwrite_finalized")


def test_rejects_bad_cues_file_untouched():
    tmp = tempfile.mkdtemp()
    try:
        path = make_repo(tmp)
        before = read_week(path)
        for bad in (["only", "four", "cues", "here"],
                    ["", "b", "c", "d", "e"],
                    ["x (set by the digest)", "b", "c", "d", "e"]):
            cues_file = os.path.join(tmp, "cues.json")
            with open(cues_file, "w") as f:
                json.dump(bad, f)
            try:
                finalize_week_cues.load_cues(cues_file)
            except ValueError:
                pass
            else:
                raise AssertionError("bad cues accepted: %r" % (bad,))
        assert read_week(path) == before, "week file touched on bad input"
    finally:
        shutil.rmtree(tmp)
    print("ok rejects_bad_cues")


def test_dict_form():
    tmp = tempfile.mkdtemp()
    try:
        make_repo(tmp)
        cues_file = os.path.join(tmp, "cues.json")
        with open(cues_file, "w") as f:
            json.dump({"anchor": CUES[0], "adventurous": CUES[1:4],
                       "wild_card": CUES[4]}, f)
        cues = finalize_week_cues.load_cues(cues_file)
        assert cues == CUES
    finally:
        shutil.rmtree(tmp)
    print("ok dict_form")


if __name__ == "__main__":
    test_happy_path()
    test_idempotent_noop()
    test_refuses_overwrite_finalized()
    test_rejects_bad_cues_file_untouched()
    test_dict_form()
    print("all finalize_week_cues tests passed")
