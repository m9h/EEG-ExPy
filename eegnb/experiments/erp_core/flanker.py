"""ERP CORE ERN/LRP — Eriksen arrow flanker.

Kappenman et al 2021: central arrow flanked by four arrows, congruent
(<<<<<) or incongruent (<<><<). Subject responds to the direction of
the central arrow with the corresponding hand. Stimulus 200 ms, ITI
1200–1400 ms. 400 trials total.

Two response-locked ERPs are extracted from this single paradigm:

- **ERN** (error-related negativity) — fronto-central, ~0–100 ms
  post-response on error trials, contrasted against correct trials.
- **LRP** (lateralized readiness potential) — motor cortex
  contralateral to the response hand, pre-response.

This paradigm therefore logs both the congruency code and the correct
response direction so that error vs. correct trials (for the ERN) and
left vs. right responses (for the LRP) can be labelled at analysis
time. The paradigm itself does not collect responses; downstream
pipelines pair markers with a separate response channel (eye-tracker
button box, keypress log, or response-locked LSL stream).
"""

from __future__ import annotations

from time import time
from typing import Optional

import numpy as np
from pandas import DataFrame
from psychopy import visual

from eegnb.bids.paradigms import ERP_CORE_FLANKER as _bids
from eegnb.experiments import Experiment
from eegnb.paradigms import build_flanker_arrow_string


_CONGRUENT_CORRECT = 1
_INCONGRUENT_CORRECT = 2
_CONGRUENT_ERROR = 3
_INCONGRUENT_ERROR = 4


class VisualERPCoreFlanker(Experiment.BaseExperiment):
    """ERP CORE Eriksen arrow flanker (yields ERN + LRP)."""

    name = "ERP CORE Flanker"
    __title__ = "ERP CORE ERN/LRP — arrow flanker (Kappenman & Luck 2021)"

    bids_task_name = _bids.bids_task_name
    bids_event_id = _bids.bids_event_id
    bids_task_json = _bids.bids_task_json

    # ERN: fronto-central; LRP: central motor. Analysis pipelines
    # decide which to extract; we list both.
    channels_of_interest = ("Fz", "FCz", "Cz", "C3", "C4")

    def __init__(
        self,
        duration: float = 600.0,
        eeg=None,
        save_fn=None,
        n_trials: int = 400,
        soa: float = 0.200,
        iti: float = 1.200,
        jitter: float = 0.200,
        congruent_prob: float = 0.5,
        target_arrow_size_deg: float = 2.0,
        use_vr: bool = False,
        devices=None,
        seed: Optional[int] = None,
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

        self.congruent_prob = congruent_prob
        self.target_arrow_size_deg = target_arrow_size_deg
        self.markernames = {
            _CONGRUENT_CORRECT: _CONGRUENT_CORRECT,
            _INCONGRUENT_CORRECT: _INCONGRUENT_CORRECT,
            _CONGRUENT_ERROR: _CONGRUENT_ERROR,
            _INCONGRUENT_ERROR: _INCONGRUENT_ERROR,
        }

        rng = np.random.default_rng(seed)
        is_congruent = rng.random(n_trials) < congruent_prob
        central_left = rng.integers(0, 2, size=n_trials).astype(bool)
        # At presentation time we assume the trial is "correct"; downstream
        # response labelling promotes some to _*_ERROR based on recorded
        # responses. The onset marker is stimulus-locked, not
        # response-locked, so it cannot encode the response outcome.
        self._is_congruent = is_congruent
        self._central_left = central_left
        self.parameter = np.where(
            is_congruent, _CONGRUENT_CORRECT, _INCONGRUENT_CORRECT
        ).astype(int)
        self.trials = DataFrame(
            dict(
                parameter=self.parameter,
                is_congruent=is_congruent,
                central_left=central_left,
                timestamp=np.zeros(n_trials),
            )
        )

    def _arrow_string(self, idx: int) -> str:
        return build_flanker_arrow_string(
            central_left=bool(self._central_left[idx]),
            congruent=bool(self._is_congruent[idx]),
        )

    def load_stimulus(self):
        self.fixation = visual.TextStim(
            win=self.window, text="+", color=[-1, -1, -1], height=1.0, units="deg"
        )
        self._arrow_stim = visual.TextStim(
            win=self.window,
            text="",
            color=[-1, -1, -1],
            height=self.target_arrow_size_deg,
            units="deg",
        )
        return []

    def present_iti(self):
        self.fixation.draw()
        self.window.flip()

    def present_stimulus(self, idx: int):
        self._arrow_stim.text = self._arrow_string(idx)
        self._arrow_stim.draw()
        label = int(self.trials["parameter"].iloc[idx])

        if self.eeg:
            self.eeg.push_sample(marker=self.markernames[label], timestamp=time())
        if self.devices:
            self.send_triggers(self.markernames[label])

        self.window.flip()
