"""Rossion FPVS face-individuation paradigm.

Matches Liu-Shuang, Norcia, Rossion 2014 Neuropsychologia 52:57-72
(doi:10.1016/j.neuropsychologia.2013.10.022): a "base" face identity
repeated at 5.88 Hz (170 ms SOA), with a novel "oddball" face inserted
every 5th item (1.176 Hz). Response at the oddball frequency and its
harmonics indexes neural face individuation, maximal at right
occipito-temporal cortex.

This is a square-wave approximation of Rossion's continuous sinusoidal
contrast modulation — adequate for an 8-channel Unicorn proof-of-concept
but not identical to the canonical paradigm.

Canonical stimuli: 50 neutral-expression unfamiliar face identities
(Liu-Shuang 2014), not publicly distributed. This module expects two
directories: `base_identity_dir` (repeated images of one identity) and
`oddball_identities_dir` (images of many other identities). When
neither is supplied it falls back to the bundled N170 face set, drawing
one identity for the base and a mix of others for oddballs — good
enough for pipeline validation, not for real face-individuation data.
"""

from __future__ import annotations

import os
import re
from glob import glob
from time import time

import numpy as np
from pandas import DataFrame
from psychopy import visual

from eegnb.experiments import Experiment
from eegnb.stimuli import FACE_HOUSE


class VisualFPVSRossion(Experiment.BaseExperiment):
    """Face-individuation FPVS oddball paradigm (Rossion 2014).

    Parameters
    ----------
    duration : float
        Block duration in seconds. Rossion's canonical sequences are
        60–80 s; 70 s is a good default.
    base_rate_hz : float
        Default 5.88 Hz (170 ms SOA) per Liu-Shuang 2014.
    standards_per_deviant : int
        Default 5 → oddball rate = base/6 = 1.176 Hz after including the
        oddball in the denominator. Liu-Shuang use "every 5th item"
        which nets to base/(standards+1) if you count inclusively, or
        base/5 = 1.176 Hz when counting every 5th position. We use the
        latter convention (standards_per_deviant=4 stands + 1 oddball
        per 5-item block), consistent with the Rossion lab docs.
    base_identity_dir : str | None
        Directory of images of the repeated identity. Falls back to the
        bundled N170 face set (arbitrary identity).
    oddball_identities_dir : str | None
        Directory of images drawn from other identities.
    """

    name = "Visual FPVS Rossion"
    __title__ = "FPVS face individuation (Rossion 2014)"

    # Use frame-count-locked presentation by default — the whole SNR
    # argument of the paradigm depends on strictly periodic onsets.
    default_frame_locked = True

    # Analysis region of interest. The face individuation response is
    # strongest at right occipito-temporal electrodes. The Unicorn's
    # fixed montage gives us PO8 (right OT), with Oz and PO7 as the
    # midline/left-hemisphere references. No P10/PO10 on this cap.
    channels_of_interest = ("PO8", "Oz", "PO7")

    def __init__(
        self,
        duration: float = 70.0,
        eeg=None,
        save_fn=None,
        base_identity_dir: str | None = None,
        oddball_identities_dir: str | None = None,
        base_rate_hz: float = 5.88,
        standards_per_deviant: int = 4,
        n_trials: int = 2000,
        use_vr: bool = False,
    ):
        cycle_s = 1.0 / base_rate_hz
        on_s = cycle_s / 2.0
        off_s = cycle_s / 2.0

        super().__init__(
            exp_name=self.name,
            duration=duration,
            eeg=eeg,
            save_fn=save_fn,
            n_trials=n_trials,
            iti=off_s,
            soa=on_s,
            jitter=0.0,
            use_vr=use_vr,
        )

        self.base_identity_dir = base_identity_dir
        self.oddball_identities_dir = oddball_identities_dir
        self.base_rate_hz = base_rate_hz
        self.standards_per_deviant = standards_per_deviant

        # 1 = base identity, 2 = oddball identity.
        self.markernames = {1: 1, 2: 2}

        # Deterministic repeating pattern: 4 standards then 1 oddball.
        pattern = [1] * standards_per_deviant + [2]
        repeats = n_trials // (standards_per_deviant + 1) + 1
        self.parameter = np.tile(pattern, repeats)[:n_trials].astype(int)
        self.trials = DataFrame(
            dict(parameter=self.parameter, timestamp=np.zeros(n_trials))
        )

    def load_stimulus(self):
        base_paths, oddball_paths = self._resolve_face_paths()

        self.base_images = [
            visual.ImageStim(win=self.window, image=p, size=8, units="deg")
            for p in base_paths
        ]
        self.oddball_images = [
            visual.ImageStim(win=self.window, image=p, size=8, units="deg")
            for p in oddball_paths
        ]
        self._rng = np.random.default_rng()
        return [self.base_images, self.oddball_images]

    def _resolve_face_paths(self) -> tuple[list[str], list[str]]:
        """Pick base vs oddball face file paths.

        User-supplied dirs take precedence. Otherwise fall back to the
        bundled N170 face set, using one identity (by filename prefix)
        as the base and the rest as oddballs — pipeline-sanity only.
        """
        if self.base_identity_dir and self.oddball_identities_dir:
            base = _gather_images(self.base_identity_dir)
            oddballs = _gather_images(self.oddball_identities_dir)
            if not base or not oddballs:
                raise FileNotFoundError(
                    "no face images in base/oddball dirs"
                )
            return base, oddballs

        # Fallback: split N170's bundled faces by filename prefix
        # (e.g. "Annie_1.jpg" ... "Blake_1.jpg" -> group by first token).
        all_faces = _gather_images(os.path.join(FACE_HOUSE, "faces"))
        if not all_faces:
            raise FileNotFoundError(
                "no fallback face images found in bundled N170 set"
            )

        by_identity: dict[str, list[str]] = {}
        for p in all_faces:
            key = re.split(r"[_.]", os.path.basename(p))[0]
            by_identity.setdefault(key, []).append(p)

        # Base = the first identity, oddballs = all the rest.
        identities = sorted(by_identity.keys())
        base_key = identities[0]
        base = by_identity[base_key]
        oddballs = [
            p for key, paths in by_identity.items()
            if key != base_key
            for p in paths
        ]
        if not oddballs:
            raise RuntimeError(
                "fallback face set only has one identity; supply"
                " base_identity_dir and oddball_identities_dir"
            )
        return base, oddballs

    def present_stimulus(self, idx: int):
        label = int(self.trials["parameter"].iloc[idx])
        if label == 2:
            image = self.oddball_images[
                self._rng.integers(0, len(self.oddball_images))
            ]
        else:
            image = self.base_images[
                self._rng.integers(0, len(self.base_images))
            ]
        image.draw()

        if self.eeg:
            self.eeg.push_sample(
                marker=self.markernames[label], timestamp=time()
            )

        self.window.flip()


def _gather_images(directory: str) -> list[str]:
    return sorted(
        p
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp")
        for p in glob(os.path.join(directory, ext))
    )
