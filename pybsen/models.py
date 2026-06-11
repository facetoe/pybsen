"""Domain model types for pybsen.

BatteryState and AlarmState are immutable Pydantic BaseModel snapshots.
Use model_copy(update={...}) to produce updated states.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class ChargeDirection(str, Enum):
    """Whether the battery is net-charging or net-discharging.

    Derived from the sign of net_current_a (F2:80).  None until the first
    F2:80 frame is decoded.  str mixin ensures JSON-serialisable without
    custom encoders.
    """

    CHARGING = "charging"
    DISCHARGING = "discharging"


class BatteryState(BaseModel):
    """Aggregated battery measurement state from all subscribed PGNs."""

    model_config = ConfigDict(frozen=True)

    timestamp: datetime | None = None
    soc_pct: int | None = None
    state_of_health_pct: int | None = None
    time_to_full_min: int | None = None
    time_to_flat_min: int | None = None
    net_current_a: float | None = None
    charge_direction: ChargeDirection | None = None
    voltage_v: float | None = None
    temp_c: float | None = None
    charge_state: int | None = None


class AlarmState(BaseModel):
    """Low-battery alarm status and setpoints from F1:0A."""

    model_config = ConfigDict(frozen=True)

    soc_alarm_active: bool | None = None
    voltage_alarm_active: bool | None = None
    soc_alarm_setpoint_pct: int | None = None
    voltage_alarm_setpoint_v: float | None = None
