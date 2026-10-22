"""下单/结算页的券试算:最优单张 vs 组合,两条路径并排给前端展示。"""

from __future__ import annotations

from vela.domain.promotion.stacking import (
    best_single,
    combine_stack,
    stack_allowed,
)


def checkout_preview(coupons: list[dict], amount) -> dict:
    """{"best": 单张最优优惠, "stacked": 组合优惠}。

    不可叠时 stacked 退回 best(前端展示"已选最优"),
    flag 关时 combine_stack 内部也会退化成 best,两层兜底是有意的。
    """
    best = best_single(coupons, amount)
    stacked = combine_stack(coupons, amount) if stack_allowed(coupons) else best
    return {"best": best, "stacked": stacked}
