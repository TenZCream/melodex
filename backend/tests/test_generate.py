"""Explore / generation tests.  Run: python tests/test_generate.py"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.catalog import load_famous  # noqa: E402
from app.generate import FAMILIAR, Explorer  # noqa: E402
from app.melody import MAJOR_SCALE, MINOR_SCALE, Note, estimate_key  # noqa: E402
from app.search import MelodyIndex  # noqa: E402
from app.vibes import VIBE_ORDER, VIBES, best_of, features  # noqa: E402

INDEX = MelodyIndex(load_famous())
EXPLORER = Explorer(INDEX)


def seed_from(title, n=12, transpose=0, sec_per_beat=0.5):
    m = next(x for x in INDEX.melodies if x.title.startswith(title))
    return [Note(x.pitch + transpose, x.start * sec_per_beat, x.duration * sec_per_beat)
            for x in m.notes[:n]]


def in_key_fraction(notes, tonic, mode):
    scale = MAJOR_SCALE if mode == "major" else MINOR_SCALE
    return np.mean([((n.pitch - tonic) % 12) in scale for n in notes])


def _check_out(out, n=4):
    assert 1 <= len(out["ideas"]) <= n
    for idea in out["ideas"]:
        assert idea.novelty >= FAMILIAR, (idea.kind, idea.novelty)
        assert len(idea.notes) >= 4
        assert idea.chords, "chords expected"
        for c in idea.chords:
            assert c["tones"] and min(c["tones"]) >= 48, c          # audible on laptops
            assert c["bass"] < min(c["tones"]), c


def test_ideas_from_seeds():
    for title, tr in [("Twinkle", -2), ("Mary", 3), ("Ode to Joy", 0), ("Greensleeves", -5)]:
        seed = seed_from(title, transpose=tr)
        tonic, mode, _ = estimate_key([n.pitch for n in seed], [n.duration for n in seed])
        for r in range(5):
            out = EXPLORER.generate(seed, rng_seed=r)
            _check_out(out)
            for idea in out["ideas"]:
                if idea.kind in ("inversion", "sequence"):
                    assert in_key_fraction(idea.notes, tonic, mode) >= 0.75


def test_every_vibe_with_and_without_seed():
    seed = seed_from("Twinkle", transpose=-2)
    for vibe in VIBE_ORDER:
        for r in range(3):
            _check_out(EXPLORER.generate(None, rng_seed=r, vibe=vibe))
            _check_out(EXPLORER.generate(seed, rng_seed=r, vibe=vibe))


def test_key_change_moves_everything():
    seed = seed_from("Twinkle")                      # C major
    out = EXPLORER.generate(seed, rng_seed=1, vibe="pop", key_pc=2)   # D major
    assert out["seed"]["key"].startswith("D")
    assert out["seed"]["notes"][0].pitch % 12 == 2
    for idea in out["ideas"]:
        assert in_key_fraction(idea.notes, 2, "major") >= 0.75


def test_surprise_mixes_vibes():
    out = EXPLORER.generate(None, rng_seed=0)
    assert len({i.vibe for i in out["ideas"]}) >= 3


def test_vibes_sound_different():
    """Each vibe's melodies must sit in a measurably different place."""
    prof = {}
    for vid in VIBE_ORDER:
        fs = [best_of(VIBES[vid], np.random.default_rng(s), keep=1)[0][4] for s in range(8)]
        prof[vid] = {k: np.mean([f[k] for f in fs]) for k in fs[0]}
    assert prof["sad"]["slope"] < prof["happy"]["slope"] - 0.2          # sad falls, happy rises
    assert prof["sad"]["density"] < prof["jazzy"]["density"] - 0.4      # sad is slow, jazz busy
    assert prof["mysterious"]["rest"] > 0.1 > prof["pop"]["rest"]       # mysterious leaves space
    assert prof["dissonant"]["tritone"] > 0.07 > prof["happy"]["tritone"]
    assert prof["dissonant"]["ct_strong"] < prof["happy"]["ct_strong"] - 0.3
    assert prof["jazzy"]["chromatic"] > prof["happy"]["chromatic"] + 0.05
    assert prof["swingy"]["blue"] > 0.1 > prof["happy"]["blue"]
    assert prof["pop"]["hook"] > 0.8
    assert prof["happy"]["ends_tonic"] > 0.8 and prof["mysterious"]["ends_tonic"] < 0.2


def test_ideas_never_copy_index():
    for r in range(15):
        out = EXPLORER.generate(seed_from("Happy Birthday"), rng_seed=r)
        for idea in out["ideas"]:
            assert idea.nearest["similarity"] < 0.70, idea.nearest


if __name__ == "__main__":
    import time
    t = time.time()
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print(f"generation tests passed ({time.time() - t:.1f}s)")
