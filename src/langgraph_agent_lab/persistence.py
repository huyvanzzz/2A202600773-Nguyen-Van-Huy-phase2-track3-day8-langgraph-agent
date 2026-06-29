# ruff: noqa: I001
"""Checkpointer adapter."""

from __future__ import annotations

from typing import Any


def build_checkpointer(kind: str = "memory", database_url: str | None = None) -> Any | None:  # noqa: ANN401
    """Return a LangGraph checkpointer.
    """
    if kind == "none":
        return None
    if kind == "memory":
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()
    if kind == "sqlite":
        import sqlite3
        from langgraph.checkpoint.sqlite import SqliteSaver

        db_path = database_url or "checkpoints.sqlite"
        conn = sqlite3.connect(db_path, check_same_thread=False)
        # Enable WAL mode for high concurrency
        conn.execute("PRAGMA journal_mode=WAL;")
        return SqliteSaver(conn)
    if kind == "postgres":
        from langgraph.checkpoint.postgres import PostgresSaver  # type: ignore
        # PostgresSaver requires connection pooling (e.g. psycopg Pool)
        # It's an optional extension, let's support it if pool is passed as database_url
        if database_url:
            import psycopg  # type: ignore
            connection_string = database_url
            conn = psycopg.connect(connection_string)
            return PostgresSaver(conn)
        raise ValueError("PostgresSaver requires database_url configuration")
    raise ValueError(f"Unknown checkpointer kind: {kind}")
