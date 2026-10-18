"""Explore: generate new melodic ideas and check each against the index.

Every idea is built in *scale degrees* (so it stays in the user's key), then turned
back into MIDI notes. Each candidate is run through the same search engine used for
Identify; ideas that sound too much like something in the index are dropped. What's
left gets a novelty score: how far it is from its nearest neighbour **in our index**
(not a claim of originality).

Generators
- continuation: a Markov chain over scale-degree steps, trained on the index,
  continues the user's phrase and resolves home
- inversion:    the user's phrase upside-down (mirror the contour), in key
- sequence:     the user's opening motif repeated a step higher, then resolved
- rhythm flip:  same pitches, long/short rhythm pattern swapped
- fresh:        a brand-new 2-bar phrase from the Markov chain (no seed needed)
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from .melody import MAJOR_SCALE, MINOR_SCALE, Melody, Note, estimate_key, key_name
from .compose import BAR
from .search import MelodyIndex
from .vibes import VIBE_ORDER, VIBES, Chord, best_of, chord_symbol, voice_chord

DEGREE_RANGE = (-7, 14)          # keep generated lines within ~3 octaves of scale steps
NOVEL = 0.50                     # novelty >= this: "not found in index"
FAMILIAR = 0.30                  # below this: too close; dropped
RHYTHM_CHOICES = [0.5, 1.0, 1.0, 1.0, 1.5, 2.0]


@dataclass
class Idea:
    kind: str
    title: str
    description: str
    notes: list[Note]                      # beats
    novelty: float = 0.0
    nearest: dict | None = None
    chords: list[dict] = field(default_factory=list)
    musicality: float = 0.0
    progression: list | None = None            # vibes.Chord list, if composed
    vibe: str | None = None
    tempo_bpm: float = 100.0
    form: str | None = None
    key: str = ""


# ------------------------------------------------------------------ scale helpers

class Scale:
    def __init__(self, tonic_pc: int, mode: str, tonic_midi: int):
        self.tonic_pc = tonic_pc
        self.mode = mode
        self.steps = MAJOR_SCALE if mode == "major" else MINOR_SCALE
        self.tonic_midi = tonic_midi       # the tonic in the user's octave

    def to_midi(self, degree: int) -> int:
        octave, idx = divmod(degree, 7)
        return self.tonic_midi + 12 * octave + self.steps[idx]

    def to_degree(self, midi: int) -> int:
        """Nearest scale degree (out-of-key notes snap to the closest scale tone)."""
        rel = midi - self.tonic_midi
        octave, pc = divmod(rel, 12)
        best = min(range(7), key=lambda i: (abs(self.steps[i] - pc), i))
        # an out-of-key pitch exactly between two scale tones snaps down; fine for ideas
        if pc - self.steps[best] > 6:
            return 7 * (octave + 1)
        return 7 * octave + best


def _scale_for(pitches, durations) -> Scale:
    tonic, mode, _ = estimate_key(np.asarray(pitches), np.asarray(durations))
    center = int(np.median(pitches))
    # tonic at or just below the middle of the user's range
    tonic_midi = center - ((center - tonic) % 12)
    return Scale(tonic, mode, tonic_midi)


# ------------------------------------------------------------------ seed -> beats

def seed_to_beats(notes: list[Note]) -> tuple[list[Note], float]:
    """Convert a recorded phrase (seconds) to beats on a simple grid.
    The most common inter-onset interval becomes one beat; durations snap to halves.
    Returns (notes_in_beats, seconds_per_beat)."""
    if len(notes) < 2:
        return [Note(n.pitch, 0.0, 1.0) for n in notes], 0.5
    onsets = np.array([n.start for n in notes])
    iois = np.diff(onsets)
    iois = iois[iois > 0.05]
    beat = float(np.median(iois)) if len(iois) else 0.5
    out = []
    t = 0.0
    for i, n in enumerate(notes):
        nxt = notes[i + 1].start if i + 1 < len(notes) else n.start + n.duration
        d = max(0.5, round(((nxt - n.start) / beat) * 2) / 2)
        d = min(d, 4.0)
        out.append(Note(n.pitch, t, d))
        t += d
    return out, beat


# ------------------------------------------------------------------ Markov model

class DegreeMarkov:
    """Order-2 Markov chain over scale-degree *steps*, trained on the index."""

    def __init__(self, melodies: list[Melody]):
        self.table: dict[tuple[int, int], dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self.uni: dict[int, int] = defaultdict(int)
        self.rhythms: dict[float, dict[float, int]] = defaultdict(lambda: defaultdict(int))
        for m in melodies:
            if len(m.notes) < 4:
                continue
            sc = _scale_for(m.pitches, m.durations)
            deg = [sc.to_degree(int(p)) for p in m.pitches]
            steps = [max(-7, min(7, b - a)) for a, b in zip(deg, deg[1:])]
            for a, b, c in zip(steps, steps[1:], steps[2:]):
                self.table[(a, b)][c] += 1
            for s in steps:
                self.uni[s] += 1
            durs = [float(d) for d in m.durations]
            for a, b in zip(durs, durs[1:]):
                self.rhythms[a][b] += 1

    def next_step(self, prev2: tuple[int, int], rng, temperature=1.0, avoid=None) -> int:
        dist = self.table.get(prev2) or self.uni
        keys = np.array(list(dist.keys()))
        w = np.array([dist[k] for k in keys], dtype=float) ** (1.0 / temperature)
        if avoid is not None:
            w[keys == avoid] *= 0.3
        return int(rng.choice(keys, p=w / w.sum()))

    def next_duration(self, prev: float, rng) -> float:
        dist = self.rhythms.get(prev)
        if not dist:
            return float(rng.choice(RHYTHM_CHOICES))
        keys = list(dist.keys())
        w = np.array([dist[k] for k in keys], dtype=float)
        d = float(keys[rng.choice(len(keys), p=w / w.sum())])
        return min(max(d, 0.25), 3.0)


# ------------------------------------------------------------------ generators

def _from_degrees(sc: Scale, degrees, durations, start=0.0) -> list[Note]:
    notes, t = [], start
    for g, d in zip(degrees, durations):
        g = int(np.clip(g, *DEGREE_RANGE))
        notes.append(Note(sc.to_midi(g), t, float(d)))
        t += float(d)
    return notes


def _resolve(degrees: list[int]) -> list[int]:
    """Nudge the last note home (nearest tonic)."""
    if degrees:
        last = degrees[-1]
        degrees[-1] = 7 * round(last / 7)
    return degrees


def gen_continuation(seed_deg, seed_dur, sc, model, rng, length=8):
    deg = list(seed_deg[-2:]) if len(seed_deg) >= 2 else [0, 0]
    steps = (deg[-1] - deg[-2],) if len(deg) >= 2 else (0,)
    prev2 = (0, steps[-1])
    out_deg, out_dur = [], []
    cur = deg[-1]
    prev_d = seed_dur[-1] if seed_dur else 1.0
    for i in range(length):
        s = model.next_step(prev2, rng, temperature=1.3, avoid=0)
        cur = int(np.clip(cur + s, *DEGREE_RANGE))
        out_deg.append(cur)
        prev_d = model.next_duration(prev_d, rng)
        out_dur.append(prev_d)
        prev2 = (prev2[1], s)
    out_deg = _resolve(out_deg)
    out_dur[-1] = max(out_dur[-1], 2.0)
    return out_deg, out_dur


def _seed_motif_rhythm(seed_dur):
    """The seed's first bar of rhythm, if it fits a 4-beat bar exactly."""
    t, out = 0.0, []
    for d in seed_dur:
        if t + d > BAR + 1e-6:
            break
        out.append(float(d))
        t += d
        if abs(t - BAR) < 1e-6:
            return out
    return None


