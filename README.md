# pybsen

Python async library for the REDARC Smart Battery Monitor BSEN500.

Connects over BLE, runs the device's proprietary R-Bus initialization sequence, and streams decoded battery measurements as typed Python objects.

> **Note:** The R-Bus protocol is reverse-engineered from the RedVision Android app. No public specification exists. See [`docs/protocol.md`](docs/protocol.md) for the full protocol reference.

---

## Requirements

- Python ≥ 3.11
- [`bleak`](https://github.com/hbldh/bleak) ≥ 0.21

## Installation

```bash
pip install -e .
```

---

## Usage

```python
import asyncio
from pybsen.client import BsenClient

async def main():
    client = BsenClient("60:15:21:00:1B:E1")
    await client.connect()
    async for battery, alarms in client.stream():
        print(f"{battery.soc_pct}%  {battery.voltage_v}V  {battery.net_current_a}A")
    await client.disconnect()

asyncio.run(main())
```

`stream()` yields `(BatteryState, AlarmState)` on every notification. Call `disconnect()` when done; break out of the loop to stop consuming without disconnecting.

---

## Data model

### `BatteryState`

| Field | Unit | Source PGN |
|---|---|---|
| `soc_pct` | % | F1:04 |
| `voltage_v` | V | F2:80 |
| `net_current_a` | A (negative = discharging) | F2:80 |
| `temp_c` | °C | F2:80 |
| `time_to_full_min` | minutes | F1:04 |
| `time_to_flat_min` | minutes | F1:04 |
| `state_of_health_pct` | % | F1:04 (always `None` on BSEN500) |

### `AlarmState`

| Field | Description |
|---|---|
| `soc_alarm_active` | Low SOC alarm firing |
| `voltage_alarm_active` | Low voltage alarm firing |
| `soc_alarm_setpoint_pct` | Configured SOC threshold |
| `voltage_alarm_setpoint_v` | Configured voltage threshold |

All fields are `None` until the corresponding PGN has been received.

---

## Protocol specification

Binary frame formats are defined as [Kaitai Struct](https://kaitai.io/) specs in [`spec/`](spec/):

| File | Describes |
|---|---|
| `spec/rbus_frame.ksy` | RBUS frame header and payload layout |
| `spec/rbus_filter.ksy` | PGN filter entry written to `CHAR_2015_8002` |
| `spec/rbus_gateway.ksy` | Gateway channel command/response format |

These can be compiled to parsers in C++, Go, Java, JavaScript, and other languages via the [Kaitai Struct compiler](https://kaitai.io/#download). The full field-level protocol reference, including decode formulas and sentinel values, is in [`docs/protocol.md`](docs/protocol.md).

---

## Linux/BlueZ

BlueZ requires a security handshake before accepting GATT operations. Run the following before connecting:

```bash
bluetoothctl connect <MAC>
```

Skipping this causes the connection to drop during service discovery.

---

## Development

```bash
make          # lint + typecheck + test
make reformat # auto-fix formatting
make test     # tests only
```

Pre-commit hooks: `make install-hooks`.
