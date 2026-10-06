#!/usr/bin/env python3
"""Rewrite Week 2 track-note cues using the human-prose models from the
2026-10-06 deep research (Christgau compression, Ross cause->effect,
Padgham mishearing-correction, Tate function, Perry physical chain,
Wright one-element-at-a-time). Kills the '**X as Y:** ...the pocket verbs'
template. Keeps titles, times, HTML structure identical; only cue text changes.
"""
import re, sys

NEW_CUES = [
# 0: Radiohead - OK Computer (12)
[
"<b>Texture:</b> the drums sound sliced — hits start and stop too cleanly, like tape cut with a razor. The bass lumbers a half-step behind them. Nobody is \"in the pocket\"; the pocket was assembled, and the unease is the point.",
"<b>Form:</b> four songs stitched end to end — acoustic lament, sludge-metal detour, choral lullaby. The groove never carries across the seams; each section resets the pulse, so the whiplash is the structure.",
"<b>Panning:</b> guitars hover at the far edges, left and right, while the voice sits dead center and dry. The stereo image is a room you float inside — wide at the walls, empty in the middle.",
"<b>Dynamics:</b> a minute of near-silence — voice and a few guitar notes — then bass and drums detonate at once. The band refuses to rush the build; they sit behind the pulse until the song shoves them forward.",
"<b>Texture:</b> two guitars arpeggiate the same figure, panned hard left and right, slightly out of sync with each other. The drums underneath are deliberately plain — all the motion is in the overlap at the edges.",
"<b>Meter:</b> straight 4/4, piano chords on the beat, the most conventional groove on the record. After five tracks of unease it feels almost suspiciously normal — the simplicity is doing the emotional work.",
"<b>Timbre:</b> a flat synthetic voice reads a checklist over a twitching loop. Nothing breathes; the \"groove\" is a machine grid, perfectly on time, and the rigidity is both the joke and the threat.",
"<b>Rhythm:</b> the one track that plays it fast and straight — guitars up front, drums driving instead of floating. The pocket leans forward here; everything else on the record leans back.",
"<b>Dynamics:</b> the beat barely moves for four minutes while strings, noise, and drums pile on under a whisper. The groove holds its breath — the pressure comes from everything stacking, not from speeding up.",
"<b>Timbre:</b> glockenspiel and clean guitar, close and narrow in the stereo image — everything huddles near the center. The prettiest, smallest sound on the record carrying the bleakest lyric.",
"<b>Form:</b> one long crescendo — verse, lift, fall back, lift higher. The rhythm section keeps agreeing to push a little harder without ever breaking tempo; the wave shape is the whole song.",
"<b>Dynamics:</b> the drums finally shuffle instead of drive. After eleven tracks of tension the beat goes slack on purpose — slower, looser, the record letting go.",
],
# 1: Beatles - Abbey Road (17)
[
"<b>Rhythm:</b> Ringo's drums land a fraction behind every beat — lazy, but never late enough to drag. That gap between the pulse and the hit is the week's concept in one bar: groove as agreed lateness.",
"<b>Panning:</b> headphones on — drums hard to one side, bass to the other, the 1969 stereo mix. The wide split lets you hear each player's lateness separately; the groove is unhurried and you can audit it per ear.",
"<b>Rhythm:</b> a bouncy, square music-hall pocket that refuses to swing. The joke works because the band plays it dead straight — the groove is the straight man and the lyric is the comic.",
"<b>Timbre:</b> Lennon's vocal is shredded at the top of its range, straining against a backbeat that won't move. The pocket stays put; the voice fights it, and the friction is the song.",
"<b>Texture:</b> bubbling guitar effects drift across the stereo field, everything soft-edged and wet. The groove paddles instead of driving — Ringo's song gets Ringo's pocket: genial, behind the beat, unbothered.",
"<b>Meter:</b> the verses slip between time signatures without telling you. Don't count it — feel how the groove keeps refreshing itself instead of settling; the brightness is the pattern refusing to sit still.",
"<b>Dynamics:</b> one riff repeated until it turns physical, then organ and white noise bury it. Everyone leans forward together — and the track doesn't end, it gets switched off mid-grind, which is a different kind of finality.",
"<b>Panning:</b> nine voices, triple-tracked, spread left to right like furniture. No drums, no groove at all — proof the stereo image alone can carry a track when the placement is this deliberate.",
"<b>Form:</b> three grooves in one song — piano ballad, honky-tonk lope, guitar rocker. A miniature of the whole side-two method: change the pocket and the same song becomes a different room.",
"<b>Texture:</b> guitars and voices soaked in reverb, wide and soft. The beat barely exists — the track floats, and the stereo wash does the work the rhythm section isn't.",
"<b>Rhythm:</b> short, fast, slightly rushed — the pocket hurries. At barely a minute it's a corridor, not a room: the groove changes just to keep the medley walking.",
"<b>Dynamics:</b> loud, fast, over in a flash. The band attacks it like a live take — forward, aggressive, a sprint wedged between two strolls.",
"<b>Rhythm:</b> the tempo settles and the groove loosens after two sprints. Same band, same session — but sitting back instead of pushing makes them sound like a different group.",
"<b>Dynamics:</b> piano and voice alone, then the full band lifts it. The drums don't enter until late — and their entrance is the emotional event of the track, not the lyric.",
"<b>Texture:</b> everyone singing at once, brass filling the stereo image wall to wall. The groove turns into a march — steady, communal, the pocket as shared labor.",
"<b>Panning:</b> the drum solo, then three guitar solos trading lines left, right, center. The week's technique made literal — stereo placement as conversation between players.",
"<b>Form:</b> one guitar, one voice, dead center. After the wall of sound the stereo image collapses to a single point — the designed object ends with a doodle.",
],
# 2: Kendrick Lamar - To Pimp a Butterfly (16)
[
"<b>Texture:</b> a live funk band and a rap vocal in the same room, bleeding into each other's mics. The drums push and pull against the bass instead of locking to a grid — the raggedness is the humanity the album is selling.",
"<b>Rhythm:</b> Kendrick raps over free-jazz piano with no fixed pulse. The \"groove\" is speech rhythm — the pocket lands wherever his breath lands, and the band chases him.",
"<b>Rhythm:</b> the bassline sits so far back it feels like it's dragging the song behind it. Pure Parliament lean — everyone agrees to arrive late, and the lateness is the funk.",
"<b>Dynamics:</b> the beat stays cool and mid-tempo while the vocal gets more frantic. The pocket refuses to match the panic — the groove holds steady so the words sound more desperate by contrast.",
"<b>Panning:</b> backing vocals stacked wide while Kendrick stays close and centered. The stereo image is a room full of voices around one confession — the placement is doing narrative work.",
"<b>Timbre:</b> the voice cracks, doubles, slurs — recorded to sound like it's coming apart in real time. The pocket stumbles with it; when the narrator breaks down, the groove is allowed to break too.",
"<b>Rhythm:</b> the hook marches, the verses float. The pocket does two jobs — anthem when the crowd needs one, loose talk when Kendrick needs to think out loud.",
"<b>Texture:</b> glassy synths, the vocal multi-tracked and slippery. The groove is deliberately easy to fall into — the pocket is the temptation, which is the point of the scene.",
"<b>Meter:</b> live drums with room sound, swinging warm and unhurried. After the middle stretch's tension the pocket exhales — the groove relaxes like shoulders dropping.",
"<b>Rhythm:</b> harder drums, faster tongue — the pocket tightens and leans forward. The band plays it like they have somewhere to be; the urgency is in the tempo, not the volume.",
"<b>Dynamics:</b> the beat stays gentle and round while the story gets heavier. The pocket is soft on purpose — the groove cradles a parable instead of hammering it.",
"<b>Texture:</b> Rhodes, live bass, harmonies spread across the field. The most relaxed pocket on the record — nobody hurries, and the glow comes from the unhurriedness.",
"<b>Dynamics:</b> boom-bap drums detonate after the softness before them. The pocket goes rigid and militant — the groove stops swaying and starts marching.",
"<b>Rhythm:</b> a loping, confident pocket right after the fury. The groove struts — and the sequencing is the statement: anger, then swagger, in that order.",
"<b>Form:</b> the crowd enters the track — call and response, hands in the air. The pocket stops belonging to the studio and belongs to the room.",
"<b>Form:</b> the beat fades and a staged interview with Tupac takes over. The pocket dissolves into speech — the designed object ends by breaking its own form.",
],
# 3: SZA - SOS (23)
[
"<b>Timbre:</b> a siren-like vocal over a dark, sparse beat. The pocket is coiled — the groove holds back, promising a bigger album than any one song.",
"<b>Rhythm:</b> mid-tempo, uncluttered, almost plain — the pocket deliberately stays out of the melody's way. That's why the hook lives in your head for days: nothing competes with it.",
"<b>Dynamics:</b> the beat simmers while the vocal stacks pile up. The pocket withholds its release — the groove waits until the harmonies force its hand.",
"<b>Rhythm:</b> trap drums sitting low in the mix, loose and unhurried. The beat leans back so the vocal can lean forward — the pocket makes room instead of taking it.",
"<b>Texture:</b> soft synths, rounded edges, vocals layered like cloth. The pocket cushions rather than drives — the groove is upholstery.",
"<b>Panning:</b> the vocal doubled and spread wide until the stereo image blurs. The pocket drifts slightly out of focus — the groove sounds uncertain on purpose, matching the lyric.",
"<b>Timbre:</b> two voices trading verses over a muted beat — SZA's warm stack against Don Toliver's thinner tone. The pocket stays small so the contrast between the voices fills the space.",
"<b>Rhythm:</b> the most effortless pocket on the record — the beat barely seems to try. The groove is so natural it disappears, which is why the song feels inevitable instead of constructed.",
"<b>Rhythm:</b> the vocal rushes and tugs against a beat that won't budge. The pocket holds firm while the voice strains at it — that tension is the song's actual subject.",
"<b>Dynamics:</b> the beat thins as the song goes, instruments dropping out one by one. The groove lets go gradually — the arrangement performs the leaving.",
"<b>Form:</b> ninety seconds, almost a skit. The pocket appears just long enough to make its point and vanishes — the groove as a shrug.",
"<b>Timbre:</b> two vocal textures in one stereo space — SZA's warm stack, Phoebe Bridgers' cool whisper. The pocket is shared carefully; neither voice crowds the other.",
"<b>Timbre:</b> pop-punk guitars crash into an R&B record. The pocket goes rigid and driving — the groove changes genre mid-album, which is the sequencing making its argument out loud.",
"<b>Dynamics:</b> guitar and voice, the beat nearly gone. After F2F's noise the groove exhales — the quiet does the emotional work the drums were doing.",
"<b>Rhythm:</b> the beat bounces, unhurried and sure of itself. The pocket struts — the groove walks the way the title talks.",
"<b>Timbre:</b> close-miked vocal, every breath audible, the beat soft underneath. The pocket handles the song gently — the groove treats it like something that bruises.",
"<b>Panning:</b> backing vocals pushed to the edges, the lead small and centered. The stereo image maps the lyric — closeness in the middle, everything else far away.",
"<b>Rhythm:</b> a slow, heavy pocket — the beat drags its feet. The lateness the week celebrates curdles here into the sound of giving up.",
"<b>Texture:</b> hazy synths, the vocal half-buried in the mix. The pocket obscures as much as it reveals — the murk is the appeal, not an accident.",
"<b>Dynamics:</b> the arrangement blooms in the chorus, voices multiplying. The pocket widens — the groove makes room for two people instead of one.",
"<b>Timbre:</b> the vocal sounds like a phone recording — small, compressed, close. The pocket is minimal; the groove gets out of the way of a message that was never meant to be a song.",
"<b>Form:</b> a guitar loop circling without resolving. The pocket is patient to the point of stillness — the groove meditates instead of arriving.",
"<b>Form:</b> Ol' Dirty Bastard crashes the finale. The pocket fractures — the groove breaks its own rules at the finish line.",
],
# 4: Swans - To Be Kind (10)
[
"<b>Rhythm:</b> one chord hammered for eight minutes over a motorik pulse. The pocket doesn't develop — it deepens, and the repetition becomes the entire content.",
"<b>Dynamics:</b> a slow swell — quiet, loud, quiet, louder. The band moves as one mass; nobody solos, everybody surges, and the pocket is collective or it's nothing.",
"<b>Texture:</b> handclaps, shouts, and a lurching riff piled into a wall. The groove stumbles on purpose — the pocket trips and the trip is the dance.",
"<b>Form:</b> two halves, one argument — the first builds a single riff into a roar, the second releases it. The pocket wins by refusing to stop.",
"<b>Dynamics:</b> after an hour of volume, near-silence — hushed voices, no drums. The pocket vanishes; the groove becomes breath, and the contrast re-tunes your ears for what's next.",
"<b>Rhythm:</b> the riff returns slower and heavier. The pocket drags — the week's celebrated lateness curdles into menace.",
"<b>Timbre:</b> wordless vocals layered over a grinding pulse. The groove repeats until meaning drains out and only physical feeling is left — ritual, not song.",
"<b>Dynamics:</b> the album's loudest stretch — drums and guitars at full force, every player hitting the same point as hard as possible. Violent agreement.",
"<b>Texture:</b> a single idea stretched until it shimmers. The groove barely moves — the pocket is a held breath, and the tension is the content.",
"<b>Form:</b> a slow, hymn-like resolution. After two hours the pocket finally relaxes — the groove forgives, and the title lands as an instruction.",
],
]

def main():
    path = "/home/hatch/workspace/long-play/docs/weeks/week-02.html"
    html = open(path, encoding="utf-8").read()
    albums = html.split('<div class="album">')
    assert len(albums) == 6, f"expected 5 album blocks, got {len(albums)-1}"
    assert len(NEW_CUES) == 5
    out = [albums[0]]
    for i, block in enumerate(albums[1:], start=0):
        cues = NEW_CUES[i]
        # find cue spans in order
        found = re.findall(r'<span class="cue">.*?</span>', block, flags=re.S)
        assert len(found) == len(cues), (
            f"album {i}: found {len(found)} cue spans, have {len(cues)} replacements")
        idx = 0
        def repl(m):
            nonlocal idx
            s = f'<span class="cue">{cues[idx]}</span>'
            idx += 1
            return s
        block = re.sub(r'<span class="cue">.*?</span>', repl, block, flags=re.S)
        out.append(block)
    open(path, "w", encoding="utf-8").write('<div class="album">'.join(out))
    print(f"rewrote {sum(len(c) for c in NEW_CUES)} cues in {path}")

if __name__ == "__main__":
    main()
