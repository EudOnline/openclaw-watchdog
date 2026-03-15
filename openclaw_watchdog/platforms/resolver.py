from __future__ import annotations

import shutil
import sys
from collections.abc import Iterable
from typing import Callable

from openclaw_watchdog.platforms.base import NoopListenerAdapter
from openclaw_watchdog.platforms.base import NoopSupervisorAdapter
from openclaw_watchdog.platforms.base import ResolvedPlatform
from openclaw_watchdog.platforms.capabilities import PlatformCapabilities
from openclaw_watchdog.platforms.linux_systemd import LinuxSystemdPlatform
from openclaw_watchdog.platforms.macos_launchd import MacosLaunchdPlatform

_PROBED_COMMANDS = ('systemctl', 'ss', 'ps', 'launchctl', 'lsof')


def detect_host_family(sys_platform: str = sys.platform) -> str:
    if sys_platform.startswith('linux'):
        return 'linux'
    if sys_platform == 'darwin':
        return 'darwin'
    if sys_platform.startswith('win'):
        return 'windows'
    return 'unknown'


def detect_available_commands(which: Callable[[str], str | None] = shutil.which) -> set[str]:
    return {name for name in _PROBED_COMMANDS if which(name)}


def resolve_platform(
    *,
    which: Callable[[str], str | None] = shutil.which,
    sys_platform: str = sys.platform,
) -> ResolvedPlatform:
    host_family = detect_host_family(sys_platform)
    available_commands = detect_available_commands(which)
    systemd_user_supported = host_family == 'linux' and {'systemctl', 'ss', 'ps'}.issubset(available_commands)
    return resolve_platform_adapter(
        host_family=host_family,
        available_commands=available_commands,
        systemd_user_supported=systemd_user_supported,
    )


def resolve_platform_adapter(
    *,
    host_family: str,
    available_commands: Iterable[str],
    systemd_user_supported: bool,
) -> ResolvedPlatform:
    commands = set(available_commands)

    if host_family == 'linux' and systemd_user_supported and {'systemctl', 'ss', 'ps'}.issubset(commands):
        linux_adapter = LinuxSystemdPlatform()
        return ResolvedPlatform(
            capabilities=linux_adapter.capabilities,
            supervisor=linux_adapter,
            listeners=linux_adapter,
        )
    elif host_family == 'darwin' and {'launchctl', 'lsof', 'ps'}.issubset(commands):
        macos_adapter = MacosLaunchdPlatform()
        return ResolvedPlatform(
            capabilities=macos_adapter.capabilities,
            supervisor=macos_adapter,
            listeners=macos_adapter,
        )
    else:
        capabilities = PlatformCapabilities(
            host_family=host_family or 'unknown',
            supervisor='manual',
            listener_tool='manual',
            supports_managed_restart=False,
            supports_listener_pid_tree=False,
        )

    return ResolvedPlatform(
        capabilities=capabilities,
        supervisor=NoopSupervisorAdapter(),
        listeners=NoopListenerAdapter(),
    )
