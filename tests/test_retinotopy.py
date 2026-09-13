"""Tests for the SSVEP sector-retinotopy paradigm.

Verify, without a display:

- BIDS metadata is well-formed and registered in the lazy loader / BY_NAME
- Block-marker plumbing for both run modes
- The frequency -> frame-hold snapping math
- The checkerboard texture is contrast-balanced (so a reversal is a true
  black/white swap, not a drift toward mean grey)
- The core timing guarantee: ``present_stimulus`` draws each sector's patch
  once per frame and toggles its contrast on exactly the frame-hold schedule,
  so the realised reversal rate equals refresh / hold. This is the property
  the whole SSVEP-tagging analysis depends on, so it is pinned deterministically
  with a mock window rather than left to an integration run.

Real Window/flip presentation is covered by the manual windowed dry-run, not here.
"""

from __future__ import annotations

import numpy as np
import pytest

from eegnb.bids import paradigms as bids_paradigms


# --- BIDS metadata ----------------------------------------------------------

def test_registered_in_bids_by_name():
    assert "visual-retinotopy-ssvep" in bids_paradigms.BY_NAME


def test_bids_metadata_shape():
    meta = bids_paradigms.RETINOTOPY_SSVEP
    assert meta.bids_task_name == "retinotopySsvep"
    assert isinstance(meta.bids_event_id, dict) and meta.bids_event_id
    assert all(
        isinstance(k, int) and isinstance(v, str)
        for k, v in meta.bids_event_id.items()
    )
    # quadrants + the all-sectors multiplex marker
    assert set(meta.bids_event_id) == {1, 2, 3, 4, 5}
    assert meta.bids_event_id[5] == "multiplexBlock"
    required = {"TaskName", "Instructions", "TaskDescription"}
    assert required.issubset(meta.bids_task_json.keys())
    # Scope honesty: it must not claim to be pRF mapping.
    assert "NOT" in meta.bids_task_json["TaskDescription"]
    assert "pRF" in meta.bids_task_json["TaskDescription"] or \
        "population-receptive-field" in meta.bids_task_json["TaskDescription"]


# --- checkerboard texture (pure) --------------------------------------------

