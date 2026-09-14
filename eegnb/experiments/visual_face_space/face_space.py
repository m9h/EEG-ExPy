"""Face-space distinctiveness continuum (norm-based coding).

Presents face identities at graded distances from the *average* (norm)
face — the manipulation at the heart of Valentine's (1991) face-space and
the norm-based coding account (Leopold et al. 2001; Rhodes & Jeffery 2006).
A morph coefficient ``c`` places each face on the identity vector through
the norm:

    stimulus = mean + c * (identity - mean)

so ``c = 0`` is the average face, ``c = 1`` the veridical identity, ``c > 1``
a caricature (extrapolated beyond the original), and ``c < 0`` an "anti-face"
(useful for adaptation designs). Distance from the norm parametrically
modulates the **P200** (typicality), **N250** (distinctiveness / identity
encoding) and **N170** — larger identity responses for more distinctive /
caricatured faces (Schulz, Kaufmann & Schweinberger 2012; the fMRI
norm-based analogue is Loffler et al. 2005).

Each trial is one face at one distance level, presented as a discrete ERP
trial (stimulus on, then a jittered fixation ITI). The event code indexes
the distance level; per-onset identity and coefficient go to a
presentation-order sidecar CSV, mirroring the RSVP paradigm.

Stimuli
-------
Two sources:

* **Pre-rendered continuum** (recommended for real data): point ``stim_dir``
  at a directory of ``level_<k>/`` subfolders of images produced by a proper
  face-space tool — webmorphR / Psychomorph (2D landmark morphs) or a 3D
  morphable model (Basel / FLAME). These are shape-normalized and
  publishable.
* **Pixel-space fallback** (default, for pipeline bring-up): builds the
  continuum by morphing each image of a source face set toward/beyond their
  *pixel* mean. This is a crude, explicitly NOT shape-normalized
  approximation — fine to validate the recording/analysis pipeline, not a
  substitute for real morphs. Defaults to the bundled N170 face set.
"""

from __future__ import annotations

import os
import random
import tempfile
from glob import glob
from time import time

import numpy as np
from pandas import DataFrame
from psychopy import visual

from eegnb.experiments import Experiment
from eegnb.stimuli import FACE_HOUSE


