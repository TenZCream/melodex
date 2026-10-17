"""Explore / generation tests.  Run: python tests/test_generate.py"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.catalog import load_famous  # noqa: E402
from app.generate import FAMILIAR, Explorer  # noqa: E402
from app.melody import MAJOR_SCALE, MINOR_SCALE, Note, estimate_key  # noqa: E402
from app.search import MelodyIndex  # noqa: E402

INDEX = MelodyIndex(load_famous())
EXPLORER = Explorer(INDEX)


def seed_from(title, n=12, transpose=0, sec_per_beat=0.5):
    m = next(x for x in INDEX.melodies if x.title.startswith(title))
    return [Note(x.pitch + transpose, x.start * sec_per_beat, x.duration * sec_per_beat)
            for x in m.notes[:n]]


def in_key_fraction(notes, tonic, mode):
    scale = MAJOR_SCALE if mode == "major" else MINOR_SCALE
    return np.mean([((n.pitch - tonic) % 12) in scale for n in notes])


def check(seed, runs=10):
    for r in range(runs):
        out = EXPLORER.generate(seed, num_ideas=4, rng_seed=r)
        assert 1 <= len(out["ideas"]) <= 4, len(out["ideas"])
        for idea in out["ideas"]:
            assert idea.novelty >= FAMILIAR, (idea.kind, idea.novelty)
            assert len(idea.notes) >= 4
            assert idea.chords, "chords expected"
            if seed:
                tonic, mode, _ = estimate_key([n.pitch for n in seed], [n.duration for n in seed])
                assert in_key_fraction(idea.notes, tonic, mode) >= 0.75, idea.kind


def test_ideas_from_seeds():
    for title, tr in [("Twinkle", -2), ("Mary", 3), ("Ode to Joy", 0), ("Greensleeves", -5)]:
        check(seed_from(title, transpose=tr))


def test_fresh_ideas_without_seed():
    check(None)


def test_ideas_never_copy_index():
    """Every returned idea must stay below 'strong match' similarity to every indexed song."""
    for r in range(20):
        out = EXPLORER.generate(seed_from("Happy Birthday"), rng_seed=r)
        for idea in out["ideas"]:
            assert idea.nearest["similarity"] < 0.70, idea.nearest


if __name__ == "__main__":
    import time
    t = time.time()
    test_ideas_from_seeds()
    test_fresh_ideas_without_seed()
    test_ideas_never_copy_index()
    print(f"generation tests passed ({time.time() - t:.1f}s)")
