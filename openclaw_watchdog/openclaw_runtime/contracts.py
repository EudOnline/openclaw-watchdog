from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field


@dataclass(frozen=True)
class GatewayContract:
    url: str = ''
    reachable: bool = False
    misconfigured: bool = False
    configured_port: int = 0
    detected_port: int = 0


@dataclass(frozen=True)
class StatusContract:
    gateway: GatewayContract = field(default_factory=GatewayContract)
    conversation: dict[str, object] = field(default_factory=dict)
    raw: dict[str, object] = field(default_factory=dict)
