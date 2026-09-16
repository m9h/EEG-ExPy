"""Tests for the sweep VEP paradigm (no display)."""

from __future__ import annotations

import numpy as np
import pytest

from eegnb.bids import paradigms as bids_paradigms


def test_registered_in_bids_by_name():
    assert "visual-sweep-vep" in bids_paradigms.BY_NAME


def test_bids_metadata_shape():
    meta = bids_paradigms.SWEEP_VEP
    assert meta.bids_task_name == "sweepVep"
    assert meta.bids_event_id == {1: "sweepStepOnset"}
    required = {"TaskName", "Instructions", "TaskDescription"}
    assert required.issubset(meta.bids_task_json.keys())
    assert "threshold" in meta.bids_task_json["TaskDescription"].lower()


def test_class_importable_and_in_cli():
    pytest.importorskip("psychopy")
    import eegnb.experiments
    from eegnb.cli.utils import get_experiments

    cls = eegnb.experiments.VisualSweepVEP
    assert cls.__name__ == "VisualSweepVEP"
    assert cls.default_frame_locked is False
    assert "visual-sweep-vep" in get_experiments()


def _make(**kw):
    pytest.importorskip("psychopy")
    from eegnb.experiments.visual_sweep_vep.sweep_vep import VisualSweepVEP
    return VisualSweepVEP(**kw)


def test_contrast_sweep_values_monotonic_and_in_range():
    exp = _make(sweep="contrast", n_steps=8, contrast_range=(0.01, 0.8))
    v = exp.sweep_values
    assert len(v) == 8
    assert v[0] == pytest.approx(0.01)
    assert v[-1] == pytest.approx(0.8)
    assert np.all(np.diff(v) > 0)  # ascending
    # log-spaced -> constant ratio between successive steps
    ratios = v[1:] / v[:-1]
    assert np.allclose(ratios, ratios[0])


def test_spatial_freq_sweep_uses_sf_range():
    exp = _make(sweep="spatial_freq", n_steps=5, sf_range_cpd=(0.5, 16.0))
    assert exp.sweep_values[0] == pytest.approx(0.5)
    assert exp.sweep_values[-1] == pytest.approx(16.0)


def test_bad_sweep_type_rejected():
    pytest.importorskip("psychopy")
    from eegnb.experiments.visual_sweep_vep.sweep_vep import VisualSweepVEP
    with pytest.raises(ValueError):
        VisualSweepVEP(sweep="colour")


def test_n_trials_and_iti_for_continuous_sweep():
    exp = _make(n_steps=10, n_sweeps=3, step_s=1.0)
    assert exp.n_trials == 30
    assert exp.iti == 0.0  # steps back-to-back
    assert list(np.unique(exp.parameter)) == [1]  # single step-onset marker


# --- per-step flicker (mocked window) ---------------------------------------

class _FakeGrating:
    def __init__(self):
        self.phase = None
        self.contrast = None
        self.sf = None
        self.phases_drawn = []

    def draw(self):
        self.phases_drawn.append(self.phase)


class _FakeStim:
    def draw(self):
        pass


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


def _wire(exp, refresh=60.0, hold=10, eeg=None):
    exp._refresh = refresh
    exp._hold = hold
    exp.grating = _FakeGrating()
    exp.fixation = _FakeStim()
    exp.window = _FakeWindow()
    exp.eeg = eeg
    return exp


def test_step_sets_contrast_and_reverses_phase_on_schedule():
    exp = _make(sweep="contrast", n_steps=4, step_s=1.0, fixed_sf_cpd=1.5)
    _wire(exp, refresh=60.0, hold=10, eeg=_FakeEEG())
    exp.present_stimulus(0)  # first step

    n_frames = 60
    assert exp.window.flips == n_frames
    assert exp.grating.contrast == pytest.approx(exp.sweep_values[0])
    assert exp.grating.sf == 1.5
    # phase flips 0.0 <-> 0.5 every `hold` frames -> reversal rate refresh/hold
    expected = [0.0 if (f // 10) % 2 == 0 else 0.5 for f in range(n_frames)]
    assert exp.grating.phases_drawn == expected
    assert exp.eeg.markers == [1]  # one step-onset marker, scalar for brainflow


def test_spatial_freq_step_sets_sf():
    exp = _make(sweep="spatial_freq", n_steps=4, step_s=0.5, fixed_contrast=0.7)
    _wire(exp, refresh=60.0, hold=10)
    exp.present_stimulus(2)  # third step
    assert exp.grating.sf == pytest.approx(exp.sweep_values[2])
    assert exp.grating.contrast == 0.7


def test_out_of_range_step_is_noop():
    exp = _make(n_steps=4, n_sweeps=1)
    _wire(exp, refresh=60.0, hold=10)
    exp.present_stimulus(99)
    assert exp.window.flips == 0
