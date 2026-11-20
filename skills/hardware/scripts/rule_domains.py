"""Resolve rule-domain aliases against the labels in the active catalogue."""

import re
import unicodedata


ALIASES = {
    "模拟与信号调理": ("模拟", "模拟电路", "信号调理", "analog", "signal conditioning"),
    "接口与时钟": ("接口", "时钟", "interface", "clock"),
    "PCB与EMC": ("PCB", "EMC", "PCB EMC", "布局", "电磁兼容"),
    "电源与磁件": ("电源", "磁件", "power", "magnetics"),
    "标准与制造": ("标准", "制造", "装配", "DFM", "manufacturing"),
    "验证与交付": ("验证", "交付", "verification", "release"),
    "采样与基准": ("采样", "基准", "ADC", "sampling", "reference"),
    "无源器件": ("无源", "阻容", "passives", "passive"),
    "热设计与可靠性": ("热", "热设计", "热与可靠性", "可靠性", "thermal", "reliability"),
}


class UnknownDomain(ValueError):
    def __init__(self, unknown, available):
        self.available_domains = sorted(available)
        super().__init__(
            f"未知规则领域：{'、'.join(unknown)}。可用领域：{'、'.join(self.available_domains)}"
        )


def domain_key(value):
    return re.sub(r"[\s_./·-]+", "", unicodedata.normalize("NFKC", value).casefold())


def resolve_domains(values, rules):
    if not values:
        return set()
    available = {rule["domain"] for rule in rules}
    keys = {domain_key(label): label for label in sorted(available)}
    for label in sorted(available):
        for alias in ALIASES.get(label, ()):
            keys.setdefault(domain_key(alias), label)
    requested = [(value, keys.get(domain_key(value))) for value in values]
    unknown = list(dict.fromkeys(value for value, label in requested if label is None))
    if unknown:
        raise UnknownDomain(unknown, available)
    return {label for _, label in requested}
