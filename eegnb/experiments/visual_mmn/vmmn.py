"""Visual mismatch negativity (vMMN) — passive visual oddball.

A frequent *standard* and a rare *deviant* differing in a single feature are
presented while attention is directed away from the stream. The
deviant-minus-standard difference wave yields the visual mismatch negativity,
a posterior negativity ~150-350 ms that indexes automatic visual
change-detection / prediction error (Stefanics, Kremlacek & Czigler 2014;
Czigler; Kimura).

Feature manipulated (``feature`` kwarg):

* ``"orientation"`` (default) — standard and deviant are gratings at
  different orientations.
* ``"colour"`` — standard and deviant are patches of different colour at
  matched luminance-ish RGB.

Discrete-trial ERP timing: each stimulus is shown briefly then a jittered
fixation ISI follows, so this runs the time-based loop (jitter only applies
there). The oddball sequence reuses the constrained generator shared with the
auditory ERP-CORE MMN (:func:`eegnb.paradigms.generate_mmn_sequence`), which
enforces lead-in standards and a minimum standard-run between deviants.

Note on rigour: the vMMN is best isolated by pairing this oddball with an
*equiprobable control* block (the deviant stimulus embedded among many
equiprobable others) to subtract stimulus-specific adaptation. This class
implements the oddball; run a separate control and difference offline, and/or
add a central fixation-change task to hold attention off the stream.
"""

from __future__ import annotations

from time import time

import numpy as np
from pandas import DataFrame
from psychopy import visual

from eegnb.experiments import Experiment
from eegnb.paradigms import generate_mmn_sequence


class VisualMMN(Experiment.BaseExperiment):
    """Passive visual oddball eliciting the visual mismatch negativity.

    Parameters
    ----------
    duration : float | None
        Total run seconds. If None, derived from the trial count and timing.
    eeg : EEG | None
    save_fn : str | None
    feature : {"orientation", "colour"}
        Which feature distinguishes standard from deviant.
    n_trials : int
        Total stimuli (standards + deviants).
    deviant_prob : float
        Deviant probability (default 0.2).
    min_standards_between : int
        Minimum standards between successive deviants.
    standard_ori, deviant_ori : float
        Grating orientations (deg) for the orientation feature.
    standard_colour, deviant_colour : sequence[float]
        PsychoPy RGB (-1..1) patch colours for the colour feature.
    sf_cpd : float
        Grating spatial frequency (orientation feature).
    size_deg : float
        Stimulus size (degrees).
    stim_s, iti_s, jitter : float
        Stimulus-on seconds, base ISI, added uniform jitter.
    seed : int
        Sequence reproducibility.
    use_fullscr, screen_num : passed through to BaseExperiment.
    """

    name = "Visual MMN"
    __title__ = "Visual mismatch negativity (vMMN) — passive oddball"

    from eegnb.bids.paradigms import VMMN as _bids
    bids_task_name = _bids.bids_task_name
    bids_event_id = _bids.bids_event_id
    bids_task_json = _bids.bids_task_json
    del _bids

    default_frame_locked = False  # discrete trials with jittered ISI
    channels_of_interest = ("Oz", "PO7", "PO8")

    STANDARD, DEVIANT = 1, 2

    def __init__(
        self,
        duration: float | None = None,
        eeg=None,
        save_fn=None,
        feature: str = "orientation",
        n_trials: int = 600,
        deviant_prob: float = 0.2,
        min_standards_between: int = 2,
        standard_ori: float = 45.0,
        deviant_ori: float = 135.0,
        standard_colour=(-1.0, 1.0, -1.0),   # green
        deviant_colour=(1.0, -1.0, -1.0),    # red
        sf_cpd: float = 2.0,
        size_deg: float = 6.0,
        stim_s: float = 0.15,
        iti_s: float = 0.45,
        jitter: float = 0.1,
        seed: int = 1,
        use_fullscr: bool = True,
        screen_num: int = 0,
    ):
        if feature not in ("orientation", "colour"):
            raise ValueError(
                f"feature must be 'orientation' or 'colour', got {feature!r}"
            )
        self.feature = feature
        self.deviant_prob = deviant_prob
        self.min_standards_between = min_standards_between
        self.standard_ori = standard_ori
        self.deviant_ori = deviant_ori
        self.standard_colour = standard_colour
        self.deviant_colour = deviant_colour
        self.sf_cpd = sf_cpd
        self.size_deg = size_deg
        self.stim_s = stim_s
        self.seed = seed

        if duration is None:
            duration = n_trials * (stim_s + iti_s + jitter) + 5.0

        super().__init__(
            exp_name=self.name,
            duration=duration,
            eeg=eeg,
            save_fn=save_fn,
            n_trials=n_trials,
            iti=iti_s,
            soa=stim_s,
            jitter=jitter,
            use_vr=False,
            use_fullscr=use_fullscr,
            screen_num=screen_num,
        )

        # Constrained standard/deviant sequence (shared with auditory MMN).
        self.parameter = generate_mmn_sequence(
            n_trials=n_trials,
            deviant_prob=deviant_prob,
            min_standards_between=min_standards_between,
            lead_in_standards=max(min_standards_between + 1, 5),
            seed=seed,
        )
        self.trials = DataFrame(
            dict(parameter=self.parameter, timestamp=np.zeros(n_trials))
        )
        self.markernames = {self.STANDARD: "standard", self.DEVIANT: "deviant"}

        self.standard_stim = None
        self.deviant_stim = None
        self.fixation = None

    def load_stimulus(self):
        if self.feature == "orientation":
            self.standard_stim = visual.GratingStim(
                win=self.window, tex="sin", mask="gauss", units="deg",
                size=self.size_deg, sf=self.sf_cpd, ori=self.standard_ori,
            )
            self.deviant_stim = visual.GratingStim(
                win=self.window, tex="sin", mask="gauss", units="deg",
                size=self.size_deg, sf=self.sf_cpd, ori=self.deviant_ori,
            )
        else:  # colour
            self.standard_stim = visual.GratingStim(
                win=self.window, tex=None, mask="circle", units="deg",
                size=self.size_deg, color=self.standard_colour,
            )
            self.deviant_stim = visual.GratingStim(
                win=self.window, tex=None, mask="circle", units="deg",
                size=self.size_deg, color=self.deviant_colour,
            )
        # Central fixation cross, always on, to anchor gaze (the stream is
        # peripheral to task-irrelevant); a distractor task can replace this.
        self.fixation = visual.TextStim(
            win=self.window, text="+", color=[1, 1, 1], height=0.6, units="deg"
        )
        n_dev = int(np.sum(self.parameter == self.DEVIANT))
        print(
            "Visual MMN ({}): {} trials, {} deviants ({:.1f}%), "
            "min {} standards between".format(
                self.feature, self.n_trials, n_dev,
                100.0 * n_dev / self.n_trials, self.min_standards_between,
            )
        )
        return [self.standard_stim, self.deviant_stim]

    def present_iti(self):
        if self.fixation is not None:
            self.fixation.draw()
        self.window.flip()

    def present_stimulus(self, idx: int):
        if idx >= self.n_trials:
            return
        label = int(self.parameter[idx])
        stim = self.deviant_stim if label == self.DEVIANT else self.standard_stim
        stim.draw()
        if self.fixation is not None:
            self.fixation.draw()
        if self.eeg:
            code = [label] if self.eeg.backend == "muselsl" else label
            self.eeg.push_sample(marker=code, timestamp=time())
        self.window.flip()
