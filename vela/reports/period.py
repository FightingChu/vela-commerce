"""报表周期解析。入参一律字符串(HTTP query 上来的东西别信),
统一解析成 UTC 的 [start, end) 区间,越界判断交给调用方。

时区:报表口径一律按 Asia/Shanghai 的自然日/自然周/自然月切,
区间端点换算成 UTC 落库查询。手动调过夏令时的问题——中国没有
夏令时,别画蛇添足。
"""

from __future__ import annotations

import datetime as dt
import re

from vela.config.errors import ValidationError

GRANULARITIES = ("day", "week", "month")

_TZ = dt.timezone(dt.timedelta(hours=8))  # Asia/Shanghai,固定的,见模块注释
_UTC = dt.timezone.utc

_WEEK_RE = re.compile(r"^(\d{4})-?W(\d{2})$", re.IGNORECASE)
_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")


def parse_granularity(text: str) -> str:
    g = (text or "").strip().lower()
    if g not in GRANULARITIES:
        raise ValidationError(
            f"未知粒度: {text!r},支持 {GRANULARITIES}"
        )
    return g


def resolve_period(text: str, granularity: str = "day") -> tuple[dt.datetime, dt.datetime]:
    """返回 UTC 的 [start, end)。解析不了抛 ValidationError。"""
    g = parse_granularity(granularity)
    raw = (text or "").strip()
    if not raw:
        raise ValidationError(f"周期不能为空 (granularity={g})")

    if g == "day":
        start = _parse_with(raw, "%Y-%m-%d", "日期", g)
        return _to_utc(start), _to_utc(start + dt.timedelta(days=1))

    if g == "week":
        m = _WEEK_RE.match(raw)
        if m:
            year, week = int(m.group(1)), int(m.group(2))
            try:
                start = dt.datetime.strptime(f"{year}-W{week:02d}-1", "%G-W%V-%u")
            except ValueError:
                raise ValidationError(f"无法解析周期: {raw!r} (granularity=week)") from None
            return _to_utc(start), _to_utc(start + dt.timedelta(days=7))
        # 也接受一个落在该周内的日期,取所在 ISO 周
        day = _parse_with(raw, "%Y-%m-%d", "日期", g)
        start = dt.datetime.combine(day - dt.timedelta(days=day.isoweekday() - 1), dt.time.min)
        return _to_utc(start), _to_utc(start + dt.timedelta(days=7))

    # month
    m = _MONTH_RE.match(raw)
    if not m or not (1 <= int(m.group(2)) <= 12):
        raise ValidationError(f"无法解析周期: {raw!r} (granularity=month)")
    year, month = int(m.group(1)), int(m.group(2))
    start = dt.datetime(year, month, 1)
    nxt = dt.datetime(year + 1, 1, 1) if month == 12 else dt.datetime(year, month + 1, 1)
    return _to_utc(start), _to_utc(nxt)


def _parse_with(raw: str, fmt: str, label: str, granularity: str) -> dt.datetime:
    try:
        return dt.datetime.strptime(raw, fmt)
    except ValueError:
        raise ValidationError(f"无法解析{label}: {raw!r} (granularity={granularity})") from None


def _to_utc(naive: dt.datetime) -> dt.datetime:
    return naive.replace(tzinfo=_TZ).astimezone(_UTC)
