from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from openclaw_watchdog.platforms.capabilities import PlatformCapabilities


class SupervisorAdapter(Protocol):
    def describe_service(self, engine) -> dict[str, str]: ...

    def service_active(self, engine) -> bool: ...

    def service_main_pid(self, engine) -> str: ...

    def restart_service(self, engine) -> bool: ...

    def install_watchdog_schedule(self, engine) -> None: ...


class ListenerAdapter(Protocol):
    def listener_pids(self, engine) -> list[str]: ...

    def listener_contains_pid(self, engine, needle: str) -> bool: ...

    def listener_matches_service_tree(self, engine, main_pid: str) -> tuple[bool, str, str]: ...


@dataclass(frozen=True)
class NoopSupervisorAdapter:
    def describe_service(self, engine) -> dict[str, str]:
        return {}

    def service_active(self, engine) -> bool:
        return False

    def service_main_pid(self, engine) -> str:
        return '0'

    def restart_service(self, engine) -> bool:
        return False

    def install_watchdog_schedule(self, engine) -> None:
        return None


@dataclass(frozen=True)
class NoopListenerAdapter:
    def listener_pids(self, engine) -> list[str]:
        return []

    def listener_contains_pid(self, engine, needle: str) -> bool:
        return False

    def listener_matches_service_tree(self, engine, main_pid: str) -> tuple[bool, str, str]:
        return False, 'none', ''


@dataclass(frozen=True)
class ResolvedPlatform:
    capabilities: PlatformCapabilities
    supervisor: SupervisorAdapter
    listeners: ListenerAdapter
