"""Demo-safety replay buffer (Phase 6.3): a rolling record of the last
`window_s` seconds of broadcasts (world-state snapshots + allocation feed
lines), so the frontend can switch to `/replay` and keep showing something
real if the live WebSocket connection drops on stage.
"""
from __future__ import annotations

import time
from collections import deque


class ReplayBuffer:
    def __init__(self, window_s: float = 60.0, max_items: int = 500):
        self.window_s = window_s
        self._items: deque[dict] = deque(maxlen=max_items)

    def append(self, kind: str, data: dict) -> None:
        self._items.append({"type": kind, "data": data, "t": time.time()})

    def recent(self) -> list[dict]:
        cutoff = time.time() - self.window_s
        return [it for it in self._items if it["t"] >= cutoff]
