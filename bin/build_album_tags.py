#!/usr/bin/env python3
"""Build engine/album_tags.json: curator tags for every syllabus album.

Each syllabus album gets: genre (course taxonomy), era (decade of release),
region (artist origin). These tags power:
  - M2  implicit/explicit taste vector (genre affinity dimensions)
  - M5  Course Wrapped genre map of taste movement
  - M6  syllabus gap analysis (era/genre/region audit)

This is a curator pass (2026-09-21), not derived data — review on the first
Course Wrapped. Keys match engine/weeks.json ("artist|album", lowercased,
whitespace-normalized).
"""
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "engine", "album_tags.json")

# (artist, album, genre, era, region)
TAGS = [
    # week 1
    ("Pink Floyd", "The Dark Side of the Moon", "prog-rock", "1970s", "UK"),
    ("Pink Floyd", "Animals", "prog-rock", "1970s", "UK"),
    ("The Smile", "A Light for Attracting Attention", "art-rock", "2020s", "UK"),
    ("These New Puritans", "Field of Reeds", "art-rock", "2010s", "UK"),
    ("Four Tet", "Beautiful Rewind", "electronic-melodic", "2010s", "UK"),
    ("Can", "Tago Mago", "krautrock", "1970s", "Germany"),
    # week 2
    ("Radiohead", "OK Computer", "art-rock", "1990s", "UK"),
    ("The Beatles", "Abbey Road", "rock-classic", "1960s", "UK"),
    ("Kendrick Lamar", "To Pimp a Butterfly", "hip-hop", "2010s", "US"),
    ("SZA", "SOS", "confessional-rnb", "2020s", "US"),
    ("Swans", "To Be Kind", "noise-rock", "2010s", "US"),
    # week 3
    ("King Crimson", "In the Court of the Crimson King", "prog-rock", "1960s", "UK"),
    ("Yes", "Close to the Edge", "prog-rock", "1970s", "UK"),
    ("Genesis", "Selling England by the Pound", "prog-rock", "1970s", "UK"),
    ("Van der Graaf Generator", "Pawn Hearts", "prog-rock", "1970s", "UK"),
    # week 4
    ("Radiohead", "Kid A", "art-rock", "2000s", "UK"),
    ("Talk Talk", "Laughing Stock", "art-rock", "1990s", "UK"),
    ("Björk", "Homogenic", "art-rock", "1990s", "Iceland"),
    ("Black Midi", "Hellfire", "math-rock", "2020s", "UK"),
    # week 5
    ("Frank Ocean", "Blonde", "confessional-rnb", "2010s", "US"),
    ("FKA twigs", "MAGDALENE", "alt-rnb", "2010s", "UK"),
    ("Solange", "A Seat at the Table", "alt-rnb", "2010s", "US"),
    ("Kelela", "Take Me Apart", "alt-rnb", "2010s", "US"),
    ("Ethel Cain", "Preacher's Daughter", "southern-gothic", "2020s", "US"),
    # week 6
    ("My Bloody Valentine", "Loveless", "shoegaze", "1990s", "Ireland"),
    ("Cocteau Twins", "Heaven or Las Vegas", "dream-pop", "1990s", "UK"),
    ("Slowdive", "Souvlaki", "shoegaze", "1990s", "UK"),
    ("Ride", "Nowhere", "shoegaze", "1990s", "UK"),
    ("Have A Nice Life", "Deathconsciousness", "doomgaze", "2000s", "US"),
    # week 7
    ("ODESZA", "A Moment Apart", "electronic-melodic", "2010s", "US"),
    ("Jamie xx", "In Colour", "electronic-melodic", "2010s", "UK"),
    ("Disclosure", "Settle", "house", "2010s", "UK"),
    ("Four Tet", "There Is Love in You", "electronic-melodic", "2010s", "UK"),
    ("Burial", "Untrue", "uk-garage", "2000s", "UK"),
    # week 8
    ("Kraftwerk", "Trans-Europe Express", "krautrock", "1970s", "Germany"),
    ("Neu!", "Neu! 2", "krautrock", "1970s", "Germany"),
    ("Can", "Ege Bamyasi", "krautrock", "1970s", "Germany"),
    ("Tangerine Dream", "Phaedra", "krautrock", "1970s", "Germany"),
    ("Suicide", "Suicide", "synth-punk", "1970s", "US"),
    # week 9
    ("Brian Eno", "Ambient 1: Music for Airports", "ambient", "1970s", "UK"),
    ("Aphex Twin", "Selected Ambient Works 85–92", "ambient", "1990s", "UK"),
    ("Tim Hecker", "Ravedeath, 1972", "drone", "2010s", "Canada"),
    ("Stars of the Lid", "And Their Refinement of the Decline", "drone", "2000s", "US"),
    ("Oneohtrix Point Never", "R Plus Seven", "electronic-experimental", "2010s", "US"),
    # week 10
    ("SOPHIE", "Oil of Every Pearl's Un-Insides", "electronic-weird", "2010s", "UK"),
    ("Arca", "Kick I", "electronic-weird", "2020s", "Venezuela"),
    ("Flying Lotus", "Cosmogramma", "electronic-weird", "2010s", "US"),
    ("Iglooghost", "Neo Wax Bloom", "electronic-weird", "2010s", "UK"),
    ("100 gecs", "1000 gecs", "hyperpop", "2010s", "US"),
    # week 11
    ("Weather Report", "Heavy Weather", "jazz-fusion", "1970s", "US"),
    ("Herbie Hancock", "Head Hunters", "jazz-fusion", "1970s", "US"),
    ("Mahavishnu Orchestra", "The Inner Mounting Flame", "jazz-fusion", "1970s", "US"),
    ("Snarky Puppy", "We Like It Here", "jazz-fusion", "2010s", "US"),
    ("Jaco Pastorius", "Jaco Pastorius", "jazz-fusion", "1970s", "US"),
    # week 12
    ("Miles Davis", "Kind of Blue", "jazz-modal", "1950s", "US"),
    ("Miles Davis", "In a Silent Way", "jazz-modal", "1960s", "US"),
    ("John Coltrane", "Blue Train", "jazz-hardbop", "1950s", "US"),
    ("Cannonball Adderley", "Somethin' Else", "jazz-hardbop", "1950s", "US"),
    ("Miles Davis", "Bitches Brew", "jazz-fusion", "1970s", "US"),
    # week 13
    ("John Coltrane", "A Love Supreme", "jazz-spiritual", "1960s", "US"),
    ("Charles Mingus", "Mingus Ah Um", "jazz", "1950s", "US"),
    ("Bill Evans", "Waltz for Debby", "jazz-piano-trio", "1960s", "US"),
    ("Alice Coltrane", "Journey in Satchidananda", "jazz-spiritual", "1970s", "US"),
    ("Kamasi Washington", "The Epic", "jazz-spiritual", "2010s", "US"),
    # week 14
    ("Jeff Buckley", "Grace", "singer-songwriter", "1990s", "US"),
    ("Nick Drake", "Pink Moon", "singer-songwriter", "1970s", "UK"),
    ("Elliott Smith", "Either/Or", "singer-songwriter", "1990s", "US"),
    ("Phoebe Bridgers", "Punisher", "singer-songwriter", "2020s", "US"),
    ("Lingua Ignota", "CALIGULA", "experimental", "2010s", "US"),
    # week 15
    ("The Beach Boys", "Pet Sounds", "harmony-pop", "1960s", "US"),
    ("Fleet Foxes", "Helplessness Blues", "folk-harmony", "2010s", "US"),
    ("Bon Iver", "Bon Iver", "indie-folk", "2010s", "US"),
    ("Dirty Projectors", "Bitte Orca", "art-pop", "2000s", "US"),
    # week 16
    ("Joni Mitchell", "Blue", "piano-songwriter", "1970s", "Canada"),
    ("Sufjan Stevens", "Carrie & Lowell", "indie-folk", "2010s", "US"),
    ("Laura Marling", "Song for Our Daughter", "singer-songwriter", "2020s", "UK"),
    ("Big Thief", "U.F.O.F.", "indie-folk", "2010s", "US"),
    ("Big Thief", "U.F.O.F", "indie-folk", "2010s", "US"),  # weeks.json variant, no trailing period
    ("Fiona Apple", "Fetch the Bolt Cutters", "art-pop", "2020s", "US"),
    # week 17
    ("Deftones", "White Pony", "alt-metal", "2000s", "US"),
    ("Tool", "Lateralus", "alt-metal", "2000s", "US"),
    ("Mastodon", "Crack the Skye", "alt-metal", "2000s", "US"),
    ("Sleep Token", "Take Me Back to Eden", "alt-metal", "2020s", "UK"),
    # week 18
    ("Alcest", "Écailles de Lune", "blackgaze", "2010s", "France"),
    ("Deafheaven", "Sunbather", "blackgaze", "2010s", "US"),
    ("Chelsea Wolfe", "Abyss", "doom", "2010s", "US"),
    ("Boris", "Flood", "drone-metal", "2000s", "Japan"),
    # week 19
    ("Red Velvet", "Perfect Velvet", "kpop", "2010s", "South Korea"),
    ("f(x)", "4 Walls", "kpop", "2010s", "South Korea"),
    ("SHINee", "Odd", "kpop", "2010s", "South Korea"),
    ("ARTMS", "DALL", "kpop", "2020s", "South Korea"),
    ("NewJeans", "Get Up", "kpop", "2020s", "South Korea"),
    # week 20
    ("BTS", "Love Yourself: Tear", "kpop", "2010s", "South Korea"),
    ("Balming Tiger", "January Never Dies", "kpop-alt", "2020s", "South Korea"),
    ("Yaeji", "With a Hammer", "electronic-melodic", "2020s", "South Korea"),
    ("Crush", "From Midnight to Sunrise", "kpop-rnb", "2010s", "South Korea"),
    # week 21
    ("Stravinsky", "The Rite of Spring", "classical-orchestral", "1910s", "Russia"),
    ("Shostakovich", "Symphony No. 5", "classical-orchestral", "1930s", "Russia"),
    ("Mahler", "Symphony No. 5", "classical-orchestral", "1900s", "Austria"),
    ("Ligeti", "Atmosphères / Requiem", "classical-orchestral", "1960s", "Hungary"),
    ("Messiaen", "Quartet for the End of Time", "classical-chamber", "1940s", "France"),
    # week 22
    ("Bach", "Goldberg Variations", "classical-piano", "1740s", "Germany"),
    ("Ligeti", "Études", "classical-piano", "1980s", "Hungary"),
    ("Ravel", "Gaspard de la nuit", "classical-piano", "1900s", "France"),
    ("Chopin", "the Ballades", "classical-piano", "1830s", "Poland"),
    ("Rzewski", "The People United Will Never Be Defeated!", "classical-piano", "1970s", "US"),
    # week 23
    ("Hans Zimmer", "Interstellar", "film-score", "2010s", "Germany"),
    ("Hans Zimmer", "Dune", "film-score", "2020s", "Germany"),
    ("Ludwig Göransson", "Oppenheimer", "film-score", "2020s", "Sweden"),
    ("Hildur Guðnadóttir", "Chernobyl", "film-score", "2010s", "Iceland"),
    ("Mica Levi", "Under the Skin", "film-score", "2010s", "UK"),
    # week 24
    ("Ryuichi Sakamoto", "async", "modern-classical", "2010s", "Japan"),
    ("Max Richter", "Sleep", "modern-classical", "2010s", "Germany"),
    ("Joe Hisaishi", "Spirited Away", "film-score", "2000s", "Japan"),
    ("Sakamoto", "Merry Christmas Mr. Lawrence", "film-score", "1980s", "Japan"),
    ("Oneohtrix Point Never", "Uncut Gems", "film-score", "2010s", "US"),
]


def norm(s):
    return " ".join(s.strip().lower().split())


def main():
    tags = {}
    for artist, album, genre, era, region in TAGS:
        tags[f"{norm(artist)}|{norm(album)}"] = {
            "genre": genre, "era": era, "region": region,
            "artist": artist, "album": album,
        }
    # verify coverage against weeks.json
    with open(os.path.join(REPO, "engine", "weeks.json")) as f:
        weeks = json.load(f)["weeks"]
    missing = []
    for w in weeks:
        picks = [w["anchor"]] + w["adventurous"] + [w["wild_card"]]
        for p in picks:
            key = f"{norm(p['artist'])}|{norm(p['album'])}"
            if key not in tags:
                missing.append((w["n"], p["artist"], p["album"]))
    with open(OUT, "w") as f:
        json.dump(tags, f, indent=1, ensure_ascii=False)
    print(json.dumps({
        "tagged": len(tags),
        "missing": [{"week": n, "artist": a, "album": b} for n, a, b in missing],
        "confidence": "curator-pass-2026-09-21",
        "out": OUT,
    }, indent=1))


if __name__ == "__main__":
    main()
