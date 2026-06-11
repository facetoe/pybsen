"""Shared pytest fixtures for test_frame.py, test_pgn.py, and test_captured.py."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from pybsen.frame import RawFrame, parse_rbus_frames
from pybsen.models import AlarmState, BatteryState
from pybsen.pgn import decode

_FIXTURE_DIR = Path(__file__).parent / "fixtures"

# Cross-validation tolerances for captured ground-truth comparisons.
# Current tolerance is wider (±0.2 A) because the app rounds to 1 dp and
# BLE updates arrive ~1 Hz so the snapshot and last notify may differ slightly.
_VOLTAGE_TOL = 0.05
_CURRENT_TOL = 0.2


@pytest.fixture
def load_bin() -> Callable[[str], bytes]:
    """Returns a callable: load_bin(name) -> bytes. Loads a fixture .bin file by name."""

    def _load(name: str) -> bytes:
        with open(_FIXTURE_DIR / name, "rb") as fh:
            return fh.read()

    return _load


@pytest.fixture
def parse_notify() -> Callable[[bytes], list[RawFrame]]:
    """Returns a callable: parse_notify(notify_bytes) -> list[RawFrame]."""
    return parse_rbus_frames


@pytest.fixture
def decode_sequence() -> Callable[[list[tuple[bytes, str, object]]], tuple[BatteryState, AlarmState]]:
    """Returns a callable: decode_sequence(sequence) -> tuple[BatteryState, AlarmState].

    Drives an entire SEQUENCE_* list through parse → decode and returns final states.
    State carries forward across all entries in the sequence.
    """

    def _run(sequence: list[tuple[bytes, str, object]]) -> tuple[BatteryState, AlarmState]:
        battery = BatteryState()
        alarms = AlarmState()
        for notify_bytes, _field, _expected in sequence:
            for frame in parse_rbus_frames(notify_bytes):
                battery, alarms = decode(frame, battery, alarms)
        return battery, alarms

    return _run


@pytest.fixture
def replay_session() -> Callable[[Path], tuple[BatteryState, AlarmState, list[dict[str, Any]]]]:
    """Returns a callable: replay_session(path) -> (battery, alarms, snapshots).

    Loads a captured JSONL fixture slice, replays all notify records through
    parse_rbus_frames → decode in order with carry-forward state, and returns
    the final accumulated (BatteryState, AlarmState) together with the list of
    snapshot records found in the file (each containing an app_values dict).
    """

    def _run(path: Path) -> tuple[BatteryState, AlarmState, list[dict[str, Any]]]:
        battery = BatteryState()
        alarms = AlarmState()
        snapshots: list[dict[str, Any]] = []

        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                record: dict[str, Any] = json.loads(line)
                rtype = record.get("type")
                if rtype == "notify":
                    raw = bytes.fromhex(record["hex"])
                    for frame in parse_rbus_frames(raw):
                        battery, alarms = decode(frame, battery, alarms)
                elif rtype == "snapshot":
                    snapshots.append(record)

        return battery, alarms, snapshots

    return _run


@pytest.fixture
def assert_app_values() -> Callable[[BatteryState, AlarmState, dict[str, Any]], None]:
    """Returns a callable: assert_app_values(battery, alarms, app_values).

    Compares decoded state against an app_values dict captured from the REDARC
    app via uiautomator.  Uses field-appropriate tolerances:

        soc_pct       : exact integer match
        voltage_v     : ±0.05 V  (app rounds to 1 dp)
        temp_c        : exact integer match (app shows integer °C)
        abs_current_a : abs(net_current_a) within ±0.2 A
                        (app rounds to 1 dp; BLE packet and snapshot may not
                        be perfectly time-aligned)

    Only fields present in app_values are checked; missing fields are skipped.
    The current sign is not validated here — the app exposes magnitude only.
    """

    def _assert(battery: BatteryState, alarms: AlarmState, app_values: dict[str, Any]) -> None:
        if "soc_pct" in app_values and battery.soc_pct is not None:
            assert battery.soc_pct == app_values["soc_pct"], (
                f"soc_pct: decoded={battery.soc_pct} app={app_values['soc_pct']}"
            )
        if "voltage_v" in app_values and battery.voltage_v is not None:
            assert abs(battery.voltage_v - app_values["voltage_v"]) <= _VOLTAGE_TOL, (
                f"voltage_v: decoded={battery.voltage_v:.3f} app={app_values['voltage_v']:.3f} "
                f"(tol ±{_VOLTAGE_TOL})"
            )
        if "temp_c" in app_values and battery.temp_c is not None:
            assert battery.temp_c == app_values["temp_c"], (
                f"temp_c: decoded={battery.temp_c} app={app_values['temp_c']}"
            )
        if "abs_current_a" in app_values and battery.net_current_a is not None:
            decoded_abs = abs(battery.net_current_a)
            assert abs(decoded_abs - app_values["abs_current_a"]) <= _CURRENT_TOL, (
                f"abs_current_a: decoded={decoded_abs:.2f} app={app_values['abs_current_a']:.2f} "
                f"(tol ±{_CURRENT_TOL})"
            )

    return _assert
