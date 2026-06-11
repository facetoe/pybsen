"""BsenClient — async BLE client for REDARC BSEN500 battery monitors.

Usage::

    client = BsenClient("60:15:21:00:1B:E1")
    await client.connect()
    async for battery, alarms in client.stream():
        print(battery.net_current_a, battery.voltage_v)
    await client.disconnect()
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

from pybsen.exceptions import BsenConnectionError, BsenTimeoutError
from pybsen.frame import parse_rbus_frames
from pybsen.models import AlarmState, BatteryState
from pybsen.pgn import decode

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GATT UUIDs (REDARC base: ...-5160-4000-XXXX-524544415243)
# ---------------------------------------------------------------------------

CHAR_2022_8001 = "10102022-5160-4000-8001-524544415243"
CHAR_2022_8011 = "10102022-5160-4000-8011-524544415243"
CHAR_2015_8001 = "09022015-5160-4000-8001-524544415243"  # RBUS CAN data (notify + write)
CHAR_2015_8002 = "09022015-5160-4000-8002-524544415243"  # filter config (write)
CHAR_2015_8003 = "09022015-5160-4000-8003-524544415243"  # gateway commands

CHAR_LABEL: dict[str, str] = {
    CHAR_2022_8001: "2022:8001",
    CHAR_2022_8011: "2022:8011",
    CHAR_2015_8001: "2015:8001",
    CHAR_2015_8002: "2015:8002",
    CHAR_2015_8003: "2015:8003",
}

# ── Gateway frames (verified from HCI snoop log) ───────────────────────────────
GW_MTU_160 = bytes([0x00, 0x02, 0x02, 0x00, 0xA0])  # MTU=160, key=0x0002
GW_RBUS_ADDR = bytes([0x80, 0x01, 0x00])  # read device RBUS address, key=0x0001

# ── Standard filter list (30 entries, exact bytes from HCI snoop log) ─────────
# Written to CHAR_2015_8002 during initialisation.
STANDARD_FILTERS: list[bytes] = [
    bytes.fromhex("002aa0ffff0000f002000000"),
    bytes.fromhex("012aa0ffff0000f100000000"),
    bytes.fromhex("022aa0ffff0000f104000000"),
    bytes.fromhex("032aa0ffff0000f108000000"),
    bytes.fromhex("042aa0ffff0000f10a0003e8"),
    bytes.fromhex("052aa0ffff0000f2000003e8"),
    bytes.fromhex("062aa0ffff0000f2040003e8"),
    bytes.fromhex("072aa0ffff0000f2060003e8"),
    bytes.fromhex("082aa0ffff0000f2080003e8"),
    bytes.fromhex("172aa0ffff0000f207000000"),
    bytes.fromhex("092aa0ffff0000f20a0003e8"),
    bytes.fromhex("0a2aa0fff90000f280000000"),
    bytes.fromhex("0b2aa0ffff0000f304000000"),
    bytes.fromhex("0d2aa0ffff0000f404000000"),
    bytes.fromhex("0c2aa0fffc0000f400000000"),
    bytes.fromhex("142aa0ffff0000f405000000"),
    bytes.fromhex("0e2aa0ffff0000f408000000"),
    bytes.fromhex("162aa0ffff0000f40a000000"),
    bytes.fromhex("0f2aa0fff90000fcd0000000"),
    bytes.fromhex("102aa0fe000000fd00000000"),
    bytes.fromhex("112aa0ffff0000f20f000000"),
    bytes.fromhex("122aa0ff000000040000" + "0000"),
    bytes.fromhex("132aa300000002000000" + "0000"),
    bytes.fromhex("152aa0ffff0000f2010003e8"),
    bytes.fromhex("182aa0ffff0000fb00000000"),
    bytes.fromhex("192aa0ffff0000fb02000000"),
    bytes.fromhex("1a2aa0ffff0000f308000000"),
    bytes.fromhex("1b2aa0ffff0000f1020007d0"),
    bytes.fromhex("1c2aa0ffff0000f406000000"),
    bytes.fromhex("1d2aa0ffff0000f205000000"),
]


class BsenClient:
    """Async BLE client for the REDARC Smart Battery Monitor BSEN500."""

    def __init__(self, address: str) -> None:
        self._address = address
        self._client: BleakClient | None = None
        self._battery = BatteryState()
        self._alarms = AlarmState()
        self._queue: asyncio.Queue[tuple[BatteryState, AlarmState] | None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self) -> None:
        """Scan for the device, connect, and run the initialization sequence.

        Raises BsenTimeoutError if the device is not found within the scan
        timeout.  Raises BsenConnectionError if the GATT connection fails.
        """
        _log.info("Scanning for %s ...", self._address)
        device: BLEDevice | None = await BleakScanner.find_device_by_address(
            self._address, timeout=15.0
        )
        if device is None:
            raise BsenTimeoutError(f"Device {self._address} not found during scan")

        self._loop = asyncio.get_running_loop()

        def _on_disconnect(_: Any) -> None:
            _log.info("Device disconnected: %s", self._address)
            if self._queue is not None and self._loop is not None:
                self._loop.call_soon_threadsafe(self._queue.put_nowait, None)

        client = BleakClient(device, disconnected_callback=_on_disconnect)
        try:
            await client.connect()
        except Exception as exc:
            raise BsenConnectionError(f"Failed to connect to {self._address}") from exc

        self._client = client
        _log.info("Connected to %s", self._address)

        for uuid in [CHAR_2015_8001, CHAR_2015_8002, CHAR_2015_8003]:
            try:
                await client.start_notify(uuid, self._on_notify)
                _log.debug("Subscribed to %s", CHAR_LABEL.get(uuid, uuid))
            except Exception as exc:
                _log.warning("start_notify failed for %s: %s", CHAR_LABEL.get(uuid, uuid), exc)

        await self._init_session(client)

    async def disconnect(self) -> None:
        """Stop notifications and disconnect the BleakClient."""
        if self._client is None:
            return
        for uuid in [CHAR_2015_8001, CHAR_2015_8002, CHAR_2015_8003]:
            try:
                await self._client.stop_notify(uuid)
            except Exception:
                pass
        await self._client.disconnect()
        self._client = None

    @property
    def battery(self) -> BatteryState:
        """Most recently decoded BatteryState. Fields are None until the relevant PGN arrives."""
        return self._battery

    async def stream(self) -> AsyncGenerator[tuple[BatteryState, AlarmState], None]:
        """Yield (BatteryState, AlarmState) tuples on each state-updating notification.

        Must be called after connect().  Yields until the caller breaks or the
        client is disconnected.  Exits cleanly when the BLE connection drops
        (the disconnected callback injects a None sentinel into the queue).
        """
        queue: asyncio.Queue[tuple[BatteryState, AlarmState] | None] = asyncio.Queue()
        self._queue = queue
        try:
            while True:
                item = await queue.get()
                if item is None:
                    return  # BLE disconnected — exit generator cleanly
                yield item
        finally:
            self._queue = None

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _on_notify(self, characteristic: Any, data: bytearray) -> None:
        frames = parse_rbus_frames(bytes(data))
        if not frames:
            return
        for frame in frames:
            self._battery, self._alarms = decode(frame, self._battery, self._alarms)
        if self._queue is not None:
            self._queue.put_nowait((self._battery, self._alarms))

    async def _init_session(self, client: BleakClient) -> None:
        """Run the mandatory RBUS initialization sequence."""
        _log.debug("Init: gateway MTU → 160 bytes")
        await client.write_gatt_char(CHAR_2015_8003, bytearray(GW_MTU_160), response=True)
        await asyncio.sleep(0.3)

        _log.debug("Init: writing %d standard filters", len(STANDARD_FILTERS))
        for flt in STANDARD_FILTERS:
            await client.write_gatt_char(CHAR_2015_8002, bytearray(flt), response=False)
            await asyncio.sleep(0.02)

        _log.debug("Init: gateway rbusAddress query")
        await client.write_gatt_char(CHAR_2015_8003, bytearray(GW_RBUS_ADDR), response=False)
        await asyncio.sleep(0.3)
