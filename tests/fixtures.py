"""
REDARC BSEN500 BLE protocol test fixtures.

Each fixture is a dict with:
  "id"          – unique identifier for the scenario
  "description" – human-readable description and provenance
  "notify_hex"  – full BLE characteristic notification bytes as hex string
                  (RBUS wire frame: [flags(1), pduFmt(1), pduSpec(1), srcAddr(1),
                  lenByte(1), payload(N)])  These are the bytes that arrive in the
                  bleak on_notify callback `data: bytearray`.
  "provenance"  – "raw_capture" means bytes taken directly from btsnoop/monitor log.
                  "constructed" means bytes built from decoded values in the log;
                  ground truth verified against REDARC app screenshot at same time.
  "expected_frames" – list of expected RBusFrame field values after parse_rbus_frames()
  "expected_state_delta" – subset of BatteryState fields that should be set after
                           decode_frame() is applied to the expected frames

All ground truth verified against REDARC Smart Battery Monitor app (au.com.redarc.redvision.tvms.user)
on 2026-06-10.

Wire header reference:
  flags    = 0xA0  (constant for device 60:15:21:00:1B:E1)
  srcAddr  = 0x36  (device RBUS address, read via GW_RBUS_ADDR command)
  lenByte  = 0x88  (bits[3:0]=8 = 8-byte payload, for all standard measurement frames)

Field mapping — confirmed from blutter ASM tracing 2026-06-10 (BLUTTER_FINDINGS.md):
  SOC               : (0xF1,0x04) payload[0]   = integer percent 0-100
  SoH               : (0xF1,0x04) payload[1]   = integer percent; 0xFF = N/A
  Time to full/flat : (0xF1,0x04) payload[2-3] = LE uint16; (raw−32127)×5 minutes
                       positive → to full; negative magnitude → to flat; 0xFFFA = N/A
  Net current       : (0xF2,0x80) payload[0-1] = LE uint16; (raw−10000)×0.1 A
                       negative = discharging; sentinel = 20000
                         9856 → −14.4 A  (session D, app confirmed ~14 A)
                         10005 → +0.5 A  (session A, app confirmed +0.5 A charging)
  Voltage (primary) : (0xF2,0x80) payload[2-3] = LE uint16; raw×0.1 V; sentinel = 643
  Voltage (secondary): (0xF1,0x02) payload[4-5] = LE uint16 millivolts
  Temperature       : (0xF2,0x80) payload[6]   = raw−60 °C; 0xFA = N/A
  Alarm status      : (0xF1,0x0A) payload[0] bits[0:2]=SOC alarm, bits[2:4]=voltage alarm
  Alarm setpoints   : (0xF1,0x0A) payload[1]=SOC%, payload[2-3]=voltage×0.001 V
"""

from pybsen.models import ChargeDirection

# ---------------------------------------------------------------------------
# Session A  –  charging +0.5A, voltage 13.385V (F1:02) / 13.3V (F2:80), SOC 99%
#               temperature 7°C  (app screenshot 2026-06-10 11:08)
# ---------------------------------------------------------------------------

# (0xF1,0x02)  Voltage frame (secondary source, 0.5 Hz)
# payload[4-5] LE uint16 = 0x3449 = 13385 mV = 13.385 V
# bytes taken directly from monitor log: "[8B] 42 44 0f 00 49 34 45 ff"
NOTIFY_A_VOLTAGE = bytes.fromhex("a0f102368842440f00493445ff")

# (0xF2,0x80)  Averaged measurements frame (PRIMARY: current + voltage + temperature, 1 Hz)
# payload[0-1] LE uint16 = 0x2715 = 10005 → (10005−10000)×0.1 = +0.5 A  (charging)
# payload[2-3] LE uint16 = 0x0085 = 133   → 133×0.1 = 13.3 V
# payload[6]   = 0x43 = 67               → 67−60 = 7°C
# bytes from calibration session manual decode
NOTIFY_A_CURRENT = bytes.fromhex("a0f280368815278500ffff43ff")

# (0xF1,0x04)  Charge status frame
# payload[0] = 0x63 = 99  (SOC integer percent)
# payload[2-3] LE uint16 = 0x7DC6 = 32198 → (32198−32127)×5 = 355 min to full ≈ 5.9h ✓
NOTIFY_A_SOC = bytes.fromhex("a0f104368863ffc67dffffffff")

