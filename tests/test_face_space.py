"""Tests for the face-space distinctiveness paradigm (no display).

The pixel-space morph builder needs only numpy + Pillow + the bundled face
set, so its norm-based geometry is pinned deterministically here.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

from eegnb.bids import paradigms as bids_paradigms


def test_registered_in_bids_by_name():
    assert "visual-face-space" in bids_paradigms.BY_NAME


def test_bids_metadata_shape():
    meta = bids_paradigms.FACE_SPACE
    assert meta.bids_task_name == "faceSpaceDistinctiveness"
    assert isinstance(meta.bids_event_id, dict) and meta.bids_event_id
    required = {"TaskName", "Instructions", "TaskDescription"}
    assert required.issubset(meta.bids_task_json.keys())
    desc = meta.bids_task_json["TaskDescription"]
    assert "Valentine" in desc and "N250" in desc


def test_class_importable_and_in_cli():
    pytest.importorskip("psychopy")
    import eegnb.experiments
    from eegnb.cli.utils import get_experiments

    cls = eegnb.experiments.VisualFaceSpace
    assert cls.__name__ == "VisualFaceSpace"
    assert cls.channels_of_interest[:2] == ("PO7", "PO8")
    assert "visual-face-space" in get_experiments()


def _make(tmp_path, **kw):
    pytest.importorskip("psychopy")
    from eegnb.experiments.visual_face_space.face_space import VisualFaceSpace
    kw.setdefault("cache_dir", str(tmp_path))
    return VisualFaceSpace(**kw)


def test_default_levels_and_markers():
    exp = _make(tmp_path=_tmp())
    assert exp.levels == [0.0, 0.5, 1.0, 1.5]
    assert exp.markernames == {1: "level0", 2: "level1", 3: "level2", 4: "level3"}


def _tmp():
    import tempfile
    from pathlib import Path
    return Path(tempfile.mkdtemp(prefix="fs_"))


def test_pixel_space_morph_geometry(tmp_path):
    """coef=1 reproduces the source; coef=0 is the pixel mean; distance from
    the norm grows monotonically with the coefficient."""
    from PIL import Image

    exp = _make(tmp_path, levels=[0.0, 1.0, 1.5], n_faces=3)
    specs = exp._build_pixel_space_morphs()
    assert len(specs) == 3 * 3  # 3 faces x 3 levels
    assert sorted({s["marker"] for s in specs}) == [1, 2, 3]

    px = exp.img_px
    paths = exp._gather(exp.source_dir)[:3]
    arrs = [
        np.asarray(Image.open(p).convert("L").resize((px, px)), dtype=np.float32)
        for p in paths
    ]
    mean = np.mean(arrs, axis=0)

    s0 = [s for s in specs if os.path.basename(paths[0]) in s["path"]]
    by_coef = {
        s["coef"]: np.asarray(Image.open(s["path"]).convert("L"), dtype=np.float32)
        for s in s0
    }
    assert np.allclose(by_coef[1.0], np.clip(arrs[0], 0, 255), atol=1)
    assert np.allclose(by_coef[0.0], np.clip(mean, 0, 255), atol=1)
    var = {c: float(np.var(by_coef[c] - mean)) for c in (0.0, 1.0, 1.5)}
    assert var[0.0] < var[1.0] < var[1.5]


def test_missing_source_dir_raises(tmp_path):
    exp = _make(tmp_path, source_dir=str(tmp_path / "nope"))
    with pytest.raises(FileNotFoundError):
        exp._build_pixel_space_morphs()


# --- present_stimulus draw/marker (mocked window) ---------------------------

class _FakeStim:
    def __init__(self):
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


def test_present_stimulus_draws_and_marks_level(tmp_path):
    exp = _make(tmp_path, levels=[0.0, 1.0])
    exp.n_trials = 3
    exp.parameter = np.array([2, 1, 2], dtype=int)  # level markers
    exp.stimuli = [_FakeStim(), _FakeStim(), _FakeStim()]
    exp.fixation = _FakeStim()
    exp.window = _FakeWindow()
    exp.eeg = _FakeEEG()

    exp.present_stimulus(0)
    assert exp.stimuli[0].drawn == 1
    assert exp.window.flips == 1
    # muselsl wraps the marker in a list; marker is the level code
    assert exp.eeg.markers == [[2]]


def test_present_stimulus_out_of_range_noop(tmp_path):
    exp = _make(tmp_path)
    exp.n_trials = 2
    exp.stimuli = [_FakeStim(), _FakeStim()]
    exp.window = _FakeWindow()
    exp.eeg = None
    exp.present_stimulus(50)
    assert exp.window.flips == 0
