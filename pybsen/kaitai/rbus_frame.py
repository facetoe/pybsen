# This is a generated file! Please edit source .ksy file and use kaitai-struct-compiler to rebuild
# type: ignore

import kaitaistruct
from kaitaistruct import KaitaiStruct, KaitaiStream, BytesIO


if getattr(kaitaistruct, 'API_VERSION', (0, 9)) < (0, 11):
    raise Exception("Incompatible Kaitai Struct Python API: 0.11 or later is required, but you have %s" % (kaitaistruct.__version__))

class RbusFrame(KaitaiStruct):
    """Single reassembled RBUS CAN frame as received on CHAR_2015_8001
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
    """
    def __init__(self, _io, _parent=None, _root=None):
        super(RbusFrame, self).__init__(_io)
        self._parent = _parent
        self._root = _root or self
        self._read()

    def _read(self):
        self.flags = self._io.read_u1()
        self.pdu_fmt = self._io.read_u1()
        self.pdu_spec = self._io.read_u1()
        self.src_addr = self._io.read_u1()
        self.len_byte = self._io.read_u1()
        _on = self.pgn_key
        if _on == 61696:
            pass
            self._raw_payload = self._io.read_bytes(self.data_len)
            _io__raw_payload = KaitaiStream(BytesIO(self._raw_payload))
            self.payload = RbusFrame.PgnF100(_io__raw_payload, self, self._root)
        elif _on == 61698:
            pass
            self._raw_payload = self._io.read_bytes(self.data_len)
            _io__raw_payload = KaitaiStream(BytesIO(self._raw_payload))
            self.payload = RbusFrame.PgnF102(_io__raw_payload, self, self._root)
        elif _on == 61700:
            pass
            self._raw_payload = self._io.read_bytes(self.data_len)
            _io__raw_payload = KaitaiStream(BytesIO(self._raw_payload))
            self.payload = RbusFrame.PgnF104(_io__raw_payload, self, self._root)
        elif _on == 61706:
            pass
            self._raw_payload = self._io.read_bytes(self.data_len)
            _io__raw_payload = KaitaiStream(BytesIO(self._raw_payload))
            self.payload = RbusFrame.PgnF10a(_io__raw_payload, self, self._root)
        elif _on == 62080:
            pass
            self._raw_payload = self._io.read_bytes(self.data_len)
            _io__raw_payload = KaitaiStream(BytesIO(self._raw_payload))
            self.payload = RbusFrame.PgnF280(_io__raw_payload, self, self._root)
        elif _on == 62212:
            pass
            self._raw_payload = self._io.read_bytes(self.data_len)
            _io__raw_payload = KaitaiStream(BytesIO(self._raw_payload))
            self.payload = RbusFrame.PgnF304(_io__raw_payload, self, self._root)
        elif _on == 62468:
            pass
            self._raw_payload = self._io.read_bytes(self.data_len)
            _io__raw_payload = KaitaiStream(BytesIO(self._raw_payload))
            self.payload = RbusFrame.PgnF404(_io__raw_payload, self, self._root)
        elif _on == 64720:
            pass
            self._raw_payload = self._io.read_bytes(self.data_len)
            _io__raw_payload = KaitaiStream(BytesIO(self._raw_payload))
            self.payload = RbusFrame.PgnFcD0(_io__raw_payload, self, self._root)
        else:
            pass
            self._raw_payload = self._io.read_bytes(self.data_len)
            _io__raw_payload = KaitaiStream(BytesIO(self._raw_payload))
            self.payload = RbusFrame.PgnUnknown(_io__raw_payload, self, self._root)


    def _fetch_instances(self):
        pass
        _on = self.pgn_key
        if _on == 61696:
            pass
            self.payload._fetch_instances()
        elif _on == 61698:
            pass
            self.payload._fetch_instances()
        elif _on == 61700:
            pass
            self.payload._fetch_instances()
        elif _on == 61706:
            pass
            self.payload._fetch_instances()
        elif _on == 62080:
            pass
            self.payload._fetch_instances()
        elif _on == 62212:
            pass
            self.payload._fetch_instances()
        elif _on == 62468:
            pass
            self.payload._fetch_instances()
        elif _on == 64720:
            pass
            self.payload._fetch_instances()
        else:
            pass
            self.payload._fetch_instances()

    class PgnF100(KaitaiStruct):
        """RBusPGNBatteryProperties — static battery configuration.
        Update rate: ~5000 ms. charge_state byte [2] is always 1 across all
        charging and discharging sessions; meaning UNKNOWN.
        Source: PROTOCOL.md §3 (F1:00 entry), fixtures.py NOTIFY_A_CHARGESTATE.
        """
        def __init__(self, _io, _parent=None, _root=None):
            super(RbusFrame.PgnF100, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.unknown_0 = self._io.read_u2le()
            self.charge_state = self._io.read_u1()


        def _fetch_instances(self):
            pass


    class PgnF102(KaitaiStruct):
        """RBusPGNBatterySensorMeasurements — secondary voltage and temperature source.
        Update rate: ~2000 ms (0.5 Hz). Provides 1 mV voltage precision vs
        F2:80's 100 mV resolution. discover.py uses the most recent update from
        either F2:80 or F1:02 for the voltage CSV column.
        Source: PROTOCOL.md §5.
        8 bytes: [counter:2][unknown:2][raw_voltage_mv:2][raw_temp:1][padding:1]
        """
        def __init__(self, _io, _parent=None, _root=None):
            super(RbusFrame.PgnF102, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.counter = self._io.read_u2le()
            self.unknown_bytes = self._io.read_u2le()
            self.raw_voltage_mv = self._io.read_u2le()
            self.raw_temp = self._io.read_u1()


        def _fetch_instances(self):
            pass

        @property
        def temp_c(self):
            """Temperature in °C. Same formula as F2:80: raw − 60.
            Returns 0 when sentinel 0xFA.
            """
            if hasattr(self, '_m_temp_c'):
                return self._m_temp_c

            self._m_temp_c = (0 if self.raw_temp == 250 else self.raw_temp - 60)
            return getattr(self, '_m_temp_c', None)

        @property
        def voltage_v(self):
            """Battery voltage in volts from millivolt raw value.
            Formula: raw_voltage_mv / 1000.0. No separate sentinel — physically
            unreachable values (e.g. 0xFFFF = 65.535 V) can be checked by caller.
            Source: PROTOCOL.md §5.
            """
            if hasattr(self, '_m_voltage_v'):
                return self._m_voltage_v

            self._m_voltage_v = self.raw_voltage_mv / 1000.0
            return getattr(self, '_m_voltage_v', None)


    class PgnF104(KaitaiStruct):
        """RBusPGNBatteryChargeStatus — state of charge, health, and time remaining.
        Update rate: ~300 ms. Source: blutter ASM 0x52c214, PROTOCOL.md §5.
        NOTE: There is NO current field in this PGN. Earlier empirical decodes of
        bytes [2-3] as current were incorrect (falsified by session D). Those bytes
        are batteryTimeUntilFullflat (minutes). See PROTOCOL.md §7.
        """
        def __init__(self, _io, _parent=None, _root=None):
            super(RbusFrame.PgnF104, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.soc_pct = self._io.read_u1()
            self.state_of_health_pct = self._io.read_u1()
            self.raw_time = self._io.read_u2le()


        def _fetch_instances(self):
            pass

        @property
        def time_until_fullflat_min(self):
            """batteryTimeUntilFullflat decoded to minutes.
            Returns -1 when raw_time == 0xFFFA (not available). 0 means device is exactly
            at crossover. Positive = minutes to full charge. Negative (excluding -1) = minutes to flat.
            Formula: (raw − 32127) × 5 minutes.
            Calibration: A→+355min(5.9h), 3→−2500min(41.7h), D→−1090min(18.2h), E→−1410min(23.5h).
            Zero-point raw=32127 is the boundary between charging and discharging directions.
            Source: PROTOCOL.md §5, §6 TIME_REMAINING_SCALE_POINTS.
            """
            if hasattr(self, '_m_time_until_fullflat_min'):
                return self._m_time_until_fullflat_min

            self._m_time_until_fullflat_min = (-1 if self.raw_time == 65530 else (self.raw_time - 32127) * 5)
            return getattr(self, '_m_time_until_fullflat_min', None)


    class PgnF10a(KaitaiStruct):
        """RBusPGNLowBatteryAlarm — alarm thresholds and status flags.
        NOT temperature data. Earlier empirical decodes of this PGN as
        temperature were incorrect (see PROTOCOL.md §5 historical note).
        Temperature is only in F2:80 byte[6] and F1:02 byte[6].
        Source: blutter ASM 0x52b0a4, PROTOCOL.md §5.
        8 bytes: [alarm_flags:1][soc_setpoint:1][raw_voltage_setpoint:2][padding:4]
        """
        def __init__(self, _io, _parent=None, _root=None):
            super(RbusFrame.PgnF10a, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.alarm_flags = self._io.read_u1()
            self.soc_alarm_setpoint_pct = self._io.read_u1()
            self.raw_voltage_setpoint = self._io.read_u2le()


        def _fetch_instances(self):
            pass

        @property
        def soc_alarm_active(self):
            """True if lowBatterySocAlarmStatus bits [1:0] are non-zero (alarm activated).
            Source: blutter RBusActivated_Boolean enum, PROTOCOL.md §5.
            """
            if hasattr(self, '_m_soc_alarm_active'):
                return self._m_soc_alarm_active

            self._m_soc_alarm_active = self.alarm_flags & 3 != 0
            return getattr(self, '_m_soc_alarm_active', None)

        @property
        def voltage_alarm_active(self):
            """True if lowBatteryVoltageAlarmStatus bits [3:2] are non-zero (alarm activated).
            Source: blutter ASM, PROTOCOL.md §5.
            """
            if hasattr(self, '_m_voltage_alarm_active'):
                return self._m_voltage_alarm_active

            self._m_voltage_alarm_active = self.alarm_flags >> 2 & 3 != 0
            return getattr(self, '_m_voltage_alarm_active', None)

        @property
        def voltage_alarm_setpoint_v(self):
            """Voltage alarm threshold in volts. Returns 0.0 when sentinel (raw=0xFFFA).
            Formula: raw × 0.001 V.
            Source: PROTOCOL.md §5.
            """
            if hasattr(self, '_m_voltage_alarm_setpoint_v'):
                return self._m_voltage_alarm_setpoint_v

            self._m_voltage_alarm_setpoint_v = (0.0 if self.raw_voltage_setpoint == 65530 else self.raw_voltage_setpoint * 0.001)
            return getattr(self, '_m_voltage_alarm_setpoint_v', None)


    class PgnF280(KaitaiStruct):
        """RBusPGNBatterySensorMeasurementsAveraged — PRIMARY measurement PGN.
        This is the frame the REDARC app home screen reads for battery current,
        voltage, and temperature. Update rate: ~1000 ms.
        Source: blutter ASM 0x526e90, PROTOCOL.md §5.
        8 bytes: [raw_current:2][raw_voltage:2][raw_load_current:2][raw_temp:1][padding:1]
        """
        def __init__(self, _io, _parent=None, _root=None):
            super(RbusFrame.PgnF280, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.raw_current = self._io.read_u2le()
            self.raw_voltage = self._io.read_u2le()
            self.raw_load_current = self._io.read_u2le()
            self.raw_temp = self._io.read_u1()


        def _fetch_instances(self):
            pass

        @property
        def net_current_a(self):
            """Net shunt current in amperes. Positive = charging, negative = discharging.
            Formula: (raw − 10000) × 0.1 A. Returns 0.0 when sentinel (raw=20000).
            CONFIRMED: A→+0.5A, B→−7.6A, C→−16.3A, D→−14.4A, E→−10.8A.
            Source: PROTOCOL.md §6 NET_CURRENT_SCALE_POINTS.
            """
            if hasattr(self, '_m_net_current_a'):
                return self._m_net_current_a

            self._m_net_current_a = (0.0 if self.raw_current == 20000 else (self.raw_current - 10000) * 0.1)
            return getattr(self, '_m_net_current_a', None)

        @property
        def temp_c(self):
            """Battery temperature in degrees Celsius. Returns 0 when sentinel (raw=0xFA).
            Formula: raw − 60 °C.
            Source: PROTOCOL.md §5, §6.
            """
            if hasattr(self, '_m_temp_c'):
                return self._m_temp_c

            self._m_temp_c = (0 if self.raw_temp == 250 else self.raw_temp - 60)
            return getattr(self, '_m_temp_c', None)

        @property
        def voltage_v(self):
            """Averaged battery voltage in volts. Returns 0.0 when sentinel (raw=643).
            Formula: raw × 0.1 V. Resolution 0.1 V; see pgn_f1_02 for 1 mV precision.
            Source: PROTOCOL.md §5.
            """
            if hasattr(self, '_m_voltage_v'):
                return self._m_voltage_v

            self._m_voltage_v = (0.0 if self.raw_voltage == 643 else self.raw_voltage * 0.1)
            return getattr(self, '_m_voltage_v', None)


    class PgnF304(KaitaiStruct):
        """RBusPGNRealTimeClock — device real-time clock.
        Set by the app; echoed back by the device.
        Source: PROTOCOL.md §4, blutter class name.
        Layout: [unknown_0:1][month:1][year:2][hour:1][minute:1][second:1][padding:1]
        """
        def __init__(self, _io, _parent=None, _root=None):
            super(RbusFrame.PgnF304, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.unknown_0 = self._io.read_u1()
            self.month = self._io.read_u1()
            self.year = self._io.read_u2le()
            self.hour = self._io.read_u1()
            self.minute = self._io.read_u1()
            self.second = self._io.read_u1()


        def _fetch_instances(self):
            pass


    class PgnF404(KaitaiStruct):
        """RBusPGNNodeSerialInformation — static device identity information.
        Payload is opaque; constant across all sessions.
        Observed payload: 5F 6D 5B 8F 14 00 18 00 (hex).
        Source: PROTOCOL.md §3, fixtures.py NOTIFY_A_DEVICEINFO.
        """
        def __init__(self, _io, _parent=None, _root=None):
            super(RbusFrame.PgnF404, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.data = self._io.read_bytes_full()


        def _fetch_instances(self):
            pass


    class PgnFcD0(KaitaiStruct):
        """RBusPGNSOCLogHourly (0xFCD0). 7 bytes, each byte = SOC% for one hour of history,
        most recent first. Example: [0x00, 0x5F, 0x63, 0x63, 0x63, 0x63, 0x63] =
        [current hour: 0%, -1h: 95%, -2h to -6h: 99%].
        Source: PROTOCOL.md §4. Has never appeared in live captures.
        -confidence: VERY LOW
        """
        def __init__(self, _io, _parent=None, _root=None):
            super(RbusFrame.PgnFcD0, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.soc_history = []
            i = 0
            while not self._io.is_eof():
                self.soc_history.append(self._io.read_u1())
                i += 1



        def _fetch_instances(self):
            pass
            for i in range(len(self.soc_history)):
                pass



    class PgnUnknown(KaitaiStruct):
        """Catch-all for unrecognised PGN keys not listed in the dispatch table.
        Reads all remaining bytes of the payload substream as raw data.
        Known PGNs not yet implemented: F1:05, F1:06, F1:08, F2:82, F2:84,
        and others in PROTOCOL.md §4.
        """
        def __init__(self, _io, _parent=None, _root=None):
            super(RbusFrame.PgnUnknown, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.data = self._io.read_bytes_full()


        def _fetch_instances(self):
            pass


    @property
    def data_len(self):
        """Actual payload byte count extracted from bits [3:0] of len_byte.
        Value 8 (from len_byte=0x88) observed in all standard frames.
        """
        if hasattr(self, '_m_data_len'):
            return self._m_data_len

        self._m_data_len = self.len_byte & 15
        return getattr(self, '_m_data_len', None)

    @property
    def pgn_key(self):
        """16-bit PGN identifier used for payload type dispatch.
        Encoding: (pdu_fmt << 8) | pdu_spec. Matches blutter RBusPGNList.off_14.
        Examples: 0xF280 (primary measurements), 0xF104 (charge status).
        """
        if hasattr(self, '_m_pgn_key'):
            return self._m_pgn_key

        self._m_pgn_key = self.pdu_fmt << 8 | self.pdu_spec
        return getattr(self, '_m_pgn_key', None)


