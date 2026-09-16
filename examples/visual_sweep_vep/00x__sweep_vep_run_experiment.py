"""
Sweep VEP run experiment
========================

Runs the steady-state sweep VEP for an objective threshold. A grating
contrast-reverses at a fixed rate while one parameter is swept: set
``sweep="contrast"`` for a contrast-sensitivity threshold or
``sweep="spatial_freq"`` for a grating-acuity threshold. Each step onset is
marked; the swept value per onset lands in a ``*_presentation.csv`` sidecar.
Read the SSVEP amplitude at the reversal frequency per step with
``eegnb.analysis.frequency_tagging.tag_response`` and extrapolate to threshold.

Present fullscreen and focused on the internal display.
"""

import os
from eegnb import generate_save_fn
from eegnb.devices.eeg import EEG
from eegnb.experiments import VisualSweepVEP

board_name = "unicorn"
experiment = "visual_sweep_vep"
subject_id = 0
session_nb = 0

eeg_device = EEG(device=board_name)
save_fn = generate_save_fn(board_name, experiment, subject_id, session_nb)
print(save_fn)

sweep = VisualSweepVEP(
    sweep="contrast",        # or "spatial_freq" for acuity
    n_steps=10,
    step_s=1.0,
    reversal_hz=6.0,
    n_sweeps=4,              # repeat the sweep for a cleaner threshold
    eeg=eeg_device,
    save_fn=save_fn,
)
sweep.run()
