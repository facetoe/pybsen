meta:
  id: rbus_frame
  title: REDARC BSEN500 RBUS CAN Frame
  license: MIT
  ks-version: 0.11
  endian: le

doc: |
  Single reassembled RBUS CAN frame as received on CHAR_2015_8001
  (UUID 09022015-5160-4000-8001-524544415243).

  A BLE notification may carry one or more concatenated RBUS frames.
  Multi-segment reassembly (flags byte bit6 set, i.e. 0x40|x continuation
  frames for FC:D0 and similar) is NOT expressible in Kaitai Struct and
  MUST be handled by a pre-processor before this spec is applied.

  Device: REDARC Smart Battery Monitor BSEN500
    MAC: 60:15:21:00:1B:E1
    RBUS source address: 0x36

  Source: Protocol reverse-engineered from Flutter/Dart AOT binary
  (blutter decompilation), HCI snoop logs, and live capture sessions A-E.
  All field formulas confirmed from ASM tracing 2026-06-10.
  See PROTOCOL.md for full calibration evidence.

  Flags byte note: 0xA0 observed in Python monitor sessions; 0x33 observed
  in original Android app HCI snoop. Both are valid RBUS frame starters.
  Bit 6 (0x40) set in flags indicates a multi-segment continuation frame —
  do not pass continuation frames to this spec.

seq:
  - id: flags
    type: u1
    doc: |
      Frame type/flags byte. 0xA0 observed via Python bleak monitor;
      0x33 observed in Android HCI snoop. Bit 6 (0x40) set = continuation
      frame; those must not be parsed by this spec (pre-processor concern).
      Source: PROTOCOL.md §3.
    -confidence: high
    -evidence: all sessions A-E, fixtures.py NOTIFY_A_CURRENT etc.

  - id: pdu_fmt
    type: u1
    doc: |
      J1939 PDU Format byte — high byte of the 16-bit PGN key.
      All observed BSEN500 frames have pdu_fmt >= 0xF0 (PDU2 broadcast).
      Source: PROTOCOL.md §4, blutter RBusPGNList.off_14.
    -confidence: high

  - id: pdu_spec
    type: u1
    doc: |
      PDU Specific byte — low byte of the 16-bit PGN key.
      Source: PROTOCOL.md §4.
    -confidence: high

  - id: src_addr
    type: u1
    doc: |
      RBUS source address of the transmitting device.
      BSEN500 unit: 0x36 (read via gateway command GW_RBUS_ADDR).
      Source: PROTOCOL.md §3, AGENTS.md device table.
    -confidence: high
    -evidence: all fixture frames have 0x36

  - id: len_byte
    type: u1
    doc: |
      Payload length encoding. Bits [3:0] = actual payload byte count
      (typically 8 for all standard measurement frames, giving len_byte=0x88).
      Upper nibble meaning is unconfirmed; observed as 0x8 in all captures.
      Source: PROTOCOL.md §3.
    -confidence: high

  - id: payload
    size: data_len
    type:
      switch-on: pgn_key
      cases:
        0xf104: pgn_f1_04
        0xf280: pgn_f2_80
        0xf102: pgn_f1_02
        0xf10a: pgn_f1_0a
        0xf100: pgn_f1_00
        0xf304: pgn_f3_04
        0xf404: pgn_f4_04
        0xfcd0: pgn_fc_d0
        _: pgn_unknown
    doc: |
      Typed payload, dispatched on pgn_key = (pdu_fmt << 8) | pdu_spec.
      Substream is exactly data_len bytes; each sub-type seq starts at
      payload byte [0] (header bytes are NOT included in sub-type seqs).

instances:
  data_len:
    value: 'len_byte & 0x0f'
    doc: |
      Actual payload byte count extracted from bits [3:0] of len_byte.
      Value 8 (from len_byte=0x88) observed in all standard frames.

  pgn_key:
    value: '(pdu_fmt << 8) | pdu_spec'
    doc: |
      16-bit PGN identifier used for payload type dispatch.
      Encoding: (pdu_fmt << 8) | pdu_spec. Matches blutter RBusPGNList.off_14.
      Examples: 0xF280 (primary measurements), 0xF104 (charge status).

