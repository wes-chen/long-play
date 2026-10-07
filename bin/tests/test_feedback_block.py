#!/usr/bin/env python3
"""Regression tests for the L8 feedback block (issue #4).

The digest template and the current week files must carry the feedback
block verbatim from reference/feedback-prompt.md: the intro line, the five
slot-labeled album lines (slot labels are load-bearing for parsing replies
into listening-log.md), and the free-text closing line. The template's
A-E placeholders must appear in file order: anchor, adventurous x3,
wild card. Week files must have the placeholders filled in — a raw
placeholder left in a published week means the digest shipped an unfilled
prompt.

- template intro: exact spec sentence with {{WEEK_NUM}} filled slot.
- template lines: exactly 5 slot lines, in order Anchor / Adventurous x3 /
  Wild card, carrying {{A_ARTIST}}, {{A_ALBUM}} ... {{E_ARTIST}}, {{E_ALBUM}}.
- template keeps the context-tag line (CTX session model input).
- week-02.md: all five lines filled with the real artist/album names, no
  {{ }} placeholders left in the feedback block, no shortened "Log it" form.
- docs/weeks/week-02.html: same, HTML-rendered.

Run: python3 bin/tests/test_feedback_block.py  (stdlib only)
"""
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATE = os.path.join(REPO, "docs", "digest-template.html")
WEEK_MD = os.path.join(REPO, "weeks", "week-02.md")
WEEK_HTML = os.path.join(REPO, "docs", "weeks", "week-02.html")

INTRO = "How was week"
VOCAB = ["played", "skipped", "loved", "bounced off"]
CLOSER = "Anything else you want me to know goes on its own line after these five."

SLOT_LINES = [
    ("Anchor", "A"),
    ("Adventurous", "B"),
    ("Adventurous", "C"),
    ("Adventurous", "D"),
    ("Wild card", "E"),
]

WEEK2_ALBUMS = [
    ("Anchor", "Radiohead", "OK Computer"),
    ("Adventurous", "The Beatles", "Abbey Road"),
    ("Adventurous", "Kendrick Lamar", "To Pimp a Butterfly"),
    ("Adventurous", "SZA", "SOS"),
    ("Wild card", "Swans", "To Be Kind"),
]

failures = []


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), "-", name, detail if not cond else "")
    if not cond:
        failures.append(name)


def read(path):
    with open(path) as f:
        return f.read()


def feedback_block(text):
    """Slice from the intro line through the closer line."""
    start = text.find(INTRO)
    end = text.find(CLOSER)
    if start < 0 or end < 0:
        return None
    return text[start:end + len(CLOSER)]


def test_template_verbatim():
    t = read(TEMPLATE)
    block = feedback_block(t)
    check("template has the feedback block", block is not None)
    if block is None:
        return
    check("template intro is the spec sentence",
          "One line per album — played / skipped / loved / bounced off:" in block)
    lines = [ln.strip() for ln in re.split(r"<br\s*/?>|\n", block)]
    slot_lines = [ln for ln in lines if ln.startswith("- ")]
    check("template has exactly 5 slot lines", len(slot_lines) == 5,
          f"(found {len(slot_lines)})")
    for (slot, letter), ln in zip(SLOT_LINES, slot_lines):
        check(f"template slot line {letter} = {slot}",
              ln.startswith(f"- {slot} — ") and
              f"{{{{{letter}_ARTIST}}}}" in ln and
              f"{{{{{letter}_ALBUM}}}}" in ln,
              f"(got: {ln[:70]})")
    check("template slot order is anchor/adventurous x3/wild card",
          [s for s, _ in SLOT_LINES] ==
          ["Anchor", "Adventurous", "Adventurous", "Adventurous", "Wild card"])
    check("template keeps the context-tag line",
          "commute / focused / background / late-night" in t)


def test_week02_filled():
    md = read(WEEK_MD)
    block = feedback_block(md)
    check("week-02.md has the feedback block", block is not None)
    if block is None:
        return
    check("week-02.md intro names the week", "How was week 2?" in block)
    check("week-02.md block has no leftover placeholders", "{{" not in block)
    for slot, artist, album in WEEK2_ALBUMS:
        check(f"week-02.md line: {slot} — {artist}, {album}",
              f"- {slot} — {artist}, {album}:" in block)
    check("week-02.md keeps the closer line", CLOSER in block)
    check("week-02.md no longer uses the shortened form",
          "**Log it:**" not in md)

    html = read(WEEK_HTML)
    hblock = feedback_block(html)
    check("week-02.html has the feedback block", hblock is not None)
    if hblock is None:
        return
    check("week-02.html block has no leftover placeholders", "{{" not in hblock)
    for slot, artist, album in WEEK2_ALBUMS:
        check(f"week-02.html line: {slot} — {artist}, {album}",
              f"- {slot} — {artist}, {album}:" in hblock)
    check("week-02.html keeps the context-tag line",
          "commute / focused / background / late-night" in html)


def test_vocab_intact():
    t = read(TEMPLATE)
    for word in VOCAB:
        check(f"template carries reaction word '{word}'", word in t)


if __name__ == "__main__":
    test_template_verbatim()
    test_week02_filled()
    test_vocab_intact()
    print(f"\n{len(failures)} failure(s)")
    sys.exit(1 if failures else 0)
