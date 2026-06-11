"""Session analyst and fixture extractor for captured BSEN500 sessions.

Subcommands::

    python -m tools.analyze list [--capture-dir capture]
        Prints a summary table of all session files.

    python -m tools.analyze extract <session.jsonl> \\
        --event (reconnect|soc-change|sign-change|mismatch) \\
        [--window-before N] [--window-after N] \\
        [--soc-delta N]  # for soc-change trigger \\
        --output tests/fixtures/captured/<name>.jsonl
        Extracts matching windows as test fixture slices.

Extracted fixture format (JSONL):

    Line 0  : session_start record (mac, label, ts)
    Lines 1+ : notify records from the window
    Last line: snapshot record (ground truth) nearest to the window

Each extracted file is a self-contained test fixture.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from pybsen.frame import parse_rbus_frames
from pybsen.models import AlarmState, BatteryState
from pybsen.pgn import decode

_log = logging.getLogger(__name__)

# Default window around each trigger event (number of notify records)
DEFAULT_WINDOW_BEFORE = 20
DEFAULT_WINDOW_AFTER = 20

# Cross-validation tolerances (must match conftest.py)
_VOLTAGE_TOL = 0.05
_CURRENT_TOL = 0.2
_SOC_TOL = 0


# ── Session loading ────────────────────────────────────────────────────────────

def load_session(path: Path) -> list[dict[str, Any]]:
    """Load all records from a JSONL session file."""
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


# ── Decode helpers ─────────────────────────────────────────────────────────────

def _decode_notify_record(record: dict[str, Any], battery: BatteryState, alarms: AlarmState) -> tuple[BatteryState, AlarmState]:
    raw = bytes.fromhex(record["hex"])
    for frame in parse_rbus_frames(raw):
        battery, alarms = decode(frame, battery, alarms)
    return battery, alarms


def _decode_sequence(notify_records: list[dict[str, Any]]) -> tuple[BatteryState, AlarmState]:
    battery = BatteryState()
    alarms = AlarmState()
    for r in notify_records:
        battery, alarms = _decode_notify_record(r, battery, alarms)
    return battery, alarms


# ── Mismatch detection ─────────────────────────────────────────────────────────

def _has_mismatch(battery: BatteryState, app_values: dict[str, Any]) -> bool:
    if battery.soc_pct is not None and "soc_pct" in app_values:
        if abs(battery.soc_pct - app_values["soc_pct"]) > _SOC_TOL:
            return True
    if battery.voltage_v is not None and "voltage_v" in app_values:
        if abs(battery.voltage_v - app_values["voltage_v"]) > _VOLTAGE_TOL:
            return True
    if battery.net_current_a is not None and "abs_current_a" in app_values:
        if abs(abs(battery.net_current_a) - app_values["abs_current_a"]) > _CURRENT_TOL:
            return True
    return False


# ── List subcommand ────────────────────────────────────────────────────────────

def cmd_list(capture_dir: Path) -> None:
    sessions_dir = capture_dir / "sessions"
    if not sessions_dir.exists():
        print(f"No sessions directory found at {sessions_dir}")
        return

    paths = sorted(sessions_dir.glob("*.jsonl"))
    if not paths:
        print("No session files found.")
        return

    header = f"{'File':<50}  {'Label':<20}  {'Notifies':>8}  {'Snapshots':>9}  {'Mismatches':>10}"
    print(header)
    print("-" * len(header))

    for path in paths:
        records = load_session(path)
        label = next((r.get("label", "?") for r in records if r.get("type") == "session_start"), "?")
        notifies = [r for r in records if r["type"] == "notify"]
        snapshots = [r for r in records if r["type"] == "snapshot"]

        mismatches = 0
        battery = BatteryState()
        alarms = AlarmState()
        notify_idx = 0
        for rec in records:
            if rec["type"] == "notify":
                battery, alarms = _decode_notify_record(rec, battery, alarms)
                notify_idx += 1
            elif rec["type"] == "snapshot":
                if _has_mismatch(battery, rec.get("app_values", {})):
                    mismatches += 1

        print(f"{path.name:<50}  {label:<20}  {len(notifies):>8}  {len(snapshots):>9}  {mismatches:>10}")


# ── Extract subcommand ─────────────────────────────────────────────────────────

def cmd_extract(
    session_path: Path,
    event: str,
    output: Path,
    window_before: int,
    window_after: int,
    soc_delta: int,
) -> None:
    records = load_session(session_path)
    session_start = next((r for r in records if r["type"] == "session_start"), {})

    # Build indexed lists for fast windowing
    notify_records = [(i, r) for i, r in enumerate(records) if r["type"] == "notify"]
    snapshot_records = [(i, r) for i, r in enumerate(records) if r["type"] == "snapshot"]

    # Map global index → notify list position for window slicing
    global_to_notify: dict[int, int] = {gi: ni for ni, (gi, _) in enumerate(notify_records)}
    notify_global_indices = [gi for gi, _ in notify_records]

    trigger_positions = _find_trigger_positions(
        records, notify_records, snapshot_records, event, soc_delta
    )

    if not trigger_positions:
        _log.warning("No trigger events found for '%s' in %s", event, session_path.name)
        return

    _log.info("Found %d trigger event(s) — extracting windows", len(trigger_positions))

    slices: list[list[dict[str, Any]]] = []
    for trigger_global_idx in trigger_positions:
        window = _extract_window(
            trigger_global_idx,
            records,
            notify_global_indices,
            global_to_notify,
            snapshot_records,
            window_before,
            window_after,
        )
        if window:
            slices.append(window)

    if not slices:
        _log.warning("No valid windows extracted")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with output.open("w", encoding="utf-8") as fh:
        # Write a session_start header for the extracted fixture
        header = dict(session_start)
        header["type"] = "session_start"
        header["source_session"] = session_path.name
        fh.write(json.dumps(header, separators=(",", ":")) + "\n")

        for window_records in slices:
            for record in window_records:
                fh.write(json.dumps(record, separators=(",", ":")) + "\n")
            written += 1

    _log.info("Wrote %d window(s) to %s", written, output)
    print(f"Extracted {written} window(s) → {output}")


def _find_trigger_positions(
    records: list[dict[str, Any]],
    notify_records: list[tuple[int, dict[str, Any]]],
    snapshot_records: list[tuple[int, dict[str, Any]]],
    event: str,
    soc_delta: int,
) -> list[int]:
    """Return list of global record indices that are trigger points."""
    positions: list[int] = []

    if event == "reconnect":
        for i, r in enumerate(records):
            if r["type"] == "connect":
                # Find the first notify after this connect
                for gi, _ in notify_records:
                    if gi > i:
                        positions.append(gi)
                        break

    elif event == "sign-change":
        prev_sign: int | None = None
        battery = BatteryState()
        alarms = AlarmState()
        for gi, r in notify_records:
            battery, alarms = _decode_notify_record(r, battery, alarms)
            if battery.net_current_a is not None:
                sign = 1 if battery.net_current_a >= 0 else -1
                if prev_sign is not None and sign != prev_sign:
                    positions.append(gi)
                prev_sign = sign

    elif event == "soc-change":
        prev_soc: int | None = None
        for _, snap in snapshot_records:
            av = snap.get("app_values", {})
            soc = av.get("soc_pct")
            if soc is None:
                continue
            if prev_soc is not None and abs(soc - prev_soc) >= soc_delta:
                # Trigger at the snapshot record itself
                positions.append(snap.get("_global_idx", 0))
            prev_soc = soc
        # Re-annotate: find actual global indices for snapshot records
        positions = []
        prev_soc = None
        for gi, snap in snapshot_records:
            av = snap.get("app_values", {})
            soc = av.get("soc_pct")
            if soc is None:
                continue
            if prev_soc is not None and abs(soc - prev_soc) >= soc_delta:
                positions.append(gi)
            prev_soc = soc

    elif event == "mismatch":
        battery = BatteryState()
        alarms = AlarmState()
        notify_iter = iter(notify_records)
        ngi, nr = next(notify_iter, (None, None))
        for gi, snap in snapshot_records:
            # Advance notify state up to this snapshot
            while ngi is not None and ngi < gi:
                battery, alarms = _decode_notify_record(nr, battery, alarms)  # type: ignore[arg-type]
                ngi, nr = next(notify_iter, (None, None))
            if _has_mismatch(battery, snap.get("app_values", {})):
                positions.append(gi)

    else:
        raise ValueError(f"Unknown event type: {event!r}")

    return positions


def _extract_window(
    trigger_global_idx: int,
    records: list[dict[str, Any]],
    notify_global_indices: list[int],
    global_to_notify: dict[int, int],
    snapshot_records: list[tuple[int, dict[str, Any]]],
    window_before: int,
    window_after: int,
) -> list[dict[str, Any]]:
    """Return notify records in the window + nearest snapshot."""
    # Find the position of the trigger in the notify list
    if trigger_global_idx in global_to_notify:
        trigger_notify_pos = global_to_notify[trigger_global_idx]
    else:
        # Trigger is a non-notify record (e.g. snapshot); find nearest notify after
        trigger_notify_pos = next(
            (pos for pos, gi in enumerate(notify_global_indices) if gi >= trigger_global_idx),
            len(notify_global_indices) - 1,
        )

    start = max(0, trigger_notify_pos - window_before)
    end = min(len(notify_global_indices), trigger_notify_pos + window_after + 1)

    window_global = set(notify_global_indices[start:end])
    window_records = [r for i, r in enumerate(records) if i in window_global]

    # Find the nearest snapshot after the window start
    window_start_global = notify_global_indices[start] if start < len(notify_global_indices) else 0
    nearest_snapshot = next(
        (r for gi, r in snapshot_records if gi >= window_start_global),
        None,
    )

    if not window_records:
        return []

    result = list(window_records)
    if nearest_snapshot:
        result.append(nearest_snapshot)
    return result


# ── CLI ────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m tools.analyze",
        description="Inspect captured BSEN500 sessions and extract test fixture slices.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # list
    ls = sub.add_parser("list", help="Summarise all sessions in capture/sessions/")
    ls.add_argument(
        "--capture-dir",
        type=Path,
        default=Path("capture"),
        metavar="DIR",
    )

    # extract
    ex = sub.add_parser("extract", help="Extract interesting windows as test fixtures")
    ex.add_argument("session", type=Path, help="Path to session JSONL file")
    ex.add_argument(
        "--event",
        required=True,
        choices=["reconnect", "soc-change", "sign-change", "mismatch"],
        help="Trigger event type",
    )
    ex.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Output JSONL fixture path",
    )
    ex.add_argument(
        "--window-before",
        type=int,
        default=DEFAULT_WINDOW_BEFORE,
        metavar="N",
        help=f"Notify records before trigger (default: {DEFAULT_WINDOW_BEFORE})",
    )
    ex.add_argument(
        "--window-after",
        type=int,
        default=DEFAULT_WINDOW_AFTER,
        metavar="N",
        help=f"Notify records after trigger (default: {DEFAULT_WINDOW_AFTER})",
    )
    ex.add_argument(
        "--soc-delta",
        type=int,
        default=5,
        metavar="N",
        help="Minimum SOC change (pct) for soc-change trigger (default: 5)",
    )

    return p


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "list":
        cmd_list(args.capture_dir)
    elif args.command == "extract":
        cmd_extract(
            session_path=args.session,
            event=args.event,
            output=args.output,
            window_before=args.window_before,
            window_after=args.window_after,
            soc_delta=args.soc_delta,
        )


if __name__ == "__main__":
    main()
