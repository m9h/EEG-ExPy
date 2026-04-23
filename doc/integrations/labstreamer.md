# LabStreamer integration

Neurobehavioral Systems LabStreamer as the **timing-truth reference** for every
EEG-ExPy experiment, independent of which EEG board is recording. On boards
that can capture a TTL pulse (FreeEEG32/128, PiEEG, IronBCI — all open hardware
where we control the firmware), the same paradigm marker also drives a hardware
pulse into the board, giving a second timestamp in the board's own sample clock.

## Goal

Stimulus timing on consumer and DIY EEG rigs has always been the unverified
leg: we trust `time.time()` in the paradigm, trust the OS to schedule the
screen flip, trust the LSL outlet to forward the marker on time, trust the
USB/GPIO link to deliver the sample, trust the driver to timestamp it. Any of
those can jitter by 5–50 ms and we usually never see it.

The LabStreamer breaks that chain by physically observing the stimulus
(photodiode / mic) with a hardware clock, so every EEG-ExPy run with
`--with-labstreamer` produces a per-trial timing audit:

1. How late did the screen actually flash vs when the paradigm said it should?
2. How far apart are the paradigm's software marker and the board-recorded
   marker? (Requires TTL capture on the board.)
3. Is the distribution tight enough for the paradigm's ERP of interest?

The audit runs the same way regardless of which board is recording — it is
an **independent** reference, not wired through the board. That makes it the
portable timing sanity check across FreeEEG32/128, PiEEG/IronBCI, and anything
else we add later.

## Two modes of use

The same LabStreamer bridge serves two distinct purposes:

1. **Per-run audit** — one paradigm on one rig. Did *this* N170 run have
   tight-enough timing to trust the ERP? Report gets attached to each run
   and lives next to the EEG recording.
2. **Hardware-stack characterization** — "what is the stim-timing profile of
   *this* laptop + OS + display combo at rest, independent of paradigm?" Run
   a scripted flash sequence at known intervals, measure the distribution of
   screen-flash latency, and save a JSON profile (`hardware_profiles/<rig>.json`)
   that becomes the rig's baseline. Future runs on that rig can compare.

Example rigs we want profiles for:

- Framework Laptop 13 on Fedora 44 (wired display, built-in screen; and again
  with common external monitors).
- Raspberry Pi 5 headless HAT setup (for PiEEG field kits).
- MacBook / Linux reference combos for cross-platform timing numbers.

This turns "I think my laptop is fine for EEG" from folklore into a measured
number with a distribution. Over time the profile catalog becomes a reference
that tells a new user whether their laptop is good enough for a given paradigm
before they collect any data.

## Context snapshot (captured 2026-04-22)

- Device on lab LAN: `LabStreamer.local` → `192.168.108.18` (MAC `00:c0:08:93:57:d3`, MOXA OUI)
- Firmware: software `1.2.5`, hardware `1.1.0` (freshly updated from `1.1.1`)
- Web UI / API: `http://LabStreamer.local:3000/` — Node + Express serving HTML,
  Socket.IO (Engine.IO v3) as the only live data transport. No auth.
- mDNS advertisement: `_workstation._tcp` on port 9 (cosmetic; real service is 3000)

### Device control surface (Socket.IO)

Observed event names on firmware 1.2.5:

- Client → server: `controls`, `connect wireless`, `enable wireless`,
  `refresh network settings`, `version-select`, `acquire`, and pulse controls
  via the `controls` channel (`pulseActive`, `pulseInactive`, `pulseValue`).
- Server → client: `data`, `latency`, `streams`, `loaded controls`,
  `network config`, `version`, `versions`, `beta-versions`, `message`,
  `new connection`.

`loaded controls` on 1.2.5 includes these **new** keys relative to 1.1.1 (each
unlocks something the bridge should expose):

| Key | Meaning | Why it matters here |
|---|---|---|
| `acquire` | boolean start/stop | Explicit acquire control — bridge can gate on this |
| `digitalChannel`, `digitalMode`, `digitalFilter`, `digitalPretime`, `digitalPosttime`, `digitalVisible`, `digitalVerticalOffset`, `digitalVoltsPerDiv` | TTL digital input | Second trigger-source option alongside analog thresholds |
| `pulseActive`, `pulseInactive`, `pulseValue` | Pulse output shaping | **This is the TTL output path to the EEG amp** |
| `extChannel`, `extStream`, `linearizeExternal` | External input stream | Not used in first pass |
| `maxBins`, `nBins`, `maxLatency` | Latency histogram | The device measures its own round-trip; worth exposing in the timing audit |
| `thresholdCrossingMinActive`, `thresholdCrossingMinInactive` | Debounce windows | Configure via CLI, don't hardcode |
| `triggerStream` | Bind channel to output stream | Output routing |

