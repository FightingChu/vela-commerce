"""backoffice 子包。后台/运营向的批量与审核操作。

和 service 根的区别:这里是"人坐在后台点按钮"的路径,统一要求
显式租户(tenant_guard)、显式操作人,落审计。api 侧的高频读写
别从这走。
"""

from vela.service.backoffice.coupon_grant import grant_to_customers
from vela.service.backoffice.csv_sink import DEFAULT_BATCH_ROWS, CsvSink
from vela.service.backoffice.export_customers import export_customers
from vela.service.backoffice.export_orders import export_orders
from vela.service.backoffice.order_adjust import adjust_line_price
from vela.service.backoffice.refund_review import approve, list_pending, reject
from vela.service.backoffice.task_lock import LockHeldError, TaskLock, hold

__all__ = [
    "DEFAULT_BATCH_ROWS",
    "CsvSink",
    "LockHeldError",
    "TaskLock",
    "adjust_line_price",
    "approve",
    "export_customers",
    "export_orders",
    "grant_to_customers",
    "hold",
    "list_pending",
    "reject",
]
