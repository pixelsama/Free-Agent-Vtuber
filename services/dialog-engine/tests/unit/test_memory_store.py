import sqlite3
from pathlib import Path

import pytest

from dialog_engine.memory_store import MemoryTurn, ShortTermMemoryStore


@pytest.mark.asyncio
async def test_fetch_recent_returns_empty_when_db_missing(tmp_path: Path):
    store = ShortTermMemoryStore(db_path=str(tmp_path / "missing.sqlite"), default_limit=5)

    result = await store.fetch_recent("session-1")

    assert result == []


@pytest.mark.asyncio
async def test_fetch_recent_returns_turns(tmp_path: Path):
    db_path = tmp_path / "memory.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            text TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO turns(session_id, role, text) VALUES (?, ?, ?)",
        [
            ("sess", "user", "你好"),
            ("sess", "assistant", "你好呀"),
            ("sess", "system", "system note"),
        ],
    )
    conn.commit()
    conn.close()

    store = ShortTermMemoryStore(db_path=str(db_path), default_limit=5)

    result = await store.fetch_recent("sess")

    assert [turn.role for turn in result] == ["user", "assistant", "system"]
    assert isinstance(result[0], MemoryTurn)


@pytest.mark.asyncio
async def test_append_turn_creates_db(tmp_path: Path):
    db_path = tmp_path / "memory.sqlite"
    store = ShortTermMemoryStore(db_path=str(db_path), default_limit=5)

    await store.append_turn(session_id="sess", role="user", content="hello")

    turns = await store.fetch_recent("sess")

    assert turns and turns[-1].content == "hello"
