"""Matching-engine tests on the 30 famous tunes.

Run:  python -m pytest backend/tests -q      (or: python backend/tests/test_search.py)
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.catalog import load_famous  # noqa: E402
from app.search import MelodyIndex  # noqa: E402

MELODIES = load_famous()
INDEX = MelodyIndex(MELODIES)


def excerpt(m, start, length, transpose=0, tempo=1.0):
    notes = m.notes[start:start + length]
    p = np.array([n.pitch for n in notes]) + transpose
    o = np.array([n.start for n in notes]) * tempo
    d = np.array([n.duration for n in notes]) * tempo
    return p, o - o[0], d


def sloppy(p, o, d, rng, wrong=1, drop=False, insert=False, jitter=0.15):
    p, o, d = p.copy(), o.copy(), d.copy()
    for _ in range(wrong):
        k = rng.integers(1, len(p))
        p[k] += rng.choice([-1, 1])
    o = o * (1 + rng.normal(0, jitter, len(o)) * 0.3)
    o = np.maximum.accumulate(o)
    d = d * np.exp(rng.normal(0, jitter, len(d)))
    if drop and len(p) > 6:
        k = rng.integers(2, len(p) - 2)
        p, o, d = np.delete(p, k), np.delete(o, k), np.delete(d, k)
    if insert:
        k = rng.integers(2, len(p) - 1)
        p = np.insert(p, k, p[k - 1])
        o = np.insert(o, k, (o[k - 1] + o[k]) / 2)
        d = np.insert(d, k, d[k - 1] / 2)
    return p, o, d


def run_suite(seed=0, verbose=False):
    rng = np.random.default_rng(seed)
    stats = {"clean": [], "sloppy": [], "very_sloppy": []}
    scores = {"clean": [], "sloppy": [], "very_sloppy": [], "negative": []}
    for m in MELODIES:
        n = len(m.notes)
        L = min(10, n)
        for trial in range(4):
            start = int(rng.integers(0, max(1, n - L)))
            tr = int(rng.integers(-7, 8))
            tempo = float(rng.uniform(0.5, 2.0))
            p, o, d = excerpt(m, start, L, tr, tempo)
            for kind, args in (("clean", None),
                               ("sloppy", dict(wrong=1, jitter=0.15)),
                               ("very_sloppy", dict(wrong=2, drop=True, insert=True, jitter=0.25))):
                qp, qo, qd = (p, o, d) if args is None else sloppy(p, o, d, rng, **args)
                hits = INDEX.search(qp, qo, qd, top_k=5)
                ok = hits[0].melody.id == m.id
                in5 = any(h.melody.id == m.id for h in hits)
                stats[kind].append((ok, in5))
                scores[kind].append(hits[0].score if ok else 0.0)
                if verbose and not ok and kind == "clean":
                    print("MISS", kind, m.title, "->", hits[0].melody.title, round(hits[0].score, 2))
    # negatives: random melodies that shouldn't match anything
    for _ in range(60):
        L = 10
        steps = rng.choice([-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 7], L - 1)
        p = 60 + np.concatenate([[0], np.cumsum(steps)])
        d = rng.choice([0.5, 1, 1, 1.5, 2], L).astype(float)
        o = np.concatenate([[0], np.cumsum(d[:-1])])
        scores["negative"].append(INDEX.search(p, o, d, top_k=1)[0].score)
    return stats, scores


def test_clean_excerpts_rank_first():
    stats, _ = run_suite()
    top1 = np.mean([a for a, _ in stats["clean"]])
    assert top1 >= 0.95, top1


def test_sloppy_excerpts_in_top5():
    stats, _ = run_suite()
    top5 = np.mean([b for _, b in stats["sloppy"]])
    assert top5 >= 0.9, top5


def test_random_melodies_are_not_strong():
    _, scores = run_suite()
    assert np.mean(np.array(scores["negative"]) >= 0.70) <= 0.05


if __name__ == "__main__":
    stats, scores = run_suite(verbose=True)
    for k, v in stats.items():
        print(f"{k:12s} top1={np.mean([a for a, _ in v]):.2f}  top5={np.mean([b for _, b in v]):.2f}  n={len(v)}")
    for k, v in scores.items():
        v = np.array(v)
        print(f"{k:12s} score: median={np.median(v):.2f}  p10={np.percentile(v,10):.2f}  p90={np.percentile(v,90):.2f}")
