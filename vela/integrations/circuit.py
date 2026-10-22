"""简易熔断器。

状态机: closed -> (连续失败达阈值) -> open -> (reset_timeout 后) -> half_open
half_open 放一个请求过去试,成功回 closed,失败回 open。

为什么自己写而不用现成库:2022 年评估过 pybreaker,就为了这一个功能
引依赖不值,而且我们要能在单测里注入时钟(见 clock 参数)。
"""

from __future__ import annotations

import time

from vela.config.errors import ExternalServiceError
from vela.config.logging import get_logger

log = get_logger(__name__)

_CLOSED = "closed"
_OPEN = "open"
_HALF_OPEN = "half_open"


class BreakerOpen(ExternalServiceError):
    """熔断打开期间的快速失败。调用方应当降级,而不是干等。"""

    code = "vela.0503"


class CircuitBreaker:
    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
        clock=time.monotonic,
    ):
        self.name = name
        self._threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._clock = clock
        self._state = _CLOSED
        self._failures = 0
        self._opened_at = 0.0

    # -- 状态查询 --------------------------------------------------------

    @property
    def state(self) -> str:
        if self._state == _OPEN and self._elapsed() >= self._reset_timeout:
            # 不在这里改状态,留给 check() 转 half_open,避免只读调用有副作用
            return _HALF_OPEN
        return self._state

    def is_open(self) -> bool:
        return self.state == _OPEN

    # -- 主流程挂钩 ------------------------------------------------------

    def check(self) -> None:
        """请求前调用。open 状态直接抛 BreakerOpen,不真正发起请求。"""
        if self._state == _CLOSED:
            return
        if self._state == _OPEN:
            if self._elapsed() >= self._reset_timeout:
                self._state = _HALF_OPEN
                log.info("breaker_half_open", breaker=self.name)
            else:
                raise BreakerOpen(
                    f"熔断打开中: {self.name},剩余 {self._reset_timeout - self._elapsed():.0f}s"
                )
            return
        # half_open:只放一个请求,其余的照样快速失败
        raise BreakerOpen(f"熔断试探中: {self.name}")

    def record_success(self) -> None:
        if self._state != _CLOSED:
            log.info("breaker_recovered", breaker=self.name)
        self._state = _CLOSED
        self._failures = 0

    def record_result(self, ok: bool) -> None:
        if ok:
            self.record_success()
            return
        self._failures += 1
        if self._state == _HALF_OPEN:
            self._trip()
            return
        if self._failures >= self._threshold:
            self._trip()

    # 兼容别名,早期接入的支付网关用的是这一对
    record_failure = record_result

    # -- internal --------------------------------------------------------

    def _trip(self) -> None:
        self._state = _OPEN
        self._opened_at = self._clock()
        log.warning("breaker_open", breaker=self.name, failures=self._failures)

    def _elapsed(self) -> float:
        return self._clock() - self._opened_at
