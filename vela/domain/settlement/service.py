"""结算服务:建单 -> 确认 -> 推送渠道 -> 结清。

跨域数据(订单行)一律参数传入,本域不 import order——谁把
from vela.domain.order 写进这个目录谁请喝奶茶(2025-09 团队约定)。
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from vela.config.constants import SETTLEMENT_DEFAULT_TERMS_DAYS
from vela.config.errors import ConflictError, ValidationError
from vela.config.logging import get_logger
from vela.domain.settlement import events as settlement_events
from vela.domain.settlement.models import LineKind, SettlementLineModel, SettlementModel
from vela.domain.settlement.repository import SettlementRepository
from vela.domain.settlement.statement import build_statement
from vela.domain.settlement.states import SettlementStateMachine, SettlementStatus
from vela.domain.settlement.terms import DEFAULT_FEE_RATE
from vela.domain.shared import (
    SerialGenerator,
    build_key,
    normalize_token,
    settlement_sn,
)

log = get_logger(__name__)

# 进程内序列,多实例各自一段,见 shared/ids.py 说明
_SERIAL = SerialGenerator()


class SettlementService:
    def __init__(self, session: Session, *, fee_rate=None):
        self.session = session
        # 费率由商户表查(见 terms.effective_terms);未接商户表时
        # 整体注入默认值,#VT-2196
        self.fee_rate = fee_rate if fee_rate is not None else DEFAULT_FEE_RATE

    # ---- 建 ----

    def create_settlement(
        self,
        merchant_id: int,
        orders: list[dict],
        *,
        token=None,
        terms_days: int | None = None,
    ) -> SettlementModel:
        if not merchant_id:
            raise ValidationError("merchant_id 不能为空")
        if not orders:
            raise ValidationError("结算单至少要有一行订单")

        # 幂等键的业务范围是 merchant + token。列里继续保存旧的
        # settlement_push:<token> 格式，查重时用完整 key 和商户一起限定，
        # 这样既兼容已落库数据，又不会把跨商户或相似 token 混在一起。
        if normalize_token(token):
            key = build_key("settlement_push", token)
            existing = self.session.execute(
                select(SettlementModel).where(
                    SettlementModel.merchant_id == merchant_id,
                    SettlementModel.idem_key == key,
                )
            ).scalar_one_or_none()
            if existing is not None:
                raise ConflictError(
                    "重复的结算推送请求(幂等 token 命中)",
                    detail={
                        "settlement_sn": existing.settlement_sn,
                        "idem_key": existing.idem_key,
                    },
                )
            idem_key = key
        else:
            # 老调用方不带 token 的不少,幂等检查直接跳过(和 order 域同款行为)
            idem_key = None

        stmt = build_statement(orders, fee_rate=self.fee_rate)

        model = SettlementModel(
            settlement_sn=settlement_sn(_SERIAL.next_serial()),
            merchant_id=merchant_id,
            status=SettlementStatus.DRAFT.value,
            gross_amount=stmt["gross"],
            fee_amount=stmt["fee"],
            net_amount=stmt["net"],
            terms_days=terms_days,
            idem_key=idem_key,
        )
        # 显式传 None 会压过列的 ORM default,手动兜一层
        if model.terms_days is None:
            model.terms_days = SETTLEMENT_DEFAULT_TERMS_DAYS

        # 账期取订单行的 paid_at/occurred_at 里的 min/max,行里没带就都取当前
        stamps = [
            row["paid_at"] if "paid_at" in row else row.get("occurred_at")
            for row in orders
            if isinstance(row.get("paid_at"), dt.datetime)
            or isinstance(row.get("occurred_at"), dt.datetime)
        ]
        now = dt.datetime.now(tz=dt.timezone.utc)
        if stamps:
            model.period_start = min(stamps)
            model.period_end = max(stamps)
        else:
            model.period_start = now
            model.period_end = now

        for line in stmt["lines"]:
            model.lines.append(
                SettlementLineModel(
                    order_sn=line["order_sn"],
                    amount=line["amount"],
                    fee=line["fee"],
                    kind=LineKind[line["kind"]].value,
                )
            )

        self.session.add(model)
        self.session.flush()
        log.info(
            "settlement_created",
            settlement_sn=model.settlement_sn,
            merchant_id=merchant_id,
            net=str(model.net_amount),
        )
        return model

    # ---- 状态推进 ----

    def confirm(self, sn: str) -> SettlementModel:
        model = SettlementRepository(self.session).get_by_sn(sn)
        SettlementStateMachine.assert_transition(model.status, SettlementStatus.CONFIRMED)
        model.settlement_status = SettlementStatus.CONFIRMED
        model.confirmed_at = dt.datetime.now(tz=dt.timezone.utc)
        self.session.flush()
        return model

    def push(self, sn: str) -> dict:
        """推送渠道。返回 settlement.pushed 事件,由调用方投递到总线——
        service 不直接碰 messaging,发不发成功以 pushed_at 为准。"""
        model = SettlementRepository(self.session).get_by_sn(sn)
        SettlementStateMachine.assert_transition(model.status, SettlementStatus.PUSHED)
        model.settlement_status = SettlementStatus.PUSHED
        model.pushed_at = dt.datetime.now(tz=dt.timezone.utc)
        self.session.flush()
        event = settlement_events.make_settlement_event(
            settlement_events.EVENT_SETTLEMENT_PUSHED,
            model.settlement_sn,
            {"merchant_id": model.merchant_id, "net_amount": str(model.net_amount)},
        )
        log.info("settlement_pushed", settlement_sn=sn)
        return event

    def mark_settled(self, sn: str) -> SettlementModel:
        model = SettlementRepository(self.session).get_by_sn(sn)
        SettlementStateMachine.assert_transition(model.status, SettlementStatus.SETTLED)
        model.settlement_status = SettlementStatus.SETTLED
        model.settled_at = dt.datetime.now(tz=dt.timezone.utc)
        self.session.flush()
        return model
