"""Pure-logic helpers for the ERP CORE paradigms.

These utilities contain no PsychoPy, no display, and no audio
dependencies. They live in :mod:`eegnb.paradigms` so that trial
generators, stimulus parsers, and arrow-string builders can be unit
tested in headless CI and reused by analysis code without forcing a
PsychoPy import.
"""

from __future__ import annotations

import csv
import os
from typing import Optional

import numpy as np


def generate_mmn_sequence(
    n_trials: int,
    deviant_prob: float = 0.2,
    min_standards_between: int = 2,
    lead_in_standards: int = 5,
    seed: Optional[int] = None,
) -> np.ndarray:
    """Generate a constrained standard/deviant sequence for the MMN.

    Returns a length-``n_trials`` integer array with ``1=standard``,
    ``2=deviant``. Enforces ``lead_in_standards`` standards at the
    start of the sequence and at least ``min_standards_between``
    standards between any two deviants (this is the Kappenman rule
    that prevents back-to-back deviants from becoming standards of
    their own).
    """
    rng = np.random.default_rng(seed)
    seq = np.ones(n_trials, dtype=int)
    n_deviants = int(round(n_trials * deviant_prob))

    candidate_positions = np.arange(lead_in_standards, n_trials)
    rng.shuffle(candidate_positions)

    placed: list[int] = []
    for pos in candidate_positions:
        if len(placed) >= n_deviants:
            break
        if all(abs(int(pos) - p) > min_standards_between for p in placed):
            placed.append(int(pos))
            seq[pos] = 2
    return seq


def build_flanker_arrow_string(central_left: bool, congruent: bool) -> str:
    """Build a 5-character flanker arrow string.

    Examples
    --------
    >>> build_flanker_arrow_string(central_left=True, congruent=True)
    '<<<<<'
    >>> build_flanker_arrow_string(central_left=True, congruent=False)
    '>><>>'
    >>> build_flanker_arrow_string(central_left=False, congruent=True)
    '>>>>>'
    >>> build_flanker_arrow_string(central_left=False, congruent=False)
    '<<><<'
    """
    central = "<" if central_left else ">"
    flank = central if congruent else (">" if central_left else "<")
    return f"{flank}{flank}{central}{flank}{flank}"


def read_word_pairs_csv(path: str) -> list[tuple[str, str, str]]:
    """Read an N400 word-pair CSV.

    The CSV must have the columns ``prime``, ``related_target``, and
    ``unrelated_target``. Returns a list of ``(prime, related_target,
    unrelated_target)`` tuples.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"word pairs CSV not found: {path}")

    pairs: list[tuple[str, str, str]] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        required = {"prime", "related_target", "unrelated_target"}
        fieldnames = set(reader.fieldnames or [])
        if not required.issubset(fieldnames):
            raise ValueError(
                f"word pairs CSV {path} must have columns {sorted(required)}; "
                f"got {reader.fieldnames}"
            )
        for row in reader:
            pairs.append(
                (row["prime"], row["related_target"], row["unrelated_target"])
            )
    if not pairs:
        raise ValueError(f"word pairs CSV {path} is empty")
    return pairs
