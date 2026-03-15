from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformCapabilities:
    host_family: str
    supervisor: str
    listener_tool: str
    supports_managed_restart: bool
    supports_listener_pid_tree: bool