# (0xF1,0x0A)  Low battery alarm frame (NOT temperature — BLUTTER_FINDINGS.md §2.3)
# payload[0]   = 0xF0 = 0b11110000 → bits[0:2]=0 (SOC alarm off), bits[2:4]=0 (volt alarm off)
# payload[1]   = 0x0E = 14         → SOC alarm setpoint = 14%
# payload[2-3] = 0xEC 0x2C = 0x2CEC = 11500 → 11500×0.001 = 11.500 V setpoint
NOTIFY_A_TEMP = bytes.fromhex("a0f10a3688f00eec2cffffffff")

# (0xF1,0x00)  Charge state frame
# payload[2] = 0x01  (charge_state = 1)
NOTIFY_A_CHARGESTATE = bytes.fromhex("a0f1003688041801ff630c01ff")

# (0xF4,0x04)  Static device info (constant; serial / config bytes)
NOTIFY_A_DEVICEINFO = bytes.fromhex("a0f40436885f6d5b8f14001800")

# ---------------------------------------------------------------------------
# Session B  –  net discharging −7.6A (loads > solar), voltage 13.214V, SOC 99%
#               (workload applied 2026-06-10 11:18; solar still exceeds load per app)
# ---------------------------------------------------------------------------

# (0xF2,0x80)  Averaged measurements frame
# payload[0-1] LE uint16 = 0x26C4 = 9924 → (9924−10000)×0.1 = −7.6 A  (net discharging)
# payload[2-3] LE uint16 = 0x0084 = 132  → 132×0.1 = 13.2 V
# payload[6]   = 0x43 = 67              → 67−60 = 7°C
# Note: provenance=constructed (decoded value from log; decoder verified correct in session A)
NOTIFY_B_CURRENT = bytes.fromhex("a0f2803688c4268400ffff43ff")

# (0xF1,0x02)  Voltage frame (secondary, 13.214V = 13214 mV)
# payload[4-5] = 0x339E = 13214 mV
# Note: provenance=constructed; payload[0-3] are accumulator/counter (not decoded)
NOTIFY_B_VOLTAGE = bytes.fromhex("a0f102368800000f009e3345ff")

# ---------------------------------------------------------------------------
# Parser edge-case fixtures
# ---------------------------------------------------------------------------

# Empty notification — parse_rbus_frames should return []
NOTIFY_EMPTY = b""

# Truncated header (4 bytes instead of minimum 5) — should return []
NOTIFY_TOO_SHORT = bytes.fromhex("a0f10436")

# Stray continuation byte at start (bit6 of b0 = 1) — should skip and return []
NOTIFY_STRAY_CONTINUATION = bytes.fromhex("40f10436885f6d5b8f14001800")

# Gateway channel response (CHAR_2015_8003) — 3 bytes, not an RBUS CAN frame
# Returned from MTU negotiation write: [0x80, 0x02, 0x00]
NOTIFY_GW_MTU_RESPONSE = bytes.fromhex("800200")

# Gateway channel response: device RBUS address = 0x36
NOTIFY_GW_ADDR_RESPONSE = bytes.fromhex("80010136")

# ---------------------------------------------------------------------------
# Composite decode sequences
# These represent a realistic burst of notifications as the device sends
# multiple PGN types in one update cycle.  Feed all into decode_frame()
# in sequence and check the final BatteryState.
# ---------------------------------------------------------------------------

SEQUENCE_A_CHARGING = [
    # (notify_hex,            expected_field,             expected_value)
    # F1:04: SOC=99%, payload[2-3]=0x7DC6=32198 → (32198−32127)×5=355 min to full
    (NOTIFY_A_SOC, "soc_pct", 99),
    (NOTIFY_A_SOC, "time_to_full_min", 355),  # (32198−32127)×5
    # F1:02: voltage fallback 13.385 V (secondary source, 1 mV precision)
    (NOTIFY_A_VOLTAGE, "voltage_V", 13.385),
    # F2:80: net current +0.5 A, voltage 13.3 V (primary, overwrites), temp 7°C
    (NOTIFY_A_CURRENT, "net_current_A", 0.5),  # (10005−10000)×0.1
    (NOTIFY_A_CURRENT, "charge_direction", ChargeDirection.CHARGING),
    (NOTIFY_A_CURRENT, "voltage_V", 13.3),  # 133×0.1
    (NOTIFY_A_CURRENT, "temp_c", 7.0),  # 67−60
    # F1:0A: alarm status — both off; setpoints present
    (NOTIFY_A_TEMP, "soc_alarm_active", False),
    (NOTIFY_A_TEMP, "voltage_alarm_active", False),
    (NOTIFY_A_TEMP, "soc_alarm_setpoint_pct", 14),
    (NOTIFY_A_TEMP, "voltage_alarm_setpoint_V", 11.5),
    (NOTIFY_A_CHARGESTATE, "charge_state", 1),
]

