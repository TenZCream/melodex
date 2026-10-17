"""Builds the melody list that goes into the index."""
from __future__ import annotations

from .famous import FAMOUS
from .melody import Melody, parse_notation


def load_famous() -> list[Melody]:
    out = []
    for i, (title, composer, notation) in enumerate(FAMOUS, start=1):
        out.append(Melody(
            id=f"famous-{i:03d}",
            title=title,
            artist=composer,
            notes=parse_notation(notation),
            collection="Public-domain classics",
            license="Public domain",
            tempo_bpm=110.0,
        ))
    return out


def load_catalog() -> list[Melody]:
    """Everything the server indexes. MVP: famous public-domain tunes only."""
    return load_famous()
