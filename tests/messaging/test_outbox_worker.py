"""outbox + SyncWorker 全链路:分发 / 重试退避 / 死信 / 批大小。"""

from __future__ import annotations

from vela.config.clocks import FrozenClock
from vela.messaging import EventBus
from vela.messaging.dispatcher import flush_pending
from vela.messaging.outbox import OutboxRepository
from vela.messaging.queue_model import OutboxStatus
from vela.messaging.retry import MAX_ATTEMPTS, next_delay_seconds
from vela.messaging.worker import SyncWorker


class FailingBus:
    """模拟总线挂掉,publish 必炸。"""

    def publish(self, event):
        raise RuntimeError("bus down")


class TestRetryPolicy:
    def test_exponential_with_cap(self):
        assert next_delay_seconds(0) == 30
        assert next_delay_seconds(1) == 60
        assert next_delay_seconds(3) == 240
        assert next_delay_seconds(20) == 3600  # 封顶


class TestDispatchHappyPath:
    def test_enqueue_then_run_once(self, db_session):
        repo = OutboxRepository(db_session)
        bus = EventBus()
        got = []
        bus.subscribe("order.paid", got.append)

        worker = SyncWorker(repo, bus)
        row = repo.enqueue("order.paid", {"order_id": 99}, trace="t-1")

        assert worker.run_once() == 1
        db_session.flush()  # refresh 不 autoflush,先落库再断言
        assert row.status == OutboxStatus.DISPATCHED
        assert row.attempts == 0
        assert got[0]["payload"] == {"order_id": 99}
        assert got[0]["trace"] == "t-1"

    def test_no_due_events_returns_zero(self, db_session):
        repo = OutboxRepository(db_session)
        worker = SyncWorker(repo, EventBus())
        assert worker.run_once() == 0


class TestRetryBackoff:
    def test_failure_schedules_retry_in_future(self, db_session):
        clock = FrozenClock()
        repo = OutboxRepository(db_session)
        row = repo.enqueue("order.paid", {"k": 1})

        worker = SyncWorker(repo, FailingBus(), clock=clock)
        assert worker.run_once() == 1
        db_session.flush()  # refresh 不 autoflush,先落库再断言

        assert row.status == OutboxStatus.PENDING
        assert row.attempts == 1
        assert row.last_error == "bus down"
        # 重试时间排在未来(指数退避 + 抖动,抖动只会更晚)
        assert row.next_retry_at > clock.now()
        # 没到点不该被捞出来
        assert repo.fetch_due(clock.now()) == []

        # 推过封顶时长后到期,可以再跑
        clock.advance(4000)
        due = repo.fetch_due(clock.now())
        assert [r.id for r in due] == [row.id]

    def test_exceeds_max_attempts_goes_dead(self, db_session):
        clock = FrozenClock()
        repo = OutboxRepository(db_session)
        row = repo.enqueue("order.paid", {"k": 1})

        worker = SyncWorker(repo, FailingBus(), clock=clock)
        for _ in range(MAX_ATTEMPTS + 1):
            worker.run_once()
            clock.advance(4000)  # 直接推过 cap,保证下一轮 due

        db_session.flush()  # refresh 不 autoflush,先落库再断言
        assert row.attempts == MAX_ATTEMPTS + 1
        assert row.status == OutboxStatus.DEAD
        assert len(worker.dead_letter) == 1
        entry = worker.dead_letter.snapshot()[0]
        assert entry["event"]["type"] == "order.paid"
        assert "bus down" in entry["reason"]
        # 死了就不会再被捞
        assert repo.fetch_due(clock.now()) == []


class TestBatchSize:
    def test_batch_size_limits_rows_per_run(self, db_session):
        repo = OutboxRepository(db_session)
        for i in range(5):
            repo.enqueue("order.paid", {"i": i})

        worker = SyncWorker(repo, EventBus(), batch_size=2)
        assert worker.run_once() == 2
        pending = repo.fetch_due()
        assert len(pending) == 3
        assert worker.run_once() == 2
        assert worker.run_once() == 1
        assert worker.run_once() == 0

    def test_default_batch_size_is_50(self, db_session):
        worker = SyncWorker(OutboxRepository(db_session), EventBus())
        assert worker.batch_size == 50


class TestFlushPending:
    def test_flush_drains_all(self, db_session):
        repo = OutboxRepository(db_session)
        for i in range(4):
            repo.enqueue("order.paid", {"i": i})
        assert flush_pending(repo, EventBus()) == 4
        assert repo.fetch_due() == []

    def test_flush_respects_limit(self, db_session):
        repo = OutboxRepository(db_session)
        for i in range(3):
            repo.enqueue("order.paid", {"i": i})
        assert flush_pending(repo, EventBus(), limit=2) == 2
        assert len(repo.fetch_due()) == 1
