"""Bridge opentrack's UDP head-pose output onto an LSL stream.

opentrack (https://github.com/opentrack/opentrack) tracks 6-DoF head pose and
can broadcast it over UDP via its ``opentrack-proto-udp`` output plugin. It has
no native LSL or XDF output, so this module receives those UDP packets and
republishes them as an LSL stream — putting head pose on the same clock as EEG,
eye tracking and response devices so everything lands in one synchronised XDF.

Wire format
-----------
opentrack's UDP protocol sends one packet per pose update: **6 little-endian
doubles, 48 bytes total**, in opentrack's internal pose order::

    [x, y, z, yaw, pitch, roll]

Translation is in centimetres and rotation in degrees. Packets of any other
size are counted and skipped (reported once) rather than silently mangled —
if you see those, check your opentrack version's protocol settings, since
plugin wire formats can change between releases.

Usage
-----
In opentrack choose output "UDP over network" and point it at this host/port
(default ``127.0.0.1:4242``), then::

    python -m eegnb.devices.opentrack_lsl                 # bridge until Ctrl-C
    python -m eegnb.devices.opentrack_lsl --port 5005
    python -m eegnb.devices.opentrack_lsl --selftest      # no opentrack needed

``--selftest`` runs a synthetic sender plus a verifying inlet, so the bridge
can be validated end-to-end without opentrack installed or a camera attached.

The stream is published at irregular rate by default: opentrack's update rate
follows its tracker (camera fps for optical trackers), so declaring a nominal
rate would be a lie unless you know it. Pass ``--srate`` if you do.
"""

from __future__ import annotations

import argparse
import signal
import socket
import struct
import sys
import threading
import time

# opentrack proto-udp: 6 little-endian doubles = 48 bytes.
_PACKET_STRUCT = struct.Struct("<6d")
PACKET_SIZE = _PACKET_STRUCT.size  # 48

#: Channel order as opentrack packs it, with units for the LSL/XDF metadata.
CHANNELS: tuple[tuple[str, str], ...] = (
    ("x", "cm"),
    ("y", "cm"),
    ("z", "cm"),
    ("yaw", "deg"),
    ("pitch", "deg"),
    ("roll", "deg"),
)

DEFAULT_UDP_HOST = "127.0.0.1"
DEFAULT_UDP_PORT = 4242  # opentrack's default UDP output port
DEFAULT_STREAM_NAME = "opentrack"
DEFAULT_STREAM_TYPE = "HeadPose"


def decode_packet(payload: bytes) -> tuple[float, ...]:
    """Decode one opentrack UDP packet into ``(x, y, z, yaw, pitch, roll)``.

    Raises ``ValueError`` if the payload is not exactly :data:`PACKET_SIZE`
    bytes, so callers can count malformed packets instead of misreading them.
    """
    if len(payload) != PACKET_SIZE:
        raise ValueError(
            f"expected {PACKET_SIZE}-byte opentrack packet "
            f"(6 doubles), got {len(payload)} bytes"
        )
    return _PACKET_STRUCT.unpack(payload)


def encode_packet(pose) -> bytes:
    """Encode a 6-value pose into opentrack's UDP wire format.

    Used by the self-test's synthetic sender; also handy for replaying a
    recorded pose trace into a consumer.
    """
    vals = tuple(float(v) for v in pose)
    if len(vals) != 6:
        raise ValueError(f"pose must have 6 values, got {len(vals)}")
    return _PACKET_STRUCT.pack(*vals)


def _build_stream_info(name: str, stype: str, srate: float, source_id: str):
    from pylsl import StreamInfo

    info = StreamInfo(
        name=name,
        type=stype,
        channel_count=len(CHANNELS),
        nominal_srate=srate,
        channel_format="float32",
        source_id=source_id,
    )
    # Channel metadata travels into the XDF header; downstream tools rely on
    # these labels/units rather than positional guessing.
    chns = info.desc().append_child("channels")
    for label, unit in CHANNELS:
        ch = chns.append_child("channel")
        ch.append_child_value("label", label)
        ch.append_child_value("unit", unit)
        ch.append_child_value("type", "Position" if unit == "cm" else "Orientation")
    acq = info.desc().append_child("acquisition")
    acq.append_child_value("manufacturer", "opentrack")
    acq.append_child_value("protocol", "proto-udp")
    return info