types:

  # ---------------------------------------------------------------------------
  # F1:04  RBusPGNBatteryChargeStatus  ~300 ms update rate
  # ---------------------------------------------------------------------------
  pgn_f1_04:
    doc: |
      RBusPGNBatteryChargeStatus — state of charge, health, and time remaining.
      Update rate: ~300 ms. Source: blutter ASM 0x52c214, PROTOCOL.md §5.
      NOTE: There is NO current field in this PGN. Earlier empirical decodes of
      bytes [2-3] as current were incorrect (falsified by session D). Those bytes
      are batteryTimeUntilFullflat (minutes). See PROTOCOL.md §7.
    seq:
      - id: soc_pct
        type: u1
        doc: |
          batteryStateOfCharge — integer percent 0-100.
          Formula: raw value is directly the SOC percentage.
          Source: blutter ASM, confirmed sessions A(99%), D(93%), E(88%).
        -confidence: high
        -evidence: NOTIFY_A_SOC[5]=0x63=99, NOTIFY_D_MEASUREMENT[5]=0x5D=93

      - id: state_of_health_pct
        type: u1
        doc: |
          batteryStateOfHealth — integer percent, or 0xFF = not available.
          Always 0xFF in all captured sessions A-E. The BSEN500 does not
          appear to populate this field in normal operation.
          Source: blutter class name RBusPGNBatteryChargeStatus.
        -confidence: medium
        -evidence: all sessions show 0xFF

      - id: raw_time
        type: u2
        doc: |
          batteryTimeUntilFullflat — raw unsigned 16-bit LE value.
          Apply formula in time_until_fullflat_min instance.
          Sentinel: 0xFFFA = not available.
          Positive decoded result = minutes to reach 100% SOC (charging).
          Negative decoded result magnitude = minutes until flat (discharging).
          Source: blutter ASM 0x52c214, confirmed 3 sessions §6.
        -confidence: high
        -evidence: NOTIFY_A_SOC raw=32198→355min, NOTIFY_D_MEASUREMENT raw=31909→−1090min

    instances:
      time_until_fullflat_min:
        value: 'raw_time == 0xfffa ? -1 : (raw_time - 32127) * 5'
        doc: |
          batteryTimeUntilFullflat decoded to minutes.
          Returns -1 when raw_time == 0xFFFA (not available). 0 means device is exactly
          at crossover. Positive = minutes to full charge. Negative (excluding -1) = minutes to flat.
          Formula: (raw − 32127) × 5 minutes.
          Calibration: A→+355min(5.9h), 3→−2500min(41.7h), D→−1090min(18.2h), E→−1410min(23.5h).
          Zero-point raw=32127 is the boundary between charging and discharging directions.
          Source: PROTOCOL.md §5, §6 TIME_REMAINING_SCALE_POINTS.
        -confidence: high
        -evidence: PROTOCOL.md §6, sessions A/3/D/E — 4 confirmed data points

  # ---------------------------------------------------------------------------
  # F2:80  RBusPGNBatterySensorMeasurementsAveraged  ~1000 ms — PRIMARY PGN
  # ---------------------------------------------------------------------------
  pgn_f2_80:
    doc: |
      RBusPGNBatterySensorMeasurementsAveraged — PRIMARY measurement PGN.
      This is the frame the REDARC app home screen reads for battery current,
      voltage, and temperature. Update rate: ~1000 ms.
      Source: blutter ASM 0x526e90, PROTOCOL.md §5.
      8 bytes: [raw_current:2][raw_voltage:2][raw_load_current:2][raw_temp:1][padding:1]
    seq:
      - id: raw_current
        type: u2
        doc: |
          batterySensorCurrentAveraged — raw unsigned 16-bit LE.
          Formula: (raw − 10000) × 0.1 A. Negative result = discharging.
          Sentinel: 20000 = not available.
          Zero-point: raw=10000 → 0.0 A (theoretical; ±17-count uncertainty
          from session E back-calculation; no 0A calibration captured yet).
          Source: blutter ASM, PROTOCOL.md §5 NET_CURRENT_SCALE_POINTS.
        -confidence: high
        -evidence: NOTIFY_A_CURRENT raw=10005→+0.5A, NOTIFY_D_CHARGER raw=9856→−14.4A

      - id: raw_voltage
        type: u2
        doc: |
          batterySensorVoltageAveraged — raw unsigned 16-bit LE, units of 0.1 V.
          Formula: raw × 0.1 V.
          Sentinel: 643 (= 64.3 V, physically unreachable for 12/24 V battery).
          Source: blutter ASM, PROTOCOL.md §5.
        -confidence: high
        -evidence: NOTIFY_A_CURRENT raw=133→13.3V, NOTIFY_C_CURRENT raw=131→13.1V

      - id: raw_load_current
        type: u2
        doc: |
          loadCurrentAveraged — raw unsigned 16-bit LE.
          Always 0xFFFF on a single-shunt BSEN500 device (not available).
          Would use same formula as raw_current if populated: (raw − 10000) × 0.1 A.
          Source: blutter class definition, PROTOCOL.md §5.
        -confidence: high
        -evidence: all sessions show 0xFFFF

      - id: raw_temp
        type: u1
        doc: |
          batterySensorTemperatureAveraged — raw unsigned byte.
          Formula: raw − 60 °C.
          Sentinel: 0xFA (= 250 raw = 190°C decoded, physically unreachable).
          CONFIRMED: session E raw=0x4B=75 → 75−60=15°C, exact match to app
          screenshot app_validation_141020.png (2026-06-10).
          Source: blutter ASM, PROTOCOL.md §5, §6.
        -confidence: high
        -evidence: NOTIFY_E_CURRENT[11]=0x4B=75→15°C confirmed vs app screenshot

    instances:
      net_current_a:
        value: 'raw_current == 20000 ? 0.0 : (raw_current - 10000) * 0.1'
        doc: |
          Net shunt current in amperes. Positive = charging, negative = discharging.
          Formula: (raw − 10000) × 0.1 A. Returns 0.0 when sentinel (raw=20000).
          CONFIRMED: A→+0.5A, B→−7.6A, C→−16.3A, D→−14.4A, E→−10.8A.
          Source: PROTOCOL.md §6 NET_CURRENT_SCALE_POINTS.
        -confidence: HIGH
        -evidence: PROTOCOL.md §6, sessions A/B/C/D/E — 5 confirmed data points

      voltage_v:
        value: 'raw_voltage == 643 ? 0.0 : raw_voltage * 0.1'
        doc: |
          Averaged battery voltage in volts. Returns 0.0 when sentinel (raw=643).
          Formula: raw × 0.1 V. Resolution 0.1 V; see pgn_f1_02 for 1 mV precision.
          Source: PROTOCOL.md §5.
        -confidence: HIGH
        -evidence: PROTOCOL.md §6, sessions A/C/D/E — 4 confirmed data points

      temp_c:
        value: 'raw_temp == 0xfa ? 0 : raw_temp - 60'
        doc: |
          Battery temperature in degrees Celsius. Returns 0 when sentinel (raw=0xFA).
          Formula: raw − 60 °C.
          Source: PROTOCOL.md §5, §6.
        -confidence: HIGH
        -evidence: PROTOCOL.md §6, session E raw=0x4B=75→15°C confirmed vs app screenshot

  # ---------------------------------------------------------------------------
  # F1:02  RBusPGNBatterySensorMeasurements  ~2000 ms — secondary voltage source
  # ---------------------------------------------------------------------------
  pgn_f1_02:
    doc: |
      RBusPGNBatterySensorMeasurements — secondary voltage and temperature source.
      Update rate: ~2000 ms (0.5 Hz). Provides 1 mV voltage precision vs
      F2:80's 100 mV resolution. discover.py uses the most recent update from
      either F2:80 or F1:02 for the voltage CSV column.
      Source: PROTOCOL.md §5.
      8 bytes: [counter:2][unknown:2][raw_voltage_mv:2][raw_temp:1][padding:1]
    seq:
      - id: counter
        type: u2
        doc: |
          batterySensorCurrent bytes [0-1] — slow-moving accumulator/counter.
          Not suitable for instantaneous current measurement; not decoded.
          Source: PROTOCOL.md §5 (field named batterySensorCurrent in blutter).
        -confidence: low

      - id: unknown_bytes
        type: u2
        doc: |
          Bytes [2-3]. Constant 0x000F (LE: 0x0F 0x00) across all captured sessions.
          Purpose UNKNOWN. Not decoded by blutter pgn class.
        -confidence: low
        -evidence: NOTIFY_C_VOLTAGE[7-8]=0x0F,0x00 (all sessions)

      - id: raw_voltage_mv
        type: u2
        doc: |
          batterySensorVoltage — raw unsigned 16-bit LE in millivolts.
          Formula: raw / 1000.0 V. Higher precision than F2:80 (1 mV vs 100 mV).
          Update rate 0.5 Hz is lower than F2:80's 1 Hz.
          Source: PROTOCOL.md §5.
        -confidence: high
        -evidence: NOTIFY_A_VOLTAGE raw=13385→13.385V, NOTIFY_D_VOLTAGE raw=13151→13.151V

      - id: raw_temp
        type: u1
        doc: |
          batterySensorTemperature — same encoding as F2:80 byte [6].
          Formula: raw − 60 °C. Sentinel: 0xFA.
          Source: PROTOCOL.md §5.
        -confidence: medium

    instances:
      voltage_v:
        value: 'raw_voltage_mv / 1000.0'
        doc: |
          Battery voltage in volts from millivolt raw value.
          Formula: raw_voltage_mv / 1000.0. No separate sentinel — physically
          unreachable values (e.g. 0xFFFF = 65.535 V) can be checked by caller.
          Source: PROTOCOL.md §5.
        -confidence: high

      temp_c:
        value: 'raw_temp == 0xfa ? 0 : raw_temp - 60'
        doc: |
          Temperature in °C. Same formula as F2:80: raw − 60.
          Returns 0 when sentinel 0xFA.
        -confidence: medium

  # ---------------------------------------------------------------------------
  # F1:0A  RBusPGNLowBatteryAlarm  ~1000 ms
  # ---------------------------------------------------------------------------
  pgn_f1_0a:
    doc: |
      RBusPGNLowBatteryAlarm — alarm thresholds and status flags.
      NOT temperature data. Earlier empirical decodes of this PGN as
      temperature were incorrect (see PROTOCOL.md §5 historical note).
      Temperature is only in F2:80 byte[6] and F1:02 byte[6].
      Source: blutter ASM 0x52b0a4, PROTOCOL.md §5.
      8 bytes: [alarm_flags:1][soc_setpoint:1][raw_voltage_setpoint:2][padding:4]
    seq:
      - id: alarm_flags
        type: u1
        doc: |
          Alarm status bitfield.
          Bits [1:0] = lowBatterySocAlarmStatus (RBusActivated_Boolean enum; 0=off).
          Bits [3:2] = lowBatteryVoltageAlarmStatus (0=off).
          Bits [7:4] = not decoded by blutter RBusPGNLowBatteryAlarm class; ignore.
          Sample: 0xF0 = 0b11110000 → both alarms off.
          Source: blutter ASM, PROTOCOL.md §5.
        -confidence: high
        -evidence: NOTIFY_A_TEMP[5]=0xF0→both alarms inactive

      - id: soc_alarm_setpoint_pct
        type: u1
        doc: |
          lowBatterySocAlarmSetPoint — SOC threshold as integer percent.
          Alarm fires when battery SOC drops below this value.
          Sample: 0x0E = 14 → alarm at 14% SOC.
          Source: blutter ASM, PROTOCOL.md §5.
        -confidence: high
        -evidence: NOTIFY_A_TEMP[6]=0x0E=14%

      - id: raw_voltage_setpoint
        type: u2
        doc: |
          lowBatteryVoltageAlarmSetPoint — raw unsigned 16-bit LE.
          Formula: raw × 0.001 V. Sentinel: 0xFFFA = not available.
          Sample: 0x2CEC = 11500 → 11500 × 0.001 = 11.500 V.
          Source: blutter ASM, PROTOCOL.md §5.
        -confidence: high
        -evidence: NOTIFY_A_TEMP bytes[7-8]=0xEC,0x2C→11500→11.500V

    instances:
      soc_alarm_active:
        value: '(alarm_flags & 0x3) != 0'
        doc: |
          True if lowBatterySocAlarmStatus bits [1:0] are non-zero (alarm activated).
          Source: blutter RBusActivated_Boolean enum, PROTOCOL.md §5.
        -confidence: high
        -evidence: NOTIFY_A_TEMP alarm_flags=0xF0→bits[1:0]=0→False, confirmed session A/E

      voltage_alarm_active:
        value: '((alarm_flags >> 2) & 0x3) != 0'
        doc: |
          True if lowBatteryVoltageAlarmStatus bits [3:2] are non-zero (alarm activated).
          Source: blutter ASM, PROTOCOL.md §5.
        -confidence: high
        -evidence: NOTIFY_A_TEMP alarm_flags=0xF0→bits[3:2]=0→False, confirmed session A/E

      voltage_alarm_setpoint_v:
        value: 'raw_voltage_setpoint == 0xfffa ? 0.0 : raw_voltage_setpoint * 0.001'
        doc: |
          Voltage alarm threshold in volts. Returns 0.0 when sentinel (raw=0xFFFA).
          Formula: raw × 0.001 V.
          Source: PROTOCOL.md §5.
        -confidence: high
        -evidence: NOTIFY_A_TEMP raw=11500→11.500V, confirmed sessions A/E

  # ---------------------------------------------------------------------------
  # F1:00  RBusPGNBatteryProperties
  # ---------------------------------------------------------------------------
  pgn_f1_00:
    doc: |
      RBusPGNBatteryProperties — static battery configuration.
      Update rate: ~5000 ms. charge_state byte [2] is always 1 across all
      charging and discharging sessions; meaning UNKNOWN.
      Source: PROTOCOL.md §3 (F1:00 entry), fixtures.py NOTIFY_A_CHARGESTATE.
    seq:
      - id: unknown_0
        type: u2
        doc: |
          Bytes [0-1]. Purpose UNKNOWN. Not decoded by blutter class.
          Sample: wire bytes 04 18 → LE u16 = 0x1804 = 6148 (NOTIFY_A_CHARGESTATE bytes[5-6]).
        -confidence: low

      - id: charge_state
        type: u1
        doc: |
          Byte [2]. Always observed as 1 across all sessions (both charging and
          discharging). Purpose UNKNOWN — does not reliably encode charge direction.
          Source: PROTOCOL.md §3.
        -confidence: low
        -evidence: NOTIFY_A_CHARGESTATE[7]=0x01, NOTIFY_E_CHARGESTATE[7]=0x01

  # ---------------------------------------------------------------------------
  # F3:04  RBusPGNRealTimeClock
  # ---------------------------------------------------------------------------
  pgn_f3_04:
    doc: |
      RBusPGNRealTimeClock — device real-time clock.
      Set by the app; echoed back by the device.
      Source: PROTOCOL.md §4, blutter class name.
      Layout: [unknown_0:1][month:1][year:2][hour:1][minute:1][second:1][padding:1]
    seq:
      - id: unknown_0
        type: u1
        doc: Byte [0]. Possibly day-of-month; UNCONFIRMED. No fixture captured.
        -confidence: low

      - id: month
        type: u1
        doc: 'Month (1-12). Source: blutter, PROTOCOL.md §4.'
        -confidence: medium

      - id: year
        type: u2
        doc: |
          Year, unsigned 16-bit LE. Example: 2024. Source: PROTOCOL.md §4.
          Cross-check only: F4:02 manufacture date uses the same year encoding: 0x07E8=2024.
        -confidence: medium

      - id: hour
        type: u1
        doc: 'Hour (0-23). Source: PROTOCOL.md §4.'
        -confidence: medium

      - id: minute
        type: u1
        doc: 'Minute (0-59). Source: PROTOCOL.md §4.'
        -confidence: medium

      - id: second
        type: u1
        doc: 'Second (0-59). Source: PROTOCOL.md §4.'
        -confidence: medium

  # ---------------------------------------------------------------------------
  # F4:04  RBusPGNNodeSerialInformation
  # ---------------------------------------------------------------------------
  pgn_f4_04:
    doc: |
      RBusPGNNodeSerialInformation — static device identity information.
      Payload is opaque; constant across all sessions.
      Observed payload: 5F 6D 5B 8F 14 00 18 00 (hex).
      Source: PROTOCOL.md §3, fixtures.py NOTIFY_A_DEVICEINFO.
    seq:
      - id: data
        size-eos: true
        doc: |
          Opaque bytes to end of substream. Tolerates any data_len without throwing.
          Constant across sessions: 5F 6D 5B 8F 14 00 18 00.
          Source: PROTOCOL.md §3.
        -confidence: low
        -evidence: NOTIFY_A_DEVICEINFO payload bytes

  # ---------------------------------------------------------------------------
  # FC:D0  RBusPGNSOCLogHourly
  # ---------------------------------------------------------------------------
  pgn_fc_d0:
    doc: |
      RBusPGNSOCLogHourly (0xFCD0). 7 bytes, each byte = SOC% for one hour of history,
      most recent first. Example: [0x00, 0x5F, 0x63, 0x63, 0x63, 0x63, 0x63] =
      [current hour: 0%, -1h: 95%, -2h to -6h: 99%].
      Source: PROTOCOL.md §4. Has never appeared in live captures.
      -confidence: VERY LOW
    seq:
      - id: soc_history
        type: u1
        repeat: eos
        doc: SOC percentage for each hour, most recent first.

  # ---------------------------------------------------------------------------
  # Unknown PGN — catch-all
  # ---------------------------------------------------------------------------
  pgn_unknown:
    doc: |
      Catch-all for unrecognised PGN keys not listed in the dispatch table.
      Reads all remaining bytes of the payload substream as raw data.
      Known PGNs not yet implemented: F1:05, F1:06, F1:08, F2:82, F2:84,
      and others in PROTOCOL.md §4.
    seq:
      - id: data
        size-eos: true
        doc: Raw payload bytes for unknown PGN.