# Session 3 — discharging (app screenshot 2026-06-10 11:25, app: 6.7A)
# F1:04 payload: 62 ff 8b 7b ff ff ff ff
#   payload[0] = 0x62 = 98  (SOC %)
#   payload[2-3] = [0x8B, 0x7B] = 0x7B8B = 31627 → (31627−32127)×5 = −2500 min to flat = 41.7h
#   time-to-flat cross-check: 280 Ah × 0.98 / 6.7 A = 41.0 h ✓
# NOTE: net current must be read from a companion F2:80 frame (not included in session 3 fixtures)
NOTIFY_3_MEASUREMENT = bytes.fromhex("a0f10436" + "88" + "62ff8b7bffffffff")
NOTIFY_3_VOLTAGE = bytes.fromhex("a0f10236" + "88" + "15280f008c3346ff")  # V=13196mV

SEQUENCE_3_DISCHARGING = [
    (NOTIFY_3_MEASUREMENT, "soc_pct", 98),
    (NOTIFY_3_MEASUREMENT, "time_to_flat_min", 2500),  # (31627−32127)×5 = −2500 → abs=2500
    (NOTIFY_3_VOLTAGE, "voltage_V", 13.196),  # 13196 mV ÷ 1000
]

SEQUENCE_B_LESS_CHARGING = [
    # F2:80: net current −7.6 A (loads > solar despite positive charger direction label in session name)
    (NOTIFY_B_CURRENT, "net_current_A", -7.6),  # (9924−10000)×0.1
    (NOTIFY_B_CURRENT, "charge_direction", ChargeDirection.DISCHARGING),
    (NOTIFY_B_CURRENT, "voltage_V", 13.2),  # 132×0.1
    (NOTIFY_B_VOLTAGE, "voltage_V", 13.214),  # F1:02 secondary: 13214 mV
]

# ---------------------------------------------------------------------------
# Session C  –  net discharging −16.3A (inverter running, solar partially compensates),
#               voltage 13.143V, SOC 98%, temperature 10°C  (2026-06-10 11:30)
# All bytes from raw verbose log capture.
# ---------------------------------------------------------------------------

# (0xF2,0x80)  Averaged measurements frame
# payload[0-1] LE uint16 = 0x266D = 9837 → (9837−10000)×0.1 = −16.3 A  (net discharging)
# payload[2-3] LE uint16 = 0x0083 = 131  → 131×0.1 = 13.1 V
# payload[6]   = 0x46 = 70              → 70−60 = 10°C
NOTIFY_C_CURRENT = bytes.fromhex("a0f2803688" + "6d268300ffff46ff")

# (0xF1,0x02)  Voltage 13.143V = 13143 mV = 0x3357, LE = [0x57, 0x33]
NOTIFY_C_VOLTAGE = bytes.fromhex("a0f1023688" + "17020f005733" + "46ff")

# (0xF1,0x04)  Charge status: SOC=98%, payload[2-3]=0x7CB7=31927 → (31927−32127)×5=−1000 min to flat
NOTIFY_C_SOC = bytes.fromhex("a0f1043688" + "62ffb77cffffffff")

SEQUENCE_C_CHARGING = [
    (NOTIFY_C_CURRENT, "net_current_A", -16.3),  # (9837−10000)×0.1
    (NOTIFY_C_CURRENT, "charge_direction", ChargeDirection.DISCHARGING),
    (NOTIFY_C_CURRENT, "voltage_V", 13.1),  # 131×0.1
    (NOTIFY_C_CURRENT, "temp_c", 10.0),  # 70−60
    (NOTIFY_C_VOLTAGE, "voltage_V", 13.143),  # F1:02 secondary: 13143 mV
    (NOTIFY_C_SOC, "soc_pct", 98),
    (NOTIFY_C_SOC, "time_to_flat_min", 1000),  # (31927−32127)×5=−1000 → abs=1000
]

