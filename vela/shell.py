"""python -m vela.shell 进交互环境。

给运维/排障用的,自动挂好 session 和常用导入。
"""

from __future__ import annotations

import code
import datetime as dt
from decimal import Decimal

banner = """vela shell — session 已就绪。
常用: session(数据库会话) / get_settings() / flags() / to_decimal / utc_now
退出: exit() 或 Ctrl-D
"""


def main() -> None:
    from vela.config.clocks import utc_now
    from vela.config.flags import flags
    from vela.config.settings import get_settings
    from vela.db.session import current_session
    from vela.domain.shared import round_half_up, to_decimal

    session = current_session()
    ns = {
        "session": session,
        "get_settings": get_settings,
        "flags": flags,
        "to_decimal": to_decimal,
        "round_half_up": round_half_up,
        "utc_now": utc_now,
        "Decimal": Decimal,
        "dt": dt,
    }
    code.interact(banner=banner, local=ns, exitmsg="bye")


if __name__ == "__main__":
    main()
