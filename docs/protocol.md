# REDARC BSEN500 BLE Protocol Reference

**Device:** REDARC Smart Battery Monitor BSEN500  
**App:** RedVision (`au.com.redarc.redvision.tvms.user`, Android, Flutter/Dart)

R-Bus is a proprietary protocol. No public specification has been published by REDARC.
All field formulas in §4 are confirmed against live device captures cross-referenced with
the RedVision app display.

---

## 1. BLE GATT Profile

### 1.1 Service and Characteristic UUIDs

All UUIDs share the base suffix `-5160-4000-XXXX-524544415243`, where `524544415243` is
ASCII for `REDARC`.

| UUID | Role |
|------|------|
| `09022015-5160-4000-8000-524544415243` | **RBUS Service** (primary) |
| `09022015-5160-4000-8001-524544415243` | `CHAR_2015_8001` — RBUS frame notify/write (incoming frames) |
| `09022015-5160-4000-8002-524544415243` | `CHAR_2015_8002` — PGN filter configuration write |
| `09022015-5160-4000-8003-524544415243` | `CHAR_2015_8003` — gateway command write/notify |
| `10102022-5160-4000-8000-524544415243` | Config Service (newer firmware; role unknown) |
| `10102022-5160-4000-8001-524544415243` | Config characteristic 1 (role unknown) |
| `10102022-5160-4000-8011-524544415243` | Config characteristic 2 (role unknown) |

### 1.2 Connection and Initialization Sequence

Steps must be executed in order. Skipping step 5 results in the device streaming nothing.

1. Scan for a device whose advertisement name starts with `REDARC` (also `BOOT`, `NINA`).
2. Connect.
3. Subscribe to notifications on `CHAR_2015_8001`, `CHAR_2015_8002`, `CHAR_2015_8003`.
4. Write MTU negotiation to `CHAR_2015_8003` (with response):
   `[0x00, 0x02, 0x02, 0x00, 0xA0]`
   Expected response: `[0x80, 0x02, 0x00]`.
5. Write PGN filter entries to `CHAR_2015_8002` (12 bytes each) — see §1.3.
6. Read device RBUS address from `CHAR_2015_8003` (without response):
   Write `[0x80, 0x01, 0x00]`.
   Expected response: `[0x80, 0x01, 0x01, 0x36]` — last byte is the RBUS address (`0x36` on BSEN500).

> **Linux/BlueZ note:** The device requires a BlueZ-level security handshake before
> accepting GATT operations. Issue a `bluetoothctl connect <MAC>` before opening the
> GATT client; otherwise the connection drops during service discovery.

### 1.3 PGN Filter Format (CHAR_2015_8002)

Each filter entry is 12 bytes and selects one PGN for periodic notification:

```
04 2A A0 FF FF 00 00 <pduFmt> <pduSpec> 00 <period_lo> <period_hi>
```

- Bytes 0–6: fixed preamble (`04 2A A0 FF FF 00 00`)
- Byte 7: `pduFmt` — high byte of PGN key
- Byte 8: `pduSpec` — low byte of PGN key
- Byte 9: `00`
- Bytes 10–11: notification period in milliseconds, little-endian (e.g. `E8 03` = 1000 ms)

The RedVision app subscribes to the following PGNs at startup:

| PGN | Period |
|-----|--------|
| `F2:80` | 1000 ms |
| `F1:04` | 300 ms |
| `F1:02` | 2000 ms |
| `F1:0A` | 1000 ms |
| `F1:00` | 5000 ms |
| `F4:00`, `F4:02`, `F4:03`, `F4:04`, `F4:05` | (period not recorded) |

### 1.4 Gateway Channel Protocol (CHAR_2015_8003)

Write frame: `[key_hi, key_lo, data_len, ...data...]`

- `key_hi` bit 7 set (`0x80`) — response expected
- Key `0x0001` — read RBUS device address
- Key `0x0002` — MTU negotiation (payload = 2-byte big-endian MTU value)

