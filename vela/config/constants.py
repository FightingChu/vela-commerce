"""散落的公共常量。域内常量放各域自己的 constants.py,别往这堆。"""

from __future__ import annotations

# 金额统一 2 位小数;JPY 等特殊币种在 pricing/currency.py 单独处理
MONEY_SCALE = 2

# 页大小上限在 settings 里也有,这里的是 schema 层硬校验值
MAX_PAGE_SIZE_HARD = 500

# 导出文件单行上限,超过截断并打标
EXPORT_CELL_MAX_CHARS = 4_096

# 内部 trace 头,网关到服务之间透传
TRACE_HEADER = "X-Vela-Trace-Id"
TENANT_HEADER = "X-Vela-Tenant"

# 结算账期默认天数
SETTLEMENT_DEFAULT_TERMS_DAYS = 30

# 预占默认 TTL(秒),与 settings.reservation_ttl_seconds 对齐
RESERVATION_DEFAULT_TTL = 900

ORDER_SN_PREFIX = "VL"
REFUND_SN_PREFIX = "VLR"
SETTLEMENT_SN_PREFIX = "VLS"
