"""
Face-space distinctiveness run experiment
==========================================

Runs the norm-based face-space paradigm: face identities presented at graded
distances from the average (norm) face. The event code indexes the distance
level; per-onset identity and morph coefficient are written to a
``*_presentation.csv`` sidecar next to the recording. Sort ERPs by level to
see the P200 (typicality), N250 (distinctiveness) and N170 modulation.

By default this builds a *pixel-space* fallback continuum from the bundled
N170 faces — fine for pipeline bring-up, but for real data supply a
pre-rendered, shape-normalized continuum (webmorphR / a 3D morphable model)
as ``stim_dir`` with ``level_<k>/`` subfolders.
"""

import os
from eegnb import generate_save_fn
from eegnb.devices.eeg import EEG
from eegnb.experiments import VisualFaceSpace

board_name = "unicorn"
experiment = "visual_face_space"
subject_id = 0
session_nb = 0

eeg_device = EEG(device=board_name)
save_fn = generate_save_fn(board_name, experiment, subject_id, session_nb)
print(save_fn)

face_space = VisualFaceSpace(
    levels=[0.0, 0.5, 1.0, 1.5],   # mean, sub-veridical, veridical, caricature
    # stim_dir="/path/to/prerendered/continuum",  # level_0/ level_1/ ...
    eeg=eeg_device,
    save_fn=save_fn,
)
face_space.run()
