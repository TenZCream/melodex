"""Rule-based melody composer: makes generated ideas sound intentional.

Songwriting rules, encoded:
1. Harmony first: pick a real chord progression (one chord per bar), put chord tones
   on strong beats and step-wise passing/neighbour tones between them.
2. Repetition: bar 3 reuses bar 1's rhythm and contour (shifted to fit its chord);
   bar 2 answers; bar 4 cadences.
3. Mostly steps, few leaps; after a leap, step back the other way (gap-fill).
4. Real ending: the last note is the tonic on the I chord, approached by step.
5. Generate many candidates, score each on these rules, keep the best.

All pitches are scale degrees (0 = tonic, 7 = tonic an octave up) so the result is in
the user's key; `generate.py` converts degrees to MIDI.
"""
from __future__ import annotations

import numpy as np

BAR = 4.0  # beats per bar

# chord progressions as scale-degree roots (0 = I, 4 = V, 5 = vi, 3 = IV ...)
PROGRESSIONS_MAJOR = [
    [0, 4, 5, 3],   # I  V  vi IV   ("pop")
    [0, 3, 4, 0],   # I  IV V  I
    [0, 5, 3, 4],   # I  vi IV V    ("50s")
    [5, 3, 0, 4],   # vi IV I  V
    [0, 3, 0, 4],   # I  IV I  V
    [0, 1, 4, 0],   # I  ii V  I
]
PROGRESSIONS_MINOR = [
    [0, 5, 2, 6],   # i  VI III VII
    [0, 3, 4, 0],   # i  iv V  i
    [0, 6, 5, 4],   # i  VII VI V
    [0, 5, 3, 4],   # i  VI iv V
]

# one-bar rhythms (beats, sum = 4). Weighted toward simple, singable patterns.
RHYTHMS = [
    ([1, 1, 1, 1], 3), ([1, 1, 2], 3), ([2, 1, 1], 2), ([1.5, 0.5, 1, 1], 3),
    ([1, 0.5, 0.5, 2], 2), ([0.5, 0.5, 1, 2], 2), ([1, 1, 1.5, 0.5], 2),
    ([2, 2], 1), ([0.5, 0.5, 0.5, 0.5, 1, 1], 1), ([1.5, 0.5, 2], 2),
]
ENDINGS = [([2, 2], 2), ([1, 1, 2], 3), ([3, 1], 1), ([1.5, 0.5, 2], 2), ([4], 1)]

LOW, HIGH = -3, 10       # allowed degree range (a bit below tonic to ~1.5 octaves up)


def _pick(options, rng):
    w = np.array([o[1] for o in options], dtype=float)
    return list(options[rng.choice(len(options), p=w / w.sum())][0])


def chord_tones(root: int) -> list[int]:
    """Degrees of the triad on `root`, in every octave within range."""
    base = [(root + k) % 7 for k in (0, 2, 4)]
    return [d + 7 * o for d in base for o in (-1, 0, 1) if LOW <= d + 7 * o <= HIGH]


def _nearest(target_set, prev, rng, max_jump=4, prefer_dir=0):
    cands = [d for d in target_set if abs(d - prev) <= max_jump] or list(target_set)
    w = np.array([1.0 / (1 + abs(d - prev)) ** 1.5 for d in cands])
    if prefer_dir:
        w *= np.array([1.6 if np.sign(d - prev) == prefer_dir else 1.0 for d in cands])
    w[[d == prev for d in cands]] *= 0.5        # discourage static repeats
    return int(cands[rng.choice(len(cands), p=w / w.sum())])


def _fill_bar(rhythm, root, prev, rng, contour=None):
    """Pitches for one bar: chord tones on strong beats, steps on weak beats.
    If `contour` (list of degree offsets) is given, follow it (motif repetition)."""
    tones = chord_tones(root)
    degs = []
    t = 0.0
    for i, d in enumerate(rhythm):
        strong = abs(t - round(t)) < 1e-6 and int(round(t)) % 2 == 0
        if contour is not None and i < len(contour):
            want = prev + contour[i] if i else contour[0]
            if strong:
                g = min(tones, key=lambda x: (abs(x - want), x))
            else:
                g = want
        elif strong or i == 0:
            g = _nearest(tones, prev, rng)
        else:
            step = int(rng.choice([-1, 1, 1, -2, 2], p=[0.35, 0.35, 0.1, 0.1, 0.1]))
            g = prev + step
        g = int(np.clip(g, LOW, HIGH))
        degs.append(g)
        prev = g
        t += d
    return degs


