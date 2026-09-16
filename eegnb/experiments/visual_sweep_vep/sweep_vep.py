"""Sweep VEP — objective contrast / acuity threshold (Norcia & Tyler 1985).

A grating contrast-reverses at a fixed rate while one parameter is stepped
monotonically across a range:

* ``sweep="contrast"`` — Michelson contrast is swept low→high; the SSVEP at
  the reversal frequency rises out of the noise as contrast passes the
  contrast-sensitivity threshold.
* ``sweep="spatial_freq"`` — spatial frequency is swept low→high (coarse→fine
  gratings); the response collapses past the grating-acuity limit.

Extrapolating the response-vs-parameter function to zero amplitude gives an
objective threshold with no behavioural report — the basis of infant / clinical
vision testing. This is a steady-state paradigm: like the SSVEP and retinotopy
paradigms it runs the time-based loop and draws every flicker frame inside
``present_stimulus`` (frame-accurate by counting frames). Each sweep step is
one "trial"; steps run back-to-back (``iti = 0``) so the sweep is continuous.

Each step onset gets a single marker; the swept value at each onset is written
to a presentation-order sidecar CSV (like the RSVP paradigm), and the step is
also recoverable from onset order since the sweep is deterministic. Analyse
with :func:`eegnb.analysis.frequency_tagging.tag_response` at the reversal
frequency, per step.
"""

from __future__ import annotations

import os
from time import time

import numpy as np
from pandas import DataFrame
from psychopy import visual

from eegnb.experiments import Experiment


