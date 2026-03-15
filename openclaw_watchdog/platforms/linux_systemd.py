from __future__ import annotations

import re
import time
from dataclasses import dataclass

from openclaw_watchdog.platforms.capabilities import PlatformCapabilities


@dataclass(frozen=True)
class LinuxSystemdPlatform:
    capabilities: PlatformCapabilities = PlatformCapabilities(
        host_family='linux',
        supervisor='systemd_user',
        listener_tool='ss',
        supports_managed_restart=True,
        supports_listener_pid_tree=True,
    )

    def describe_service(self, engine) -> dict[str, str]:
        result = engine.run_command(
            [
                'systemctl',
                '--user',
                'show',
                '-p',
                'LoadState,UnitFileState,FragmentPath,ActiveState,SubState',
                engine.config.openclaw_gateway_service,
            ],
            timeout=15,
        )
        values: dict[str, str] = {}
        for line in result.output.splitlines():
            if '=' not in line:
                continue
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip()
        return values

    def service_active(self, engine) -> bool:
        result = engine.run_command(
            ['systemctl', '--user', 'is-active', '--quiet', engine.config.openclaw_gateway_service],
            timeout=15,
        )
        return result.returncode == 0

    def service_main_pid(self, engine) -> str:
        result = engine.run_command(
            ['systemctl', '--user', 'show', '-p', 'MainPID', '--value', engine.config.openclaw_gateway_service],
            timeout=15,
        )
        value = (result.stdout or result.output).strip()
        return value if value.isdigit() else '0'

    def listener_pids(self, engine) -> list[str]:
        result = engine.run_command(['ss', '-tlnp'], timeout=15)
        if result.returncode != 0 and not result.stdout and not result.stderr:
            return []
        pattern = re.compile(rf":{engine.config.openclaw_gateway_port}\b.*pid=(\d+)")
        pids = {match.group(1) for match in pattern.finditer(result.output)}
        return sorted(pids, key=int)

    def listener_contains_pid(self, engine, needle: str) -> bool:
        return needle.isdigit() and needle != '0' and needle in self.listener_pids(engine)

    def pid_descends_from(self, engine, pid: str, ancestor_pid: str) -> bool:
        if not pid.isdigit() or not ancestor_pid.isdigit() or pid == '0' or ancestor_pid == '0':
            return False
        current = pid
        seen: set[str] = set()
        while current.isdigit() and current != '0' and current not in seen:
            if current == ancestor_pid:
                return True
            seen.add(current)
            result = engine.run_command(['ps', '-o', 'ppid=', '-p', current], timeout=15)
            parent = (result.stdout or result.output).strip()
            parent = re.sub(r'\s+', '', parent)
            if not parent.isdigit() or parent == '0':
                return False
            current = parent
        return False

    def listener_matches_service_tree(self, engine, main_pid: str) -> tuple[bool, str, str]:
        if not main_pid.isdigit() or main_pid == '0':
            return False, 'none', ''
        for listener_pid in self.listener_pids(engine):
            if listener_pid == main_pid:
                return True, 'direct', listener_pid
            if self.pid_descends_from(engine, listener_pid, main_pid):
                return True, 'child', listener_pid
        return False, 'none', ''

    def restart_service(self, engine) -> bool:
        engine.log('INFO', f'restarting {engine.config.openclaw_gateway_service}')
        engine.run_command(['systemctl', '--user', 'reset-failed', engine.config.openclaw_gateway_service], timeout=15)
        result = engine.run_command(['systemctl', '--user', 'restart', engine.config.openclaw_gateway_service], timeout=30)
        if result.returncode == 0:
            time.sleep(engine.config.watchdog_restart_wait_seconds)
            return True
        engine.log('WARN', f'failed to restart {engine.config.openclaw_gateway_service}: {result.output.strip()}')
        return False

    def install_watchdog_schedule(self, engine) -> None:
        return None
