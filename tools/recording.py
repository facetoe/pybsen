"""BLE session recording: SessionWriter and RecordingBsenClient.

SessionWriter writes a JSONL file where each line is one record.

Record types:
    session_start  { type, ts, mac, label }
    notify         { type, ts, char, hex }
    connect        { type, ts }
    disconnect     { type, ts, reason }
    snapshot       { type, ts, app_values, screenshot }
    session_end    { type, ts }

Usage::

    writer = SessionWriter(Path("capture/sessions/20260611_120000_label.jsonl"))
    client = RecordingBsenClient("60:15:21:00:1B:E1", writer)
    writer.session_start("60:15:21:00:1B:E1", "label")
    await client.connect()
    writer.connect()
    async for battery, alarms in client.stream():
        ...
    await client.disconnect()
    writer.disconnect("clean")
    writer.session_end()
"""

import json
import time
from pathlib import Path
from typing import Any

from pybsen.client import BsenClient, CHAR_LABEL
from pybsen.models import BatteryState

_CHAR_HEX_KEYS = {v: v for v in CHAR_LABEL.values()}


class SessionWriter:
    """Append-only JSONL writer for a single capture session."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = path.open("a", encoding="utf-8")

    # ── Record writers ─────────────────────────────────────────────────────

    def session_start(self, mac: str, label: str) -> None:
        self._write({"type": "session_start", "mac": mac, "label": label})

    def notify(self, char_label: str, data: bytes) -> None:
        self._write({"type": "notify", "char": char_label, "hex": data.hex()})

    def connect(self) -> None:
        self._write({"type": "connect"})

    def disconnect(self, reason: str = "clean") -> None:
        self._write({"type": "disconnect", "reason": reason})

    def battery(self, state: BatteryState) -> None:
        self._write({
            "type": "battery",
            "net_current_a": state.net_current_a,
            "charge_direction": state.charge_direction,
            "voltage_v": state.voltage_v,
            "temp_c": state.temp_c,
            "soc_pct": state.soc_pct,
        })

    def snapshot(self, app_values: dict[str, Any], screenshot: str, charge_direction: str | None = None) -> None:
        record: dict[str, Any] = {"type": "snapshot", "app_values": app_values, "screenshot": screenshot}
        if charge_direction is not None:
            record["charge_direction"] = charge_direction
        self._write(record)

    def session_end(self) -> None:
        self._write({"type": "session_end"})
        self.close()

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()

    # ── Internal ───────────────────────────────────────────────────────────

    def _write(self, record: dict[str, Any]) -> None:
        record["ts"] = time.time()
        self._fh.write(json.dumps(record, separators=(",", ":")) + "\n")
        self._fh.flush()


class RecordingBsenClient(BsenClient):
    """BsenClient subclass that records every raw BLE notification to a SessionWriter.

    The recording happens before decoding, so every wire byte is preserved
    regardless of whether the frame is recognised or not.
    """

    def __init__(self, address: str, writer: SessionWriter) -> None:
        super().__init__(address)
        self._writer = writer

    def _on_notify(self, characteristic: Any, data: bytearray) -> None:
        char_uuid: str = str(characteristic.uuid) if hasattr(characteristic, "uuid") else str(characteristic)
        label = CHAR_LABEL.get(char_uuid, char_uuid)
        self._writer.notify(label, bytes(data))
        super()._on_notify(characteristic, data)
        self._writer.battery(self._battery)
