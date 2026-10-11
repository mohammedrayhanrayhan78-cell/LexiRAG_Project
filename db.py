# ============================================
# DB.PY - Centralized Database Connection & Dialect Engine
# ============================================
# Supports:
# 1. PostgreSQL (via psycopg 3 + psycopg_pool) for cloud/production (e.g. Neon, Render)
# 2. SQLite (via sqlite3) for local development and offline testing
# Single place for all database connections across LexiRAG.
# ============================================

import os
import sqlite3
import threading
from typing import Optional, Any, List, Tuple

_POOL: Optional[Any] = None
_POOL_LOCK = threading.Lock()
_POOL_URL: Optional[str] = None


def get_database_url() -> Optional[str]:
    """Retrieve configured PostgreSQL URL from environment if set."""
    url = (os.getenv("DATABASE_URL") or os.getenv("TEST_DATABASE_URL") or "").strip()
    return url if url else None


def get_dialect() -> str:
    """Return 'postgres' if DATABASE_URL is set and starts with postgres, else 'sqlite'."""
    url = get_database_url()
    if url and (url.startswith("postgres://") or url.startswith("postgresql://")):
        return "postgres"
    return "sqlite"


def get_sqlite_path() -> str:
    """Path to SQLite database file when running in SQLite mode."""
    return os.getenv("DATABASE_PATH", "lexirag.db")


# Backward compatibility alias
DB_PATH = get_sqlite_path()


def translate_query_placeholders(query: str) -> str:
    """
    Translates SQLite '?' parameter placeholders to PostgreSQL '%s' placeholders,
    preserving literal '?' characters inside single- or double-quoted strings.
    """
    in_single = False
    in_double = False
    out = []
    for ch in query:
        if ch == "'" and not in_double:
            in_single = not in_single
            out.append(ch)
        elif ch == '"' and not in_single:
            in_double = not in_double
            out.append(ch)
        elif ch == '?' and not in_single and not in_double:
            out.append('%s')
        else:
            out.append(ch)
    return ''.join(out)


def _get_pg_pool(url: str):
    """Retrieve or initialize the thread-safe psycopg ConnectionPool."""
    global _POOL, _POOL_URL
    with _POOL_LOCK:
        if _POOL is None or _POOL_URL != url:
            if _POOL is not None:
                try:
                    _POOL.close()
                except Exception:
                    pass
            from psycopg_pool import ConnectionPool
            _POOL = ConnectionPool(
                conninfo=url,
                min_size=1,
                max_size=5,
                kwargs={
                    "sslmode": "require",
                    "prepare_threshold": None,  # Required for Neon pooled endpoints (PgBouncer)
                },
                check=ConnectionPool.check_connection,
                open=True,
            )
            _POOL_URL = url
        return _POOL


def close_pool():
    """Explicitly close the connection pool (used during testing or shutdown)."""
    global _POOL, _POOL_URL
    with _POOL_LOCK:
        if _POOL is not None:
            try:
                _POOL.close()
            except Exception:
                pass
            _POOL = None
            _POOL_URL = None