Response format: `[0x80, key_hi, key_lo, ...data...]`

---

## 2. RBUS Frame Format

RBUS is a proprietary protocol layered on J1939/CAN principles. Each notification on
`CHAR_2015_8001` may carry one or more concatenated RBUS frames.

### 2.1 Single Frame

```
[flags:1] [pduFmt:1] [pduSpec:1] [src:1] [len_byte:1] [payload:N bytes]
```

| Field | Size | Notes |
|-------|------|-------|
| `flags` | 1 | Frame type/flags. `0xA0` observed from Python client; `0x33` observed in Android HCI snoop. Both are valid frame starters. Bit 6 (`0x40`) set = continuation frame. |
| `pduFmt` | 1 | High byte of PGN key. All BSEN500 measurement frames have `pduFmt >= 0xF0` (J1939 PDU2 broadcast). |
| `pduSpec` | 1 | Low byte of PGN key. |
| `src` | 1 | Source RBUS device address. BSEN500 = `0x36`. |
| `len_byte` | 1 | Bits [3:0] = payload byte count. Upper nibble observed as `0x8` in all captures. Standard measurement frames: `len_byte = 0x88` (8-byte payload). |
| `payload` | N | PGN payload bytes. Length = `len_byte & 0x0F`. |

### 2.2 Multi-Frame (Continuation)

A flags byte with bit 6 set (`0x40`) indicates a continuation frame. Multi-segment
messages (e.g. `FC:D0` SOC log) must be reassembled from their continuation frames before
the payload is decoded. Reassembly requires a stateful accumulator and is not expressible
as a declarative binary format.

---

## 3. PGN → Wire ID Mapping

PGN key = `(pduFmt << 8) | pduSpec`.

### Battery Sensor PGNs (BSEN500 source `0x36`)

| PGN | Hex | App Class | Description |
|-----|-----|-----------|-------------|
| `F1:00` | `0xF100` | `RBusPGNBatteryProperties` | Battery properties (static config) |
| `F1:02` | `0xF102` | `RBusPGNBatterySensorMeasurements` | Instantaneous measurements (secondary) |
| `F1:04` | `0xF104` | `RBusPGNBatteryChargeStatus` | State of charge, health, time remaining |
| `F1:05` | `0xF105` | `RBusPGNBatteryBankStatus` | Battery bank status |
| `F1:06` | `0xF106` | `RBusPGNBatterySensorSettings1` | Shunt config (max current, max voltage drop) |
| `F1:08` | `0xF108` | `RBusPGNLoadDisconnectStatus` | Load disconnect relay status |
| `F1:0A` | `0xF10A` | `RBusPGNLowBatteryAlarm` | Low battery alarm thresholds and status |
| `F1:0C` | `0xF10C` | `RBusPGNIgnitionStatus` | Ignition sense input |
| `F1:0E` | `0xF10E` | `RBusPGNStartBatteryProperties` | Start battery properties |
| `F2:80` | `0xF280` | `RBusPGNBatterySensorMeasurementsAveraged` | **Averaged measurements — primary display PGN** |
| `F2:82` | `0xF282` | `RBusPGNChargerCurrentsAveraged` | Averaged charger input currents |
| `F2:84` | `0xF284` | `RBusPGNChargerVoltagesAveraged` | Averaged charger voltages |
| `F2:07` | `0xF207` | `RBusPGNDCInputConfiguration` | DC input config |
| `F2:08` | `0xF208` | `RBusPGNSolarInputStatus` | Solar input status |
| `F2:0A` | `0xF20A` | `RBusPGNDeviceOutputStatus` | Device output status |
| `F2:0E` | `0xF20E` | `RBusPGNBluetoothStatus` | Bluetooth status |
| `FC:D0` | `0xFCD0` | `RBusPGNSOCLogHourly` | SOC hourly log (7 bytes, most recent first) |
| `FC:D2` | `0xFCD2` | `RBusPGNMinimumSOCLogDaily` | Minimum SOC daily log |
| `FC:D4` | `0xFCD4` | `RBusPGNMaximumSOCLogDaily` | Maximum SOC daily log |
| `FC:D5` | `0xFCD5` | `RBusPGNCumulativeSolarPowerLogHourly` | Cumulative solar power hourly log |
| `FC:D6` | `0xFCD6` | `RBusPGNCumulativeSolarPowerLogDaily` | Cumulative solar power daily log |

