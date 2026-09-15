"""
Pattern-reversal VEP run experiment
===================================

Runs the binocular full-field checkerboard pattern-reversal VEP (ISCEV
standard: 2 reversals/s, 1 deg checks). Each reversal is marked; average
epochs around the reversal marker to recover the N75-P100-N145 complex.
A quick, reliable electrode/signal sanity check for any occipital montage.

Present fullscreen and focused on the internal display.
"""

import os
from eegnb import generate_save_fn
from eegnb.devices.eeg import EEG
from eegnb.experiments import VisualPatternReversalVEP

board_name = "unicorn"
experiment = "visual_pattern_reversal"
subject_id = 0
session_nb = 0

eeg_device = EEG(device=board_name)
save_fn = generate_save_fn(board_name, experiment, subject_id, session_nb)
print(save_fn)

vep = VisualPatternReversalVEP(
    n_reversals=200,        # ~100 s at 2 reversals/s
    reversals_per_s=2.0,
    check_deg=1.0,          # ISCEV standard check size; 0.25 for fine checks
    eeg=eeg_device,
    save_fn=save_fn,
)
vep.run()
