"""ERP CORE N170 — face perception (faces vs. cars, intact vs. scrambled).

Kappenman et al 2021 present 40 face, 40 car, 40 scrambled-face, and 40
scrambled-car images in each of two blocks (320 trials total). Stimulus
duration 300 ms, ISI 1200–1600 ms jittered. Subjects press one button
for intact images and another for scrambled.

Canonical stimuli are on OSF (https://osf.io/thsqg/). When ``faces_dir``
and ``cars_dir`` are left at their defaults, the paradigm falls back to
the bundled ``FACE_HOUSE`` photos (using the ``faces`` subset as
"faces" and the ``houses`` subset as "cars") with phase-scrambled
variants generated at load time. This lets the paradigm smoke-test
without any downloads while remaining functionally Kappenman-compatible.
"""

from __future__ import annotations

import os
from glob import glob
from time import time
from typing import Optional

import numpy as np
from pandas import DataFrame
from psychopy import visual

from eegnb.bids.paradigms import ERP_CORE_N170 as _bids
from eegnb.experiments import Experiment
from eegnb.stimuli import FACE_HOUSE


def _phase_scramble(image: np.ndarray) -> np.ndarray:
    """Phase-randomise a single image while preserving its amplitude
    spectrum. Works on HxW (grayscale) or HxWxC (colour) float arrays.
    """
    if image.ndim == 2:
        spec = np.fft.fft2(image)
        amp = np.abs(spec)
        random_phase = np.exp(1j * np.random.uniform(-np.pi, np.pi, size=image.shape))
        out = np.real(np.fft.ifft2(amp * random_phase))
    else:
        out = np.empty_like(image)
        for c in range(image.shape[-1]):
            out[..., c] = _phase_scramble(image[..., c])
    out -= out.min()
    if out.max() > 0:
        out /= out.max()
    return out


class VisualERPCoreN170(Experiment.BaseExperiment):
    """ERP CORE N170 face-perception paradigm."""

    name = "ERP CORE N170"
    __title__ = "ERP CORE N170 — face perception (Kappenman & Luck 2021)"

    bids_task_name = _bids.bids_task_name
    bids_event_id = _bids.bids_event_id
    bids_task_json = _bids.bids_task_json

    channels_of_interest = ("PO7", "PO8", "P7", "P8")

    def __init__(
        self,
        duration: float = 640.0,
        eeg=None,
        save_fn=None,
        faces_dir: Optional[str] = None,
        cars_dir: Optional[str] = None,
        n_trials: int = 320,
        soa: float = 0.300,
        iti: float = 1.200,
        jitter: float = 0.400,
        use_vr: bool = False,
        devices=None,
    ):
        super().__init__(
            exp_name=self.name,
            duration=duration,
            eeg=eeg,
            save_fn=save_fn,
            n_trials=n_trials,
            iti=iti,
            soa=soa,
            jitter=jitter,
            use_vr=use_vr,
            devices=devices,
        )

        self.faces_dir = faces_dir or os.path.join(FACE_HOUSE, "faces")
        # Kappenman uses cars; fall back to FACE_HOUSE houses for bundled
        # smoke testing. Real N170 studies should supply Kappenman's cars.
        self.cars_dir = cars_dir or os.path.join(FACE_HOUSE, "houses")

        # 25% each of face / car / scrambled-face / scrambled-car.
        self.markernames = {
            1: 1,  # face
            2: 2,  # car
            3: 3,  # scrambled face
            4: 4,  # scrambled car
        }

        rng = np.random.default_rng()
        self.parameter = rng.integers(1, 5, size=n_trials)
        self.trials = DataFrame(
            dict(parameter=self.parameter, timestamp=np.zeros(n_trials))
        )

    def _load_category(self, path: str) -> list[np.ndarray]:
        paths = sorted(
            p for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp")
            for p in glob(os.path.join(path, ext))
        )
        if not paths:
            raise FileNotFoundError(f"no images found in {path}")
        from PIL import Image
        out = []
        for p in paths:
            img = np.asarray(Image.open(p).convert("L"), dtype=np.float32) / 255.0
            out.append(img)
        return out

    def load_stimulus(self):
        face_arrays = self._load_category(self.faces_dir)
        car_arrays = self._load_category(self.cars_dir)

        def _to_stim(arr: np.ndarray) -> visual.ImageStim:
            return visual.ImageStim(
                win=self.window,
                image=(arr * 2.0 - 1.0),
                size=10,
                units="deg",
            )

        self.faces = [_to_stim(a) for a in face_arrays]
        self.cars = [_to_stim(a) for a in car_arrays]
        self.scrambled_faces = [_to_stim(_phase_scramble(a)) for a in face_arrays]
        self.scrambled_cars = [_to_stim(_phase_scramble(a)) for a in car_arrays]

        self._pools = {
            1: self.faces,
            2: self.cars,
            3: self.scrambled_faces,
            4: self.scrambled_cars,
        }
        self._rng = np.random.default_rng()
        return [self.faces, self.cars, self.scrambled_faces, self.scrambled_cars]

    def present_stimulus(self, idx: int):
        label = int(self.trials["parameter"].iloc[idx])
        pool = self._pools[label]
        image = pool[self._rng.integers(0, len(pool))]
        image.draw()

        if self.eeg:
            self.eeg.push_sample(marker=self.markernames[label], timestamp=time())
        if self.devices:
            self.send_triggers(self.markernames[label])

        self.window.flip()
