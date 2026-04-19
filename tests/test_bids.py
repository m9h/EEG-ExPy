"""TDD tests for the eegnb.bids converter.

Uses a small synthetic brainflow-style CSV and a lightweight paradigm
stand-in. Asserts the BIDS-EEG folder layout, filenames, and that the
resulting dataset passes mne-bids's own validator helpers.

Cross-platform: all paths built via pathlib; no POSIX-only assumptions.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("mne_bids")


class _FakeParadigm:
    """Duck-typed paradigm stand-in exposing the BIDS attrs we need."""

    name = "Fake Fastball"
    bids_task_name = "fakeFastball"
    bids_task_json = {
        "TaskName": "Fake Fastball (test)",
        "TaskDescription": "Synthetic test paradigm.",
        "Instructions": "Fixate centre.",
    }
    bids_event_id = {1: "standard", 2: "oddball"}


def _write_fake_brainflow_csv(path: Path, sfreq: int = 250, seconds: int = 5) -> None:
    """Write a brainflow-style CSV with timestamps, 8 EEG channels, and stim."""
    n = sfreq * seconds
    t = np.linspace(0, seconds, n, endpoint=False) + 1_700_000_000.0
    rng = np.random.default_rng(0)
    eeg = rng.standard_normal((n, 8))
    stim = np.zeros(n)
    # Drop a few markers through the recording.
    for frame, code in [(sfreq, 1), (2 * sfreq, 1), (3 * sfreq, 2)]:
        stim[frame] = code
    df = pd.DataFrame(
        np.column_stack([t, eeg, stim]),
        columns=["timestamps", "Fz", "C3", "Cz", "C4", "Pz", "PO7", "Oz", "PO8", "stim"],
    )
    df.to_csv(path, index=False)


def test_to_bids_produces_expected_layout(tmp_path):
    """Calling eegnb.bids.to_bids on a brainflow CSV + paradigm stub
    should produce the canonical BIDS-EEG folder with the
    task-specific sidecar and events.tsv populated."""
    from eegnb.bids import to_bids

    csv = tmp_path / "recording.csv"
    _write_fake_brainflow_csv(csv)

    bids_root = tmp_path / "bids"
    out = to_bids(
        csv_path=csv,
        paradigm=_FakeParadigm(),
        subject="01",
        session="test01",
        bids_root=bids_root,
        device="unicorn",
    )
    assert bids_root.exists()
    assert (bids_root / "dataset_description.json").exists()
    assert (bids_root / "participants.tsv").exists()

    eeg_dir = bids_root / "sub-01" / "ses-test01" / "eeg"
    assert eeg_dir.is_dir()
    stem = "sub-01_ses-test01_task-fakeFastball_run-01"
    # At least the three core sidecar / data files must exist
    # (extension on the EEG file is driven by mne-bids' preferred format).
    assert (eeg_dir / f"{stem}_eeg.json").exists()
    assert (eeg_dir / f"{stem}_channels.tsv").exists()
    assert (eeg_dir / f"{stem}_events.tsv").exists()
    assert out == bids_root


def test_events_tsv_contains_paradigm_codes(tmp_path):
    """events.tsv must map our marker codes to the paradigm-supplied
    trial_type labels."""
    from eegnb.bids import to_bids

    csv = tmp_path / "recording.csv"
    _write_fake_brainflow_csv(csv)

    bids_root = tmp_path / "bids"
    to_bids(
        csv_path=csv, paradigm=_FakeParadigm(),
        subject="01", session="test01", bids_root=bids_root,
        device="unicorn",
    )
    events = pd.read_csv(
        bids_root / "sub-01" / "ses-test01" / "eeg"
        / "sub-01_ses-test01_task-fakeFastball_run-01_events.tsv",
        sep="\t",
    )
    assert {"onset", "duration", "trial_type"}.issubset(events.columns)
    trial_types = set(events["trial_type"])
    # At least one standard and one oddball should be present per
    # our marker pattern.
    assert "standard" in trial_types
    assert "oddball" in trial_types


def test_task_json_carries_paradigm_metadata(tmp_path):
    from eegnb.bids import to_bids

    csv = tmp_path / "recording.csv"
    _write_fake_brainflow_csv(csv)

    bids_root = tmp_path / "bids"
    to_bids(
        csv_path=csv, paradigm=_FakeParadigm(),
        subject="01", session="test01", bids_root=bids_root,
        device="unicorn",
    )
    json_path = (bids_root / "sub-01" / "ses-test01" / "eeg"
                 / "sub-01_ses-test01_task-fakeFastball_run-01_eeg.json")
    data = json.loads(json_path.read_text())
    # mne-bids populates required fields; our paradigm metadata must
    # be merged into the sidecar.
    assert data["TaskName"] == "Fake Fastball (test)"
    assert "Synthetic test paradigm" in data.get("TaskDescription", "")
