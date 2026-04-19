"""Brainflow recording -> MNE Raw -> BIDS-EEG via mne-bids.

The heavy lifting is all `mne-bids`. EEG-ExPy's role is to:

* Read the brainflow-style CSV we produced (timestamps,
  <channels...>, stim).
* Rebuild an ``mne.io.RawArray`` with correct channel types
  (``eeg`` for the data, ``stim`` for the marker column).
* Turn the marker column into an MNE events array plus the
  paradigm-supplied ``event_id`` mapping.
* Call ``mne_bids.write_raw_bids`` with a sensible ``BIDSPath``
  and the paradigm's ``bids_task_json`` metadata merged in.

Cross-platform: all filesystem paths use ``pathlib.Path``; no POSIX
assumptions. The EEG file format defaults to BrainVision (mne-bids
default) which works on every platform.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def to_bids(
    csv_path: str | Path,
    paradigm: Any,
    subject: str,
    session: str,
    bids_root: str | Path,
    device: str = "unicorn",
    run: str = "01",
    line_freq: float = 50.0,
    overwrite: bool = True,
) -> Path:
    """Convert a brainflow-style CSV recording to a BIDS-EEG dataset.

    Parameters
    ----------
    csv_path : path
        EEG recording CSV; columns ``timestamps, <channels...>, stim``.
    paradigm : object
        Any object exposing ``bids_task_name`` (str), ``bids_event_id``
        (``{int: str}``) and ``bids_task_json`` (dict). Our
        ``VisualFPVS…`` classes provide these; see
        ``eegnb.experiments.fpvs_stothart``.
    subject : str
        BIDS subject label (typically zero-padded, e.g. ``"01"``).
    session : str
        BIDS session label.
    bids_root : path
        Root of the BIDS dataset to create or append to.
    device : str
        Acquisition device name (recorded as ``Manufacturer`` in the
        sidecar). Default ``"unicorn"``.
    run : str
        BIDS run label. Defaults to ``"01"``.
    line_freq : float
        Power line frequency in Hz (``50`` for EU, ``60`` for US).
    overwrite : bool
        Whether to overwrite an existing run.

    Returns
    -------
    Path
        The BIDS root (so tests and callers can chain from it).
    """
    import mne
    from mne_bids import BIDSPath, write_raw_bids

    csv_path = Path(csv_path)
    bids_root = Path(bids_root)
    bids_root.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)
    timestamps = df["timestamps"].to_numpy()
    stim_col = (
        df["stim"].to_numpy() if "stim" in df.columns else np.zeros(len(df))
    )
    eeg_cols = [c for c in df.columns if c not in ("timestamps", "stim")]
    eeg_arr = df[eeg_cols].to_numpy().T  # (n_channels, n_samples)

    if len(timestamps) < 2:
        raise ValueError("CSV has too few samples to infer sample rate")
    sfreq = float(round(1.0 / np.median(np.diff(timestamps))))

    # Build the MNE Raw: EEG channels + a stim channel.
    ch_names = list(eeg_cols) + ["STI"]
    ch_types = ["eeg"] * len(eeg_cols) + ["stim"]
    data = np.vstack([eeg_arr, stim_col[np.newaxis, :]])

    info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types=ch_types)
    info["line_freq"] = line_freq
    raw = mne.io.RawArray(data, info, verbose=False)

    # Build events + event_id from the stim column (non-zero entries).
    events = _stim_column_to_events(stim_col)
    event_id = {
        paradigm.bids_event_id[code]: int(code)
        for code in paradigm.bids_event_id
        if (events[:, 2] == int(code)).any()
    }
    # mne-bids requires event_id to be non-empty when events are
    # supplied; skip the events path entirely if no matches.
    write_events = events if events.size and event_id else None
    write_event_id = event_id if write_events is not None else None

    bids_path = BIDSPath(
        subject=subject,
        session=session,
        task=paradigm.bids_task_name,
        run=run,
        datatype="eeg",
        root=bids_root,
    )
    write_raw_bids(
        raw,
        bids_path,
        events=write_events,
        event_id=write_event_id,
        overwrite=overwrite,
        allow_preload=True,
        format="BrainVision",
        verbose=False,
    )

    _merge_paradigm_metadata_into_sidecar(bids_path, paradigm, device)

    return bids_root


def _stim_column_to_events(stim: np.ndarray) -> np.ndarray:
    """Convert a dense stim channel to an MNE events array.

    MNE events: (sample, prev_id, new_id). We emit one row per non-zero
    sample in the stim column — good enough for discrete markers that
    don't overlap.
    """
    idxs = np.nonzero(stim)[0]
    if idxs.size == 0:
        return np.zeros((0, 3), dtype=int)
    return np.column_stack(
        [idxs.astype(int), np.zeros_like(idxs, dtype=int), stim[idxs].astype(int)]
    )


def _merge_paradigm_metadata_into_sidecar(
    bids_path, paradigm, device: str
) -> None:
    """Overlay the paradigm's `bids_task_json` onto the auto-generated
    ``*_eeg.json`` and stamp the manufacturer."""
    sidecar = bids_path.copy().update(
        suffix="eeg", extension=".json"
    ).fpath
    try:
        data = json.loads(Path(sidecar).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    paradigm_json = getattr(paradigm, "bids_task_json", {}) or {}
    data.update(paradigm_json)
    data.setdefault("Manufacturer", device)
    data.setdefault(
        "SoftwareFilters", "n/a (brainflow raw, no filter applied)"
    )
    Path(sidecar).write_text(json.dumps(data, indent=2))
