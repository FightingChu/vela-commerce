"""job 报警出口。

现状:只往日志里打 alert 标记,告警平台按 level=ERROR + alert=true
抓取。飞书 webhook 版写过一版,凌晨重试风暴把群炸了又下掉了,
限流没做好之前别接回去(#VT-2262)。
"""

from __future__ import annotations

from vela.config.logging import get_logger

log = get_logger(__name__)


def error(job: str, message: str, *, trace: str | None = None, **extra) -> None:
    # severity 不叫 level、正文不叫 message:前者撞 _log 位置参数,
    # 后者是 LogRecord 保留字,踩过的坑别再踩
    log.error("job_alert", alert=True, severity="error", job=job,
              detail=message, trace=trace, **extra)


def warn(job: str, message: str, *, trace: str | None = None, **extra) -> None:
    """数值异常但不影响主流程的(死信堆积、对账差异)走这。"""
    log.warning("job_alert", alert=True, severity="warn", job=job,
                detail=message, trace=trace, **extra)