# ---------------------------------------------------------------------------
# Session D  –  discharging −14.4A, SOC 93%, V≈13.151V (F1:02) / 13.1V (F2:80), temp 12°C
#               Inverter + fridge + lights + laptop charging running.
#               Final validation session 2026-06-10 12:24.
#               All bytes from raw verbose log capture.
#               App ground truth: ~13–14 A discharge confirmed — now correctly decoded from F2:80.
#               (Previous decode from F1:04 bytes[2-3] gave wrong −3.1 A — RESOLVED.)
# ---------------------------------------------------------------------------

# (0xF1,0x04): SOC=93% (0x5D=93), payload[2-3]=0x7CA5=31909
# time_to_flat = (31909−32127)×5 = −1090 min = 18.2h; cross-check: 280×0.93/14.4 = 18.1h ✓
NOTIFY_D_MEASUREMENT = bytes.fromhex("a0f104368" + "8" + "5dffa57cffffffff")

# (0xF1,0x02): V=13151mV = 0x335F, LE=[0x5F,0x33]
NOTIFY_D_VOLTAGE = bytes.fromhex("a0f102368" + "8" + "150a0f005f3348ff")

# (0xF2,0x80): net_current = −14.4 A, voltage = 13.1 V, temp = 12°C
# payload[0-1] LE uint16 = 0x2680 = 9856  → (9856−10000)×0.1 = −14.4 A ✓ (app ~14 A)
# payload[2-3] LE uint16 = 0x0083 = 131   → 131×0.1 = 13.1 V
# payload[6]   = 0x48 = 72               → 72−60 = 12°C
NOTIFY_D_CHARGER = bytes.fromhex("a0f280368" + "8" + "802683 00ffff48ff".replace(" ", ""))

SEQUENCE_D_DISCHARGING = [
    (NOTIFY_D_MEASUREMENT, "soc_pct", 93),
    (NOTIFY_D_MEASUREMENT, "time_to_flat_min", 1090),  # (31909−32127)×5=−1090 → abs=1090
    (NOTIFY_D_VOLTAGE, "voltage_V", 13.151),  # F1:02: 13151 mV
    # F2:80 is the authoritative current source (blutter confirmed)
    (NOTIFY_D_CHARGER, "net_current_A", -14.4),  # (9856−10000)×0.1
    (NOTIFY_D_CHARGER, "charge_direction", ChargeDirection.DISCHARGING),
    (NOTIFY_D_CHARGER, "voltage_V", 13.1),  # 131×0.1
    (NOTIFY_D_CHARGER, "temp_c", 12.0),  # 72−60
]

# ---------------------------------------------------------------------------
# Session E  –  discharging −10.0 to −10.8 A, voltage 13.20 V, SOC 88%, temperature 15°C
#               2026-06-10 ~14:08–14:10.  All bytes from raw verbose log capture.
#               App ground truth: app_validation_141020.png (~80s after monitor stopped):
#                 SOC 88% ✓  voltage 13.2V ✓  temperature 15°C ✓
#                 current 9.1 A discharge (directionally correct; ~80s lag + load fluctuation)
# ---------------------------------------------------------------------------

# (0xF2,0x80)  Averaged measurements frame
# payload[0-1] LE uint16 = 0x26A4 = 9892 → (9892−10000)×0.1 = −10.8 A  (net discharging)
# payload[2-3] LE uint16 = 0x0084 = 132  → 132×0.1 = 13.2 V
# payload[4-5] = 0xFFFF                  → load current N/A (single-shunt config)
# payload[6]   = 0x4B = 75              → 75−60 = 15°C  (CONFIRMED vs app screenshot)
NOTIFY_E_CURRENT = bytes.fromhex("a0f2803688" + "a42684 00ffff4bff".replace(" ", ""))

# (0xF1,0x04)  Charge status frame
# payload[0] = 0x58 = 88  (SOC integer percent)
# payload[1] = 0xFF       (SoH N/A)
# payload[2-3] LE uint16 = [0x65, 0x7C] = 0x7C65 = 31845
#   → (31845−32127)×5 = −1410 min to flat ≈ 23.5h
#   cross-check: 280×0.88/10.4 ≈ 23.7h ✓  (using midpoint 10.4A)
NOTIFY_E_SOC = bytes.fromhex("a0f104368858ff657cffffffff")

