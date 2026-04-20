"""ERP CORE N2pc — lateralized visual search.

Kappenman et al 2021: bilateral search arrays of one pink and one blue
square, each with a gap on the top or bottom. The subject attends one
colour (blocked — "pink" or "blue") and reports whether the attended
square's gap is on top (one button) or bottom (the other button).
Stimulus 200 ms, ITI 1300–1700 ms jittered. 160 trials × 2 attended
colours = 320 trials. Elicits the N2pc contralateral to the target
175–250 ms post-stimulus at PO7/PO8.
"""

from __future__ import annotations

from time import time
from typing import Optional

import numpy as np
from pandas import DataFrame
from psychopy import visual

from eegnb.bids.paradigms import ERP_CORE_N2PC as _bids
from eegnb.experiments import Experiment


_PINK = (1.0, -0.6, 0.2)    # RGB in PsychoPy [-1,1] — approximates Kappenman pink
_BLUE = (-0.6, -0.2, 1.0)
_BACKGROUND_GREY = (0.0, 0.0, 0.0)

_TARGET_LEFT_BLUE = 1
_TARGET_RIGHT_BLUE = 2
_TARGET_LEFT_PINK = 3
_TARGET_RIGHT_PINK = 4


class VisualERPCoreN2pc(Experiment.BaseExperiment):
    """ERP CORE N2pc lateralized visual search."""

    name = "ERP CORE N2pc"
    __title__ = "ERP CORE N2pc — visual attention (Kappenman & Luck 2021)"

    bids_task_name = _bids.bids_task_name
    bids_event_id = _bids.bids_event_id
    bids_task_json = _bids.bids_task_json

    channels_of_interest = ("PO7", "PO8")

    def __init__(
        self,
        duration: float = 640.0,
        eeg=None,
        save_fn=None,
        n_trials: int = 320,
        soa: float = 0.200,
        iti: float = 1.300,
        jitter: float = 0.400,
        square_size_deg: float = 2.2,
        target_eccentricity_deg: float = 4.5,
        gap_size_deg: float = 0.6,
        attended_colour_blocks: tuple[str, ...] = ("blue", "pink"),
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

        self.square_size_deg = square_size_deg
        self.target_eccentricity_deg = target_eccentricity_deg
        self.gap_size_deg = gap_size_deg
        self.attended_colour_blocks = attended_colour_blocks
        self.markernames = {
            _TARGET_LEFT_BLUE: _TARGET_LEFT_BLUE,
            _TARGET_RIGHT_BLUE: _TARGET_RIGHT_BLUE,
            _TARGET_LEFT_PINK: _TARGET_LEFT_PINK,
            _TARGET_RIGHT_PINK: _TARGET_RIGHT_PINK,
        }

        # Interleaved block design: halve n_trials across attended colours.
        trials_per_block = n_trials // len(attended_colour_blocks)
        conditions = []
        for colour in attended_colour_blocks:
            block_base = (
                [_TARGET_LEFT_BLUE, _TARGET_RIGHT_BLUE]
                if colour == "blue"
                else [_TARGET_LEFT_PINK, _TARGET_RIGHT_PINK]
            )
            block = np.tile(block_base, trials_per_block // 2 + 1)[:trials_per_block]
            np.random.default_rng().shuffle(block)
            conditions.append(block)
        self.parameter = np.concatenate(conditions)[:n_trials]
        self.trials = DataFrame(
            dict(parameter=self.parameter, timestamp=np.zeros(n_trials))
        )

    def _square(self, colour: tuple[float, float, float], pos: tuple[float, float],
                gap_top: bool) -> list[visual.BaseVisualStim]:
        """A coloured square with a small gap on top or bottom."""
        square = visual.Rect(
            win=self.window,
            width=self.square_size_deg,
            height=self.square_size_deg,
            fillColor=colour,
            lineColor=colour,
            pos=pos,
            units="deg",
        )
        gap_y = pos[1] + (self.square_size_deg / 2.0) * (1 if gap_top else -1)
        gap = visual.Rect(
            win=self.window,
            width=self.gap_size_deg,
            height=self.gap_size_deg,
            fillColor=_BACKGROUND_GREY,
            lineColor=_BACKGROUND_GREY,
            pos=(pos[0], gap_y),
            units="deg",
        )
        return [square, gap]

    def load_stimulus(self):
        self.fixation = visual.TextStim(
            win=self.window, text="+", color=[-1, -1, -1], height=1.0, units="deg"
        )
        self._rng = np.random.default_rng()
        return []

    def _build_array(self, target_code: int) -> list[visual.BaseVisualStim]:
        left = (-self.target_eccentricity_deg, 0.0)
        right = (self.target_eccentricity_deg, 0.0)

        target_colour = _BLUE if target_code in (_TARGET_LEFT_BLUE, _TARGET_RIGHT_BLUE) else _PINK
        distractor_colour = _PINK if target_colour is _BLUE else _BLUE
        target_pos, distractor_pos = (
            (left, right)
            if target_code in (_TARGET_LEFT_BLUE, _TARGET_LEFT_PINK)
            else (right, left)
        )

        target_gap_top = bool(self._rng.integers(0, 2))
        distractor_gap_top = bool(self._rng.integers(0, 2))

        return (
            self._square(target_colour, target_pos, target_gap_top)
            + self._square(distractor_colour, distractor_pos, distractor_gap_top)
            + [self.fixation]
        )

    def present_iti(self):
        self.fixation.draw()
        self.window.flip()

    def present_stimulus(self, idx: int):
        target_code = int(self.trials["parameter"].iloc[idx])
        for s in self._build_array(target_code):
            s.draw()

        if self.eeg:
            self.eeg.push_sample(marker=self.markernames[target_code], timestamp=time())
        if self.devices:
            self.send_triggers(self.markernames[target_code])

        self.window.flip()
