# ============================================
# DATABASE.PY - Database Operations for LexiRAG (SECURED)
# ============================================
# This file handles ALL database operations for LexiRAG
# Including: users, chats, messages, and document chunks
# Routed exclusively through db.py for PostgreSQL / SQLite portability.
# ============================================

import os
import json
import numpy as np
from passlib.context import CryptContext

from db import get_connection, init_schema, get_sqlite_path, DB_PATH

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


# ============================================
# 1. INITIALIZATION
# ============================================

def init_db():
    """Initialize chunks table (and full schema idempotently)."""
    init_schema()


def init_users_table():
    """Initialize users table (and full schema idempotently)."""
    init_schema()


def create_chat_session(username):
    """Initialize chat tables (and full schema idempotently)."""
    init_schema()


# ============================================
# 2. CHUNKS & DOCUMENTS
# ============================================

def save_chunk(doc_name, chunk_text, embedding):
    """Save a SINGLE chunk to database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chunks (doc_name, chunk_text, embedding) VALUES (?, ?, ?)",
        (doc_name, chunk_text, json.dumps(embedding.tolist()))
    )
    conn.commit()
    conn.close()


def get_all_chunks():
    """Retrieve ALL chunks from database across all chats."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, doc_name, chunk_text, embedding FROM chunks")
    rows = cursor.fetchall()
    conn.close()

    result = []
    for row in rows:
        result.append({
            "id": row[0],
            "doc_name": row[1],
            "chunk_text": row[2],
            "embedding": np.array(json.loads(row[3]))
        })
    return result


def delete_document(doc_name):
    """Delete ALL chunks of a document."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chunks WHERE doc_name = ?", (doc_name,))
    conn.commit()
    conn.close()


def get_documents():
    """Get list of all unique document names across chunks."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT doc_name FROM chunks")
    docs = [row[0] for row in cursor.fetchall()]
    conn.close()
    return docs


def save_chunks_batch(doc_name, chunks, embeddings, chat_id=None):
    """Save MULTIPLE chunks at once using executemany."""
    conn = get_connection()
    cursor = conn.cursor()

    data = [
        (doc_name, chunk, json.dumps(emb.tolist() if hasattr(emb, "tolist") else emb), chat_id)
        for chunk, emb in zip(chunks, embeddings)
    ]

    cursor.executemany(
        "INSERT INTO chunks (doc_name, chunk_text, embedding, chat_id) VALUES (?, ?, ?, ?)",
        data
    )
    conn.commit()
    conn.close()


# ============================================
# 3. USERS & AUTHENTICATION
# ============================================

def create_user(username, password):
    """Register a new user with hashed password."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        hashed = pwd_context.hash(password)
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hashed)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        return False


def verify_user(username, password):
    """Check if username exists and password matches."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()

    if result:
        stored_hash = result[0]
        return pwd_context.verify(password, stored_hash)
    return False


def block_account(username):
    """Block account after multiple failed attempts."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET blocked = TRUE WHERE username = ?",
        (username,)
    )
    conn.commit()
    conn.close()


def is_blocked(username):
    """Check if account is blocked."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT blocked FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    return bool(result[0]) if result and result[0] is not None else False


# ============================================
# 4. CHAT SESSIONS & MESSAGES
# ============================================

def save_chat_message(chat_id, role, content):
    """Save a user or bot message to a chat."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_messages (chat_id, role, content) VALUES (?, ?, ?)",
        (chat_id, role, content)
    )
    conn.commit()
    conn.close()


def get_chat_messages(chat_id):
    """Get all messages from a specific chat in chronological order."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content FROM chat_messages WHERE chat_id = ? ORDER BY id",
        (chat_id,)
    )
    messages = cursor.fetchall()
    conn.close()
    return [{"role": msg[0], "content": msg[1]} for msg in messages]


def get_user_chats(username):
    """Get all chats for a user, newest first."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, chat_name, created_at FROM chat_sessions WHERE username = ? ORDER BY created_at DESC",
        (username,)
    )
    chats = cursor.fetchall()
    conn.close()
    return [{"id": chat[0], "name": chat[1], "created_at": str(chat[2])} for chat in chats]


def create_new_chat(username, chat_name):
    """Create a new chat session for a user and return its ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_sessions (username, chat_name) VALUES (?, ?)",
        (username, chat_name)
    )
    conn.commit()
    chat_id = cursor.lastrowid
    conn.close()
    return chat_id


def get_chat_owner(chat_id):
    """Get username who owns this chat_id, or None if not found."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM chat_sessions WHERE id = ?", (chat_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def delete_chat_and_chunks(chat_id):
    """Delete entire chat session, its messages, AND its chunks."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chunks WHERE chat_id = ?", (chat_id,))
    cursor.execute("DELETE FROM chat_messages WHERE chat_id = ?", (chat_id,))
    cursor.execute("DELETE FROM chat_sessions WHERE id = ?", (chat_id,))
    conn.commit()
    conn.close()


def delete_chat_document(chat_id, doc_name):
    """Delete all chunks of a specific document within a specific chat."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM chunks WHERE chat_id = ? AND doc_name = ?",
        (chat_id, doc_name)
    )
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted


def delete_user_document(username, doc_name):
    """Delete all chunks of doc_name across all chats owned by username."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM chunks WHERE doc_name = ? AND chat_id IN (SELECT id FROM chat_sessions WHERE username = ?)",
        (doc_name, username)
    )
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted


def get_chat_documents(chat_id):
    """Get all unique document names within a specific chat."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT doc_name FROM chunks WHERE chat_id = ?",
        (chat_id,)
    )
    docs = [row[0] for row in cursor.fetchall()]
    conn.close()
    return docs


def delete_user_account(username):
    """
    Delete a user and ALL their associated data:
    1. Chunks in all their chats
    2. Messages in all their chats
    3. All their chat sessions
    4. The user account itself
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM chunks WHERE chat_id IN (SELECT id FROM chat_sessions WHERE username = ?)",
        (username,)
    )
    cursor.execute(
        "DELETE FROM chat_messages WHERE chat_id IN (SELECT id FROM chat_sessions WHERE username = ?)",
        (username,)
    )
    cursor.execute(
        "DELETE FROM chat_sessions WHERE username = ?",
        (username,)
    )
    cursor.execute(
        "DELETE FROM users WHERE username = ?",
        (username,)
    )
    conn.commit()
    conn.close()
    return True