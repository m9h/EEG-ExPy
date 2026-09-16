"""Tests for the visual mismatch negativity (vMMN) paradigm (no display)."""

from __future__ import annotations

import numpy as np
import pytest

from eegnb.bids import paradigms as bids_paradigms


def test_registered_in_bids_by_name():
    assert "visual-mmn" in bids_paradigms.BY_NAME


def test_bids_metadata_shape():
    meta = bids_paradigms.VMMN
    assert meta.bids_task_name == "visualMmn"
    assert meta.bids_event_id == {1: "standard", 2: "deviant"}
    required = {"TaskName", "Instructions", "TaskDescription"}
    assert required.issubset(meta.bids_task_json.keys())
    assert "mismatch negativity" in meta.bids_task_json["TaskDescription"].lower()


def test_class_importable_and_in_cli():
    pytest.importorskip("psychopy")
    import eegnb.experiments
    from eegnb.cli.utils import get_experiments

    cls = eegnb.experiments.VisualMMN
    assert cls.__name__ == "VisualMMN"
    assert cls.default_frame_locked is False
    assert "visual-mmn" in get_experiments()


def _make(**kw):
    pytest.importorskip("psychopy")
    from eegnb.experiments.visual_mmn.vmmn import VisualMMN
    return VisualMMN(**kw)


def test_sequence_enforces_deviant_probability_and_spacing():
    exp = _make(n_trials=500, deviant_prob=0.2, min_standards_between=2, seed=7)
    seq = exp.parameter
    assert len(seq) == 500
    assert set(np.unique(seq).tolist()) == {1, 2}
    # roughly the requested deviant proportion
    assert 0.15 < (seq == 2).mean() < 0.25
    # at least min_standards_between standards between deviants
    dev_idx = np.where(seq == 2)[0]
    assert np.all(np.diff(dev_idx) >= 3)


def test_bad_feature_rejected():
    pytest.importorskip("psychopy")
    from eegnb.experiments.visual_mmn.vmmn import VisualMMN
    with pytest.raises(ValueError):
        VisualMMN(feature="motion")


def test_markernames():
    exp = _make()
    assert exp.markernames == {1: "standard", 2: "deviant"}


# --- present_stimulus picks the right stim + marker (mocked window) ---------

class _FakeStim:
    def __init__(self, tag):
        self.tag = tag
        self.drawn = 0

    def draw(self):
        self.drawn += 1


class _FakeWindow:
    def __init__(self):
        self.flips = 0

    def flip(self):
        self.flips += 1


class _FakeEEG:
    backend = "muselsl"

    def __init__(self):
        self.markers = []

    def push_sample(self, marker, timestamp):
        self.markers.append(marker)


def _wire(exp, eeg=None):
    exp.standard_stim = _FakeStim("std")
    exp.deviant_stim = _FakeStim("dev")
    exp.fixation = _FakeStim("fix")
    exp.window = _FakeWindow()
    exp.eeg = eeg
    return exp


def test_standard_and_deviant_route_to_correct_stim_and_marker():
    exp = _make(n_trials=20, seed=3)
    _wire(exp, eeg=_FakeEEG())
    # find a standard index and a deviant index from the generated sequence
    std_i = int(np.where(exp.parameter == 1)[0][0])
    dev_i = int(np.where(exp.parameter == 2)[0][0])

    exp.present_stimulus(std_i)
    assert exp.standard_stim.drawn == 1 and exp.deviant_stim.drawn == 0
    assert exp.eeg.markers[-1] == [1]  # muselsl list-wrap, standard

    exp.present_stimulus(dev_i)
    assert exp.deviant_stim.drawn == 1
    assert exp.eeg.markers[-1] == [2]  # deviant
    assert exp.window.flips == 2


def test_out_of_range_trial_is_noop():
    exp = _make(n_trials=10)
    _wire(exp)
    exp.present_stimulus(999)
    assert exp.window.flips == 0