class PostgresCursorWrapper:
    """
    Cursor wrapper for PostgreSQL connections:
    - Automatically maps '?' placeholders to '%s'
    - Supports cursor.lastrowid on INSERT queries via RETURNING id
    - Maintains standard fetchone, fetchall, rowcount semantics
    """
    def __init__(self, raw_cursor):
        self._cur = raw_cursor
        self._lastrowid = None

    def execute(self, query: str, params=None):
        sql = translate_query_placeholders(query)
        sql_stripped = sql.strip()
        is_insert = sql_stripped.upper().startswith("INSERT INTO")
        has_returning = "RETURNING" in sql_stripped.upper()

        if is_insert and not has_returning:
            # Append RETURNING id so cursor.lastrowid is populated seamlessly
            sql = f"{sql_stripped} RETURNING id"
            if params is not None:
                self._cur.execute(sql, params)
            else:
                self._cur.execute(sql)
            try:
                row = self._cur.fetchone()
                if row:
                    self._lastrowid = row[0]
            except Exception:
                self._lastrowid = None
            return self

        if params is not None:
            self._cur.execute(sql, params)
        else:
            self._cur.execute(sql)
        return self

    def executemany(self, query: str, params_seq):
        sql = translate_query_placeholders(query)
        self._cur.executemany(sql, params_seq)
        return self

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def fetchmany(self, size=None):
        return self._cur.fetchmany(size) if size is not None else self._cur.fetchmany()

    @property
    def lastrowid(self):
        return self._lastrowid

    @property
    def rowcount(self):
        return self._cur.rowcount

    def close(self):
        self._cur.close()

    def __iter__(self):
        return iter(self._cur)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class PostgresConnectionWrapper:
    """
    Connection wrapper for pooled PostgreSQL connections.
    Releasing/closing returns the connection back to the pool.
    """
    def __init__(self, raw_conn, pool):
        self._conn = raw_conn
        self._pool = pool
        self._closed = False

    def cursor(self):
        return PostgresCursorWrapper(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        if not self._closed:
            self._closed = True
            try:
                self._pool.putconn(self._conn)
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        self.close()


class SQLiteConnectionWrapper:
    """
    Connection wrapper for SQLite connections ensuring consistent interface.
    """
    def __init__(self, raw_conn: sqlite3.Connection):
        self._conn = raw_conn

    def cursor(self):
        return self._conn.cursor()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        self.close()


def get_connection():
    """
    The SINGLE entrypoint for acquiring database connections in LexiRAG.
    Returns a connection wrapper matching the active dialect (PostgreSQL or SQLite).
    """
    dialect = get_dialect()
    if dialect == "postgres":
        url = get_database_url()
        pool = _get_pg_pool(url)
        raw_conn = pool.getconn()
        schema = os.getenv("TEST_POSTGRES_SCHEMA")
        if schema:
            with raw_conn.cursor() as cur:
                cur.execute(f"SET search_path TO {schema}, public")
        return PostgresConnectionWrapper(raw_conn, pool)
    else:
        path = get_sqlite_path()
        raw_conn = sqlite3.connect(path)
        return SQLiteConnectionWrapper(raw_conn)


def init_schema():
    """
    Idempotent schema creation for both PostgreSQL and SQLite.
    Creates tables: users, chat_sessions, chat_messages, chunks.
    Creates indexes: on username, chat_id, doc_name.
    """
    dialect = get_dialect()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if dialect == "postgres":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    blocked BOOLEAN DEFAULT FALSE
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    username TEXT NOT NULL,
                    chat_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(username) REFERENCES users(username)
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    role TEXT,
                    content TEXT,
                    FOREIGN KEY(chat_id) REFERENCES chat_sessions(id)
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    doc_name TEXT,
                    chunk_text TEXT,
                    embedding TEXT,
                    chat_id INTEGER DEFAULT NULL
                );
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    blocked INTEGER DEFAULT 0
                );
            """)
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN blocked INTEGER DEFAULT 0")
            except Exception:
                pass

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    chat_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(username) REFERENCES users(username)
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    role TEXT,
                    content TEXT,
                    FOREIGN KEY(chat_id) REFERENCES chat_sessions(id)
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_name TEXT,
                    chunk_text TEXT,
                    embedding TEXT,
                    chat_id INTEGER DEFAULT NULL
                );
            """)
            try:
                cursor.execute("ALTER TABLE chunks ADD COLUMN chat_id INTEGER DEFAULT NULL")
            except Exception:
                pass

        # Performance indexes for both dialects
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_sessions_username ON chat_sessions(username);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_chat_id ON chat_messages(chat_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_chat_id ON chunks(chat_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_name ON chunks(doc_name);")

        conn.commit()
    finally:
        conn.close()
