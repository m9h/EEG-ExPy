
# Available Experiments

### Visual P300 with Oddball paradigm
The visual P300 is a spike that occurs 300ms after perceiving a visual stimulus that has implications on decision making. This was validated in Muse by Alexandre Barachant with the Oddball paradigm, in which low-probability target items (oddballs) are interspersed with high probability non-target items. With AB's paradigm, the experiment takes about 10 minutes to run (5 x 2 minute trials). Although the Muse's sensors aren't in the ideal position for detecting the P300, AB was able to attain "good" accuracy in identifying P300 spikes.

### N170
The N170 is an ERP specifically related to the perception of faces. This was validated in Muse by Hubert with a 12 minute experiment (6 x 2 minute trials). Stimuli consists of 12 pictures of houses and 12 pictures of faces. Accuracy of N170 detection is rather good.

### SSVEP
The steady state visual evoked potential is a frequency response produced visual stimulation at specific frequencies. It was validated by Hubert in a 12 minute experiment (6 x 2 minute trials). Stimulation frequencies of 30hz and 20hz were used and an extra electrode at POz was added. Found clear peaks in the PSD at the stimulation frequencies. The peaks were most significant at the extra electrode, which is closest to the primary visual regions, but was detectable at all electrodes and found to have remarkably high accuracy when using a filter bank approach to isolate specific frequencies.

## Modernization-line paradigms

These are the newer `BaseExperiment` paradigms on the `morgan/modernize` line, launchable by their CLI key. Each carries BIDS-EEG metadata (`eegnb.bids.paradigms`) and, for the frequency-tagged ones, has an analysis counterpart in `eegnb.analysis.frequency_tagging` (per-tag SNR, harmonic sum, per-sector topography) alongside the design-side `eegnb.analysis.power`.

### THINGS RSVP — `visual-rsvp-things`
Rapid serial visual presentation of unique natural-object images from the THINGS database at 5 Hz (100 ms on / 100 ms blank), one marker per image onset, for EEG-to-image decoding. Replicates the Alljoined-1.6M acquisition protocol. Every image is unique, so identity per onset is written to a presentation-order sidecar CSV rather than the event code. Frame-locked presentation; optional photodiode patch for timing validation.

### FPVS Fastball (Stothart) — `visual-fpvs-stothart`
Fast periodic visual stimulation object-recognition oddball: standards at a 3 Hz base rate with a deviant every 5th item (0.6 Hz). Analysis is frequency-domain (SNR at 0.6 Hz and harmonics). Falls back to the bundled N170 face/house images for out-of-the-box smoke tests.

### FPVS Face Individuation (Rossion) — `visual-fpvs-rossion`
FPVS face-identity oddball (Liu-Shuang, Norcia & Rossion 2014): a base face identity repeated at 5.88 Hz with a novel identity every 5th item (1.176 Hz). The oddball-frequency response indexes neural face individuation, maximal at right occipito-temporal sites.

### SSVEP Sector Retinotopy — `visual-retinotopy-ssvep`
Frequency-tagged visual-field mapping: contrast-reversing checkerboard patches in visual-field sectors (four quadrants by default), each reversing at a distinct integer-divisor frequency (15/12/10/8.57 Hz on a 60 Hz display). `multiplex` mode flickers all sectors at once (separated by frequency); `sequential` mode does one sector per block. The SNR and scalp topography at each tag index coarse (quadrant/hemifield) retinotopic position. This is coarse retinotopy, **not** pRF mapping.

### Pattern-reversal VEP — `visual-pattern-reversal`
Binocular full-field black/white checkerboard reversing at a fixed rate (2 reversals/s, 1° checks, ISCEV standard), each reversal marked. Elicits the transient N75–P100–N145 complex over occipital cortex; the robust P100 also makes it a fast electrode/signal sanity check.

### Face-space distinctiveness — `visual-face-space`
Norm-based face-space paradigm: face identities presented at graded distances from the average (norm) face (morph coefficient 0 = mean, 1 = veridical, >1 = caricature). The event code indexes the distance level; per-onset identity/coefficient go to a presentation-order sidecar. Modulates the P200 (typicality), N250 (distinctiveness) and N170. Reads a pre-rendered continuum (webmorphR / 3D morphable model) when supplied, else builds a pixel-space fallback by morphing a source face set toward/beyond its pixel mean.

### Sweep VEP — `visual-sweep-vep`
Objective contrast-sensitivity / grating-acuity threshold (Norcia & Tyler 1985). A grating contrast-reverses at a fixed rate while either its contrast or spatial frequency is stepped monotonically across a range; the SSVEP at the reversal frequency rises out of the noise as the parameter passes threshold, and extrapolating the response-vs-parameter function to zero gives the threshold with no behavioural report. Each step onset is marked and the swept value per onset is written to a presentation-order sidecar. Analyse with `eegnb.analysis.frequency_tagging`.

### Visual MMN — `visual-mmn`
Passive visual oddball eliciting the visual mismatch negativity (Stefanics, Kremláček & Czigler 2014): a frequent standard and rare deviant differing in a single feature (orientation by default, or colour), with attention directed away from the stream. The deviant-minus-standard difference wave shows a posterior negativity ~150–350 ms indexing automatic visual change-detection. Reuses the constrained oddball sequence generator shared with the auditory ERP-CORE MMN. For a strict design, pair with an equiprobable control block to subtract stimulus-specific adaptation.

### ERP CORE suite — `erp-core-*`
The six standardized ERP CORE paradigms (Kappenman & Luck 2021): N170 (faces/cars), MMN (auditory oddball), N2pc (visual search), N400 (semantic priming), P3 (active oddball), and ERN/LRP (arrow flanker).

## Old experiments
### Go/No-Go
An experiment designed to investigate the event-related potentials that can be detected during a Go-No-Go Task, which measures executive, inhibitory control and sustained attention. The subject is rapidly presented with a sequence of circles and squares and is asked to indicate, by pressing the spacebar, whether a shape is a circle.


### SSAEP
The steady state auditory evoked potential is a frequency response produced when hearing modulating tones of certain frequencies. It was validated in Muse by Hubert, who used 45hz and 40hz amplitude modulation applied to 900 and 770h carrier frequencies. A PSD of the produced EEG signal showed clear spikes, correspondingly, at 45 and 40hz in the temporal electrodes. The N100 and P200 complex was also noticed at the beginning of stimulus onset.


### C1 and P1
C1 and P1 are two ERPs related to the perception of a visual stimulus. The C1 is the first component, appearing in the 65-90ms range after stimulus onset while the P1 appears later, around 100ms.

C1 and P1 were validated in Muse by Hubert with a left/right visual field experiment. Comparing ERPs to left or right-field presentation of visual stimuli revealed a contralateral pattern of C1 and P1 in both the temporal and anterior electrodes. However, their timing seems a little delayed.


### Auditory P300
Same as the visual P300, but dependent on auditory stimulus. Auditory P300s are normally less distinguishable than visual P300s, but they may be more suited to the Muse since its electrodes are closer to auditory centers (superior temporal cortex).


## Unvalidated Experiments and other phenomena

### N100 - P200
The combination of a negative evoked potential around 100ms after any unpredictable stimulus and a positive potential 200ms after. These were noticed in Hubert's SSAEP experiment, but not independently classified or tested.

### On-task Beta
Noticed in Hubert's visual grating test, but difficult to extract.

### Alpha reset
A noticeable increase in alpha activity after stimulus presentation ends. Noticed in Hubert's visual grating test.
