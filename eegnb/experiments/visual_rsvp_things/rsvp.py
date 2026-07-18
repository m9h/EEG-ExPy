"""THINGS RSVP paradigm (Alljoined-1.6M replication).

Rapid serial visual presentation of *unique* natural-object images from the
THINGS database for EEG-to-image decoding, matching the Alljoined-1.6M
acquisition protocol (arXiv 2508.18571): 100 ms image on / 100 ms blank
(5 Hz), one marker per image onset, order randomized.

Built on EEG-ExPy's frame-locked ``BaseExperiment`` loop — the presentation
duration must be exact, so this paradigm sets ``default_frame_locked = True``
and holds each image across its on-frames via ``_show_persistent``.

Unlike the FPVS paradigms (which repeat a small standard/deviant set) every
image here is unique, so the single stim column cannot encode image
identity. Identity per onset is written to a *presentation-order sidecar*
CSV next to the recording; downstream decoding joins EEG epochs to images by
onset order.

Stimuli are the THINGS subset shipped with Alljoined-1.6M. They are not
bundled with EEG-ExPy; point ``stim_dir`` at a directory containing
``stimuli.zip`` (``images/NNNNN.jpg``) and
``experiment_metadata_categories.parquet``. The default location is the
repo's gitignored ``data/alljoined-1.6M/``.
"""

from __future__ import annotations

import os
import random
import zipfile

import numpy as np
import pandas as pd
from psychopy import visual

from eegnb.experiments import Experiment

# Repo-root/data/alljoined-1.6M — this file lives at
# <repo>/eegnb/experiments/visual_rsvp_things/rsvp.py
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
DEFAULT_STIM_DIR = os.path.join(_REPO_ROOT, "data", "alljoined-1.6M")


