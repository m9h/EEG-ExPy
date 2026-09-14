"""Pattern-reversal VEP (binocular full-field checkerboard).

The clinical workhorse: a black/white checkerboard that reverses contrast
at a fixed rate at constant mean luminance. Each reversal is a transient
event that elicits the N75-P100-N145 complex over occipital cortex, the
P100 being the robust, standardized peak (~100 ms). This is the ISCEV
clinical VEP standard and doubles as a fast electrode/signal sanity check
for any occipital montage.

This is a clean ``BaseExperiment`` implementation for a normal monitor,
binocular viewing, no extra dependencies. A separate stereoscopic /
monocular VR interocular variant (built on ``BlockExperiment`` and
requiring ``stimupy``) already exists at
``eegnb.experiments.visual_vep.pattern_reversal_vep`` and is left untouched.

Timing model: each ``present_stimulus`` call performs exactly one reversal
(toggles the checkerboard contrast, marks it, and flips once). It runs the
time-based trial loop with ``iti = 0`` so the pattern simply alternates A/B
with no intervening blank — the reversal cadence is set by ``soa`` (0.5 s =
2 reversals/s by default). Response averaging is per-reversal, so a run is
many reversals (200 by default ≈ 100 s).
"""

from __future__ import annotations

from time import time

import numpy as np
from pandas import DataFrame
from psychopy import visual

from eegnb.experiments import Experiment
from eegnb.experiments.visual_retinotopy.retinotopy import _checkerboard


class VisualPatternReversalVEP(Experiment.BaseExperiment):
    """Binocular full-field checkerboard pattern-reversal VEP.

    Parameters
    ----------
    duration : float | None
        Total run seconds. If None, derived from ``n_reversals`` and the
        reversal rate (with margin).
    eeg : EEG | None
    save_fn : str | None
    n_reversals : int
        Number of contrast reversals in the run (each is one marked event).
    reversals_per_s : float
        Reversal rate. ISCEV standard is 2 reversals/s (i.e. a 1 Hz full
        pattern cycle). SOA = 1 / reversals_per_s.
    field_deg : float
        Side length of the square checkerboard field in degrees.
    check_deg : float
        Side length of one check in degrees. ISCEV uses 1 deg (and 0.25 deg
        for a fine-check condition). ``n_checks`` = round(field / check).
    use_fullscr, screen_num : passed through to BaseExperiment.
    """

    name = "Visual Pattern Reversal VEP"
    __title__ = "Pattern-reversal VEP — checkerboard (ISCEV standard)"

    from eegnb.bids.paradigms import PATTERN_REVERSAL_VEP as _bids
    bids_task_name = _bids.bids_task_name
    bids_event_id = _bids.bids_event_id
    bids_task_json = _bids.bids_task_json
    del _bids

    # Time-based loop: one reversal per present_stimulus; the pattern persists
    # (no re-flip) through the SOA until the next reversal. Not the hold loop.
    default_frame_locked = False

    # Transient VEP is maximal at the occipital midline.
    channels_of_interest = ("Oz", "O1", "O2")

    REVERSAL_MARKER = 1

    def __init__(
        self,
        duration: float | None = None,
        eeg=None,
        save_fn=None,
        n_reversals: int = 200,
        reversals_per_s: float = 2.0,
        field_deg: float = 12.0,
        check_deg: float = 1.0,
        use_fullscr: bool = True,
        screen_num: int = 0,
    ):
        soa = 1.0 / reversals_per_s
        if duration is None:
            duration = n_reversals * soa + 5.0

        super().__init__(
            exp_name=self.name,
            duration=duration,
            eeg=eeg,
            save_fn=save_fn,
            n_trials=n_reversals,
            iti=0.0,
            soa=soa,
            jitter=0.0,
            use_vr=False,
            use_fullscr=use_fullscr,
            screen_num=screen_num,
        )

        self.n_reversals = n_reversals
        self.reversals_per_s = reversals_per_s
        self.field_deg = field_deg
        self.check_deg = check_deg
        self.n_checks = max(2, int(round(field_deg / check_deg)))

        self.markernames = {self.REVERSAL_MARKER: "reversal"}
        # Every trial is a reversal; the parameter just records the running
        # phase (0/1) so analysis can split by reversal direction if wanted.
        self.parameter = (np.arange(n_reversals) % 2).astype(int)
        self.trials = DataFrame(
            dict(parameter=self.parameter, timestamp=np.zeros(n_reversals))
        )

        self.checkerboard = None
        self.fixation = None

    def load_stimulus(self):
        tex = _checkerboard(self.n_checks)
        self.checkerboard = visual.GratingStim(
            win=self.window,
            tex=tex,
            mask=None,
            units="deg",
            size=self.field_deg,
            sf=1.0 / self.field_deg,  # one texture copy across the field
        )
        # Small central fixation so the participant holds gaze.
        self.fixation = visual.GratingStim(
            win=self.window, pos=[0, 0], sf=0, size=0.3, color=[1, 0, 0]
        )
        print(
            "Pattern-reversal VEP: {:.0f} deg field, {} x {} checks "
            "({:.2f} deg/check), {:.1f} reversals/s, {} reversals".format(
                self.field_deg, self.n_checks, self.n_checks,
                self.field_deg / self.n_checks, self.reversals_per_s,
                self.n_reversals,
            )
        )
        return self.checkerboard

    def present_iti(self):
        # iti is 0 so this is effectively never used, but keep fixation up.
        if self.fixation is not None:
            self.fixation.draw()
        self.window.flip()

    def present_stimulus(self, idx: int):
        if idx >= self.n_reversals:
            return
        # Toggle contrast: even reversals show phase A (+1), odd show B (-1).
        self.checkerboard.contrast = 1.0 if (idx % 2 == 0) else -1.0
        self.checkerboard.draw()
        if self.fixation is not None:
            self.fixation.draw()

        # Mark the reversal at the flip that renders it.
        if self.eeg:
            code = (
                [self.REVERSAL_MARKER]
                if self.eeg.backend == "muselsl"
                else self.REVERSAL_MARKER
            )
            self.eeg.push_sample(marker=code, timestamp=time())
        self.window.flip()