def gen_composed_continuation(seed_deg, seed_dur, sc, rng):
    """An answer phrase: starts near where the user stopped, reuses their rhythm."""
    start = seed_deg[-1] if seed_deg else 0
    start = int(np.clip(start, -3, 10))
    motif = _seed_motif_rhythm(seed_dur)
    return best_phrases(rng, sc.mode, n_candidates=40, keep=6, start_deg=start, motif_rhythm=motif)


def gen_composed_fresh(sc, rng):
    return best_phrases(rng, sc.mode, n_candidates=40, keep=8)


def gen_inversion(seed_deg, seed_dur):
    axis = seed_deg[0]
    return [axis - (g - axis) for g in seed_deg], list(seed_dur)


def gen_sequence(seed_deg, seed_dur, rng):
    k = min(4, len(seed_deg))
    motif, mdur = seed_deg[:k], seed_dur[:k]
    shift = int(rng.choice([1, 2, -1]))
    deg = motif + [g + shift for g in motif] + [g + 2 * shift for g in motif[:2]]
    dur = mdur + mdur + mdur[:2]
    deg.append(7 * round(deg[-1] / 7))
    dur.append(2.0)
    return deg, dur


def gen_rhythm_flip(seed_deg, seed_dur):
    mx, mn = max(seed_dur), min(seed_dur)
    if mx == mn:
        pattern = [1.5, 0.5] * (len(seed_dur) // 2 + 1)
        return list(seed_deg), pattern[:len(seed_deg)]
    return list(seed_deg), [mx + mn - d for d in seed_dur]


def gen_fresh(model, rng, length=8):
    deg = [0]
    dur = [1.0]
    prev2 = (0, int(rng.choice([1, 2, -1, 4])))
    cur = prev2[1]
    deg.append(cur)
    dur.append(1.0)
    for _ in range(length - 2):
        s = model.next_step(prev2, rng, temperature=1.4, avoid=0)
        cur = int(np.clip(cur + s, -4, 11))
        deg.append(cur)
        dur.append(model.next_duration(dur[-1], rng))
        prev2 = (prev2[1], s)
    deg = _resolve(deg)
    dur[-1] = max(dur[-1], 2.0)
    return deg, dur


# ------------------------------------------------------------------ chords

_TRIADS_MAJOR = [("I", 0), ("ii", 1), ("iii", 2), ("IV", 3), ("V", 4), ("vi", 5)]
_TRIADS_MINOR = [("i", 0), ("iv", 3), ("v", 4), ("V", 4), ("VI", 5), ("III", 2), ("VII", 6)]
_PREF = {"I": 0.3, "i": 0.3, "IV": 0.2, "iv": 0.2, "V": 0.25, "v": 0.1, "vi": 0.1, "VI": 0.1}
_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def suggest_chords(notes: list[Note], sc: Scale, bar_beats: float = 2.0) -> list[dict]:
    """One diatonic triad per `bar_beats`, chosen to cover the melody notes in that span."""
    if not notes:
        return []
    end = notes[-1].start + notes[-1].duration
    triads = _TRIADS_MAJOR if sc.mode == "major" else _TRIADS_MINOR
    out = []
    t = 0.0
    while t < end - 1e-6:
        span = [(n, min(n.start + n.duration, t + bar_beats) - max(n.start, t))
                for n in notes if n.start < t + bar_beats and n.start + n.duration > t]
        best, best_score = triads[0], -1.0
        for name, root in triads:
            tones = {(sc.steps[(root + k) % 7] + sc.tonic_pc) % 12 for k in (0, 2, 4)}
            if name == "V" and sc.mode == "minor":     # harmonic-minor dominant
                tones = {(sc.tonic_pc + 7) % 12, (sc.tonic_pc + 11) % 12, (sc.tonic_pc + 2) % 12}
            cover = sum(w for n, w in span if n.pitch % 12 in tones)
            total = sum(w for _, w in span) or 1.0
            score = cover / total + _PREF.get(name, 0.0)
            if out and out[-1]["roman"] == name:
                score -= 0.15                           # prefer some movement
            if score > best_score:
                best, best_score = (name, root), score
        name, root = best
        root_pc = (sc.steps[root] + sc.tonic_pc) % 12
        quality = "" if name[0].isupper() else "m"
        if name in ("V",):
            quality = ""
        out.append({"start": round(t, 3), "duration": bar_beats, "roman": name,
                    "symbol": f"{_NAMES[root_pc]}{quality}"})
        t += bar_beats
    # end on the home chord
    home = "I" if sc.mode == "major" else "i"
    if out and out[-1]["roman"] != home:
        out[-1].update(roman=home, symbol=f"{_NAMES[sc.tonic_pc]}{'' if sc.mode == 'major' else 'm'}")
    return out


# ------------------------------------------------------------------ main entry

class Explorer:
    def __init__(self, index: MelodyIndex):
        self.index = index
        self.model = DegreeMarkov(index.melodies)

    def _novelty(self, notes: list[Note]):
        p = [n.pitch for n in notes]
        hits = self.index.search(p, [n.start for n in notes], [n.duration for n in notes], top_k=1)
        h = hits[0]
        nearest = {"id": h.melody.id, "title": h.melody.title, "composer": h.melody.artist,
                   "similarity": round(h.score, 3)}
        return round(1.0 - h.score, 3), nearest

    def generate(self, seed_notes: list[Note] | None, num_ideas: int = 4,
                 rng_seed: int | None = None, vibe: str | None = None,
                 key_pc: int | None = None) -> dict:
        """vibe: one of VIBES (or None). key_pc: tonic pitch class 0-11 (or None = auto)."""
        rng = np.random.default_rng(rng_seed)
        has_seed = bool(seed_notes) and len(seed_notes) >= 3
        if vibe is not None and vibe not in VIBES:
            raise ValueError(f"unknown vibe '{vibe}'")

        if has_seed:
            seed_beats, beat_sec = seed_to_beats(seed_notes)
            sc = _scale_for([n.pitch for n in seed_beats], [n.duration for n in seed_beats])
            seed_deg = [sc.to_degree(n.pitch) for n in seed_beats]
            seed_dur = [n.duration for n in seed_beats]
            seed_tempo = float(np.clip(round(60.0 / max(beat_sec, 0.2)), 60, 160))
        else:
            sc = Scale(0, "major", 60)
            seed_deg, seed_dur = [], []
            seed_beats, seed_tempo = [], 100.0

        tonic_pc = key_pc if key_pc is not None else (sc.tonic_pc if has_seed else 0)
        if has_seed:
            # keep ideas in the user's register: tonic at or just below their median note
            med = int(np.median([n.pitch for n in seed_beats]))
            orig_tonic_midi = med - ((med - sc.tonic_pc) % 12)
            shift = ((tonic_pc - sc.tonic_pc + 6) % 12) - 6      # smallest move to the new key
            tonic_midi = orig_tonic_midi + shift
            if shift:
                seed_beats = [Note(n.pitch + shift, n.start, n.duration) for n in seed_beats]
            sc = Scale(tonic_pc, sc.mode, tonic_midi)
        else:
            tonic_midi = 60 + ((tonic_pc - 60) % 12)       # tonic in C4..B4
            if tonic_midi > 65:
                tonic_midi -= 12                           # keep melodies comfortably mid-range

        default_vibe = vibe or ("sad" if sc.mode == "minor" else "pop")
        candidates: list[Idea] = []

        def add(idea: Idea):
            n = idea.notes
            if len(n) < 4 or len({x.pitch for x in n}) < 3:
                return
            if any(_same_pitches(n, c.notes) for c in candidates):
                return
            idea.novelty, idea.nearest = self._novelty(n)
            candidates.append(idea)

        def composed(v, kind, title, desc, start=None, motif=None, keep=3, tempo=None):
            for mus, ev, prog, form, _f in best_of(v, rng, n=30, keep=keep, start=start, motif=motif):
                notes = [Note(tonic_midi + e.pitch, round(e.start, 3), round(e.dur, 3))
                         for e in ev if e.pitch is not None]
                t = tempo or float(rng.integers(v.tempo[0], v.tempo[1] + 1))
                add(Idea(kind, title, desc, notes, musicality=mus, progression=prog,
                         vibe=v.id, tempo_bpm=t, form=form,
                         key=f"{_KEY_NAMES[tonic_pc]} {v.mode_label}"))

        if has_seed:
            v = VIBES[default_vibe]
            last = seed_beats[-1].pitch - tonic_midi
            composed(v, "continuation", "Continuation",
                     f"{v.label} answer to your phrase: picks up where you stopped and reuses "
                     "your rhythm.", start=int(np.clip(last, v.center - 10, v.center + 10)),
                     motif=_seed_motif_rhythm(seed_dur), keep=3, tempo=seed_tempo)
            composed(v, "fresh", f"{v.label} idea", v.description, keep=3)
            d, r = gen_inversion(seed_deg, seed_dur)
            add(Idea("inversion", "Mirror", "Your phrase turned upside-down: every rise becomes a fall.",
                     _from_degrees(sc, d, r), tempo_bpm=seed_tempo, key=key_name(tonic_pc, sc.mode)))
            for _ in range(3):
                d, r = gen_sequence(seed_deg, seed_dur, rng)
                add(Idea("sequence", "Sequence", "Your opening motif, restated on a new step of the scale.",
                         _from_degrees(sc, d, r), tempo_bpm=seed_tempo, key=key_name(tonic_pc, sc.mode)))
            order = ["continuation", "fresh", "inversion", "sequence", "fresh", "continuation"]
        elif vibe:
            v = VIBES[vibe]
            composed(v, "fresh", f"{v.label} idea", v.description, keep=6)
            order = ["fresh"] * 8
        else:
            # Surprise me: a different vibe on every card
            picks = list(rng.permutation(VIBE_ORDER))
            for vid in picks[:max(num_ideas + 1, 5)]:
                v = VIBES[vid]
                composed(v, "fresh", f"{v.label} idea", v.description, keep=1)
            order = ["fresh"] * 8

        kept = [c for c in candidates if c.novelty >= FAMILIAR]
        dropped = len(candidates) - len(kept)
        kept.sort(key=lambda c: (-(c.musicality or 0.0), -c.novelty))
        chosen: list[Idea] = []
        for k in order:
            if len(chosen) >= num_ideas:
                break
            for c in kept:
                if c.kind == k and c not in chosen and \
                        (k != "fresh" or vibe or has_seed or c.vibe not in {x.vibe for x in chosen}):
                    chosen.append(c)
                    break
        for c in kept:
            if len(chosen) >= num_ideas:
                break
            if c not in chosen:
                chosen.append(c)
        chosen = chosen[:num_ideas]

        for c in chosen:
            low = min(n.pitch for n in c.notes)
            if c.progression:
                minor = VIBES[c.vibe].mode_label.startswith("minor") if c.vibe else sc.mode == "minor"
                c.chords = chords_for(c.progression, tonic_pc, tonic_midi, low, c.notes, minor)
            else:
                c.chords = triad_chords(suggest_chords(c.notes, sc), tonic_midi, low)

        return {
            "seed": {"used": has_seed, "key": key_name(tonic_pc, sc.mode),
                     "num_notes": len(seed_notes or []), "tempo_bpm": seed_tempo,
                     "notes": seed_beats},
            "vibe": vibe,
            "ideas": chosen,
            "candidates_considered": len(candidates),
            "too_familiar_dropped": dropped,
        }



_ROMAN_MAJOR = ["I", "ii", "iii", "IV", "V", "vi", "vii°"]
_ROMAN_MINOR = ["i", "ii°", "III", "iv", "V", "VI", "VII"]


def _prog_name(prog, mode) -> str:
    romans = _ROMAN_MAJOR if mode == "major" else _ROMAN_MINOR
    return "–".join(romans[r % 7] for r in prog[:4])


def chords_from_progression(prog, sc: Scale, notes: list[Note]) -> list[dict]:
    """One chord per bar from the composed progression."""
    romans = _ROMAN_MAJOR if sc.mode == "major" else _ROMAN_MINOR
    end = notes[-1].start + notes[-1].duration if notes else BAR * len(prog)
    out = []
    for i, root in enumerate(prog):
        start = i * BAR
        if start >= end - 1e-6:
            break
        roman = romans[root % 7]
        pc = (sc.steps[root % 7] + sc.tonic_pc) % 12
        if sc.mode == "minor" and roman == "V":
            quality = ""                                   # major dominant in minor
        elif roman.endswith("°"):
            quality = "dim"
        elif roman[0].islower():
            quality = "m"
        else:
            quality = ""
        out.append({"start": start, "duration": min(BAR, end - start), "roman": roman,
                    "symbol": f"{_NAMES[pc]}{quality}"})
    return out


def chords_for(prog: list, tonic_pc: int, tonic_midi: int, melody_low: int,
               notes: list[Note], minor: bool = False) -> list[dict]:
    """Chord list for a composed idea, with exact voicings for playback."""
    end = notes[-1].start + notes[-1].duration if notes else 16.0
    out, t = [], 0.0
    for ch in prog:
        if t >= end - 1e-6:
            break
        tones, bass = voice_chord(tonic_midi, ch, melody_low)
        out.append({"start": round(t, 3), "duration": round(min(ch.beats, end - t), 3),
                    "roman": ch.roman, "symbol": chord_symbol(tonic_pc, ch, minor),
                    "root_pc": (tonic_pc + ch.root) % 12, "quality": ch.quality,
                    "suffix": _suffix(ch.quality), "tones": tones, "bass": bass})
        t += ch.beats
    return out


def _suffix(q):
    from .vibes import QUALITY_SUFFIX
    return QUALITY_SUFFIX[q]


_KEY_NAMES = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
_SYMBOL_PC = {n: i for i, n in enumerate(["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"])}


def triad_chords(chords: list[dict], tonic_midi: int, melody_low: int) -> list[dict]:
    """Add exact voicings to simple triad chords (from suggest_chords)."""
    tonic_pc = tonic_midi % 12
    out = []
    for c in chords:
        sym = c["symbol"]
        name = sym[:2] if len(sym) > 1 and sym[1] in "b#" else sym[:1]
        qual = sym[len(name):]
        root_pc = _SYMBOL_PC.get(name, 0)
        quality = {"": "maj", "m": "min", "dim": "dim"}.get(qual, "maj")
        ch = Chord((root_pc - tonic_pc) % 12, quality, c["roman"], c["duration"])
        tones, bass = voice_chord(tonic_midi, ch, melody_low)
        out.append({**c, "root_pc": root_pc, "quality": quality, "suffix": _suffix(quality),
                    "tones": tones, "bass": bass})
    return out


def _same_pitches(a: list[Note], b: list[Note]) -> bool:
    return [n.pitch for n in a] == [n.pitch for n in b]


def novelty_label(novelty: float) -> str:
    if novelty >= NOVEL:
        return "novel"
    if novelty >= FAMILIAR:
        return "echoes"
    return "familiar"
