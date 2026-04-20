"""ERP CORE P3 — active visual oddball with letters.

Kappenman et al 2021: five letters (A, B, C, D, E) presented in random
order, with one designated target per block. The subject presses one
button for the target letter and another for non-targets. Over the
course of 5 blocks each letter serves as target exactly once, so
stimulus identity and target assignment are fully counterbalanced.
Target probability is 0.2 within each block. Stimulus 200 ms, ITI
1200–1400 ms. Elicits the P3b at centro-parietal sites 300–600 ms
post-target.
"""

from __future__ import annotations

from time import time
from typing import Optional

import numpy as np
from pandas import DataFrame
from psychopy import visual

from eegnb.bids.paradigms import ERP_CORE_P3 as _bids
from eegnb.experiments import Experiment


_STANDARD = 1
_TARGET = 2


class VisualERPCoreP3(Experiment.BaseExperiment):
    """ERP CORE P3 active visual oddball."""

    name = "ERP CORE P3"
    __title__ = "ERP CORE P3 — active visual oddball (Kappenman & Luck 2021)"

    bids_task_name = _bids.bids_task_name
    bids_event_id = _bids.bids_event_id
    bids_task_json = _bids.bids_task_json

    channels_of_interest = ("Cz", "CPz", "Pz")

    def __init__(
        self,
        duration: float = 600.0,
        eeg=None,
        save_fn=None,
        letters: tuple[str, ...] = ("A", "B", "C", "D", "E"),
        target_letter: Optional[str] = None,
        n_trials: int = 200,
        soa: float = 0.200,
        iti: float = 1.200,
        jitter: float = 0.200,
        target_prob: float = 0.20,
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

        self.letters = tuple(letters)
        self.target_letter = target_letter if target_letter is not None else self.letters[0]
        if self.target_letter not in self.letters:
            raise ValueError(
                f"target_letter {self.target_letter!r} not in letters {self.letters}"
            )
        self.target_prob = target_prob
        self.markernames = {_STANDARD: _STANDARD, _TARGET: _TARGET}

        rng = np.random.default_rng(seed)
        is_target = rng.random(n_trials) < target_prob
        # For each trial, choose letter: target letter if is_target, else
        # random non-target letter.
        non_targets = [c for c in self.letters if c != self.target_letter]
        letter_seq = np.where(
            is_target,
            self.target_letter,
            rng.choice(non_targets, size=n_trials),
        )
        self._letter_seq = letter_seq
        self.parameter = np.where(is_target, _TARGET, _STANDARD).astype(int)
        self.trials = DataFrame(
            dict(
                parameter=self.parameter,
                letter=letter_seq,
                timestamp=np.zeros(n_trials),
            )
        )

    def load_stimulus(self):
        self.fixation = visual.TextStim(
            win=self.window, text="+", color=[-1, -1, -1], height=1.0, units="deg"
        )
        self._letter_stim = visual.TextStim(
            win=self.window, text="", color=[-1, -1, -1], height=3.0, units="deg"
        )
        return []

    def present_iti(self):
        self.fixation.draw()
        self.window.flip()

    def present_stimulus(self, idx: int):
        letter = str(self._letter_seq[idx])
        label = int(self.trials["parameter"].iloc[idx])
        self._letter_stim.text = letter
        self._letter_stim.draw()

        if self.eeg:
            self.eeg.push_sample(marker=self.markernames[label], timestamp=time())
        if self.devices:
            self.send_triggers(self.markernames[label])

        self.window.flip()
