"""Stothart Fastball paradigm (object-recognition FPVS).

Frequency-tagged oddball: standards presented at a fast base rate with a
deviant every Nth stimulus. Matches Stothart, Smith, Milton 2020/2021
(Brain 144:2812): 3 Hz base, 0.6 Hz oddball, 5:1 standards:deviant,
166 ms on + 166 ms ISI.

Reference implementation: https://github.com/aung2phyowai/Fastball
Canonical stimuli: Bank of Standardised Stimuli (BOSS) v2.0. Not bundled;
see `standard_dir` / `deviant_dir` kwargs to point at your own sets.

Falls back to the N170 face/house images when no stimulus dirs are
supplied, so the paradigm can be smoke-tested out-of-the-box on a
Unicorn without any additional downloads.
"""

from __future__ import annotations

import os
from glob import glob
from time import time

from psychopy import visual
from pandas import DataFrame
import numpy as np

from eegnb.experiments import Experiment
from eegnb.paradigms.fsl_timing import FSLTimingSchedule, load_fsl_three_column
from eegnb.stimuli import FACE_HOUSE


class VisualFPVSStothart(Experiment.BaseExperiment):
    """Stothart fastball: object-recognition memory via FPVS.

    The paradigm presents a rapid stream of "standard" images with a
    "deviant" every 5th frame, at a 3 Hz base rate (0.6 Hz oddball).
    Analysis is frequency-domain: SNR at 0.6 Hz and its harmonics.

    Parameters
    ----------
    duration : float
        Block duration in seconds. Stothart's default is ~173 s
        (one epoch = 104 cycles × 5 images).
    eeg : EEG | None
    save_fn : str | None
    standard_dir : str | None
        Directory of standard (repeated) images. Defaults to the bundled
        N170 house set.
    deviant_dir : str | None
        Directory of deviant (oddball) images. Defaults to the bundled
        N170 face set.
    base_rate_hz : float
        Base stimulation rate. Stothart uses 3.0 Hz.
    standards_per_deviant : int
        How many standards precede each deviant. 5 gives a 0.6 Hz oddball
        at 3 Hz base.
    n_trials : int
        Upper bound on stimulus count; duration actually caps the run.
    """

    name = "Visual FPVS Stothart"
    __title__ = "Fastball — object-recognition FPVS (Stothart 2021)"

    # BIDS-EEG metadata lives in eegnb.bids.paradigms so non-PsychoPy
    # callers (CLI, exporters) can read it without loading PsychoPy.
    from eegnb.bids.paradigms import STOTHART as _bids
    bids_task_name = _bids.bids_task_name
    bids_event_id = _bids.bids_event_id
    bids_task_json = _bids.bids_task_json
    del _bids

    # Use frame-count-locked presentation by default — the whole SNR
    # argument of the paradigm depends on strictly periodic onsets.
    default_frame_locked = True

    # Analysis region of interest for the Unicorn Hybrid Black montage.
    # The Unicorn has fixed hardware electrodes; this attribute only
    # advises downstream analysis which channels carry the response.
    # Stothart's task elicits a mid-occipital/parietal oddball response
    # (BOSS objects, category-level distinction, memory-modulated).
    channels_of_interest = ("Oz", "Pz")

    def __init__(
        self,
        duration: float = 173.0,
        eeg=None,
        save_fn=None,
        standard_dir: str | None = None,
        deviant_dir: str | None = None,
        base_rate_hz: float = 3.0,
        standards_per_deviant: int = 5,
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

        self.standard_dir = standard_dir or os.path.join(FACE_HOUSE, "houses")
        self.deviant_dir = deviant_dir or os.path.join(FACE_HOUSE, "faces")
        self.base_rate_hz = base_rate_hz
        self.standards_per_deviant = standards_per_deviant

        # marker codes -> brainflow insert-into-stim-column values.
        # 1 = standard, 2 = deviant. Gives sub-frame marker timing via
        # the in-process brainflow path used by eegnb.devices.EEG.
        self.markernames = {1: 1, 2: 2}

        # Rebuild `parameter` / `trials` as a deterministic 1..1..1..2
        # pattern rather than a binomial draw.
        pattern = [1] * standards_per_deviant + [2]
        repeats = n_trials // (standards_per_deviant + 1) + 1
        self.parameter = np.tile(pattern, repeats)[:n_trials].astype(int)
        self.trials = DataFrame(
            dict(parameter=self.parameter, timestamp=np.zeros(n_trials))
        )

        # If a schedule is attached via from_fsl_timing_file, it
        # overrides the deterministic pattern below in load_stimulus.
        self._fsl_schedule: FSLTimingSchedule | None = None

    @classmethod
    def from_fsl_timing_file(
        cls,
        path: str,
        *,
        duration: float | None = None,
        eeg=None,
        save_fn=None,
        standard_dir: str | None = None,
        deviant_dir: str | None = None,
        base_rate_hz: float = 3.0,
        standards_per_deviant: int = 5,
    ) -> "VisualFPVSStothart":
        """Build a Stothart paradigm whose trial sequence is driven
        by a published FSL 3-column timing file.

        Each non-comment row of the timing file is treated as one
        stimulus with onset, duration and a value column where 1
        designates a standard and 2 designates an oddball. The
        paradigm's internal `parameter`, `iti`, `soa` and `duration`
        are overwritten to match the schedule.
        """
        schedule = load_fsl_three_column(path)
        if not schedule.events:
            raise ValueError(f"{path}: schedule contains no events")
        schedule_duration = schedule.total_duration_s

        inst = cls(
            duration=duration if duration is not None else schedule_duration,
            eeg=eeg,
            save_fn=save_fn,
            standard_dir=standard_dir,
            deviant_dir=deviant_dir,
            base_rate_hz=base_rate_hz,
            standards_per_deviant=standards_per_deviant,
            n_trials=len(schedule),
        )
        inst._fsl_schedule = schedule
        inst.parameter = np.array(
            [int(e.value) for e in schedule.events], dtype=int
        )
        inst.trials = DataFrame(
            dict(parameter=inst.parameter, timestamp=np.zeros(len(schedule)))
        )
        # SOA / ITI become the schedule's own durations / gaps.
        # We take the first event's duration as the nominal "on" time
        # and the gap to the next event as the "off" time; BaseExperiment's
        # trial loop respects these per-trial (the loop uses the class
        # attribute, not per-event timing — so this is an approximation
        # until frame-locked presentation is in place).
        first = schedule.events[0]
        inst.soa = first.duration_s
        if len(schedule) > 1:
            second = schedule.events[1]
            inst.iti = max(0.0, second.onset_s - (first.onset_s + first.duration_s))
        return inst

    def load_stimulus(self):
        if not os.path.isdir(self.standard_dir):
            raise FileNotFoundError(
                f"standard image directory not found: {self.standard_dir}"
            )
        if not os.path.isdir(self.deviant_dir):
            raise FileNotFoundError(
                f"deviant image directory not found: {self.deviant_dir}"
            )

        standards_paths = sorted(
            p for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp")
            for p in glob(os.path.join(self.standard_dir, ext))
        )
        deviants_paths = sorted(
            p for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp")
            for p in glob(os.path.join(self.deviant_dir, ext))
        )
        if not standards_paths or not deviants_paths:
            raise FileNotFoundError(
                "no images found in standard/deviant dirs; pass valid paths"
            )

        self.standards = [
            visual.ImageStim(win=self.window, image=p, size=10, units="deg")
            for p in standards_paths
        ]
        self.deviants = [
            visual.ImageStim(win=self.window, image=p, size=10, units="deg")
            for p in deviants_paths
        ]
        self._rng = np.random.default_rng()
        return [self.standards, self.deviants]

    def present_stimulus(self, idx: int):
        label = int(self.trials["parameter"].iloc[idx])
        pool = self.deviants if label == 2 else self.standards
        image = pool[self._rng.integers(0, len(pool))]
        image.draw()

        if self.eeg:
            self.eeg.push_sample(
                marker=self.markernames[label], timestamp=time()
            )

        self.window.flip()
