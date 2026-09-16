"""
Visual MMN run experiment
=========================

Runs the passive visual oddball for the visual mismatch negativity. A
frequent standard and rare deviant differ in one feature
(``feature="orientation"`` by default, or ``"colour"``). Average epochs by
marker (1=standard, 2=deviant) and take the deviant-minus-standard difference
wave to reveal the vMMN (~150-350 ms, posterior).

For rigour, run a separate equiprobable-control block and subtract
stimulus-specific adaptation offline; optionally add a central
fixation-change task to hold attention off the stream. Present fullscreen and
focused on the internal display.
"""

import os
from eegnb import generate_save_fn
from eegnb.devices.eeg import EEG
from eegnb.experiments import VisualMMN

board_name = "unicorn"
experiment = "visual_mmn"
subject_id = 0
session_nb = 0

eeg_device = EEG(device=board_name)
save_fn = generate_save_fn(board_name, experiment, subject_id, session_nb)
print(save_fn)

vmmn = VisualMMN(
    feature="orientation",   # or "colour"
    n_trials=600,
    deviant_prob=0.2,
    eeg=eeg_device,
    save_fn=save_fn,
)
vmmn.run()
