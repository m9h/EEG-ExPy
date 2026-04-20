"""Tests for the ERP CORE paradigm suite.

These tests verify:

- BIDS metadata is well-formed for all six paradigms
- Paradigm classes are registered in the lazy loader and resolve when
  PsychoPy is available (skipped otherwise, since paradigm modules
  import ``psychopy.visual``)
- Pure-logic helpers (MMN sequence generator, flanker arrow strings,
  word-pair reader) round-trip correctly without a display

Stimulus-presentation tests (Window creation, tone generation, actual
flips) are intentionally omitted: they need an X display plus an audio
backend and belong in an integration test run with Xvfb + portaudio.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

from eegnb.bids import paradigms as bids_paradigms
from eegnb.paradigms import (
    build_flanker_arrow_string,
    generate_mmn_sequence,
    read_word_pairs_csv,
)


ERP_CORE_META = {
    "N170": bids_paradigms.ERP_CORE_N170,
    "MMN": bids_paradigms.ERP_CORE_MMN,
    "N2pc": bids_paradigms.ERP_CORE_N2PC,
    "N400": bids_paradigms.ERP_CORE_N400,
    "P3": bids_paradigms.ERP_CORE_P3,
    "Flanker": bids_paradigms.ERP_CORE_FLANKER,
}


# --- BIDS metadata ----------------------------------------------------------

def test_all_six_paradigms_registered_in_bids_by_name():
    expected = {
        "erp-core-n170",
        "erp-core-mmn",
        "erp-core-n2pc",
        "erp-core-n400",
        "erp-core-p3",
        "erp-core-flanker",
    }
    assert expected.issubset(bids_paradigms.BY_NAME.keys())


@pytest.mark.parametrize("name,meta", list(ERP_CORE_META.items()))
def test_bids_metadata_shape(name, meta):
    assert meta.bids_task_name.startswith("erpCore"), name
    assert isinstance(meta.bids_event_id, dict)
    assert meta.bids_event_id
    assert all(
        isinstance(k, int) and isinstance(v, str)
        for k, v in meta.bids_event_id.items()
    )
    required_json_keys = {"TaskName", "Instructions", "TaskDescription"}
    assert required_json_keys.issubset(meta.bids_task_json.keys())
    assert "Kappenman" in meta.bids_task_json["TaskDescription"]


# --- Pure-logic helpers (no PsychoPy) ---------------------------------------

def test_mmn_sequence_respects_lead_in_and_spacing():
    seq = generate_mmn_sequence(
        n_trials=400,
        deviant_prob=0.2,
        min_standards_between=2,
        lead_in_standards=5,
        seed=42,
    )
    assert len(seq) == 400
    assert np.all(seq[:5] == 1), "lead-in standards not enforced"
    deviant_idx = np.where(seq == 2)[0]
    gaps = np.diff(deviant_idx)
    assert np.all(gaps >= 3), f"deviants too close: min gap = {gaps.min()}"
    assert 0.15 < (seq == 2).mean() < 0.25


def test_mmn_deviant_proportion_is_enforced():
    low = generate_mmn_sequence(n_trials=500, deviant_prob=0.10, seed=1)
    high = generate_mmn_sequence(n_trials=500, deviant_prob=0.30, seed=1)
    assert (low == 2).mean() < (high == 2).mean()


@pytest.mark.parametrize(
    "central_left,congruent,expected",
    [
        (True, True, "<<<<<"),
        (True, False, ">><>>"),
        (False, True, ">>>>>"),
        (False, False, "<<><<"),
    ],
)
def test_flanker_arrow_string_cases(central_left, congruent, expected):
    assert build_flanker_arrow_string(central_left, congruent) == expected


def test_flanker_arrow_string_is_always_five_chars():
    for central_left in (True, False):
        for congruent in (True, False):
            s = build_flanker_arrow_string(central_left, congruent)
            assert len(s) == 5


def test_n400_bundled_word_pairs_load():
    # Locate the bundled CSV via the package.
    import eegnb.stimuli as stim_pkg
    csv_path = os.path.join(
        os.path.dirname(stim_pkg.__file__), "word_pairs_erp_core.csv"
    )
    pairs = read_word_pairs_csv(csv_path)
    assert len(pairs) >= 20
    for prime, rel, unrel in pairs:
        assert prime and rel and unrel
        assert rel != unrel


def test_n400_reader_rejects_missing_csv(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_word_pairs_csv(str(tmp_path / "does-not-exist.csv"))


def test_n400_reader_rejects_malformed_csv(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("foo,bar\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_word_pairs_csv(str(bad))


# --- Paradigm class registration (requires PsychoPy) ------------------------

@pytest.mark.parametrize("cls_name", [
    "VisualERPCoreN170",
    "AuditoryERPCoreMMN",
    "VisualERPCoreN2pc",
    "VisualERPCoreN400",
    "VisualERPCoreP3",
    "VisualERPCoreFlanker",
])
def test_experiment_classes_importable(cls_name):
    """Paradigm classes resolve through the eegnb.experiments lazy loader.

    Skipped when PsychoPy is unavailable (analysis-only installs),
    since paradigm modules import ``psychopy.visual`` directly.
    """
    pytest.importorskip("psychopy")
    import eegnb.experiments

    cls = getattr(eegnb.experiments, cls_name)
    assert cls.__name__ == cls_name
    assert hasattr(cls, "bids_task_name")
    assert hasattr(cls, "bids_event_id")
    assert hasattr(cls, "bids_task_json")
    assert hasattr(cls, "channels_of_interest")
