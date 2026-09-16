"""Paradigm BIDS-EEG metadata, decoupled from the PsychoPy paradigm classes.

The paradigm classes in `eegnb.experiments.fpvs_*` re-export these
constants so paradigm code and BIDS code share one source of truth.
Anything that only needs the BIDS metadata (CLI, exporters, validators)
imports from here directly and avoids loading PsychoPy/pyglet.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Mapping


def _meta(
    bids_task_name: str,
    bids_event_id: Mapping[int, str],
    bids_task_json: Mapping[str, str],
) -> SimpleNamespace:
    return SimpleNamespace(
        bids_task_name=bids_task_name,
        bids_event_id=dict(bids_event_id),
        bids_task_json=dict(bids_task_json),
    )


STOTHART = _meta(
    bids_task_name="fastballStothart",
    bids_event_id={1: "standard", 2: "oddball"},
    bids_task_json={
        "TaskName": "Fastball (Stothart) — object-recognition FPVS",
        "Instructions": (
            "Fixate centre of the screen. Simply watch the stream of "
            "images — no response is required."
        ),
        "TaskDescription": (
            "Fast periodic visual stimulation of BOSS-style object "
            "photographs at a 3 Hz base rate with an oddball (seen vs "
            "unseen) every 5th stimulus (0.6 Hz). Stothart, Smith, "
            "Milton 2020 NeuroImage; Stothart et al 2021 Brain."
        ),
    },
)


ROSSION = _meta(
    bids_task_name="fpvsFaceIndividuation",
    bids_event_id={1: "baseIdentity", 2: "oddballIdentity"},
    bids_task_json={
        "TaskName": "FPVS face individuation (Rossion 2014)",
        "Instructions": (
            "Fixate centre. Passive viewing of rapidly presented faces; "
            "no response is required."
        ),
        "TaskDescription": (
            "Fast periodic visual stimulation of unfamiliar face "
            "identities at a 5.88 Hz base rate with a novel identity "
            "every 5th stimulus (1.176 Hz). Liu-Shuang, Norcia, Rossion "
            "2014 Neuropsychologia."
        ),
    },
)


RSVP_THINGS = _meta(
    bids_task_name="rsvpThings",
    bids_event_id={1: "imageOnset"},
    bids_task_json={
        "TaskName": "THINGS RSVP — natural-image EEG decoding",
        "Instructions": (
            "Fixate the central cross. Passively watch the rapid stream "
            "of images; no response is required. Try not to blink during "
            "a block."
        ),
        "TaskDescription": (
            "Rapid serial visual presentation of unique natural object "
            "images from the THINGS database, 100 ms on / 100 ms blank "
            "(5 Hz), one marker per image onset. Image identity per onset "
            "is recorded in a presentation-order sidecar, not in the "
            "event code. Replicates the Alljoined-1.6M acquisition "
            "protocol (arXiv 2508.18571) for EEG-to-image decoding."
        ),
    },
)


RETINOTOPY_SSVEP = _meta(
    bids_task_name="retinotopySsvep",
    bids_event_id={
        1: "upperLeft",
        2: "upperRight",
        3: "lowerLeft",
        4: "lowerRight",
        5: "multiplexBlock",
    },
    bids_task_json={
        "TaskName": "SSVEP sector retinotopy — frequency-tagged visual field mapping",
        "Instructions": (
            "Keep your eyes fixed on the central dot for the whole block "
            "and try not to blink. Flickering checkerboard patches will "
            "appear around fixation; do not look at them directly — just "
            "hold central fixation. No response is required."
        ),
        "TaskDescription": (
            "Frequency-tagged steady-state visual evoked potential (SSVEP) "
            "mapping of the visual field. Contrast-reversing checkerboard "
            "patches are placed in visual-field sectors (four quadrants by "
            "default), each reversing at a distinct frequency that is an "
            "integer divisor of the monitor refresh rate (e.g. 15/12/10/"
            "8.57 Hz on a 60 Hz display) so each tag lands in one FFT bin. "
            "In multiplex mode all sectors flicker simultaneously and are "
            "separated by their tag frequency; in sequential mode one "
            "sector flickers per block and its scalp topography is read "
            "directly. The SSVEP amplitude/phase at each tag, and its "
            "scalp topography (upper vs lower field cruciform polarity "
            "inversion at Oz, left vs right hemifield lateralization), "
            "index coarse retinotopic position. This yields honest coarse "
            "(quadrant/hemifield) retinotopy on a low-density occipital "
            "montage; it is NOT population-receptive-field mapping, which "
            "requires high-density EEG with individual anatomy, MEG with an "
            "fMRI-derived forward model, or intracranial recordings. "
            "SSVEP methods: Norcia, Appelbaum, Ales, Cottereau & Rossion "
            "(2015) J Vision 15(6):4. Multifocal/retinotopic VEP context: "
            "Baseler et al. (1994); Slotnick et al. (1999); Ales, Yates & "
            "Norcia (2010) NeuroImage."
        ),
    },
)


PATTERN_REVERSAL_VEP = _meta(
    bids_task_name="patternReversalVep",
    bids_event_id={1: "reversal"},
    bids_task_json={
        "TaskName": "Pattern-reversal VEP — checkerboard",
        "Instructions": (
            "Keep your eyes fixed on the central dot and try not to blink "
            "while the checkerboard is reversing. No response is required."
        ),
        "TaskDescription": (
            "Binocular full-field black/white checkerboard that reverses "
            "contrast at a fixed rate (2 reversals/s by default; 1 deg "
            "checks) at constant mean luminance. Each reversal is marked. "
            "Elicits the transient N75-P100-N145 complex over occipital "
            "cortex, with the P100 the robust, clinically standardized "
            "peak (~100 ms). Follows the ISCEV clinical VEP standard and "
            "serves as a fast electrode/signal sanity check. A separate "
            "stereoscopic/monocular VR variant lives in "
            "eegnb.experiments.visual_vep.pattern_reversal_vep."
        ),
    },
)


FACE_SPACE = _meta(
    bids_task_name="faceSpaceDistinctiveness",
    bids_event_id={1: "level0mean", 2: "level1", 3: "level2veridical", 4: "level3caricature"},
    bids_task_json={
        "TaskName": "Face-space distinctiveness continuum",
        "Instructions": (
            "Fixate the central cross. Faces will appear one at a time; "
            "watch each one. Depending on the configured task, either "
            "passively view or make the requested judgment."
        ),
        "TaskDescription": (
            "Norm-based face-space paradigm. Face identities are presented "
            "at graded distances from the average (norm) face: a morph "
            "coefficient of 0 is the average, 1 the veridical identity, and "
            ">1 a caricature (identity vector extrapolated beyond the "
            "original). The event code indexes the distance-from-mean "
            "level; per-trial identity and coefficient are written to a "
            "presentation-order sidecar. Distance from the norm modulates "
            "the P200 (typicality), N250 (distinctiveness/encoding) and "
            "N170; caricatures/distinctive faces yield larger identity "
            "responses. Stimuli are supplied pre-rendered (e.g. webmorphR "
            "or a 3D morphable model) or built by the fallback as a "
            "pixel-space morph toward the average of a supplied face set "
            "(crude, clearly not shape-normalized). Face-space theory: "
            "Valentine (1991); norm-based coding and identity aftereffects: "
            "Leopold et al. (2001), Rhodes & Jeffery (2006); "
            "distinctiveness/caricature ERPs: Schulz, Kaufmann & "
            "Schweinberger (2012); norm-based fMRI: Loffler et al. (2005)."
        ),
    },
)


SWEEP_VEP = _meta(
    bids_task_name="sweepVep",
    bids_event_id={1: "sweepStepOnset"},
    bids_task_json={
        "TaskName": "Sweep VEP — objective contrast / acuity threshold",
        "Instructions": (
            "Keep your eyes on the central dot and try not to blink while "
            "the pattern is flickering. No response is required."
        ),
        "TaskDescription": (
            "Steady-state sweep VEP (Norcia & Tyler 1985). A grating "
            "contrast-reverses at a fixed rate while one parameter — "
            "contrast (contrast-sensitivity threshold) or spatial "
            "frequency (grating-acuity threshold) — is stepped "
            "monotonically across a range, each step held briefly. The "
            "SSVEP amplitude at the reversal frequency rises out of the "
            "noise as the parameter passes threshold; extrapolating the "
            "response-vs-parameter function to zero gives an objective "
            "threshold with no behavioural report. Each step onset is "
            "marked with a single code; the swept value per onset is "
            "recorded in a presentation-order sidecar. Analyse with "
            "eegnb.analysis.frequency_tagging (SNR at the reversal "
            "frequency per step)."
        ),
    },
)


VMMN = _meta(
    bids_task_name="visualMmn",
    bids_event_id={1: "standard", 2: "deviant"},
    bids_task_json={
        "TaskName": "Visual mismatch negativity (vMMN)",
        "Instructions": (
            "Keep your eyes on the central cross. Ignore the surrounding "
            "pattern stream — it is task-irrelevant. (A central "
            "fixation-change detection task can be added to hold attention "
            "away from the stream.)"
        ),
        "TaskDescription": (
            "Passive visual oddball: a frequent standard and a rare "
            "deviant differing in a single feature (orientation by "
            "default, or colour), presented while attention is directed "
            "away from the stream. The deviant-minus-standard difference "
            "wave yields the visual mismatch negativity, a posterior "
            "negativity ~150-350 ms indexing automatic visual "
            "change-detection / prediction error. For a strict design, "
            "pair with an equiprobable control to separate genuine "
            "deviance from stimulus-specific adaptation. Stefanics, "
            "Kremlacek & Czigler (2014), Front Hum Neurosci; Czigler; "
            "Kimura."
        ),
    },
)


_ERP_CORE_CITATION = (
    "Kappenman, Farrens, Zhang, Stewart, & Luck (2021), NeuroImage "
    "225:117465. Stimulus specs and data: https://osf.io/thsqg/"
)


ERP_CORE_N170 = _meta(
    bids_task_name="erpCoreN170",
    bids_event_id={1: "face", 2: "car", 3: "scrambledFace", 4: "scrambledCar"},
    bids_task_json={
        "TaskName": "ERP CORE N170 — face perception",
        "Instructions": (
            "Press the left button for intact images (faces or cars) and "
            "the right button for scrambled images. Respond as quickly "
            "and accurately as you can."
        ),
        "TaskDescription": (
            "Visual presentation of faces, cars, scrambled faces and "
            "scrambled cars (40 of each per block, 2 blocks = 320 trials). "
            "Stimulus 300 ms, ISI 1200–1600 ms jittered. "
            "Elicits the N170 over lateral posterior sites (PO7/PO8) with "
            "a face-specific enhancement. " + _ERP_CORE_CITATION
        ),
    },
)


ERP_CORE_MMN = _meta(
    bids_task_name="erpCoreMMN",
    bids_event_id={1: "standard", 2: "deviant"},
    bids_task_json={
        "TaskName": "ERP CORE MMN — passive auditory oddball",
        "Instructions": (
            "Watch the silent video and ignore the tones. No response "
            "is required — keep still, relaxed, and eyes on the screen."
        ),
        "TaskDescription": (
            "Passive auditory oddball: 1000 Hz standards (80%) and "
            "1200 Hz deviants (20%) presented at ~500 ms SOA while the "
            "subject watches a silent video. 70 ms tone duration with "
            "5 ms rise/fall. Elicits the MMN at fronto-central sites "
            "(Fz/FCz) 100–250 ms post-deviant. " + _ERP_CORE_CITATION
        ),
    },
)


ERP_CORE_N2PC = _meta(
    bids_task_name="erpCoreN2pc",
    bids_event_id={
        1: "targetLeftBlueBlock",
        2: "targetRightBlueBlock",
        3: "targetLeftPinkBlock",
        4: "targetRightPinkBlock",
    },
    bids_task_json={
        "TaskName": "ERP CORE N2pc — lateralized visual search",
        "Instructions": (
            "At the start of each block you are told which colour to "
            "attend (blue or pink). When the display appears, find the "
            "square of the attended colour and report whether the gap "
            "in it is on top or bottom. Keep eyes on the central cross."
        ),
        "TaskDescription": (
            "Bilateral search arrays of one pink and one blue square "
            "with a gap on top or bottom. Subject attends one colour "
            "(blocked) and indicates the gap side. Elicits the N2pc "
            "contralateral to the attended hemifield 175–250 ms "
            "post-stimulus at PO7/PO8. " + _ERP_CORE_CITATION
        ),
    },
)


ERP_CORE_N400 = _meta(
    bids_task_name="erpCoreN400",
    bids_event_id={
        1: "primeRelated",
        2: "targetRelated",
        3: "primeUnrelated",
        4: "targetUnrelated",
    },
    bids_task_json={
        "TaskName": "ERP CORE N400 — semantic priming",
        "Instructions": (
            "You will see pairs of words. Read both and then indicate "
            "whether the second word is semantically related to the first."
        ),
        "TaskDescription": (
            "Prime-target word pairs, half semantically related and half "
            "unrelated. Prime 200 ms, SOA 1000 ms, target 200 ms, "
            "response window 1000 ms. Elicits the N400 at centro-parietal "
            "sites (Cz/CPz) 300–500 ms post-target, more negative for "
            "unrelated pairs. " + _ERP_CORE_CITATION
        ),
    },
)


ERP_CORE_P3 = _meta(
    bids_task_name="erpCoreP3",
    bids_event_id={
        1: "standard",
        2: "target",
    },
    bids_task_json={
        "TaskName": "ERP CORE P3 — active visual oddball",
        "Instructions": (
            "At the start of each block you will see one letter (A–E) "
            "designated as the target. Press the target button for the "
            "target letter and the non-target button for any other letter."
        ),
        "TaskDescription": (
            "Five letters (A, B, C, D, E) with one designated target "
            "per block (5 blocks, each letter serves as target once). "
            "Target probability 20%. Stimulus 200 ms, ISI 1200–1400 ms. "
            "Elicits the P3b at centro-parietal sites (Pz) 300–600 ms "
            "post-target. " + _ERP_CORE_CITATION
        ),
    },
)


ERP_CORE_FLANKER = _meta(
    bids_task_name="erpCoreFlanker",
    bids_event_id={
        1: "congruentCorrect",
        2: "incongruentCorrect",
        3: "congruentError",
        4: "incongruentError",
    },
    bids_task_json={
        "TaskName": "ERP CORE ERN/LRP — arrow flanker",
        "Instructions": (
            "Respond to the direction of the CENTRAL arrow, ignoring "
            "the flanking arrows. Left arrow = left button, right arrow "
            "= right button. Respond as quickly and accurately as you "
            "can."
        ),
        "TaskDescription": (
            "Eriksen arrow flanker with 5-arrow arrays, congruent "
            "(<<<<<) or incongruent (<<><<). 200 ms stimulus, 1200–1400 "
            "ms ITI. Yields two response-locked ERPs: the ERN "
            "(error-related negativity, fronto-central, ~0–100 ms "
            "post-response) and the LRP (lateralized readiness "
            "potential, motor cortex contralateral to the response "
            "hand, pre-response). " + _ERP_CORE_CITATION
        ),
    },
)


BY_NAME: dict[str, SimpleNamespace] = {
    "visual-fpvs-stothart": STOTHART,
    "visual-fpvs-rossion": ROSSION,
    "visual-rsvp-things": RSVP_THINGS,
    "visual-retinotopy-ssvep": RETINOTOPY_SSVEP,
    "visual-pattern-reversal": PATTERN_REVERSAL_VEP,
    "visual-face-space": FACE_SPACE,
    "visual-sweep-vep": SWEEP_VEP,
    "visual-mmn": VMMN,
    "erp-core-n170": ERP_CORE_N170,
    "erp-core-mmn": ERP_CORE_MMN,
    "erp-core-n2pc": ERP_CORE_N2PC,
    "erp-core-n400": ERP_CORE_N400,
    "erp-core-p3": ERP_CORE_P3,
    "erp-core-flanker": ERP_CORE_FLANKER,
}
