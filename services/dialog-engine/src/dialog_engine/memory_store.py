from __future__ import annotations

"""Short-term memory access helpers for dialog-engine."""

import asyncio
import os
import sqlite3
from dataclasses import dataclass
from typing import List, Optional

import logging

logger = logging.getLogger(__name__)


@dataclass
class MemoryTurn:
    role: str
    content: str


class ShortTermMemoryStore:
    """SQLite-backed store for recent dialog turns."""

    def __init__(self, *, db_path: str, default_limit: int = 20) -> None:
        self._db_path = db_path
        self._default_limit = default_limit

    async def fetch_recent(self, session_id: str, limit: Optional[int] = None) -> List[MemoryTurn]:
        if not self._db_path or not os.path.exists(self._db_path):
            return []
        query_limit = limit or self._default_limit
        if query_limit <= 0:
            return []

        def _query() -> List[MemoryTurn]:
            try:
                conn = sqlite3.connect(self._db_path)
                conn.row_factory = sqlite3.Row
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.debug("stm.connect.error", exc_info=True)
                raise RuntimeError("failed to open memory database") from exc

            try:
                rows = conn.execute(
                    """
                    SELECT role, text
                    FROM turns
                    WHERE session_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (session_id, query_limit),
                ).fetchall()
            except Exception as exc:
                logger.debug("stm.query.error", exc_info=True)
                raise RuntimeError("failed to query memory database") from exc
            finally:
                conn.close()

            turns: List[MemoryTurn] = []
            for row in reversed(rows):
                role = row["role"] if row["role"] in {"user", "assistant", "system"} else "assistant"
                content = row["text"] or ""
                turns.append(MemoryTurn(role=role, content=content))
            return turns

        try:
            return await asyncio.to_thread(_query)
        except FileNotFoundError:  # pragma: no cover - race condition
            return []
        except RuntimeError:
            return []


__all__ = ["ShortTermMemoryStore", "MemoryTurn"]
