import asyncio
import json
import os
import sqlite3
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

import redis.asyncio as redis


DB_PATH = os.getenv("DIALOG_ENGINE_DB", "/app/data/dialog_engine.db")
OUTBOX_FLUSH_INTERVAL_MS = int(os.getenv("OUTBOX_FLUSH_INTERVAL_MS", "500"))
EVENT_STREAM_MAXLEN = int(os.getenv("EVENT_STREAM_MAXLEN", "100000"))


def _ensure_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS outbox_events(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              type TEXT,
              payload TEXT,
              created_at INTEGER,
              delivered INTEGER DEFAULT 0
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def add_event(event_type: str, payload: Dict[str, Any]) -> None:
    _ensure_db()
    now = int(time.time())
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO outbox_events(type, payload, created_at, delivered) VALUES(?,?,?,0)",
            (event_type, json.dumps(payload, ensure_ascii=False), now),
        )
        conn.commit()
    finally:
        conn.close()


def _fetch_batch(limit: int = 100) -> List[Tuple[int, str, str]]:
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, type, payload FROM outbox_events WHERE delivered=0 ORDER BY id ASC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        return rows  # [(id, type, payload_json)]
    finally:
        conn.close()


def _mark_delivered(ids: Iterable[int]) -> None:
    ids = list(ids)
    if not ids:
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        qmarks = ",".join(["?"] * len(ids))
        cur.execute(f"UPDATE outbox_events SET delivered=1 WHERE id IN ({qmarks})", ids)
        conn.commit()
    finally:
        conn.close()


def _stream_for_type(event_type: str) -> str:
    et = (event_type or "").lower()
    if et.startswith("ltm"):
        return "events.ltm"
    if et.startswith("analytics"):
        return "events.analytics"
    # default bucket
    return "events.analytics"


async def _flush_once(r: redis.Redis) -> int:
    rows = _fetch_batch(200)
    if not rows:
        return 0
    delivered_ids: List[int] = []
    for row_id, event_type, payload_json in rows:
        try:
            stream = _stream_for_type(event_type)
            fields = {"type": event_type, "payload": payload_json}
            await r.xadd(stream, fields, maxlen=EVENT_STREAM_MAXLEN, approximate=True)
            delivered_ids.append(row_id)
        except Exception:
            # Stop on first failure; retry next round
            break
    if delivered_ids:
        _mark_delivered(delivered_ids)
    return len(delivered_ids)


async def start_flush_task(r: redis.Redis, *, enabled: bool = True) -> asyncio.Task:
    """Start a background task to flush outbox to Redis Streams when enabled."""
    _ensure_db()

    async def _runner():
        if not enabled:
            return
        interval = max(50, OUTBOX_FLUSH_INTERVAL_MS) / 1000.0
        while True:
            try:
                await _flush_once(r)
            except Exception:
                # swallow and retry
                pass
            await asyncio.sleep(interval)

    return asyncio.create_task(_runner())