### Misc Device PGNs

| PGN | Hex | App Class | Description |
|-----|-----|-----------|-------------|
| `F3:04` | `0xF304` | `RBusPGNRealTimeClock` | Device clock. Set by app; echoed back. Layout: `[?:1][month:1][year:2 LE][hour:1][min:1][sec:1]` |

### Node/Firmware PGNs

| PGN | Hex | App Class | Description |
|-----|-----|-----------|-------------|
| `F4:00` | `0xF400` | `RBusPGNNodeFirmware` | Firmware version |
| `F4:01` | `0xF401` | `RBusPGNNodeFirmwareExtended` | Extended firmware info |
| `F4:02` | `0xF402` | `RBusPGNNodeManufactureDate` | Manufacture date (constant) |
| `F4:03` | `0xF403` | `RBusPGNNodeProductName` | Product name string |
| `F4:04` | `0xF404` | `RBusPGNNodeSerialInformation` | Serial number / device type |
| `F4:05` | `0xF405` | `RBusPGNNodeDeviceID` | Device ID / index |
| `F4:06` | `0xF406` | `RBusPGNDeviceOperatingMode` | Operating mode |
| `F4:08` | `0xF408` | `RBusPGNChargerDeviceCapabilities` | Charger capability flags |
| `F4:0A` | `0xF40A` | `RBusPGNFanNightMode` | Fan night mode config |
| `F4:0C` | `0xF40C` | `RBusPGNNodePowerDistributionStatus` | Power distribution status |

### Command PGNs (write-only)

| Off14 | App Class | Direction |
|-------|-----------|-----------|
| `0x0000` | `RBusPGNRbusParameterSet` | Write |
| `0x0100` | `RBusPGNTestAndCalibrationModeRequest` | Write |
| `0x0300` | `RBusPGNPgnRequest` | Write (request a PGN) |
| `0x0400` | `RBusPGNAcknowledgementMessage` | Bidirectional |
| `0x0A00` | `RBusPGNChargeBackCommand` | Write |

---

## 4. PGN Field Definitions

All byte offsets are 0-indexed relative to the PGN payload (after the 5-byte RBUS frame
header). Only PGNs with confirmed field layouts are documented here.

### `F1:04` — `RBusPGNBatteryChargeStatus` (~300 ms)

| Bytes | Field | Formula | Sentinel |
|-------|-------|---------|----------|
| `[0]` | `batteryStateOfCharge` | raw % (integer 0–100) | — |
| `[1]` | `batteryStateOfHealth` | raw % (integer 0–100) | `0xFF` = not available |
| `[2–3]` LE u16 | `batteryTimeUntilFullflat` | `(raw − 32127) × 5` minutes | `0xFFFA` = not available |
| `[4–7]` | reserved | — | always `0xFF` |

**`batteryTimeUntilFullflat` sign convention:** positive = minutes to reach 100% SOC
(charging); negative magnitude = minutes to empty (discharging).

---

### `F2:80` — `RBusPGNBatterySensorMeasurementsAveraged` (~1000 ms) — primary measurement PGN

| Bytes | Field | Formula | Sentinel |
|-------|-------|---------|----------|
| `[0–1]` LE u16 | `batterySensorCurrentAveraged` | `(raw − 10000) × 0.1` A | `20000` = not available |
| `[2–3]` LE u16 | `batterySensorVoltageAveraged` | `raw × 0.1` V | `643` = not available |
| `[4–5]` LE u16 | `loadCurrentAveraged` | `(raw − 10000) × 0.1` A | `0xFFFF` = not available |
| `[6]` | `batterySensorTemperatureAveraged` | `raw − 60` °C | `0xFA` = not available |
| `[7]` | padding | — | `0xFF` |

