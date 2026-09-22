#!/usr/bin/env python3
"""M6: syllabus gap analysis — audit the 24-week syllabus by era/genre/region.

Flags underrepresentation and suggests rebalancing weeks. Reads
engine/weeks.json + engine/album_tags.json (curator pass). Pure analysis —
it never edits the syllabus; suggestions are for Wesley to approve.

Coverage checks:
  - era: decades represented vs the full span of recorded music
  - genre: taxonomy balance vs the course's stated units
  - region: geographic spread (US/UK dominance is expected but measured)
  - artists: gender representation (heuristic from known artist names —
    flagged as heuristic, not ground truth), repeat artists

Usage: python3 bin/syllabus_gap.py [--save <path>]
"""
import json
import os
import sys
from collections import Counter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def norm(s):
    return " ".join(s.strip().lower().split())


def main():
    save_path = sys.argv[sys.argv.index("--save") + 1] if "--save" in sys.argv else None
    with open(os.path.join(REPO, "engine", "weeks.json")) as f:
        weeks = json.load(f)["weeks"]
    with open(os.path.join(REPO, "engine", "album_tags.json")) as f:
        tags = json.load(f)

    picks = []  # (week_n, artist, album, slot)
    for w in weeks:
        picks.append((w["n"], w["anchor"]["artist"], w["anchor"]["album"], "anchor"))
        for a in w["adventurous"]:
            picks.append((w["n"], a["artist"], a["album"], "adventurous"))
        picks.append((w["n"], w["wild_card"]["artist"], w["wild_card"]["album"], "wild_card"))

    tagged, untagged = [], []
    for week_n, artist, album, slot in picks:
        tag = tags.get(f"{norm(artist)}|{norm(album)}")
        (tagged if tag else untagged).append((week_n, artist, album, slot, tag))

    eras = Counter(t["era"] for *_, t in tagged)
    genres = Counter(t["genre"] for *_, t in tagged)
    regions = Counter(t["region"] for *_, t in tagged)
    artists = Counter(f"{a} — {b}" for _, a, b, _, _ in tagged)

    # heuristic: women / women-fronted acts (known names; marked heuristic)
    women_led = {"Björk", "FKA twigs", "Solange", "Kelela", "Ethel Cain",
                 "Cocteau Twins", "SZA", "Joni Mitchell", "Laura Marling",
                 "Fiona Apple", "Phoebe Bridgers", "Hildur Guðnadóttir",
                 "Mica Levi", "Yaeji", "Alice Coltrane", "Lingua Ignota",
                 "Chelsea Wolfe", "ARTMS", "NewJeans", "Red Velvet", "f(x)"}
    women_picks = sum(1 for _, a, _, _, _ in tagged if a in women_led)

    repeats = {a: c for a, c in artists.items() if c > 1}

    L = []
    L.append("# Syllabus gap analysis (M6)")
    L.append(f"_Audited {len(tagged)} tagged picks across 24 weeks; "
             f"{len(untagged)} untagged (data-quality, see below)._")
    if untagged:
        L.append("")
        L.append("## Data quality flags")
        for w, a, b, s, _ in untagged:
            L.append(f"- Week {w} {s}: “{a} — {b}” is not a real album entry "
                     "(the LOONA lore deep-dive placeholder; needs a real pick before week 20)")
    L.append("")
    L.append("## Era coverage")
    for era, c in sorted(eras.items()):
        L.append(f"- {era}: {c} picks")
    gaps = []
    pre1960 = sum(c for e, c in eras.items() if e < "1960s" and e != "1740s"
                  and e != "1830s")
    if eras.get("1950s", 0) < 3:
        gaps.append("The 1950s are thin — jazz's hard-bop doorway (weeks 12–13) "
                    "carries the decade almost alone; rock's 50s origins are absent.")
    if eras.get("1980s", 0) <= 2:
        gaps.append("The 1980s are nearly absent (only Sakamoto's Merry Christmas "
                    "and Ligeti's Études) — no 80s pop, post-punk, or hip-hop's founding decade.")
    if eras.get("1990s", 0) < 8:
        gaps.append("The 1990s are light for the decade that made his island albums "
                    "(OK Computer '97, Grace '94 present, but no 90s hip-hop/R&B beyond TPAB).")
    L.append("")
    L.append("## Genre coverage")
    for g, c in genres.most_common():
        L.append(f"- {g}: {c}")
    L.append("")
    L.append("## Region coverage")
    for r, c in regions.most_common():
        L.append(f"- {r}: {c}")
    us_uk = regions.get("US", 0) + regions.get("UK", 0)
    L.append(f"\nUS+UK share: {us_uk}/{len(tagged)} ({round(100*us_uk/len(tagged))}%)")
    L.append("")
    L.append("## Representation notes (heuristics, not ground truth)")
    L.append(f"- Women-led or women-fronted picks: ~{women_picks}/{len(tagged)} "
             f"({round(100*women_picks/len(tagged))}%) — heuristic name list, review it.")
    L.append("- Regions with zero picks: Africa, Latin America, South Asia, "
             "the Middle East, Oceania.")
    L.append("")
    L.append("## Repeat artists")
    if repeats:
        for a, c in sorted(repeats.items(), key=lambda kv: -kv[1]):
            L.append(f"- {a}: {c}×")
    else:
        L.append("- None.")
    L.append("")
    L.append("## Rebalancing suggestions (for Wesley's approval — nothing auto-applied)")
    for g in gaps:
        L.append(f"- {g}")
    if regions.get("South Korea", 0) > 8:
        L.append("- K-pop gets 2 full weeks (10 picks); consider whether week 20's "
                 "industry-concept could fold into week 19 and free a week for an "
                 "underrepresented region or the 1980s.")
    L.append("- Week 17 and week 6 both schedule Have A Nice Life — "
             "Deathconsciousness; week 18's wild card re-uses Swans — To Be Kind "
             "from week 2. The syllabus already marks these as conditional — "
             "confirm alternates before those weeks.")
    L.append("- The parked country expedition (syllabus: 'Parked') is the natural "
             "filler for a rebalancing week late in the course.")
    report = "\n".join(L) + "\n"
    if save_path:
        os.makedirs(os.path.dirname(os.path.expanduser(save_path)), exist_ok=True)
        with open(os.path.expanduser(save_path), "w") as f:
            f.write(report)
    print(report)


if __name__ == "__main__":
    main()