# (0xF1,0x0A)  Low battery alarm frame — same setpoints as all other sessions
# payload[0] = 0xF0 → bits[0:2]=0 (SOC alarm off), bits[2:4]=0 (volt alarm off)
# payload[1] = 0x0E = 14  → SOC alarm setpoint 14%
# payload[2-3] = 0x2CEC = 11500 → 11500×0.001 = 11.500 V setpoint
NOTIFY_E_ALARM = bytes.fromhex("a0f10a3688f00eec2cffffffff")

# (0xF1,0x00)  Charge state frame — charge_state = 1 (same as all sessions)
NOTIFY_E_CHARGESTATE = bytes.fromhex("a0f1003688041801ff630c01ff")

SEQUENCE_E_DISCHARGING = [
    # F2:80: current/voltage/temperature (primary authoritative source)
    (NOTIFY_E_CURRENT, "net_current_A", -10.8),  # (9892−10000)×0.1
    (NOTIFY_E_CURRENT, "charge_direction", ChargeDirection.DISCHARGING),
    (NOTIFY_E_CURRENT, "voltage_V", 13.2),  # 132×0.1
    (NOTIFY_E_CURRENT, "temp_c", 15.0),  # 75−60  (confirmed vs app)
    # F1:04: SOC and time to flat
    (NOTIFY_E_SOC, "soc_pct", 88),
    (NOTIFY_E_SOC, "time_to_flat_min", 1410),  # (31845−32127)×5=−1410 → abs=1410
    # F1:0A: alarms off (configuration unchanged from prior sessions)
    (NOTIFY_E_ALARM, "soc_alarm_active", False),
    (NOTIFY_E_ALARM, "voltage_alarm_active", False),
    (NOTIFY_E_ALARM, "soc_alarm_setpoint_pct", 14),
    (NOTIFY_E_ALARM, "voltage_alarm_setpoint_V", 11.5),
    (NOTIFY_E_CHARGESTATE, "charge_state", 1),
]

# ---------------------------------------------------------------------------
# Net current scale confirmation
# Formula (F2:80 bytes[0:2]): net_current_A = (raw_u16 − 10000) × 0.1
# Confirmed from blutter ASM: RBusPGNBatterySensorMeasurementsAveraged.batterySensorCurrentAveraged
# offset=−10000, resolution=0.1, sentinel=20000  (BLUTTER_FINDINGS.md §2.2)
# ---------------------------------------------------------------------------
NET_CURRENT_SCALE_POINTS = [
    # (raw_u16_from_F280_bytes01, expected_net_A, source)
    (10005, 0.5, "session A — F2:80 bytes[0:1]=0x2715; app: +0.5A charging, no load"),
    (9924, -7.6, "session B — F2:80 bytes[0:1]=0x26C4; loads running"),
    (9837, -16.3, "session C — F2:80 bytes[0:1]=0x266D; inverter running"),
    (9856, -14.4, "session D — F2:80 bytes[0:1]=0x2680; app confirmed ~14A ✓"),
    (9892, -10.8, "session E — F2:80 bytes[0:1]=0x26A4; app 9.1A ~80s later (temporal gap)"),
    (10000, 0.0, "zero-point (theoretical, raw=10000; ±17-count uncertainty from session E back-calc)"),
]

# F1:04 bytes[2:4] time-to-full/flat calibration points
# Formula: (raw_u16 − 32127) × 5 minutes; positive=to-full, negative=to-flat
# Confirmed from blutter ASM: RBusPGNBatteryChargeStatus.batteryTimeUntilFullflat
# offset=−32127, resolution=5, sentinel=0xFFFA  (BLUTTER_FINDINGS.md §2.1)
TIME_REMAINING_SCALE_POINTS = [
    # (raw_u16_from_F104_bytes23, expected_minutes, interpretation, cross_check)
    (32198, 355, "session A  charging +0.5A  99% SOC  to-full", "280×0.01/0.5=5.6h ≈ 5.9h ✓"),
    (31627, -2500, "session 3  discharging 6.7A 98% SOC  to-flat", "280×0.98/6.7=41.0h ≈ 41.7h ✓"),
    (31909, -1090, "session D  discharging 14.4A 93% SOC to-flat", "280×0.93/14.4=18.1h ≈ 18.2h ✓"),
    (31845, -1410, "session E  discharging ~10.4A 88% SOC to-flat", "280×0.88/10.4=23.7h ≈ 23.5h ✓"),
    (32127, 0, "zero-point (raw=32127, formula value=0)"),
]