`batterySensorCurrentAveraged` is the net shunt current (all sources combined). Negative =
discharging. This is the field the app home screen displays as battery current.

`loadCurrentAveraged` is always `0xFFFF` on a standalone single-shunt BSEN500. It is
populated only when a RBUS-enabled charger (e.g. BCDC Alpha R) is present on the bus.

Voltage sentinel `643` decodes to 64.3 V, which is physically unreachable on a 12/24 V
system and thus unambiguous.

---

### `F1:02` — `RBusPGNBatterySensorMeasurements` (~2000 ms) — secondary voltage source

| Bytes | Field | Formula | Notes |
|-------|-------|---------|-------|
| `[0–1]` | `batterySensorCurrent` | — | Slow accumulator; not suitable for instantaneous current |
| `[2–3]` | unknown | — | Constant `0x0F 0x00` in all captures |
| `[4–5]` LE u16 | `batterySensorVoltage` | `raw / 1000.0` V (raw = millivolts) | 1 mV resolution vs. F2:80's 100 mV |
| `[6]` | `batterySensorTemperature` | `raw − 60` °C | Same formula as F2:80 `[6]`; sentinel `0xFA` |
| `[7]` | padding | — | `0xFF` |

---

### `F1:0A` — `RBusPGNLowBatteryAlarm` (~1000 ms)

| Bytes | Field | Formula | Sentinel |
|-------|-------|---------|----------|
| `[0]` bits [1:0] | `lowBatterySocAlarmStatus` | `RBusActivated_Boolean` enum (0 = inactive) | — |
| `[0]` bits [3:2] | `lowBatteryVoltageAlarmStatus` | `RBusActivated_Boolean` enum (0 = inactive) | — |
| `[0]` bits [7:4] | reserved | — | not decoded |
| `[1]` | `lowBatterySocAlarmSetPoint` | integer % | — |
| `[2–3]` LE u16 | `lowBatteryVoltageAlarmSetPoint` | `raw × 0.001` V | `0xFFFA` = not available |
| `[4–7]` | reserved | — | `0xFF` |

This PGN contains alarm thresholds and status flags only. Temperature data is in
`F2:80 [6]` and `F1:02 [6]`.

Sample payload `F0 0E EC 2C FF FF FF FF`:
- `byte[0]` = `0xF0` → bits[0:4] = 0 → both alarms inactive
- `byte[1]` = `0x0E` = 14 → SOC alarm fires at 14%
- `bytes[2:4]` = `0x2CEC` = 11500 → `11500 × 0.001` = 11.500 V voltage alarm setpoint

---

### `F1:00` — `RBusPGNBatteryProperties` (~5000 ms)

Partially decoded. `byte[2]` = `charge_state`; always `1` in all captures across both
charging and discharging conditions. Meaning unknown.

---

### `F4:02` — `RBusPGNNodeManufactureDate` (static)

Constant payload encoding manufacture date, not current measurements.
Sample: `17 05 E8 07 00 00 00 00` = day 23, month 5, year 2024.

---

### `FC:D0` — `RBusPGNSOCLogHourly`

7-byte payload. Each byte = SOC% for one hour of history, most recent first.
Example: `00 5F 63 63 63 63 63` → [current hour: 0%, −1h: 95%, −2h to −6h: 99%].
Multi-segment reassembly required (see §2.2).

---

## 5. Calibration Points

### `F2:80` net current — `(raw − 10000) × 0.1` A

