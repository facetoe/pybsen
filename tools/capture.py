"""Long-running BLE capture harness for the REDARC BSEN500.

Records raw BLE notifications to JSONL and periodically takes ADB-driven
ground-truth snapshots from the phone app.

Usage::

    python -m tools.capture \\
        --mac 60:15:21:00:1B:E1 \\
        --label heavy-discharge \\
        [--snapshot-interval 120] \\
        [--reconnect-interval 900] \\
        [--output-dir capture] \\
        [--adb-serial RFCX91K1CZM]

Output layout::

    capture/
      sessions/YYYYMMDD_HHMMSS_{label}.jsonl
      screenshots/YYYYMMDD_HHMMSS_{label}_{seq:04d}.png
"""

import argparse
import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

from tools.recording import RecordingBsenClient, SessionWriter
from tools.adb import AdbController

_log = logging.getLogger(__name__)


# ── Orchestrator ───────────────────────────────────────────────────────────────

class CaptureSession:
    """Manages the full lifecycle of one recording session."""

    def __init__(
        self,
        mac: str,
        label: str,
        output_dir: Path,
        snapshot_interval: float,
        reconnect_interval: float,
        adb_serial: str | None,
        unlock_pin: str | None = None,
    ) -> None:
        self._mac = mac
        self._label = label
        self._output_dir = output_dir
        self._snapshot_interval = snapshot_interval
        self._reconnect_interval = reconnect_interval
        self._adb = AdbController(serial=adb_serial, pin=unlock_pin)
        self._stop_event = asyncio.Event()
        self._seq = 0

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        sessions_dir = output_dir / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        self._session_path = sessions_dir / f"{ts}_{label}.jsonl"
        self._screenshot_prefix = output_dir / "screenshots" / f"{ts}_{label}"
        (output_dir / "screenshots").mkdir(parents=True, exist_ok=True)

        self._writer = SessionWriter(self._session_path)
        self._client = RecordingBsenClient(mac, self._writer)

    async def run(self) -> None:
        self._writer.session_start(self._mac, self._label)
        _log.info("Session file: %s", self._session_path)

        try:
            await self._connect_cycle()
        finally:
            self._writer.session_end()
            _log.info("Session ended: %s", self._session_path)

    def stop(self) -> None:
        self._stop_event.set()

    # ── Internal ───────────────────────────────────────────────────────────

    async def _sleep_or_stop(self, delay: float) -> bool:
        """Sleep for up to delay seconds. Returns True if stop was requested early."""
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
            return True
        except asyncio.TimeoutError:
            return False

    async def _connect_cycle(self) -> None:
        """Outer reconnect loop — reconnects every reconnect_interval seconds."""
        loop = asyncio.get_running_loop()
        while not self._stop_event.is_set():
            _log.info("Stopping phone app to release BLE connection ...")
            await loop.run_in_executor(None, self._adb.force_stop)
            await self._sleep_or_stop(1.5)
            if self._stop_event.is_set():
                break

            _log.info("Connecting to %s ...", self._mac)
            try:
                await self._client.connect()
            except Exception as exc:
                _log.error("Connect failed: %s — retrying in 30s", exc)
                await self._sleep_or_stop(30)
                continue

            self._writer.connect()
            _log.info("Connected")

            try:
                await self._stream_with_snapshots()
            except Exception as exc:
                _log.warning("Stream interrupted: %s", exc)
                self._writer.disconnect("unexpected")
            else:
                self._writer.disconnect("clean")

            try:
                await self._client.disconnect()
            except Exception:
                pass

            if self._stop_event.is_set():
                break

            _log.info("Disconnected — sleeping 5s before reconnect")
            await self._sleep_or_stop(5)

    async def _stream_with_snapshots(self) -> None:
        """Stream BLE notifications, interleaving periodic snapshots and planned disconnects."""
        loop = asyncio.get_running_loop()
        snapshot_task = asyncio.create_task(self._snapshot_loop(loop))
        reconnect_task = asyncio.create_task(self._reconnect_timer())

        stream_gen = self._client.stream()
        try:
            async for _battery, _alarms in stream_gen:
                if self._stop_event.is_set() or reconnect_task.done():
                    break
        finally:
            snapshot_task.cancel()
            reconnect_task.cancel()
            await asyncio.gather(snapshot_task, reconnect_task, return_exceptions=True)

    async def _snapshot_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Take an ADB snapshot every snapshot_interval seconds."""
        while True:
            await self._sleep_or_stop(self._snapshot_interval)
            if self._stop_event.is_set():
                return
            _log.info("Taking snapshot ...")
            try:
                await loop.run_in_executor(None, self._take_snapshot)
            except Exception as exc:
                _log.warning("Snapshot failed: %s", exc)

    async def _reconnect_timer(self) -> None:
        """Signal stream to stop after reconnect_interval seconds."""
        await self._sleep_or_stop(self._reconnect_interval)
        if not self._stop_event.is_set():
            _log.info("Reconnect interval elapsed — disconnecting")

    def _take_snapshot(self) -> None:
        """Blocking: wake screen, wait for live values, screenshot, write record."""
        self._adb.wake_screen()

        if not self._adb.is_app_foreground():
            _log.info("App not foreground — launching")
            self._adb.launch_app()

        app_values = self._adb.wait_for_app_values(timeout=30)
        charge_direction = self._client.battery.charge_direction
        _log.info("App values: %s charge_direction=%s", app_values, charge_direction)

        self._seq += 1
        shot_path = Path(f"{self._screenshot_prefix}_{self._seq:04d}.png")
        self._adb.screenshot(shot_path)

        self._writer.snapshot(app_values, str(shot_path), charge_direction=charge_direction)
        _log.info("Snapshot %04d written", self._seq)


# ── CLI ────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m tools.capture",
        description="Record BSEN500 BLE wire data with ADB ground-truth snapshots.",
    )
    p.add_argument("--mac", required=True, help="BLE MAC address of the BSEN500")
    p.add_argument("--label", required=True, help="Short label for this session (no spaces)")
    p.add_argument(
        "--snapshot-interval",
        type=float,
        default=120.0,
        metavar="SECS",
        help="Seconds between ADB snapshots (default: 120)",
    )
    p.add_argument(
        "--reconnect-interval",
        type=float,
        default=900.0,
        metavar="SECS",
        help="Seconds between planned BLE reconnects (default: 900)",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path("capture"),
        metavar="DIR",
        help="Root directory for session files (default: capture/)",
    )
    p.add_argument(
        "--adb-serial",
        default=None,
        metavar="SERIAL",
        help="ADB device serial (omit if only one device connected)",
    )
    p.add_argument(
        "--unlock-pin",
        default=None,
        metavar="PIN",
        help="Numeric PIN to enter when dismissing the lock screen (omit for no-lock or swipe-to-unlock)",
    )
    return p


async def _main(args: argparse.Namespace) -> None:
    session = CaptureSession(
        mac=args.mac,
        label=args.label,
        output_dir=args.output_dir,
        snapshot_interval=args.snapshot_interval,
        reconnect_interval=args.reconnect_interval,
        adb_serial=args.adb_serial,
        unlock_pin=args.unlock_pin,
    )

    loop = asyncio.get_running_loop()

    def _on_signal() -> None:
        _log.info("Interrupt received — stopping after current cycle")
        session.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _on_signal)

    await session.run()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = _build_parser()
    args = parser.parse_args()

    if " " in args.label:
        parser.error("--label must not contain spaces")

    asyncio.run(_main(args))


if __name__ == "__main__":
    main()