def test_checkerboard_is_contrast_balanced_and_reverses():
    from eegnb.experiments.visual_retinotopy.retinotopy import _checkerboard

    cb = _checkerboard(n_checks=8, res=256)
    assert cb.shape == (256, 256)
    assert set(np.unique(cb).tolist()) == {-1.0, 1.0}
    # Zero mean: a contrast flip swaps black<->white, never averages to grey.
    assert abs(cb.mean()) < 1e-9
    # Adjacent checks differ.
    assert cb[0, 0] != cb[0, 256 // 8]


# --- class registration (requires PsychoPy) ---------------------------------

def test_class_importable_through_lazy_loader():
    pytest.importorskip("psychopy")
    import eegnb.experiments

    cls = eegnb.experiments.VisualRetinotopySSVEP
    assert cls.__name__ == "VisualRetinotopySSVEP"
    for attr in ("bids_task_name", "bids_event_id", "bids_task_json",
                 "channels_of_interest"):
        assert hasattr(cls, attr)
    assert cls.default_frame_locked is False  # time-based loop, not hold loop


def test_in_cli_experiment_registry():
    pytest.importorskip("psychopy")
    from eegnb.cli.utils import get_experiments

    assert "visual-retinotopy-ssvep" in get_experiments()


# --- block-marker plumbing (requires PsychoPy for the class) ----------------

def _make(**kw):
    pytest.importorskip("psychopy")
    from eegnb.experiments.visual_retinotopy.retinotopy import VisualRetinotopySSVEP
    return VisualRetinotopySSVEP(**kw)


def test_multiplex_every_block_is_multiplex_marker():
    exp = _make(mode="multiplex", n_blocks=4)
    assert list(exp.parameter) == [5, 5, 5, 5]
    assert exp.n_trials == 4


def test_sequential_cycles_through_quadrant_markers():
    exp = _make(mode="sequential", n_blocks=6)
    assert list(exp.parameter) == [1, 2, 3, 4, 1, 2]


def test_bad_mode_rejected():
    pytest.importorskip("psychopy")
    from eegnb.experiments.visual_retinotopy.retinotopy import VisualRetinotopySSVEP
    with pytest.raises(ValueError):
        VisualRetinotopySSVEP(mode="diagonal")


def test_frequency_snaps_to_integer_divisor_of_refresh():
    """Targets must snap to refresh/hold so each tag lands in one FFT bin."""
    # Mirror the load_stimulus snapping arithmetic for a 60 Hz panel.
    refresh = 60.0
    for target, hold, actual in [
        (15.0, 4, 15.0),
        (12.0, 5, 12.0),
        (10.0, 6, 10.0),
        (8.571, 7, 60.0 / 7),
    ]:
        h = max(2, int(round(refresh / target)))
        assert h == hold
        assert refresh / h == pytest.approx(actual)


# --- the core timing guarantee: per-frame contrast schedule -----------------

class _FakePatch:
    def __init__(self):
        self.contrast = None
        self.drawn = []  # contrast value recorded at each draw()

    def draw(self):
        self.drawn.append(self.contrast)


class _FakeFixation:
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


def _wire_for_present(exp, refresh=60.0, block_s=1.0, eeg=None):
    """Inject fakes so present_stimulus can run with no display."""
    exp._refresh = refresh
    exp.block_s = block_s
    exp.window = _FakeWindow()
    exp.fixation = _FakeFixation()
    exp.eeg = eeg
    exp._patches = [_FakePatch() for _ in exp.sectors]
    # hold frames as load_stimulus would compute them
    exp._hold_frames = [
        max(2, int(round(refresh / s["target_freq"]))) for s in exp.sectors
    ]
    return exp


def _expected_contrast_sequence(n_frames, hold):
    return [1.0 if (f // hold) % 2 == 0 else -1.0 for f in range(n_frames)]


def test_multiplex_draws_every_sector_on_its_own_reversal_schedule():
    exp = _make(mode="multiplex", n_blocks=1, block_s=1.0)
    _wire_for_present(exp, refresh=60.0, block_s=1.0)
    exp.present_stimulus(0)

    n_frames = 60  # refresh * block_s
    assert exp.window.flips == n_frames
    # Every sector was drawn once per frame, each toggling on its own hold.
    for patch, hold in zip(exp._patches, exp._hold_frames):
        assert len(patch.drawn) == n_frames
        assert patch.drawn == _expected_contrast_sequence(n_frames, hold)


def test_multiplex_realised_reversal_rate_matches_tag():
    exp = _make(mode="multiplex", n_blocks=1, block_s=2.0)
    _wire_for_present(exp, refresh=60.0, block_s=2.0)
    exp.present_stimulus(0)
    n_frames = 120
    for patch, hold, sector in zip(exp._patches, exp._hold_frames, exp.sectors):
        seq = np.array(patch.drawn)
        # count sign changes = number of reversals over the block
        reversals = int(np.sum(seq[1:] != seq[:-1]))
        measured_hz = reversals / 2.0  # block_s == 2 s
        assert measured_hz == pytest.approx(60.0 / hold, abs=0.5)


def test_sequential_draws_only_the_active_sector():
    exp = _make(mode="sequential", n_blocks=4, block_s=1.0)
    _wire_for_present(exp, refresh=60.0, block_s=1.0)
    # Block 0 -> parameter[0] == sectors[0]['marker'] == 1 -> only sector 0 active
    exp.present_stimulus(0)
    assert len(exp._patches[0].drawn) == 60
    for patch in exp._patches[1:]:
        assert patch.drawn == []


def test_marker_pushed_once_per_block_as_scalar_for_brainflow():
    exp = _make(mode="sequential", n_blocks=4, block_s=0.5)
    eeg = _FakeEEG()
    _wire_for_present(exp, refresh=60.0, block_s=0.5, eeg=eeg)
    exp.present_stimulus(0)
    assert eeg.markers == [1]  # sector-0 marker, scalar (not a list) for brainflow


def test_marker_wrapped_in_list_for_muselsl():
    exp = _make(mode="multiplex", n_blocks=1, block_s=0.2)
    eeg = _FakeEEG()
    eeg.backend = "muselsl"
    _wire_for_present(exp, refresh=60.0, block_s=0.2, eeg=eeg)
    exp.present_stimulus(0)
    assert eeg.markers == [[5]]  # multiplex marker, list-wrapped for muselsl


def test_present_stimulus_out_of_range_is_noop():
    exp = _make(mode="multiplex", n_blocks=1, block_s=0.2)
    _wire_for_present(exp, refresh=60.0, block_s=0.2)
    exp.present_stimulus(99)  # beyond n_blocks
    assert exp.window.flips == 0
