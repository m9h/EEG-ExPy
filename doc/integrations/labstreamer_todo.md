# LabStreamer integration — TODO

Branch: `morgan/labstreamer-integration` off `morgan/modernize`.
Design doc: `labstreamer.md` (same folder). Read that first.

## Phase 1 — input path (timing-audit MVP)

- [ ] `eegnb/devices/labstreamer.py`: `LabStreamerSession` with mDNS +
      env-var fallback, Socket.IO v3 client, backoff reconnect.
- [ ] `LabStreamerMarkers`: port the device's threshold/direction/debounce
      logic from firmware 1.2.5 JS (`/main.js` on the device at
      `http://LabStreamer.local:3000/main.js`). Re-run detection in Python on
      the `data` stream.
- [ ] `pylsl.StreamOutlet` for markers, 4 channels, irregular rate, JSON
      payload with device-clock timestamps.
- [ ] `tests/test_labstreamer.py`: unit tests with a mocked Socket.IO server
      and recorded `data` event samples. Include replay of a synthetic
      photodiode burst, confirm outlet receives one marker.

## Phase 2 — CLI

- [ ] `eegnb/cli/labstreamer_cmd.py`: `scan`, `status`, `set`, `bridge`,
      `test-pulse`, `update`, `install-service`.
- [ ] Wire the subcommand into `eegnb/cli/__main__.py`.
- [ ] `scan` discovers via mDNS, prints firmware version + `loaded controls`.
- [ ] `install-service`: template a systemd user unit running `bridge` at login.

## Phase 3 — timing-audit report

- [ ] `eegnb/reports/timing_audit.py`: pair software markers to photodiode
      markers, compute diff stats, plot histogram.
- [ ] `eegnb/paradigms/fsl_timing.py`: per-paradigm latency tolerances
      (N170: 5 ms std; FPVS: 2 ms std; P300: 10 ms std).
- [ ] `eegnb/reports/templates/report.Pnw`: add `## Timing audit` section
      (guarded so it no-ops when no LabStreamer stream was present).
- [ ] `eegnb runexp`: on run end, if LabStreamer stream was recorded, run
      timing audit and include in report. `--enforce-timing-tolerance` flag
      fails the run when above threshold.

## Phase 4 — output path (TTL)

- [ ] `LabStreamerTrigger.push(marker)`: Socket.IO `controls` emit with
      `pulseValue` + `pulseActive` toggle.
- [ ] Thread-safe: call from paradigm main thread without blocking > 1 ms.
- [ ] Integrate into `EEG` class so `push_marker()` optionally fans out to
      both LSL outlet and LabStreamer. Gate with `eeg.labstreamer_trigger`
      attribute set at device init time.

## Phase 5 — board wiring docs

- [ ] `doc/integrations/labstreamer_wiring.md`: per-board cabling + firmware.
  - [ ] FreeEEG32 / FreeEEG128: identify a free digital input, document how
        to include the digital byte in the sample frame (check `freeeeg128`
        firmware repo).
  - [ ] PiEEG: pick a GPIO, sample inside the capture read loop, stamp into
        the stream.
  - [ ] IronBCI: same approach as PiEEG if HAT-compatible; otherwise
        investigate.
  - [ ] Muse / consumer-fixed boards: document as audit-only.
- [ ] `eegnb labstreamer test-pulse` walk-through per board.

## Phase 7 — hardware-stack characterization

- [ ] `eegnb labstreamer characterize --rig <name>`: run a scripted flash
      sequence (e.g. 500 flashes at random 0.5–2 s ISI) on the stim display,
      capture photodiode markers, compute timing distribution, save
      `hardware_profiles/<rig>.json`.
- [ ] Ship a starter catalog: Framework Laptop 13 on Fedora 44 (internal
      display and one common external monitor), Raspberry Pi 5 headless,
      whatever MacBook we have handy.
- [ ] `eegnb runexp` reads the rig's profile and warns if paradigm tolerance
      is tighter than the rig's known jitter.

## Phase 6 — bi-directional runtime & tests

- [ ] Runtime: on `--with-labstreamer` with TTL wired, paradigm emits both
      LSL marker and TTL pulse on every stim onset. Confirm the amp's
      trigger-channel recording shows the pulse.
- [ ] Integration test on Unicorn: record 30s, assert software markers,
      photodiode markers, and amp TTL markers are all present and
      pair-aligned within 10 ms.

## Known caveats (from 2026-04-22 session)

- Firmware update 1.1.1 → 1.2.5 left the Node web service down post-install;
  required a power cycle. Document this and gate the `update` CLI to warn +
  suggest ≥ 10 min wait before manual intervention.
- mDNS record stays live during update; only port 3000 goes down. Use
  port-3000 TCP probe as readiness check, not mDNS.
- Engine.IO v3 only. Do not use `python-socketio[client]` default v4 transport
  without pinning `EIO=3`.
- Device's own trigger decisions are not emitted as discrete events over
  Socket.IO in 1.2.5. Re-implement detection in Python against the sample
  stream.

## Nice-to-haves (not blocking merge)

- [ ] Ingest the device's `latency` event (it self-reports jitter) and
      surface in report.
- [ ] Expose `extStream` external-input path — useful if someone feeds the
      LabStreamer an extra channel (e.g., button box).
- [ ] Wireless operation — device supports it but wired is more reliable for
      timing-critical work. Test later.