class VisualRSVPThings(Experiment.BaseExperiment):
    """THINGS natural-image RSVP for EEG-to-image decoding.

    Parameters
    ----------
    duration : float | None
        Block duration in seconds. Only used to size the EEG buffer; the
        frame-locked loop actually runs exactly ``n_images`` trials. If
        None, derived from ``n_images`` and the on/off times.
    eeg : EEG | None
    save_fn : str | None
    stim_dir : str | None
        Directory holding ``stimuli.zip`` and
        ``experiment_metadata_categories.parquet``. Defaults to the repo's
        ``data/alljoined-1.6M/``.
    n_images : int
        Number of unique images to present this block.
    on_ms, off_ms : float
        Image-on and blank durations in milliseconds. Alljoined-1.6M uses
        100 / 100.
    partition : str | None
        Filter the metadata to one partition (``"stim_train"`` /
        ``"stim_test"``). None uses all images.
    seed : int
        Seed for the image-order shuffle (reproducible runs).
    image_size_deg : float
        On-screen image size in degrees (square).
    """

    name = "Visual RSVP THINGS"
    __title__ = "THINGS RSVP — natural-image EEG decoding (Alljoined-1.6M)"

    # BIDS-EEG metadata lives in eegnb.bids.paradigms so non-PsychoPy
    # callers (CLI, exporters) can read it without loading PsychoPy.
    from eegnb.bids.paradigms import RSVP_THINGS as _bids
    bids_task_name = _bids.bids_task_name
    bids_event_id = _bids.bids_event_id
    bids_task_json = _bids.bids_task_json
    del _bids

    # Presentation duration must be exact for clean decoding epochs.
    default_frame_locked = True

    # Single onset marker — every image gets code 1; identity comes from the
    # presentation-order sidecar, not the event code.
    ONSET_MARKER = 1

    def __init__(
        self,
        duration: float | None = None,
        eeg=None,
        save_fn=None,
        stim_dir: str | None = None,
        n_images: int = 200,
        on_ms: float = 100.0,
        off_ms: float = 100.0,
        partition: str | None = "stim_train",
        seed: int = 1,
        image_size_deg: float = 10.0,
        photodiode: bool = False,
        photodiode_corner: str = "top-left",
        photodiode_size: float = 0.2,
        use_vr: bool = False,
        use_fullscr: bool = True,
        screen_num: int = 0,
    ):
        on_s = on_ms / 1000.0
        off_s = off_ms / 1000.0
        if duration is None:
            # +10 s margin so the EEG ring buffer comfortably spans the block.
            duration = n_images * (on_s + off_s) + 10.0

        super().__init__(
            exp_name=self.name,
            duration=duration,
            eeg=eeg,
            save_fn=save_fn,
            n_trials=n_images,
            iti=off_s,
            soa=on_s,
            jitter=0.0,
            use_vr=use_vr,
            use_fullscr=use_fullscr,
            screen_num=screen_num,
        )

        self.stim_dir = stim_dir or DEFAULT_STIM_DIR
        self.n_images = n_images
        self.on_ms = on_ms
        self.off_ms = off_ms
        self.partition = partition
        self.seed = seed
        self.image_size_deg = image_size_deg
        self.photodiode = photodiode
        self.photodiode_corner = photodiode_corner
        self.photodiode_size = photodiode_size
        self.photodiode_patch = None

        self.markernames = {1: "imageOnset"}
        # Populated in load_stimulus: one row per trial in presentation order.
        self.order: pd.DataFrame | None = None

    # ------------------------------------------------------------------ #
    # Stimulus loading
    # ------------------------------------------------------------------ #
    def _resolve_sources(self) -> tuple[str, str, str]:
        zip_path = os.path.join(self.stim_dir, "stimuli.zip")
        meta_path = os.path.join(
            self.stim_dir, "experiment_metadata_categories.parquet"
        )
        cache_dir = os.path.join(self.stim_dir, "images_cache")
        if not os.path.isfile(zip_path):
            raise FileNotFoundError(
                f"THINGS stimuli.zip not found at {zip_path}. Point stim_dir "
                "at the Alljoined-1.6M data directory."
            )
        if not os.path.isfile(meta_path):
            raise FileNotFoundError(
                f"metadata parquet not found at {meta_path}."
            )
        return zip_path, meta_path, cache_dir

    def load_stimulus(self):
        zip_path, meta_path, cache_dir = self._resolve_sources()

        meta = pd.read_parquet(meta_path).reset_index(drop=True)
        if self.partition:
            meta = meta[meta["partition"] == self.partition].reset_index(
                drop=True
            )
        if len(meta) == 0:
            raise ValueError(
                f"no images in partition {self.partition!r} of {meta_path}"
            )

        rng = random.Random(self.seed)
        idx = list(range(len(meta)))
        rng.shuffle(idx)
        chosen = idx[: min(self.n_images, len(idx))]

        os.makedirs(cache_dir, exist_ok=True)
        zf = zipfile.ZipFile(zip_path)
        rows = []
        self.stimuli = []
        for trial, i in enumerate(chosen):
            row = meta.iloc[i]
            fname = row["fname"]
            dest = os.path.join(cache_dir, fname)
            if not os.path.exists(dest):
                with zf.open("images/" + fname) as src, open(dest, "wb") as out:
                    out.write(src.read())
            self.stimuli.append(
                visual.ImageStim(
                    win=self.window,
                    image=dest,
                    size=self.image_size_deg,
                    units="deg",
                )
            )
            rows.append(
                dict(
                    trial=trial,
                    marker=self.ONSET_MARKER,
                    fname=fname,
                    category_name=row.get("category_name"),
                    category_num=int(row.get("category_num", -1)),
                    super_category=row.get("super_category"),
                )
            )
        zf.close()

        # Actual number of trials may be capped by the pool size.
        self.n_trials = len(self.stimuli)
        self.order = pd.DataFrame(rows)

        # Central fixation cross shown during the blank ITI frames.
        self.fixation = visual.TextStim(
            win=self.window, text="+", color=[1, 1, 1], height=1.0, units="deg"
        )

        # Optional photodiode patch: a square in a screen corner that goes
        # white for exactly the image on-frames and black for the blanks.
        # A photodiode taped over it turns the true on-screen luminance
        # transition into a signal we can timestamp externally — the only
        # way to measure real marker-to-photon latency. It is always drawn
        # (autoDraw) and only its fill colour toggles, so the black state
        # gives maximum contrast against the white state.
        if self.photodiode:
            half = self.photodiode_size / 2.0
            corners = {
                "top-left": (-1 + half, 1 - half),
                "top-right": (1 - half, 1 - half),
                "bottom-left": (-1 + half, -1 + half),
                "bottom-right": (1 - half, -1 + half),
            }
            if self.photodiode_corner not in corners:
                raise ValueError(
                    f"photodiode_corner must be one of {sorted(corners)}, "
                    f"got {self.photodiode_corner!r}"
                )
            self.photodiode_patch = visual.Rect(
                win=self.window,
                width=self.photodiode_size,
                height=self.photodiode_size,
                pos=corners[self.photodiode_corner],
                units="norm",
                fillColor=[-1, -1, -1],
                lineColor=None,
            )
            self.photodiode_patch.setAutoDraw(True)

        return self.stimuli

    def present_iti(self):
        """Blank ITI, but keep a fixation cross up for the participant."""
        if self._active_stim is not None:
            self._active_stim.setAutoDraw(False)
            self._active_stim = None
        if self.photodiode_patch is not None:
            self.photodiode_patch.fillColor = [-1, -1, -1]  # black
        self.fixation.draw()
        self.window.flip()

    def present_stimulus(self, idx: int):
        # Photodiode patch goes white on exactly the same flip as the image,
        # so the light transition marks true stimulus onset.
        if self.photodiode_patch is not None:
            self.photodiode_patch.fillColor = [1, 1, 1]  # white
        # Hold the image for every on-frame of this cycle; a plain
        # draw()+flip() would blank after one frame under the frame-locked
        # loop (see BaseExperiment._show_persistent).
        self._show_persistent(self.stimuli[idx], marker=self.ONSET_MARKER)

    # ------------------------------------------------------------------ #
    # Run + presentation-order sidecar
    # ------------------------------------------------------------------ #
    def run(self, instructions=True, frame_locked=None, refresh_hz=None):
        super().run(
            instructions=instructions,
            frame_locked=frame_locked,
            refresh_hz=refresh_hz,
        )
        self._write_presentation_log()

    def _write_presentation_log(self):
        if self.order is None:
            return
        if self.save_fn:
            sidecar = os.path.splitext(self.save_fn)[0] + "_presentation.csv"
        else:
            runs = os.path.join(self.stim_dir, "runs")
            os.makedirs(runs, exist_ok=True)
            sidecar = os.path.join(runs, "rsvp_dryrun_presentation.csv")
        self.order.to_csv(sidecar, index=False)
        print(f"[rsvp] presentation order -> {sidecar}")
