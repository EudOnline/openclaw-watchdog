#!/usr/bin/env python3
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
import sys

repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from rehearsal.lib.rehearsal_common import backup_dir, openclaw_config_path  # noqa: E402


def main() -> int:
    destination_dir = backup_dir()
    destination_dir.mkdir(parents=True, exist_ok=True)
    config_path = openclaw_config_path()
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    manifest = destination_dir / f"backup-manifest.{stamp}.txt"
    if config_path.exists():
        target = destination_dir / f"openclaw-config.{stamp}.json"
        shutil.copy2(config_path, target)
        manifest.write_text(f"source={config_path}\ncopy={target}\n", encoding="utf-8")
        print(f"backup saved to {target}")
        return 0
    manifest.write_text(f"source={config_path}\ncopy=none\n", encoding="utf-8")
    print(f"no config found at {config_path}; manifest saved to {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

