"""自定义列类型。金额列一律 Numeric(18, 4),展示层再舍入。"""

from __future__ import annotations

import datetime as dt
import json

from sqlalchemy import DateTime, Numeric, String, TypeDecorator

MONEY_COLUMN = Numeric(18, 4)


class JsonColumn(TypeDecorator):
    """sqlite/pg 双兼容的 JSON 列。老迁移里大量直接用 sa.JSON,
    新表用这个。"""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False, default=str)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value  # pg dialect 已经解过
        return json.loads(value)


class UTCDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if isinstance(value, dt.datetime) and value.tzinfo is not None:
            return value.astimezone(dt.timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=dt.timezone.utc)
        return value


class StrEnumColumn(TypeDecorator):
    """存的是 name,读回来还是原来的枚举。枚举值别改名,历史数据存的是字符串。"""

    impl = String
    cache_ok = True

    def __init__(self, enum_cls, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enum_cls = enum_cls

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return getattr(value, "name", str(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return self.enum_cls[value]