class VisualFaceSpace(Experiment.BaseExperiment):
    """Norm-based face-space distinctiveness continuum.

    Parameters
    ----------
    duration : float | None
        Total run seconds. If None, derived from the trial count and timing.
    eeg : EEG | None
    save_fn : str | None
    levels : sequence[float] | None
        Morph coefficients (distance-from-mean). Default
        ``[0.0, 0.5, 1.0, 1.5]`` → mean / sub-veridical / veridical /
        caricature. The event code is the 1-based level index.
    stim_dir : str | None
        Pre-rendered continuum root with ``level_<k>/`` subfolders. When
        given (and non-empty) it is used instead of the pixel-space fallback;
        ``levels`` must then match the number of ``level_<k>`` folders.
    source_dir : str | None
        Face set the pixel-space fallback builds its norm from. Defaults to
        the bundled N170 faces.
    n_faces : int | None
        Cap on source identities/images used by the fallback (None = all).
    n_trials : int | None
        Total trials. None = every (face, level) once, shuffled.
    stim_s, iti_s, jitter : float
        Stimulus-on seconds, base ITI, and added uniform jitter.
    image_size_deg : float
        On-screen face size (square, degrees).
    img_px : int
        Cache/morph resolution in pixels (fallback only).
    seed : int
        Shuffle + morph reproducibility.
    cache_dir : str | None
        Where fallback morphs are written. Defaults to a temp subfolder.
    use_fullscr, screen_num : passed through to BaseExperiment.
    """

    name = "Visual Face Space"
    __title__ = "Face-space distinctiveness continuum (norm-based coding)"

    from eegnb.bids.paradigms import FACE_SPACE as _bids
    bids_task_name = _bids.bids_task_name
    bids_event_id = _bids.bids_event_id
    bids_task_json = _bids.bids_task_json
    del _bids

    # Discrete ERP trials with a jittered ITI -> time-based loop (jitter is
    # only applied there), stimulus persists on-screen through the SOA.
    default_frame_locked = False

    # Face ERPs: N170 lateral-posterior (PO7/PO8), P200/N250 more central.
    channels_of_interest = ("PO7", "PO8", "Oz")

    def __init__(
        self,
        duration: float | None = None,
        eeg=None,
        save_fn=None,
        levels=None,
        stim_dir: str | None = None,
        source_dir: str | None = None,
        n_faces: int | None = None,
        n_trials: int | None = None,
        stim_s: float = 0.3,
        iti_s: float = 0.8,
        jitter: float = 0.4,
        image_size_deg: float = 8.0,
        img_px: int = 256,
        seed: int = 1,
        cache_dir: str | None = None,
        use_fullscr: bool = True,
        screen_num: int = 0,
    ):
        self.levels = list(levels) if levels is not None else [0.0, 0.5, 1.0, 1.5]
        self.stim_dir = stim_dir
        self.source_dir = source_dir or os.path.join(FACE_HOUSE, "faces")
        self.n_faces = n_faces
        self.stim_s = stim_s
        self.image_size_deg = image_size_deg
        self.img_px = img_px
        self.seed = seed
        self.cache_dir = cache_dir or os.path.join(
            tempfile.gettempdir(), "eegnb_face_space"
        )

        # Provisional trial count; finalised in load_stimulus once the pool
        # size is known.
        provisional = n_trials
        if provisional is None:
            provisional = 40  # placeholder for buffer sizing pre-load
        if duration is None:
            duration = provisional * (stim_s + iti_s + jitter) + 5.0

        super().__init__(
            exp_name=self.name,
            duration=duration,
            eeg=eeg,
            save_fn=save_fn,
            n_trials=provisional,
            iti=iti_s,
            soa=stim_s,
            jitter=jitter,
            use_vr=False,
            use_fullscr=use_fullscr,
            screen_num=screen_num,
        )

        self._requested_n_trials = n_trials
        self.markernames = {
            i + 1: f"level{i}" for i in range(len(self.levels))
        }
        self.order: DataFrame | None = None
        self.fixation = None

    # ------------------------------------------------------------------ #
    # Stimulus loading
    # ------------------------------------------------------------------ #
    def _gather(self, directory: str) -> list[str]:
        return sorted(
            p
            for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp")
            for p in glob(os.path.join(directory, ext))
        )

    def _build_pixel_space_morphs(self) -> list[dict]:
        """Fallback: morph each source face toward/beyond the pixel mean."""
        from PIL import Image

        paths = self._gather(self.source_dir)
        if not paths:
            raise FileNotFoundError(
                f"no source faces in {self.source_dir}"
            )
        if self.n_faces:
            paths = paths[: self.n_faces]

        px = self.img_px
        arrays = []
        for p in paths:
            im = Image.open(p).convert("L").resize((px, px))
            arrays.append(np.asarray(im, dtype=np.float32))
        mean = np.mean(arrays, axis=0)

        os.makedirs(self.cache_dir, exist_ok=True)
        specs = []
        for p, arr in zip(paths, arrays):
            identity = os.path.splitext(os.path.basename(p))[0].split("_")[0]
            for li, coef in enumerate(self.levels):
                morph = np.clip(mean + coef * (arr - mean), 0, 255).astype(
                    np.uint8
                )
                dest = os.path.join(
                    self.cache_dir,
                    f"{identity}_{os.path.basename(p)}_lvl{li}.png",
                )
                # 2-D uint8 array is inferred as an "L" (grayscale) image;
                # the explicit mode= arg is deprecated in Pillow 11+.
                Image.fromarray(morph).save(dest)
                specs.append(
                    dict(
                        path=dest, marker=li + 1, identity=identity,
                        coef=coef, level=li,
                    )
                )
        return specs

    def _load_prerendered(self) -> list[dict]:
        """Use pre-rendered level_<k>/ subfolders under stim_dir."""
        specs = []
        for li in range(len(self.levels)):
            sub = os.path.join(self.stim_dir, f"level_{li}")
            imgs = self._gather(sub)
            if not imgs:
                raise FileNotFoundError(
                    f"pre-rendered continuum: no images in {sub}"
                )
            for p in imgs:
                identity = os.path.splitext(os.path.basename(p))[0].split("_")[0]
                specs.append(
                    dict(
                        path=p, marker=li + 1, identity=identity,
                        coef=self.levels[li], level=li,
                    )
                )
        return specs

    def load_stimulus(self):
        use_prerendered = bool(
            self.stim_dir
            and os.path.isdir(self.stim_dir)
            and glob(os.path.join(self.stim_dir, "level_*"))
        )
        specs = (
            self._load_prerendered() if use_prerendered
            else self._build_pixel_space_morphs()
        )

        rng = random.Random(self.seed)
        rng.shuffle(specs)
        if self._requested_n_trials is not None:
            # Repeat/truncate to the requested count.
            if self._requested_n_trials <= len(specs):
                specs = specs[: self._requested_n_trials]
            else:
                reps = self._requested_n_trials // len(specs) + 1
                specs = (specs * reps)[: self._requested_n_trials]
                rng.shuffle(specs)

        self.stimuli = [
            visual.ImageStim(
                win=self.window, image=s["path"],
                size=self.image_size_deg, units="deg",
            )
            for s in specs
        ]
        self.n_trials = len(self.stimuli)
        self.parameter = np.array([s["marker"] for s in specs], dtype=int)
        self.trials = DataFrame(
            dict(parameter=self.parameter, timestamp=np.zeros(self.n_trials))
        )
        self.order = DataFrame(
            [
                dict(
                    trial=i, marker=s["marker"], level=s["level"],
                    coef=s["coef"], identity=s["identity"],
                    fname=os.path.basename(s["path"]),
                )
                for i, s in enumerate(specs)
            ]
        )

        self.fixation = visual.TextStim(
            win=self.window, text="+", color=[1, 1, 1], height=0.6, units="deg"
        )
        print(
            "Face space: {} trials, {} levels {}, source {}{}".format(
                self.n_trials, len(self.levels), self.levels,
                "pre-rendered" if use_prerendered else self.source_dir,
                "" if use_prerendered else " (pixel-space fallback)",
            )
        )
        return self.stimuli

    # ------------------------------------------------------------------ #
    # Presentation
    # ------------------------------------------------------------------ #
    def present_iti(self):
        if self.fixation is not None:
            self.fixation.draw()
        self.window.flip()

    def present_stimulus(self, idx: int):
        if idx >= self.n_trials:
            return
        marker = int(self.parameter[idx])
        self.stimuli[idx].draw()
        if self.fixation is not None:
            self.fixation.draw()
        if self.eeg:
            code = [marker] if self.eeg.backend == "muselsl" else marker
            self.eeg.push_sample(marker=code, timestamp=time())
        self.window.flip()

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
            os.makedirs(self.cache_dir, exist_ok=True)
            sidecar = os.path.join(self.cache_dir, "facespace_dryrun_presentation.csv")
        self.order.to_csv(sidecar, index=False)
        print(f"[face-space] presentation order -> {sidecar}")
