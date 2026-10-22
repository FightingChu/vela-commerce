"""通用 HTTP 客户端。

设计取舍(2023-03 重构留下的):
- Transport 是协议不是基类,测试注入 Fake 很轻,不用继承。
- 重试只对 5xx 和网络异常,4xx 重试没有意义(参数错了,试一百次也错)。
- 退避带抖动,当年没加抖动,一批订单同时失败后同时重试,把网关打挂过一次,
  见 #VT-2871。
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from typing import Any, Protocol

from vela.config.errors import ExternalServiceError
from vela.config.logging import get_logger

log = get_logger(__name__)

# 单次重试间隔基数(秒)。total = base * 2^attempt,上限封在 2s,别调大,
# 同步链路上调用方等不起
_BACKOFF_BASE = 0.2
_BACKOFF_CAP = 2.0

_DEFAULT_UA = "vela-integrations/2.0 (python-urllib)"


class Transport(Protocol):
    """把"怎么发请求"抽出来。request 返回 (status, 响应体原始字节)。"""

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
    ) -> tuple[int, bytes]:
        ...


class UrllibTransport:
    """默认实现,标准库 urllib。没有连接池,没有 keep-alive,够用就行。"""

    def __init__(self, timeout: float = 3.0):
        self._timeout = timeout

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
    ) -> tuple[int, bytes]:
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            # HTTPError 也是合法响应,4xx/5xx 要把 status 和 body 带回去
            return e.code, e.read()


class BaseClient:
    """所有三方适配器的底座。

    用法:
        client = BaseClient("https://gw.internal/pay")
        data = client.request("POST", "/orders", json_body={...})

    非 2xx 统一抛 ExternalServiceError,detail 里带 status/body 片段,
    方便排障时从日志直接看出对端回了什么。
    """

    def __init__(
        self,
        base_url: str,
        transport: Transport | None = None,
        timeout: float = 3.0,
        max_retries: int = 2,
        # 2024-01 加的,老 client 不传就是 None,行为不变
        breaker: Any | None = None,
    ):
        if not base_url:
            raise ValueError("base_url 不能为空")
        self._base_url = base_url.rstrip("/")
        self._transport = transport or UrllibTransport(timeout)
        self._max_retries = max(0, max_retries)
        self._breaker = breaker

    # -- public ---------------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | list | None = None,
        headers: dict[str, str] | None = None,
        raw_body: bytes | None = None,
    ) -> Any:
        """发请求并解析 JSON。非 JSON 响应返回文本。

        4xx 直接抛(不重试);5xx/超时按指数退避重试 max_retries 次。
        """
        url = self._url_for(path)
        body = raw_body
        hdrs = {"User-Agent": _DEFAULT_UA}
        if json_body is not None:
            body = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            hdrs["Content-Type"] = "application/json"
        hdrs.update(headers or {})

        last_err: Exception | None = None
        for attempt in range(self._max_retries + 1):
            if self._breaker is not None:
                self._breaker.check()
            try:
                status, resp_body = self._transport.request(method, url, hdrs, body)
            except Exception as e:  # 超时、连接拒绝都算可重试
                last_err = e
                log.warning("http_transport_error", url=url, attempt=attempt, err=str(e))
                self._sleep_backoff(attempt)
                continue

            if 200 <= status < 300:
                if self._breaker is not None:
                    self._breaker.record_success()
                return _decode(resp_body)

            if status < 500:
                # 4xx:参数问题,重试无意义,立刻失败
                if self._breaker is not None:
                    self._breaker.record_result(False)
                raise _to_error(url, status, resp_body)

            last_err = _to_error(url, status, resp_body)
            log.warning(
                "http_retryable_status", url=url, status=status, attempt=attempt
            )
            if self._breaker is not None:
                self._breaker.record_result(False)
            self._sleep_backoff(attempt)

        raise last_err or ExternalServiceError("请求失败: " + url)

    # -- internal -------------------------------------------------------

    def _url_for(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path  # 偶尔要打到别的主机,允许绝对地址
        return self._base_url + "/" + path.lstrip("/")

    def _sleep_backoff(self, attempt: int) -> None:
        delay = min(_BACKOFF_BASE * (2 ** attempt), _BACKOFF_CAP)
        # +/- 20% 抖动
        delay *= random.uniform(0.8, 1.2)
        time.sleep(delay)


def _decode(resp_body: bytes) -> Any:
    if not resp_body:
        return None
    text = resp_body.decode("utf-8", "replace")
    try:
        return json.loads(text)
    except ValueError:
        return text


def _to_error(url: str, status: int, resp_body: bytes) -> ExternalServiceError:
    snippet = resp_body[:512].decode("utf-8", "replace") if resp_body else ""
    return ExternalServiceError(
        f"三方服务返回 {status}: {url}",
        detail={"status": status, "body": snippet},
    )
