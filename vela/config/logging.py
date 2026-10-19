"""日志初始化。没有引入 structlog,是自制的 dict 化封装,够用。

用法:
    from vela.config.logging import get_logger
    log = get_logger(__name__)
    log.info("order_created", order_id=oid)
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message", "asctime", "taskName"
}

_CONFIGURED = False


class VelaLogger(logging.Logger):
    """支持 log.info("msg", key=value) 的结构化写法。

    标准库的 kwargs 只认 extra/exc_info 那几个,业务代码到处都是
    key=value 风格,统一在 _log 里收进 extra,格式化器才能拿到。
    """

    def _log(self, level, msg, args, exc_info=None, extra=None,
             stack_info=False, stacklevel=1, **kw):
        if kw:
            extra = dict(extra or {}, **kw)
        super()._log(level, msg, args, exc_info=exc_info, extra=extra,
                     stack_info=stack_info, stacklevel=stacklevel)


def setup_logging(level: str = "INFO", *, force: bool = False) -> None:
    global _CONFIGURED
    if _CONFIGURED and not force:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    _CONFIGURED = True


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for k, v in record.__dict__.items():
            if k not in _RESERVED and not k.startswith("_"):
                payload[k] = v
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def get_logger(name: str) -> logging.Logger:
    if not _CONFIGURED:
        setup_logging()
    logger = logging.getLogger(name)
    # 已存在的 logger(第三方库先建过)也换上,否则同名字段两种行为
    if not isinstance(logger, VelaLogger):
        logger.__class__ = VelaLogger
    return logger