def compose_phrase(rng, mode: str = "major", start_deg: int | None = None,
                   motif_rhythm: list[float] | None = None):
    """A 4-bar phrase. Returns (degrees, durations, chord_roots_per_bar)."""
    prog = list((PROGRESSIONS_MAJOR if mode == "major" else PROGRESSIONS_MINOR)[
        rng.integers(len(PROGRESSIONS_MAJOR if mode == "major" else PROGRESSIONS_MINOR))])
    r1 = motif_rhythm if motif_rhythm else _pick(RHYTHMS, rng)
    r2 = _pick(RHYTHMS, rng)
    r4 = _pick(ENDINGS, rng)

    prev = start_deg if start_deg is not None else int(rng.choice([0, 2, 4]))
    bar1 = _fill_bar(r1, prog[0], prev, rng)
    bar2 = _fill_bar(r2, prog[1], bar1[-1], rng)
    # bar 3 repeats bar 1's rhythm and shape, moved to fit chord 3
    contour = [bar1[0] + (chord_tones(prog[2])[0] - chord_tones(prog[0])[0]) % 7] + \
              [b - a for a, b in zip(bar1, bar1[1:])]
    contour[0] = min(chord_tones(prog[2]), key=lambda x: abs(x - bar2[-1]))
    bar3 = _fill_bar(r1, prog[2], bar2[-1], rng, contour=contour)
    bar4 = _fill_bar(r4, prog[3], bar3[-1], rng)

    degs = bar1 + bar2 + bar3 + bar4
    durs = list(r1) + list(r2) + list(r1) + list(r4)
    # cadence: if the phrase doesn't already end on I, add a resolving bar on I
    # (V -> I is the strongest ending; IV -> I and others resolve too)
    if prog[3] != 0:
        prog.append(0)
        degs.append(0)
        durs.append(BAR)
        last = 0
    else:
        last = len(degs) - 1
    tonic = min([0, 7], key=lambda t: abs(t - degs[last - 1]))
    degs[last] = tonic
    if abs(degs[last - 1] - tonic) > 2:
        degs[last - 1] = tonic + (1 if degs[last - 1] > tonic else -1)
    return degs, durs, prog


def musicality(degs, durs, prog) -> float:
    """0..1 score for how 'composed' a degree sequence sounds (heuristic)."""
    d = np.asarray(degs)
    steps = np.diff(d)
    if len(steps) == 0:
        return 0.0
    s = 0.0
    stepwise = np.mean(np.abs(steps) <= 1)
    s += 1.0 - min(abs(stepwise - 0.65) / 0.65, 1.0)                  # mostly steps
    leaps = np.nonzero(np.abs(steps) >= 3)[0]
    if len(leaps):
        filled = [i + 1 < len(steps) and np.sign(steps[i + 1]) == -np.sign(steps[i])
                  and abs(steps[i + 1]) <= 2 for i in leaps]
        s += np.mean(filled)                                         # gap-fill after leaps
    else:
        s += 0.7
    s += 1.0 if (d.max() - d.min()) <= 9 else 0.4                    # singable range
    s += 1.0 if d.min() < d.argmax() and 0 < d.argmax() < len(d) - 1 else 0.6  # arch
    repeats = max((len(list(g)) for g in _runs_of(d)), default=1)
    s += 1.0 if repeats <= 2 else 0.3                                # no droning
    big = np.mean(np.abs(steps) > 5)
    s += 1.0 - min(big * 4, 1.0)                                     # few huge leaps
    s += 1.0 if d[-1] % 7 == 0 else 0.0                              # ends home
    # chord tones on downbeats
    t, hits, total = 0.0, 0, 0
    for g, du in zip(degs, durs):
        if abs(t - round(t)) < 1e-6 and int(round(t)) % 2 == 0:
            bar = min(int(t // BAR), len(prog) - 1)
            total += 1
            hits += (g % 7) in {(prog[bar] + k) % 7 for k in (0, 2, 4)}
        t += du
    s += hits / max(total, 1)
    return float(s / 8.0)


def _runs_of(d):
    run = [d[0]]
    for x in d[1:]:
        if x == run[-1]:
            run.append(x)
        else:
            yield run
            run = [x]
    yield run


def best_phrases(rng, mode="major", n_candidates=40, keep=8, start_deg=None,
                 motif_rhythm=None):
    """Compose many phrases and return the most musical ones (with their scores)."""
    cands = []
    for _ in range(n_candidates):
        degs, durs, prog = compose_phrase(rng, mode, start_deg, motif_rhythm)
        cands.append((musicality(degs, durs, prog), degs, durs, prog))
    cands.sort(key=lambda c: -c[0])
    seen, out = set(), []
    per_prog: dict[tuple, int] = {}
    for c in cands:
        key = tuple(c[1])
        pk = tuple(c[3][:4])
        if key in seen or per_prog.get(pk, 0) >= 2:     # variety: <= 2 ideas per progression
            continue
        seen.add(key)
        per_prog[pk] = per_prog.get(pk, 0) + 1
        out.append(c)
        if len(out) >= keep:
            break
    return out
