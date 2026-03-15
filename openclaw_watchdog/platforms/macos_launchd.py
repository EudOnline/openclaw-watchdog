from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass

from openclaw_watchdog.platforms.capabilities import PlatformCapabilities


@dataclass(frozen=True)
class MacosLaunchdPlatform:
    uid: int = os.getuid()
    capabilities: PlatformCapabilities = PlatformCapabilities(
        host_family='darwin',
        supervisor='launchd',
        listener_tool='lsof',
        supports_managed_restart=True,
        supports_listener_pid_tree=True,
    )

    def launchd_target(self, engine) -> str:
        return f'gui/{self.uid}/{engine.config.openclaw_gateway_service}'

    def describe_service(self, engine) -> dict[str, str]:
        result = engine.run_command(
            ['launchctl', 'print', self.launchd_target(engine)],
            timeout=15,
        )
        info: dict[str, str] = {}
        state_match = re.search(r'^\s*state\s*=\s*(\S+)', result.output, re.MULTILINE)
        pid_match = re.search(r'^\s*pid\s*=\s*(\d+)', result.output, re.MULTILINE)
        if state_match:
            info['state'] = state_match.group(1).strip()
        if pid_match:
            info['pid'] = pid_match.group(1).strip()
        return info

    def service_active(self, engine) -> bool:
        info = self.describe_service(engine)
        return info.get('state') == 'running'

    def service_main_pid(self, engine) -> str:
        pid = self.describe_service(engine).get('pid', '')
        return pid if pid.isdigit() else '0'

    def listener_pids(self, engine) -> list[str]:
        result = engine.run_command(
            ['lsof', '-nP', f'-iTCP:{engine.config.openclaw_gateway_port}', '-sTCP:LISTEN'],
            timeout=15,
        )
        if result.returncode != 0 and not result.stdout and not result.stderr:
            return []
        pattern = re.compile(r'^\S+\s+(\d+)\s', re.MULTILINE)
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
        result = engine.run_command(
            ['launchctl', 'kickstart', '-k', self.launchd_target(engine)],
            timeout=30,
        )
        if result.returncode == 0:
            time.sleep(engine.config.watchdog_restart_wait_seconds)
            return True
        engine.log('WARN', f'failed to restart {engine.config.openclaw_gateway_service}: {result.output.strip()}')
        return False

    def install_watchdog_schedule(self, engine) -> None:
        return None
