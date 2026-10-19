# -*- coding: utf-8 -*-
"""短信模板注册与渲染。

模板和渠道侧必须同步登记,这边改了文案渠道那边不改,发出去就是旧文案,
所以 render 只管变量替换,文案本体以渠道后台为准(这里只是留档)。
"""

from __future__ import annotations

import re

from vela.config.errors import ValidationError

# 占位符形如 {code},和渠道侧约定一致,别换成 jinja
_PARAM_RE = re.compile(r"\{(\w+)\}")


class SmsTemplate:
    def __init__(self, code: str, text: str, *, desc: str = ""):
        if not code or not _PARAM_RE.sub("", text).strip():
            raise ValueError(f"模板定义不完整: {code!r}")
        self.code = code
        self.text = text
        self.desc = desc
        self.params = tuple(_PARAM_RE.findall(text))

    def render(self, **params) -> str:
        """渲染模板。缺参数/多参数都报错——多出来的多半是调用方写错了。"""
        missing = [p for p in self.params if p not in params]
        if missing:
            raise ValidationError(
                f"模板 {self.code} 缺少参数: {missing}",
                detail={"template": self.code, "expected": list(self.params)},
            )
        extra = set(params) - set(self.params)
        if extra:
            raise ValidationError(
                f"模板 {self.code} 收到未知参数: {sorted(extra)}",
                detail={"template": self.code, "expected": list(self.params)},
            )
        return _PARAM_RE.sub(lambda m: str(params[m.group(1)]), self.text)


class TemplateRegistry:
    """进程内模板注册表。加载时机在服务启动时一次性灌入,别运行时热改。"""

    def __init__(self):
        self._templates: dict[str, SmsTemplate] = {}

    def register(self, template: SmsTemplate) -> None:
        if template.code in self._templates:
            # 重复注册大概率是两处定义了同一个 code,宁可启动失败
            raise ConflictDuplicate(template.code)
        self._templates[template.code] = template

    def get(self, code: str) -> SmsTemplate:
        tpl = self._templates.get(code)
        if tpl is None:
            raise ValidationError(
                f"未注册的短信模板: {code!r}",
                detail={"registered": sorted(self._templates)},
            )
        return tpl

    def codes(self) -> list[str]:
        return sorted(self._templates)


class ConflictDuplicate(Exception):
    """注册冲突,单独一个小异常,启动失败时日志好认。"""

    def __init__(self, code: str):
        super().__init__(f"短信模板重复注册: {code}")


# 内置模板(code 与渠道侧同步维护,改这里先在 ops 群里吼一声)
BUILTIN_TEMPLATES = (
    SmsTemplate("verify_code", "您的验证码是 {code},{minutes} 分钟内有效", desc="登录/下单验证码"),
    SmsTemplate("ship_notice", "您的订单 {order_no} 已由 {carrier} 揽收,运单号 {waybill_no}", desc="发货通知"),
    SmsTemplate("refund_done", "您的订单 {order_no} 已退款 {amount} 元,请注意查收", desc="退款到账"),
)


def default_registry() -> TemplateRegistry:
    reg = TemplateRegistry()
    for tpl in BUILTIN_TEMPLATES:
        reg.register(tpl)
    return reg
