"""ERP CORE N400 — semantic priming.

Kappenman et al 2021: prime-target word pairs, half semantically
related and half unrelated. Prime 200 ms, SOA 1000 ms (prime->target),
target 200 ms, 1000 ms response window. 120 pairs in total (60 related
/ 60 unrelated). The N400 is measured at centro-parietal sites 300–500
ms post-target, more negative for unrelated targets.

Word pairs are read from a CSV with columns
``prime,related_target,unrelated_target``. Each row contributes one
related trial and one unrelated trial (the same prime paired with its
related and its unrelated target in different trials, matched for
frequency across subjects). Supply your own CSV via ``word_pairs_csv=``
for non-default stimulus sets (e.g. non-English).
"""

from __future__ import annotations

import os
from time import time
from typing import Optional

import numpy as np
from pandas import DataFrame
from psychopy import visual

from eegnb.bids.paradigms import ERP_CORE_N400 as _bids
from eegnb.experiments import Experiment
from eegnb.paradigms import read_word_pairs_csv
from eegnb.stimuli import __file__ as _stimuli_init


DEFAULT_WORD_PAIRS_CSV = os.path.join(
    os.path.dirname(_stimuli_init), "word_pairs_erp_core.csv"
)

_PRIME_RELATED = 1
_TARGET_RELATED = 2
_PRIME_UNRELATED = 3
_TARGET_UNRELATED = 4


class VisualERPCoreN400(Experiment.BaseExperiment):
    """ERP CORE N400 semantic priming."""

    name = "ERP CORE N400"
    __title__ = "ERP CORE N400 — semantic priming (Kappenman & Luck 2021)"

    bids_task_name = _bids.bids_task_name
    bids_event_id = _bids.bids_event_id
    bids_task_json = _bids.bids_task_json

    channels_of_interest = ("Cz", "CPz", "Pz")

    def __init__(
        self,
        duration: float = 480.0,
        eeg=None,
        save_fn=None,
        word_pairs_csv: Optional[str] = None,
        prime_ms: float = 200.0,
        target_ms: float = 200.0,
        soa_ms: float = 1000.0,
        response_window_ms: float = 1000.0,
        n_trials: Optional[int] = None,
        use_vr: bool = False,
        devices=None,
    ):
        self.word_pairs_csv = word_pairs_csv or DEFAULT_WORD_PAIRS_CSV
        self.pairs = read_word_pairs_csv(self.word_pairs_csv)

        if n_trials is None:
            n_trials = len(self.pairs) * 2  # one related + one unrelated trial/pair

        # SOA here is the target presentation; the prime is presented via
        # a custom present_stimulus that handles the full prime->ISI->target
        # sequence. We keep the BaseExperiment timing as target-centred.
        super().__init__(
            exp_name=self.name,
            duration=duration,
            eeg=eeg,
            save_fn=save_fn,
            n_trials=n_trials,
            iti=(soa_ms + response_window_ms) / 1000.0,
            soa=target_ms / 1000.0,
            jitter=0.0,
            use_vr=use_vr,
            devices=devices,
        )

        self.prime_ms = prime_ms
        self.target_ms = target_ms
        self.soa_ms = soa_ms
        self.response_window_ms = response_window_ms
        self.markernames = {
            _PRIME_RELATED: _PRIME_RELATED,
            _TARGET_RELATED: _TARGET_RELATED,
            _PRIME_UNRELATED: _PRIME_UNRELATED,
            _TARGET_UNRELATED: _TARGET_UNRELATED,
        }

        rng = np.random.default_rng()
        # Each pair contributes both a related and an unrelated trial;
        # interleave and shuffle across the whole run.
        trial_specs: list[tuple[str, str, int, int]] = []
        for prime, rel, unrel in self.pairs:
            trial_specs.append((prime, rel, _PRIME_RELATED, _TARGET_RELATED))
            trial_specs.append((prime, unrel, _PRIME_UNRELATED, _TARGET_UNRELATED))
        rng.shuffle(trial_specs)
        trial_specs = trial_specs[:n_trials]
        self._trial_specs = trial_specs
        self.parameter = np.array([t[3] for t in trial_specs], dtype=int)
        self.trials = DataFrame(
            dict(parameter=self.parameter, timestamp=np.zeros(n_trials))
        )

    def load_stimulus(self):
        self.fixation = visual.TextStim(
            win=self.window, text="+", color=[-1, -1, -1], height=1.0, units="deg"
        )
        self._word_stim = visual.TextStim(
            win=self.window, text="", color=[-1, -1, -1], height=1.4, units="deg"
        )
        return []

    def present_iti(self):
        self.fixation.draw()
        self.window.flip()

    def present_stimulus(self, idx: int):
        """Presents the full prime→ISI→target sequence for one trial.

        The BaseExperiment trial loop will call this once per trial and
        advance ``soa`` seconds later — but here the paradigm itself
        controls the internal sub-timing since the N400 protocol
        requires a prime-target SOA rather than a single stimulus flip.
        """
        from psychopy import core

        prime, target, prime_code, target_code = self._trial_specs[idx]

        self._word_stim.text = prime
        self._word_stim.draw()
        flip_time = time()
        self.window.flip()
        if self.eeg:
            self.eeg.push_sample(marker=self.markernames[prime_code], timestamp=flip_time)
        if self.devices:
            self.send_triggers(self.markernames[prime_code])

        core.wait(self.prime_ms / 1000.0)
        self.fixation.draw()
        self.window.flip()
        isi = (self.soa_ms - self.prime_ms) / 1000.0
        if isi > 0:
            core.wait(isi)

        self._word_stim.text = target
        self._word_stim.draw()
        flip_time = time()
        self.window.flip()
        if self.eeg:
            self.eeg.push_sample(marker=self.markernames[target_code], timestamp=flip_time)
        if self.devices:
            self.send_triggers(self.markernames[target_code])
