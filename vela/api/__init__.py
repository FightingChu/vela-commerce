"""vela.api -- HTTP 层。

create_app() 是唯一入口;blueprint 按资源一文件,放 http/ 下。
DTO 一律走 schemas/,handler 里不许手写参数校验(历史教训见 #VT-1987)。
"""

from vela.api.app import create_app

__all__ = ["create_app"]