class OpentrackLSLBridge:
    """Receive opentrack UDP pose packets and republish them over LSL.

    Parameters
    ----------
    udp_host, udp_port : str, int
        Local address to bind for opentrack's packets.
    name, stype : str
        LSL stream name and type.
    srate : float
        Nominal sampling rate to declare. ``0`` (default) means irregular,
        which is honest for camera-driven trackers.
    source_id : str | None
        LSL source id; defaults to one derived from host/port so a restarted
        bridge is recognised as the same source.
    """

    def __init__(
        self,
        udp_host: str = DEFAULT_UDP_HOST,
        udp_port: int = DEFAULT_UDP_PORT,
        name: str = DEFAULT_STREAM_NAME,
        stype: str = DEFAULT_STREAM_TYPE,
        srate: float = 0.0,
        source_id: str | None = None,
    ):
        self.udp_host = udp_host
        self.udp_port = udp_port
        self.name = name
        self.stype = stype
        self.srate = float(srate)
        self.source_id = source_id or f"opentrack-udp-{udp_host}-{udp_port}"

        self._sock: socket.socket | None = None
        self._outlet = None
        self._stop = threading.Event()

        # Counters, readable after/while running.
        self.n_forwarded = 0
        self.n_malformed = 0
        self.last_pose: tuple[float, ...] | None = None

    # -- lifecycle ------------------------------------------------------- #
    def open(self) -> "OpentrackLSLBridge":
        from pylsl import StreamOutlet

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.udp_host, self.udp_port))
        self._sock.settimeout(0.25)  # so stop() is responsive

        info = _build_stream_info(self.name, self.stype, self.srate, self.source_id)
        self._outlet = StreamOutlet(info)
        return self

    def close(self) -> None:
        self._stop.set()
        if self._sock is not None:
            self._sock.close()
            self._sock = None
        # Dropping the outlet un-publishes the stream.
        self._outlet = None

    def __enter__(self):
        return self.open()

    def __exit__(self, *exc):
        self.close()

    def stop(self) -> None:
        self._stop.set()

    # -- pump ------------------------------------------------------------ #
    def pump_once(self, timeout: float | None = None) -> tuple[float, ...] | None:
        """Receive and forward at most one packet.

        Returns the forwarded pose, or ``None`` on timeout or a malformed
        packet (which increments :attr:`n_malformed`).
        """
        from pylsl import local_clock

        if self._sock is None or self._outlet is None:
            raise RuntimeError("bridge is not open(); call open() first")
        if timeout is not None:
            self._sock.settimeout(timeout)
        try:
            payload, _addr = self._sock.recvfrom(1024)
        except socket.timeout:
            return None
        except OSError:
            return None  # socket closed under us during shutdown

        # Stamp as close to arrival as possible.
        ts = local_clock()
        try:
            pose = decode_packet(payload)
        except ValueError:
            self.n_malformed += 1
            if self.n_malformed == 1:
                print(
                    f"[opentrack-lsl] ignoring malformed packet "
                    f"({len(payload)} bytes, expected {PACKET_SIZE}); "
                    "check opentrack's UDP protocol settings. "
                    "Further malformed packets will be counted silently.",
                    file=sys.stderr,
                )
            return None

        self._outlet.push_sample(list(pose), ts)
        self.n_forwarded += 1
        self.last_pose = pose
        return pose

    def run(self, duration: float | None = None, report_every: float = 5.0) -> None:
        """Pump until :meth:`stop`, ``duration`` elapses, or Ctrl-C."""
        t0 = time.monotonic()
        last_report = t0
        last_count = 0
        while not self._stop.is_set():
            if duration is not None and (time.monotonic() - t0) >= duration:
                break
            self.pump_once()
            now = time.monotonic()
            if report_every and (now - last_report) >= report_every:
                rate = (self.n_forwarded - last_count) / (now - last_report)
                pose = self.last_pose
                posestr = (
                    " last=[" + ", ".join(f"{v:+.2f}" for v in pose) + "]"
                    if pose else " (no packets yet — is opentrack sending?)"
                )
                print(
                    f"[opentrack-lsl] {self.n_forwarded} forwarded, "
                    f"{rate:.1f} pkt/s, {self.n_malformed} malformed.{posestr}",
                    file=sys.stderr,
                )
                last_report, last_count = now, self.n_forwarded


# -- self-test ----------------------------------------------------------- #

