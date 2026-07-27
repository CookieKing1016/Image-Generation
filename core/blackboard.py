"""Serializable per-turn agent trace used for debugging and later retries."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass
class Blackboard:
    events: List[Dict[str, Any]] = field(default_factory=list)

    def record(self, agent: str, event_type: str, payload: Dict[str, Any]) -> None:
        self.events.append(
            {
                "agent": agent,
                "event_type": event_type,
                "payload": payload,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    def to_list(self) -> List[Dict[str, Any]]:
        return list(self.events)
