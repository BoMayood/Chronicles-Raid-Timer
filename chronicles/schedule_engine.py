"""Schedule calculation engine for Chronicles Raid Timer."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from chronicles.models import RaidDefinition, RaidStatus, RaidWindow


def _parse_hhmm(value: str) -> tuple[int, int]:
    """Parse an 'HH:MM' UTC string into (hour, minute), clamped safely."""
    parts = value.strip().split(":")
    try:
        hour = int(parts[0]) % 24
        minute = int(parts[1]) % 60 if len(parts) > 1 else 0
        return hour, minute
    except (ValueError, IndexError):
        return 0, 0


def generate_raid_windows(
    raid: RaidDefinition,
    ref_ts: Optional[float] = None,
    past_days: int = 2,
    future_days: int = 8,
) -> list[RaidWindow]:
    """Generate sorted concrete windows around ``ref_ts`` for any schedule kind."""
    if ref_ts is None:
        ref_ts = time.time()

    windows: list[RaidWindow] = []
    norm_sec = max(60, raid.normal_duration_min * 60)
    hard_sec = max(0, raid.hard_duration_min * 60)

    if raid.schedule_kind == "interval_manual":
        if raid.manual_target_ts is not None:
            start_ts = float(raid.manual_target_ts)
            end_ts = start_ts + norm_sec
            windows.append(
                RaidWindow(
                    raid_id=raid.id,
                    raid_name=raid.name,
                    phase_label=raid.normal_label,
                    is_hard=False,
                    start_ts=start_ts,
                    end_ts=end_ts,
                    accent_color=raid.accent_color,
                    icon_key=raid.icon_key,
                )
            )
            if hard_sec > 0:
                windows.append(
                    RaidWindow(
                        raid_id=raid.id,
                        raid_name=raid.name,
                        phase_label=raid.hard_label,
                        is_hard=True,
                        start_ts=end_ts,
                        end_ts=end_ts + hard_sec,
                        accent_color=raid.accent_color,
                        icon_key=raid.icon_key,
                    )
                )
        return windows

    dt_ref = datetime.fromtimestamp(ref_ts, tz=timezone.utc)
    allowed_weekdays = set(raid.weekdays) if raid.schedule_kind == "weekly_utc" else None

    for day_offset in range(-past_days, future_days + 1):
        day_dt = (dt_ref + timedelta(days=day_offset)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        if allowed_weekdays is not None and day_dt.weekday() not in allowed_weekdays:
            continue

        for hhmm in raid.utc_times:
            hour, minute = _parse_hhmm(hhmm)
            start_dt = day_dt.replace(hour=hour, minute=minute)
            start_ts = start_dt.timestamp()
            end_ts = start_ts + norm_sec
            windows.append(
                RaidWindow(
                    raid_id=raid.id,
                    raid_name=raid.name,
                    phase_label=raid.normal_label,
                    is_hard=False,
                    start_ts=start_ts,
                    end_ts=end_ts,
                    accent_color=raid.accent_color,
                    icon_key=raid.icon_key,
                )
            )
            if hard_sec > 0:
                windows.append(
                    RaidWindow(
                        raid_id=raid.id,
                        raid_name=raid.name,
                        phase_label=raid.hard_label,
                        is_hard=True,
                        start_ts=end_ts,
                        end_ts=end_ts + hard_sec,
                        accent_color=raid.accent_color,
                        icon_key=raid.icon_key,
                    )
                )

    windows.sort(key=lambda w: w.start_ts)
    return windows


def compute_raid_status(
    raid: RaidDefinition,
    now_ts: Optional[float] = None,
    imminent_minutes: int = 5,
    snoozed_until_ts: float = 0.0,
) -> RaidStatus:
    """Compute full live status, countdown, and progress ratio for a raid."""
    if now_ts is None:
        now_ts = time.time()

    if raid.schedule_kind == "interval_manual" and raid.manual_target_ts is None:
        return RaidStatus(
            raid=raid,
            is_active=False,
            is_configured=False,
            phase_label="Standby",
            is_hard=False,
            seconds_left=0,
            total_duration=max(60, raid.interval_minutes * 60),
            progress=0.0,
            active_window=None,
            next_window=None,
            following_window=None,
            is_imminent=False,
            is_snoozed=False,
        )

    windows = generate_raid_windows(raid, now_ts)
    active_window: Optional[RaidWindow] = None
    past_windows: list[RaidWindow] = []
    upcoming_windows: list[RaidWindow] = []

    for w in windows:
        if w.start_ts <= now_ts < w.end_ts:
            active_window = w
        elif w.end_ts <= now_ts:
            past_windows.append(w)
        else:
            upcoming_windows.append(w)

    if active_window is not None:
        total_dur = active_window.duration_sec
        seconds_left = max(0, int(active_window.end_ts - now_ts))
        progress = max(0.0, min(1.0, (active_window.end_ts - now_ts) / total_dur))
        next_win = upcoming_windows[0] if upcoming_windows else None
        following_win = upcoming_windows[1] if len(upcoming_windows) > 1 else None
        is_snoozed = snoozed_until_ts > now_ts and snoozed_until_ts >= active_window.start_ts
        return RaidStatus(
            raid=raid,
            is_active=True,
            is_configured=True,
            phase_label=active_window.phase_label,
            is_hard=active_window.is_hard,
            seconds_left=seconds_left,
            total_duration=total_dur,
            progress=progress,
            active_window=active_window,
            next_window=next_win,
            following_window=following_win,
            is_imminent=False,
            is_snoozed=is_snoozed,
        )

    next_win = upcoming_windows[0] if upcoming_windows else None
    following_win = upcoming_windows[1] if len(upcoming_windows) > 1 else None

    if next_win is None:
        return RaidStatus(
            raid=raid,
            is_active=False,
            is_configured=False,
            phase_label="Expired",
            is_hard=False,
            seconds_left=0,
            total_duration=max(60, raid.interval_minutes * 60),
            progress=0.0,
            active_window=None,
            next_window=None,
            following_window=None,
            is_imminent=False,
            is_snoozed=False,
        )

    seconds_left = max(0, int(next_win.start_ts - now_ts))
    if raid.schedule_kind == "interval_manual":
        total_cycle = max(60, raid.interval_minutes * 60)
        elapsed = max(0.0, total_cycle - (next_win.start_ts - now_ts))
        progress = max(0.0, min(1.0, elapsed / total_cycle))
    elif past_windows:
        prev_end = past_windows[-1].end_ts
        span = max(60.0, next_win.start_ts - prev_end)
        progress = max(0.0, min(1.0, (now_ts - prev_end) / span))
        total_cycle = int(span)
    else:
        total_cycle = 8 * 3600
        progress = max(0.0, min(1.0, 1.0 - ((next_win.start_ts - now_ts) / total_cycle)))

    imminent_sec = max(60, imminent_minutes * 60)
    is_imminent = seconds_left <= imminent_sec
    is_snoozed = snoozed_until_ts > now_ts

    return RaidStatus(
        raid=raid,
        is_active=False,
        is_configured=True,
        phase_label=next_win.phase_label,
        is_hard=next_win.is_hard,
        seconds_left=seconds_left,
        total_duration=int(total_cycle),
        progress=progress,
        active_window=None,
        next_window=next_win,
        following_window=following_win,
        is_imminent=is_imminent,
        is_snoozed=is_snoozed,
    )


def build_timeline_windows(
    raids: Iterable[RaidDefinition],
    start_ts: Optional[float] = None,
    hours: int = 24,
) -> list[RaidWindow]:
    """Return all raid windows overlapping [start_ts, start_ts + hours*3600]."""
    if start_ts is None:
        start_ts = time.time()
    end_ts = start_ts + hours * 3600
    result: list[RaidWindow] = []

    for raid in raids:
        if not raid.enabled:
            continue
        for w in generate_raid_windows(raid, start_ts, past_days=1, future_days=3):
            if w.end_ts >= start_ts and w.start_ts <= end_ts:
                result.append(w)

    result.sort(key=lambda w: (w.start_ts, w.raid_name))
    return result


def format_countdown(seconds: int) -> str:
    """Format seconds as HH:MM:SS or Dd HH:MM when >= 24h."""
    seconds = max(0, int(seconds))
    days = seconds // 86400
    rem = seconds % 86400
    h = rem // 3600
    m = (rem % 3600) // 60
    s = rem % 60
    if days > 0:
        return f"{days}d {h:02d}:{m:02d}:{s:02d}"
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_local_time(ts: float, use_24h: bool = False) -> str:
    """Format a timestamp into local wall-clock time."""
    dt = datetime.fromtimestamp(ts)
    if use_24h:
        return dt.strftime("%H:%M")
    return dt.strftime("%I:%M %p").lstrip("0")


def format_utc_time(ts: float) -> str:
    """Format a timestamp into 24-hour UTC time."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%H:%M UTC")