Default channel config on this device: analog ch0 = `white` (photodiode),
ch1 = `sound`, ch2/ch4 = unused. Thresholds midscale (2047 on a 12-bit ADC),
pre/post windows 10 ms / 500 ms.

## Architecture

Two classes in `eegnb/devices/labstreamer.py`, sharing one Socket.IO connection
owned by a `LabStreamerSession` context manager. Separation keeps the input
path (which is always-on in timing-audit mode) from the output path (which
is opt-in and amp-specific).

```
eegnb/devices/labstreamer.py
    LabStreamerSession(host, port=3000)   # socket.io connection, event pump
    LabStreamerMarkers(session, channels) # INPUT: data events → LSL outlet
    LabStreamerTrigger(session, pulse_ms) # OUTPUT: paradigm call → TTL pulse
eegnb/cli/labstreamer_cmd.py              # `eegnb labstreamer ...`
eegnb/reports/timing_audit.py             # post-run timing diff + report block
tests/test_labstreamer.py                 # unit + integration tests
doc/integrations/labstreamer.md           # (this file)
```

### `LabStreamerSession`

Thin wrapper over `python-socketio.Client`. Handles:
- mDNS-resolve `LabStreamer.local` (fallback to env var `LABSTREAMER_HOST` or IP).
- Engine.IO v3 (the device is stuck on v3 — verified against firmware 1.2.5).
- Reconnect with backoff. Network hiccups must not crash the experiment runner.
- Pub/sub dispatch so `LabStreamerMarkers` and `LabStreamerTrigger` can attach.
- Exposes `get_controls() -> dict` and `set_controls(dict)` for CLI tooling.

### `LabStreamerMarkers` — input path (always on in audit mode)

1. On start: verify `acquire=true` via `set_controls`.
2. Subscribe to `data` events. Replay the device's threshold / direction /
   debounce logic in Python against the sample stream so what the scope *shows*
   as a trigger is what we *emit* as a marker. (We cannot just rely on the
   device's own trigger decisions; those do not arrive as discrete events over
   Socket.IO in firmware 1.2.5 — they appear only in the live display stream.)
3. Publish a `pylsl.StreamOutlet`:
   - `name="LabStreamer"`, `type="Markers"`, `channel_count=4`,
     `nominal_srate=IRREGULAR_RATE`, `channel_format=cft_string`.
   - Channel labels: `["ch0_photodiode", "ch1_sound", "ch2", "ch3"]`.
   - Marker payload: JSON string with `{channel, direction, sample_index,
     device_ts}` so downstream can reconstruct device-clock timestamps.
4. On stop: clean disconnect, flush outlet.

### `LabStreamerTrigger` — output path (opt-in, amp-aware)

1. On construction, take:
   - Pulse width (ms), active level, idle level.
   - Amp type (for documentation and warnings only — it does not talk to the amp).
2. `push(marker: int | str)` emits via Socket.IO `controls` channel:
   - Set `pulseValue` to the marker code (device supports 8-bit values in
     digital mode; analog pulse carries timing but no code bits).
   - Toggle `pulseActive` for `pulse_ms`, then back to `pulseInactive`.
3. Thread-safe: `push` is safe to call from paradigm main thread. Uses the
   session's eventloop.
4. Not a replacement for the LSL markers outlet. The paradigm should push the
   marker **both** to the existing LSL outlet (for software-clock record) and
   to `LabStreamerTrigger` (for amp sample-clock record). The timing-audit
   compares the two.

### Timing-audit report

Post-run, `eegnb runexp` (with `--with-labstreamer`) generates a timing block
in the pweave report (`eegnb/reports/templates/report.Pnw`):

- Paired diff: for each paradigm marker, find the nearest LabStreamer
  photodiode (or sound) marker within a configurable window, compute
  `dt = ls_photodiode_ts - paradigm_marker_ts`.
