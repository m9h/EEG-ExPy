"""TDD tests for the `eegnb to-bids` CLI command.

Drives a brainflow-style CSV through the click CLI and asserts the
resulting BIDS-EEG dataset layout. Cross-platform: paths via pathlib
and tmp_path (no /tmp).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from click.testing import CliRunner

pytest.importorskip("mne_bids")


def _write_fake_brainflow_csv(path: Path, sfreq: int = 250, seconds: int = 5) -> None:
    n = sfreq * seconds
    t = np.linspace(0, seconds, n, endpoint=False) + 1_700_000_000.0
    rng = np.random.default_rng(0)
    eeg = rng.standard_normal((n, 8))
    stim = np.zeros(n)
    for frame, code in [(sfreq, 1), (2 * sfreq, 1), (3 * sfreq, 2)]:
        stim[frame] = code
    df = pd.DataFrame(
        np.column_stack([t, eeg, stim]),
        columns=[
            "timestamps", "Fz", "C3", "Cz", "C4",
            "Pz", "PO7", "Oz", "PO8", "stim",
        ],
    )
    df.to_csv(path, index=False)


def test_cli_to_bids_round_trip(tmp_path):
    """`eegnb to-bids` on a Stothart CSV should emit a BIDS-EEG dataset
    rooted at the requested directory with the task-specific layout."""
    from eegnb.cli.bids_cmd import to_bids_cmd

    csv = tmp_path / "recording.csv"
    _write_fake_brainflow_csv(csv)
    bids_root = tmp_path / "bids"

    runner = CliRunner()
    result = runner.invoke(
        to_bids_cmd,
        [
            "--csv", str(csv),
            "--paradigm", "visual-fpvs-stothart",
            "--subject", "01",
            "--session", "test01",
            "--bids-root", str(bids_root),
        ],
    )
    assert result.exit_code == 0, result.output

    eeg_dir = bids_root / "sub-01" / "ses-test01" / "eeg"
    stem = "sub-01_ses-test01_task-fastballStothart_run-01"
    assert (eeg_dir / f"{stem}_eeg.json").exists()
    assert (eeg_dir / f"{stem}_events.tsv").exists()


def test_cli_to_bids_unknown_paradigm_fails_cleanly(tmp_path):
    """Unknown paradigm names should fail with a non-zero exit and a
    message listing the valid choices, not a stack trace."""
    from eegnb.cli.bids_cmd import to_bids_cmd

    csv = tmp_path / "recording.csv"
    _write_fake_brainflow_csv(csv)

    runner = CliRunner()
    result = runner.invoke(
        to_bids_cmd,
        [
            "--csv", str(csv),
            "--paradigm", "nope-not-a-paradigm",
            "--subject", "01",
            "--session", "test01",
            "--bids-root", str(tmp_path / "bids"),
        ],
    )
    assert result.exit_code != 0
    # click renders --paradigm as a Choice; the error mentions valid options.
    assert "visual-fpvs-stothart" in result.output
