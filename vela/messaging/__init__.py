"""messaging:进程内事件总线 + outbox worker。

同步 job 用 worker.SyncWorker,常驻 asyncio 服务用 async_worker。
跨进程投递统一走 outbox 落库 + 外部投递器消费。
"""

from vela.messaging.bus import EventBus, get_bus, publish, subscribe

__all__ = ["EventBus", "get_bus", "publish", "subscribe"]
