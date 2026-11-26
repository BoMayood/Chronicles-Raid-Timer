"""Typed domain models for Chronicles Raid Timer."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


VALID_SCHEDULE_KINDS = ("daily_utc", "weekly_utc", "interval_manual")
VALID_ICON_KEYS = ("rift", "nightmare", "dragon", "sword", "compass", "stopwatch")


@dataclass
class RaidDefinition:
    """Configuration for a built-in or user-created raid/world event timer."""

    id: str
    name: str
    subtitle: str = "World Event"
    icon_key: str = "sword"
    accent_color: str = "#38BDF8"
    enabled: bool = True
    builtin: bool = False
    schedule_kind: str = "daily_utc"
    utc_times: list[str] = field(default_factory=lambda: ["12:00"])
    weekdays: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])
    normal_duration_min: int = 30
    hard_duration_min: int = 0
    normal_label: str = "Normal"
    hard_label: str = "Hard"
    interval_minutes: int = 120
    manual_target_ts: Optional[float] = None
    order: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RaidDefinition":
        schedule_kind = data.get("schedule_kind", "daily_utc")
        if schedule_kind not in VALID_SCHEDULE_KINDS:
            schedule_kind = "daily_utc"

        icon_key = data.get("icon_key", "sword")
        if icon_key not in VALID_ICON_KEYS:
            icon_key = "sword"

        utc_times = [str(t).strip() for t in data.get("utc_times", ["12:00"]) if str(t).strip()]
        if not utc_times:
            utc_times = ["12:00"]

        weekdays = [
            int(d) for d in data.get("weekdays", [0, 1, 2, 3, 4, 5, 6])
            if isinstance(d, int) and 0 <= d <= 6
        ]
        if not weekdays:
            weekdays = [0, 1, 2, 3, 4, 5, 6]

        manual_ts = data.get("manual_target_ts")
        if manual_ts is not None:
            try:
                manual_ts = float(manual_ts)
            except (TypeError, ValueError):
                manual_ts = None

        return cls(
            id=str(data.get("id", "custom_raid")),
            name=str(data.get("name", "Custom Raid")).strip() or "Custom Raid",
            subtitle=str(data.get("subtitle", "World Event")).strip() or "World Event",
            icon_key=icon_key,
            accent_color=str(data.get("accent_color", "#38BDF8")),
            enabled=bool(data.get("enabled", True)),
            builtin=bool(data.get("builtin", False)),
            schedule_kind=schedule_kind,
            utc_times=utc_times,
            weekdays=weekdays,
            normal_duration_min=max(1, int(data.get("normal_duration_min", 30))),
            hard_duration_min=max(0, int(data.get("hard_duration_min", 0))),
            normal_label=str(data.get("normal_label", "Normal")).strip() or "Normal",
            hard_label=str(data.get("hard_label", "Hard")).strip() or "Hard",
            interval_minutes=max(1, int(data.get("interval_minutes", 120))),
            manual_target_ts=manual_ts,
            order=int(data.get("order", 0)),
        )


@dataclass(frozen=True)
class RaidWindow:
    """A concrete start/end occurrence of a raid phase."""

    raid_id: str
    raid_name: str
    phase_label: str
    is_hard: bool
    start_ts: float
    end_ts: float
    accent_color: str = "#38BDF8"
    icon_key: str = "sword"

    @property
    def duration_sec(self) -> int:
        return max(1, int(self.end_ts - self.start_ts))


@dataclass
class RaidStatus:
    """Computed live telemetry state for a single raid at a specific timestamp."""

    raid: RaidDefinition
    is_active: bool
    is_configured: bool
    phase_label: str
    is_hard: bool
    seconds_left: int
    total_duration: int
    progress: float
    active_window: Optional[RaidWindow]
    next_window: Optional[RaidWindow]
    following_window: Optional[RaidWindow]
    is_imminent: bool = False
    is_snoozed: bool = False


def default_builtin_raids() -> list[RaidDefinition]:
    """Return the canonical built-in Chronicles raids."""
    return [
        RaidDefinition(
            id="crimson_rift",
            name="Crimson Rift",
            subtitle="Normal 30m • Hard 30m",
            icon_key="rift",
            accent_color="#FF476F",
            enabled=True,
            builtin=True,
            schedule_kind="daily_utc",
            utc_times=["03:00", "11:00", "19:00"],
            normal_duration_min=30,
            hard_duration_min=30,
            normal_label="Normal",
            hard_label="Hard",
            order=0,
        ),
        RaidDefinition(
            id="brutal_nightmare",
            name="Brutal Nightmare",
            subtitle="Normal 1h • Hard 1h",
            icon_key="nightmare",
            accent_color="#A855F7",
            enabled=True,
            builtin=True,
            schedule_kind="daily_utc",
            utc_times=["04:00", "12:00", "20:00"],
            normal_duration_min=60,
            hard_duration_min=60,
            normal_label="Normal",
            hard_label="Hard",
            order=1,
        ),
    ]


def sample_preset_raids() -> list[RaidDefinition]:
    """Preset optional templates users can one-click add from the Command Center."""
    return [
        RaidDefinition(
            id="abyssal_kraken",
            name="Abyssal Clash",
            subtitle="Sea Boss • Weekly Event",
            icon_key="dragon",
            accent_color="#00D2FF",
            enabled=True,
            builtin=False,
            schedule_kind="weekly_utc",
            utc_times=["19:00"],
            weekdays=[1, 3, 5],  # Tue, Thu, Sat
            normal_duration_min=45,
            hard_duration_min=0,
            normal_label="Active",
            order=2,
        ),
        RaidDefinition(
            id="world_boss_respawn",
            name="World Boss Respawn",
            subtitle="Manual 4h Respawn Tracker",
            icon_key="stopwatch",
            accent_color="#F59E0B",
            enabled=True,
            builtin=False,
            schedule_kind="interval_manual",
            interval_minutes=240,
            normal_duration_min=15,
            hard_duration_min=0,
            normal_label="Spawned",
            order=3,
        ),
    ]