class VisualSweepVEP(Experiment.BaseExperiment):
    """Steady-state sweep VEP for objective contrast / acuity thresholds.

    Parameters
    ----------
    duration : float | None
        Total run seconds. If None, derived from steps × step length.
    eeg : EEG | None
    save_fn : str | None
    sweep : {"contrast", "spatial_freq"}
        Which grating parameter is swept.
    n_steps : int
        Number of sweep levels.
    step_s : float
        Duration of each step in seconds (the SSVEP epoch per level).
    reversal_hz : float
        Pattern-reversal rate. Snapped to refresh/hold at load time so the
        tag lands in one FFT bin (default 6 reversals/s, exact at 60 Hz).
    n_sweeps : int
        Number of times to repeat the whole sweep (more repeats = cleaner
        threshold). Steps of all sweeps run back-to-back.
    contrast_range : (float, float)
        Michelson contrast endpoints for a contrast sweep (log-spaced).
    sf_range_cpd : (float, float)
        Spatial-frequency endpoints in cycles/deg for an acuity sweep
        (log-spaced).
    fixed_contrast : float
        Contrast held constant during a spatial-frequency sweep.
    fixed_sf_cpd : float
        Spatial frequency held constant during a contrast sweep.
    field_deg : float
        Grating field size (square, degrees).
    refresh_hz : float | None
        Override the measured monitor refresh.
    use_fullscr, screen_num : passed through to BaseExperiment.
    """

    name = "Visual Sweep VEP"
    __title__ = "Sweep VEP — objective contrast/acuity threshold (Norcia)"

    from eegnb.bids.paradigms import SWEEP_VEP as _bids
    bids_task_name = _bids.bids_task_name
    bids_event_id = _bids.bids_event_id
    bids_task_json = _bids.bids_task_json
    del _bids

    default_frame_locked = False  # time-based loop; flicker drawn per frame
    channels_of_interest = ("Oz", "O1", "O2")

    STEP_MARKER = 1

    def __init__(
        self,
        duration: float | None = None,
        eeg=None,
        save_fn=None,
        sweep: str = "contrast",
        n_steps: int = 10,
        step_s: float = 1.0,
        reversal_hz: float = 6.0,
        n_sweeps: int = 1,
        contrast_range: tuple[float, float] = (0.005, 0.8),
        sf_range_cpd: tuple[float, float] = (0.5, 20.0),
        fixed_contrast: float = 0.8,
        fixed_sf_cpd: float = 1.0,
        field_deg: float = 10.0,
        refresh_hz: float | None = None,
        use_fullscr: bool = True,
        screen_num: int = 0,
    ):
        if sweep not in ("contrast", "spatial_freq"):
            raise ValueError(
                f"sweep must be 'contrast' or 'spatial_freq', got {sweep!r}"
            )

        self.sweep = sweep
        self.n_steps = n_steps
        self.step_s = step_s
        self.reversal_hz = reversal_hz
        self.n_sweeps = n_sweeps
        self.contrast_range = contrast_range
        self.sf_range_cpd = sf_range_cpd
        self.fixed_contrast = fixed_contrast
        self.fixed_sf_cpd = fixed_sf_cpd
        self.field_deg = field_deg
        self._refresh_override = refresh_hz

        # Monotonic, log-spaced sweep values (perceptually even steps).
        if sweep == "contrast":
            lo, hi = contrast_range
        else:
            lo, hi = sf_range_cpd
        self.sweep_values = np.geomspace(lo, hi, n_steps)

        total_steps = n_steps * n_sweeps
        if duration is None:
            duration = total_steps * step_s + 5.0

        super().__init__(
            exp_name=self.name,
            duration=duration,
            eeg=eeg,
            save_fn=save_fn,
            n_trials=total_steps,
            iti=0.0,
            soa=step_s,
            jitter=0.0,
            use_vr=False,
            use_fullscr=use_fullscr,
            screen_num=screen_num,
        )

        # Every trial is a step onset -> the same marker; step identity is by
        # onset order + the sidecar.
        self.parameter = np.full(total_steps, self.STEP_MARKER, dtype=int)
        self.trials = DataFrame(
            dict(parameter=self.parameter, timestamp=np.zeros(total_steps))
        )
        self.markernames = {self.STEP_MARKER: "sweepStepOnset"}

        self.grating = None
        self.fixation = None
        self.order: DataFrame | None = None

    def load_stimulus(self):
        refresh = self._refresh_override or self.window.getActualFrameRate() or 60.0
        refresh = float(np.round(refresh))
        self._refresh = refresh
        self._hold = max(2, int(round(refresh / self.reversal_hz)))
        self.actual_reversal_hz = refresh / self._hold

        self.grating = visual.GratingStim(
            win=self.window,
            tex="sin",
            mask="gauss",
            units="deg",
            size=self.field_deg,
            sf=self.fixed_sf_cpd,
            contrast=self.fixed_contrast,
        )
        self.fixation = visual.GratingStim(
            win=self.window, pos=[0, 0], sf=0, size=0.3, color=[1, 0, 0]
        )

        # One row per step onset in presentation order.
        rows = []
        for sweep_i in range(self.n_sweeps):
            for step_i, val in enumerate(self.sweep_values):
                rows.append(
                    dict(
                        trial=len(rows),
                        sweep=sweep_i,
                        step=step_i,
                        swept=self.sweep,
                        value=float(val),
                        reversal_hz=self.actual_reversal_hz,
                    )
                )
        self.order = DataFrame(rows)

        print(
            "Sweep VEP: {} sweep, {} steps x {} sweeps @ {:.2f} reversals/s "
            "(hold {} frames), values {:.4g}..{:.4g}".format(
                self.sweep, self.n_steps, self.n_sweeps,
                self.actual_reversal_hz, self._hold,
                self.sweep_values[0], self.sweep_values[-1],
            )
        )
        return self.grating

    def present_iti(self):
        if self.fixation is not None:
            self.fixation.draw()
        self.window.flip()

    def present_stimulus(self, idx: int):
        if idx >= len(self.parameter):
            return
        step_i = idx % self.n_steps
        val = float(self.sweep_values[step_i])
        if self.sweep == "contrast":
            self.grating.contrast = val
            self.grating.sf = self.fixed_sf_cpd
        else:
            self.grating.sf = val
            self.grating.contrast = self.fixed_contrast

        if self.eeg:
            code = (
                [self.STEP_MARKER]
                if self.eeg.backend == "muselsl"
                else self.STEP_MARKER
            )
            self.eeg.push_sample(marker=code, timestamp=time())

        n_frames = max(1, int(round(self._refresh * self.step_s)))
        for f in range(n_frames):
            # Contrast-reverse the grating by flipping its phase by 0.5 every
            # `hold` frames -> reversal rate = refresh / hold.
            self.grating.phase = 0.0 if (f // self._hold) % 2 == 0 else 0.5
            self.grating.draw()
            if self.fixation is not None:
                self.fixation.draw()
            self.window.flip()

    def run(self, instructions=True, frame_locked=None, refresh_hz=None):
        super().run(
            instructions=instructions, frame_locked=frame_locked,
            refresh_hz=refresh_hz,
        )
        self._write_presentation_log()

    def _write_presentation_log(self):
        if self.order is None:
            return
        if self.save_fn:
            sidecar = os.path.splitext(self.save_fn)[0] + "_presentation.csv"
        else:
            import tempfile
            sidecar = os.path.join(
                tempfile.gettempdir(), "sweepvep_dryrun_presentation.csv"
            )
        self.order.to_csv(sidecar, index=False)
        print(f"[sweep-vep] presentation order -> {sidecar}")
