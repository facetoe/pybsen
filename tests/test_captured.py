"""Regression tests for captured BSEN500 wire sessions.

Each .jsonl file under tests/fixtures/captured/ is a self-contained fixture
slice produced by ``python -m tools.analyze extract``.  Tests in this module
auto-discover all committed slices and replay each one through the full
parse → decode pipeline, asserting that the final decoded state matches the
ADB-captured ground truth from the REDARC app.

To add a new test case:
    1. Run a capture session:
           python -m tools.capture --mac 60:15:21:00:1B:E1 --label <label>
    2. Extract an interesting window:
           python -m tools.analyze extract capture/sessions/<file>.jsonl \\
               --event reconnect \\
               --output tests/fixtures/captured/<name>.jsonl
    3. Commit the .jsonl file.  This module picks it up automatically on the
       next test run.

The test suite skips entirely when no captured fixtures exist yet.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from pybsen.models import AlarmState, BatteryState

_CAPTURED_DIR = Path(__file__).parent / "fixtures" / "captured"
_CAPTURED_FIXTURES = [p for p in sorted(_CAPTURED_DIR.glob("*.jsonl")) if p.stat().st_size > 0]


@pytest.mark.skipif(not _CAPTURED_FIXTURES, reason="no captured fixtures in tests/fixtures/captured/")
@pytest.mark.parametrize("fixture_path", _CAPTURED_FIXTURES, ids=lambda p: p.stem)
def test_captured_session(
    fixture_path: Path,
    replay_session: Callable[[Path], tuple[BatteryState, AlarmState, list[dict[str, Any]]]],
    assert_app_values: Callable[[BatteryState, AlarmState, dict[str, Any]], None],
) -> None:
    """Replay a captured session and cross-validate against ADB ground truth.

    For each snapshot record in the fixture, the decoded state accumulated up
    to that point is compared against the app_values the REDARC app reported
    at that moment.
    """
    battery, alarms, snapshots = replay_session(fixture_path)

    assert snapshots, f"Fixture {fixture_path.name} contains no snapshot records — cannot validate"

    for snap in snapshots:
        app_values = snap.get("app_values", {})
        assert app_values, f"Snapshot record in {fixture_path.name} has no app_values"
        assert_app_values(battery, alarms, app_values)

        captured_direction = snap.get("charge_direction")
        if captured_direction is not None and battery.charge_direction is not None:
            assert battery.charge_direction == captured_direction, (
                f"charge_direction: decoded={battery.charge_direction!r} "
                f"captured={captured_direction!r}"
            )
