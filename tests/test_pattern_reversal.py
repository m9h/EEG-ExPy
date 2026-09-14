"""Tests for the pattern-reversal VEP paradigm (no display)."""

from __future__ import annotations

import numpy as np
import pytest

from eegnb.bids import paradigms as bids_paradigms


def test_registered_in_bids_by_name():
    assert "visual-pattern-reversal" in bids_paradigms.BY_NAME


def test_bids_metadata_shape():
    meta = bids_paradigms.PATTERN_REVERSAL_VEP
    assert meta.bids_task_name == "patternReversalVep"
    assert meta.bids_event_id == {1: "reversal"}
    required = {"TaskName", "Instructions", "TaskDescription"}
    assert required.issubset(meta.bids_task_json.keys())
    assert "P100" in meta.bids_task_json["TaskDescription"]


def test_class_importable_and_in_cli():
    pytest.importorskip("psychopy")
    import eegnb.experiments
    from eegnb.cli.utils import get_experiments

    cls = eegnb.experiments.VisualPatternReversalVEP
    assert cls.__name__ == "VisualPatternReversalVEP"
    assert cls.default_frame_locked is False
    assert "visual-pattern-reversal" in get_experiments()


def _make(**kw):
    pytest.importorskip("psychopy")
    from eegnb.experiments.visual_pattern_reversal.pattern_reversal import (
        VisualPatternReversalVEP,
    )
    return VisualPatternReversalVEP(**kw)


def test_soa_derived_from_reversal_rate():
    exp = _make(n_reversals=20, reversals_per_s=2.0)
    assert exp.soa == pytest.approx(0.5)
    assert exp.iti == 0.0  # continuous reversals, no blank
    assert exp.jitter == 0.0


def test_n_checks_from_field_and_check_size():
    exp = _make(field_deg=12.0, check_deg=1.0)
    assert exp.n_checks == 12
    exp2 = _make(field_deg=16.0, check_deg=0.25)  # ISCEV fine-check
    assert exp2.n_checks == 64


def test_phase_parameter_alternates():
    exp = _make(n_reversals=6)
    assert list(exp.parameter) == [0, 1, 0, 1, 0, 1]


# --- per-reversal draw/contrast/marker (mocked window) ----------------------

class _FakeStim:
    def __init__(self):
        self.contrast = None
        self.drawn = []

    def draw(self):
        self.drawn.append(self.contrast)


class _FakeWindow:
    def __init__(self):
        self.flips = 0

    def flip(self):
        self.flips += 1


class _FakeEEG:
    backend = "brainflow"

    def __init__(self):
        self.markers = []

    def push_sample(self, marker, timestamp):
        self.markers.append(marker)


def _wire(exp, eeg=None):
    exp.checkerboard = _FakeStim()
    exp.fixation = _FakeStim()
    exp.window = _FakeWindow()
    exp.eeg = eeg
    return exp


def test_contrast_toggles_each_reversal_and_marks_it():
    exp = _wire(_make(n_reversals=4), eeg=_FakeEEG())
    exp.present_stimulus(0)
    exp.present_stimulus(1)
    exp.present_stimulus(2)
    # even reversals -> +1 (phase A), odd -> -1 (phase B)
    assert exp.checkerboard.drawn == [1.0, -1.0, 1.0]
    assert exp.window.flips == 3
    # one reversal marker pushed per call, scalar for brainflow
    assert exp.eeg.markers == [1, 1, 1]


def test_out_of_range_reversal_is_noop():
    exp = _wire(_make(n_reversals=4))
    exp.present_stimulus(99)
    assert exp.window.flips == 0