| bytes[0–1] raw | Decoded | Condition |
|----------------|---------|-----------|
| 10005 | +0.5 A | Charging, confirmed vs. app display |
| 9924 | −7.6 A | Net discharge |
| 9837 | −16.3 A | Net discharge, inverter running |
| 9856 | −14.4 A | Net discharge, confirmed vs. app display |
| 9892 | −10.8 A | Net discharge |

Zero-point: raw = 10000 → 0.0 A. A ±17-count uncertainty (±1.7 A) at the zero-point
remains unresolved; no 0 A rest-state capture has been taken.

### `F1:04` time remaining — `(raw − 32127) × 5` minutes

| bytes[2–3] raw | Decoded | Condition |
|----------------|---------|-----------|
| 32198 | +355 min (5.9 h to full) | Charging 0.5 A, 99% SOC |
| 31627 | −2500 min (41.7 h to flat) | Discharging 6.7 A, 98% SOC |
| 31909 | −1090 min (18.2 h to flat) | Discharging 14.4 A, 93% SOC |
| 31845 | −1410 min (23.5 h to flat) | Discharging ~10 A, 88% SOC |

### `F2:80` temperature — `raw − 60` °C

| raw | Decoded |
|-----|---------|
| `0x43` = 67 | 7°C |
| `0x46` = 70 | 10°C |
| `0x48` = 72 | 12°C |
| `0x4B` = 75 | 15°C — confirmed vs. app display |

### `F1:0A` alarm setpoints (constant across all captures)

| Field | Value |
|-------|-------|
| SOC alarm setpoint | 14% |
| Voltage alarm setpoint | 11.500 V |
| Both alarm statuses | inactive |

---

## 6. Sentinel Values

| Value | Type | Applies to |
|-------|------|------------|
| `0xFF` | uint8 | Not available or reserved (general) |
| `0xFFFF` | uint16 | Not available (general) |
| `0xFFFA` | uint16 | `batteryTimeUntilFullflat` (F1:04); `lowBatteryVoltageAlarmSetPoint` (F1:0A) |
| `20000` | uint16 | `batterySensorCurrentAveraged` (F2:80) |
| `643` | uint16 | `batterySensorVoltageAveraged` (F2:80) |
| `0xFA` | uint8 | Temperature fields: `batterySensorTemperatureAveraged` (F2:80 `[6]`), `batterySensorTemperature` (F1:02 `[6]`) |

---

## 7. Known Limitations

The following aspects of the protocol are unresolved or unconfirmed.

1. **`batteryStateOfHealth` (F1:04 `[1]`)** — Always `0xFF` in all captures. The BSEN500
   does not appear to populate this field in normal operation.

2. **`charge_state` (F1:00 `[2]`)** — Always `1` in all captures across both charging and
   discharging conditions. Meaning unknown.

3. **F2:80 current zero-point** — Formula zero-point raw = 10000 has a ±17-count
   uncertainty (±1.7 A). No 0 A rest-state capture has been taken to confirm this exactly.

4. **`F1:06` shunt settings** (`RBusPGNBatterySensorSettings1`) — Not captured. Field
   layout unknown. Contains `batterySensorMaximumShuntCurrent` and
   `batterySensorMaximumShuntVoltageDrop`.

5. **`FC:D0` multi-segment reassembly** — Logic is implemented but has not been validated
   against a real device notification.

6. **`10102022` service** — UUIDs enumerated. Role of characteristics `8001` and `8011`
   is unknown; they were not subscribed in any tested session.

7. **`loadCurrentAveraged` (F2:80 `[4–5]`) on dual-shunt configuration** — Always
   `0xFFFF` on a standalone single-shunt BSEN500. Populated when a RBUS-enabled charger
   (e.g. BCDC Alpha R) is present on the bus; formula assumed to be the same as
   `batterySensorCurrentAveraged`: `(raw − 10000) × 0.1` A.

8. **`(0x08, 0x1C)` PGN** — Observed in HCI captures from source address `0x00`. Identity
   unknown; does not correspond to any standard J1939 or NMEA 2000 PGN.
