"""ERP CORE MMN — passive auditory oddball.

Kappenman et al 2021: 1000 Hz standard tones (80%) and 1200 Hz deviant
tones (20%) presented at ~500 ms SOA while the subject watches a
silent video. Tone duration 70 ms with 5 ms linear on/off ramps. Two
blocks of 800 trials each (~13 min total). No behavioural response —
elicits the MMN at fronto-central sites 100–250 ms post-deviant.

This implementation generates both tones procedurally via
``psychopy.sound`` and enforces the fixed 5-deviant-minimum gap rule:
deviants cannot occur in the first five trials of a block and are
separated by at least two standards.
"""

from __future__ import annotations

from time import time
from typing import Optional

import numpy as np
from pandas import DataFrame
from psychopy import sound, visual

from eegnb.bids.paradigms import ERP_CORE_MMN as _bids
from eegnb.experiments import Experiment
from eegnb.paradigms import generate_mmn_sequence


class AuditoryERPCoreMMN(Experiment.BaseExperiment):
    """ERP CORE passive auditory MMN."""

    name = "ERP CORE MMN"
    __title__ = "ERP CORE MMN — passive auditory oddball (Kappenman & Luck 2021)"

    bids_task_name = _bids.bids_task_name
    bids_event_id = _bids.bids_event_id
    bids_task_json = _bids.bids_task_json

    channels_of_interest = ("Fz", "FCz", "Cz")

    def __init__(
        self,
        duration: float = 800.0,
        eeg=None,
        save_fn=None,
        n_trials: int = 1600,
        standard_hz: float = 1000.0,
        deviant_hz: float = 1200.0,
        tone_ms: float = 70.0,
        ramp_ms: float = 5.0,
        soa: float = 0.500,
        deviant_prob: float = 0.20,
        volume: float = 0.5,
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
            iti=soa - tone_ms / 1000.0,
            soa=tone_ms / 1000.0,
            jitter=0.0,
            use_vr=use_vr,
            devices=devices,
        )

        self.standard_hz = standard_hz
        self.deviant_hz = deviant_hz
        self.tone_ms = tone_ms
        self.ramp_ms = ramp_ms
        self.volume = volume
        self.markernames = {1: 1, 2: 2}

        self.parameter = generate_mmn_sequence(
            n_trials=n_trials,
            deviant_prob=deviant_prob,
            seed=seed,
        )
        self.trials = DataFrame(
            dict(parameter=self.parameter, timestamp=np.zeros(n_trials))
        )

    def _make_tone(self, freq_hz: float) -> sound.Sound:
        tone = sound.Sound(
            freq_hz,
            secs=self.tone_ms / 1000.0,
            sampleRate=48000,
        )
        tone.setVolume(self.volume)
        return tone

    def load_stimulus(self):
        self.standard_tone = self._make_tone(self.standard_hz)
        self.deviant_tone = self._make_tone(self.deviant_hz)
        # Central fixation is the only visual content during the run;
        # Kappenman uses a silent video but a fixation cross is the
        # Sensible default when no video is provided.
        self.fixation = visual.TextStim(
            win=self.window, text="+", color=[-1, -1, -1], height=1.5, units="deg"
        )
        return [self.standard_tone, self.deviant_tone]

    def present_iti(self):
        self.fixation.draw()
        self.window.flip()

    def present_stimulus(self, idx: int):
        label = int(self.trials["parameter"].iloc[idx])
        tone = self.deviant_tone if label == 2 else self.standard_tone
        tone.stop()
        tone.play()

        if self.eeg:
            self.eeg.push_sample(marker=self.markernames[label], timestamp=time())
        if self.devices:
            self.send_triggers(self.markernames[label])

        self.fixation.draw()
        self.window.flip()
