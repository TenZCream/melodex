"""Evaluate on real recordings (not committed: voice data stays local).

Usage: python tests/real_eval.py <folder-with-wavs>
Expected song per file is set in EXPECTED below (substring of the title).
"""
import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.catalog import load_famous  # noqa: E402
from app.melody import midi_to_name  # noqa: E402
from app.pitch import transcribe  # noqa: E402
from app.search import MelodyIndex  # noqa: E402

EXPECTED = {
    "171151": "Mary", "171208": "Mary", "171216": "Mary", "171222": "Mary",
    "172450": "Twinkle",
    "175731": "Twinkle", "175800": "Twinkle", "175824": "Mary", "175908": "Happy Birthday",
}


def main(folder, verbose=True):
    index = MelodyIndex(load_famous())
    ok = 0
    total = 0
    for f in sorted(glob.glob(os.path.join(folder, "*.wav"))):
        key = os.path.basename(f)[:6]
        want = EXPECTED.get(key)
        if not want:
            continue
        tx = transcribe(open(f, "rb").read())
        total += 1
        if len(tx.notes) < 4:
            print(f"{key} {want:8s} MISS (only {len(tx.notes)} notes)")
            continue
        hits = index.search([n.pitch for n in tx.notes], [n.start for n in tx.notes],
                            [n.duration for n in tx.notes], top_k=3)
        good = want in hits[0].melody.title
        ok += good
        if verbose:
            notes = " ".join(midi_to_name(n.pitch) for n in tx.notes)
            print(f"{key} {want:8s} {'OK  ' if good else 'MISS'} {hits[0].melody.title[:22]:22s} "
                  f"{hits[0].label:8s} {hits[0].score:.2f} | {notes}")
    print(f"real recordings: {ok}/{total} correct at #1")
    return ok, total


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads/github/melodex/backend/debug_recordings")
