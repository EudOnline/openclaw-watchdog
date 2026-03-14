from __future__ import annotations

import re


def service_active(engine) -> bool:
    result = engine.run_command(['systemctl', '--user', 'is-active', '--quiet', engine.config.openclaw_gateway_service], timeout=15)
    return result.returncode == 0


def service_main_pid(engine) -> str:
    result = engine.run_command(
        ['systemctl', '--user', 'show', '-p', 'MainPID', '--value', engine.config.openclaw_gateway_service],
        timeout=15,
    )
    value = (result.stdout or result.output).strip()
    return value if value.isdigit() else '0'


def listener_pids(engine) -> list[str]:
    result = engine.run_command(['ss', '-tlnp'], timeout=15)
    if result.returncode != 0 and not result.stdout and not result.stderr:
        return []
    pattern = re.compile(rf":{engine.config.openclaw_gateway_port}\b.*pid=(\d+)")
    pids = {match.group(1) for match in pattern.finditer(result.output)}
    return sorted(pids, key=int)


def listener_count(engine) -> int:
    return len(listener_pids(engine))


def listener_contains_pid(engine, needle: str) -> bool:
    return needle.isdigit() and needle != '0' and needle in listener_pids(engine)


def pid_descends_from(engine, pid: str, ancestor_pid: str) -> bool:
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


def listener_matches_service_tree(engine, main_pid: str) -> tuple[bool, str, str]:
    if not main_pid.isdigit() or main_pid == '0':
        return False, 'none', ''
    for listener_pid in listener_pids(engine):
        if listener_pid == main_pid:
            return True, 'direct', listener_pid
        if pid_descends_from(engine, listener_pid, main_pid):
            return True, 'child', listener_pid
    return False, 'none', ''