- Summary stats: mean, median, std, 5/95 pct, max. Histogram.
- Pass/fail against a paradigm-level tolerance. N170 wants ≤ 5 ms std; FPVS
  wants ≤ 2 ms. Tolerances live in `eegnb/paradigms/fsl_timing.py`.
- If `LabStreamerTrigger` was active, add a second diff between paradigm
  marker timestamps and the amp's TTL-received timestamps (extracted from the
  EEG recording's trigger channel during post-processing).

## Operational modes

| Mode | `--with-labstreamer` | Amp TTL wired | Behavior |
|---|---|---|---|
| Off | absent | n/a | No change from today |
| Audit only | present, `--no-hw-trigger` | no | Photodiode markers + timing report |
| Full | present (default) | yes | Photodiode markers + TTL pulses + full diff |

The default when `--with-labstreamer` is passed is to attempt TTL output and
warn (not fail) if the amp-side config does not expect it.

## CLI surface

```
eegnb labstreamer scan             # mDNS discovery + print version + controls
eegnb labstreamer status           # live read of device state
eegnb labstreamer set K=V ...      # poke controls (threshold, debounce, etc.)
eegnb labstreamer bridge           # run standalone bridge (input path only)
eegnb labstreamer test-pulse       # fire a single pulse (for wiring tests)
eegnb labstreamer update --to X    # firmware update via `version-select`
eegnb labstreamer install-service  # systemd user unit for always-on bridge
```

`eegnb runexp ... --with-labstreamer` implies `bridge` for the run's duration.

## Target boards

Input path (photodiode / mic) already works on this unit today and is
board-agnostic: it drops an LSL markers stream into the XDF alongside
whatever the board records. Output path is per-board because none of our
target boards has a stock TTL trigger port — each needs a documented pin
to tap and board-side firmware/software to latch the pulse into the sample
stream.

| Board | TTL-input approach | Status |
|---|---|---|
| FreeEEG32 | Spare digital input on the MCU breakout; ADC firmware must include the digital byte in the sample frame | Research needed. See `freeeeg128` repo for firmware entrypoint. |
| FreeEEG128 | Same family as FreeEEG32; check whether the 128-channel firmware branch already reserves a trigger bit | Research needed |
| PiEEG (Raspberry Pi HAT) | Any free Pi GPIO; capture-side code samples the GPIO inside the read loop | Viable; Pi GPIO latency is ~μs |
| IronBCI | Inherits PiEEG's GPIO approach if same HAT; otherwise investigate | Research needed |

Boards that cannot be modified (Muse etc.) operate in **audit-only mode**:
no TTL, but photodiode markers still give the screen-vs-code diff. That
alone is already more timing information than most EEG-ExPy users have today.

Per-board wiring and firmware notes live in
`doc/integrations/labstreamer_wiring.md` (followup — opens as part of Phase 5
in the TODO).

## Failure modes and handling

1. **Device disappears mid-run.** `LabStreamerSession` reconnects in the
   background; the runner keeps going. Report flags the gap but does not
   abort the experiment.
2. **Port 3000 refused after firmware update.** Reproduced 2026-04-22:
   1.1.1 → 1.2.5 install never restarted the Node service. Required a power
   cycle; LEDs went all solid, no flash-write blink. Fix: document this in
   the `update` CLI subcommand and warn user to wait ≥ 10 min, then pinhole
   reset, then power cycle as last resort.
3. **Threshold noise on photodiode.** `thresholdCrossingMinActive` debounce
   is per-device; calibrate during `eegnb labstreamer scan` against ambient.
4. **TTL output miswired.** `test-pulse` subcommand exists to fire a single
   pulse while the user watches the amp's input channel.

## Scope and non-goals

**In scope (this PR):**
- Input + output path, timing-audit report, CLI, tests, docs.
- Unicorn and OpenBCI amp notes.

**Out of scope (followups):**
- Wireless bridging (device supports it; we have not tested it).
- Beta firmware channel (`beta-versions`).
- Histogram `latency` event ingestion (device self-reports jitter — nice to
  have but not needed for v1).
- Multi-device coordination.

## References

- Device API observed live; no vendor-published Socket.IO spec. Event names
  extracted from the device's own `/main.js`.
- Firmware 1.2.5 `loaded controls` schema captured in this doc's context
  snapshot.
- EEG-ExPy LSL marker outlet already implemented by commit `02b42dc` on
  `morgan/modernize` — the LabStreamer outlet is an additional stream, not a
  replacement.
