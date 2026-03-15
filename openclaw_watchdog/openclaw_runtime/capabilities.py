from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass


@dataclass(frozen=True)
class DoctorCapabilities:
    supports_repair: bool = False
    supports_non_interactive: bool = False
    supports_yes: bool = False
    supports_non_interactive_yes: bool = False

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)