def _selftest(n: int = 50, port: int = 0) -> int:
    """Run bridge + synthetic sender + verifying inlet in one process.

    Validates the whole path without opentrack or a camera: encode -> UDP ->
    bridge -> LSL outlet -> inlet -> compare against what was sent.
    """
    from pylsl import StreamInlet, resolve_byprop

    # Bind an ephemeral port if none given, so the test never collides with a
    # real opentrack bridge already running on 4242.
    if port == 0:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.bind((DEFAULT_UDP_HOST, 0))
        port = probe.getsockname()[1]
        probe.close()

    name = f"opentrack-selftest-{port}"
    sent = [
        (float(i), float(i) * 2, float(i) * 3, float(i) * 0.5, -float(i), float(i) % 7)
        for i in range(n)
    ]
    print(f"  selftest: UDP 127.0.0.1:{port}, stream {name!r}, {n} packets")

    bridge = OpentrackLSLBridge(udp_port=port, name=name).open()
    try:
        streams = resolve_byprop("name", name, timeout=5)
        if not streams:
            print("  FAIL: bridge's LSL stream not discoverable")
            return 1
        sinfo = streams[0]
        print(
            f"  resolved: name={sinfo.name()} type={sinfo.type()} "
            f"ch={sinfo.channel_count()} srate={sinfo.nominal_srate()}"
        )
        inlet = StreamInlet(sinfo, max_chunklen=8)
        inlet.open_stream(timeout=5.0)

        # Channel metadata round-trip.
        ch = inlet.info().desc().child("channels").child("channel")
        labels = []
        for _ in range(len(CHANNELS)):
            labels.append(ch.child_value("label"))
            ch = ch.next_sibling()
        print(f"  channel labels: {labels}")
        if labels != [c[0] for c in CHANNELS]:
            print("  FAIL: channel labels did not round-trip")
            return 1

        # Sender thread emits packets; main thread pumps the bridge.
        def send():
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            time.sleep(0.2)
            for pose in sent:
                s.sendto(encode_packet(pose), (DEFAULT_UDP_HOST, port))
                time.sleep(0.002)
            s.sendto(b"\x00\x01\x02", (DEFAULT_UDP_HOST, port))  # malformed
            s.close()

        t = threading.Thread(target=send, daemon=True)
        t.start()
        deadline = time.monotonic() + 15
        while bridge.n_forwarded < n and time.monotonic() < deadline:
            bridge.pump_once(timeout=0.2)
        t.join(timeout=2)
        # Drain the deliberate malformed packet.
        bridge.pump_once(timeout=0.5)

        time.sleep(0.4)
        chunk, ts = inlet.pull_chunk(timeout=3.0, max_samples=n * 2)
        print(
            f"  forwarded={bridge.n_forwarded} malformed={bridge.n_malformed} "
            f"| inlet received={len(chunk)} samples"
        )
        if len(chunk) < n:
            print(f"  FAIL: expected >= {n} samples, got {len(chunk)}")
            return 1
        if bridge.n_malformed != 1:
            print(f"  FAIL: expected 1 malformed packet, counted {bridge.n_malformed}")
            return 1

        first_ok = all(abs(a - b) < 1e-3 for a, b in zip(chunk[0], sent[0]))
        last_ok = all(abs(a - b) < 1e-3 for a, b in zip(chunk[n - 1], sent[n - 1]))
        print(f"  first sample {['FAIL','OK'][first_ok]}: {[round(v,2) for v in chunk[0]]} vs {sent[0]}")
        print(f"  last  sample {['FAIL','OK'][last_ok]}: {[round(v,2) for v in chunk[n-1]]} vs {sent[n-1]}")
        if not (first_ok and last_ok):
            return 1
        if len(ts) and len(ts) > 1:
            import statistics
            print(f"  timestamps monotonic: {all(b >= a for a, b in zip(ts, ts[1:]))}")
        inlet.close_stream()
        print("  >>> SELFTEST PASS")
        return 0
    finally:
        bridge.close()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Bridge opentrack UDP head pose onto an LSL stream.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "In opentrack: Output = 'UDP over network', set the remote address\n"
            "to this bridge's --host/--port, then start tracking."
        ),
    )
    p.add_argument("--host", default=DEFAULT_UDP_HOST, help="local bind address")
    p.add_argument("--port", type=int, default=DEFAULT_UDP_PORT, help="local UDP port")
    p.add_argument("--name", default=DEFAULT_STREAM_NAME, help="LSL stream name")
    p.add_argument("--type", dest="stype", default=DEFAULT_STREAM_TYPE, help="LSL stream type")
    p.add_argument(
        "--srate", type=float, default=0.0,
        help="nominal rate to declare; 0 = irregular (default, honest for camera trackers)",
    )
    p.add_argument("--duration", type=float, default=None, help="stop after N seconds")
    p.add_argument("--quiet", action="store_true", help="suppress periodic stats")
    p.add_argument("--selftest", action="store_true",
                   help="verify the bridge end-to-end with a synthetic sender")
    args = p.parse_args(argv)

    if args.selftest:
        return _selftest()

    bridge = OpentrackLSLBridge(
        udp_host=args.host, udp_port=args.port,
        name=args.name, stype=args.stype, srate=args.srate,
    )

    def _sigint(_s, _f):
        print("\n[opentrack-lsl] stopping…", file=sys.stderr)
        bridge.stop()

    signal.signal(signal.SIGINT, _sigint)

    with bridge:
        print(
            f"[opentrack-lsl] listening on udp://{args.host}:{args.port} -> "
            f"LSL '{args.name}' (type={args.stype}, "
            f"{len(CHANNELS)} ch, srate={args.srate or 'irregular'})",
            file=sys.stderr,
        )
        bridge.run(duration=args.duration, report_every=0 if args.quiet else 5.0)
    print(
        f"[opentrack-lsl] done: {bridge.n_forwarded} forwarded, "
        f"{bridge.n_malformed} malformed.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
