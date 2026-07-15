# ============================================
# DATABASE.PY - SQLite Database Functions (SECURED)
# ============================================
# This file handles ALL database operations for LexiRAG
# Including: users, chats, messages, and document chunks
# WITH SECURITY: Password hashing with bcrypt
# ============================================

# ============================================
# 1. ALL IMPORTS AT TOP
# ============================================

import sqlite3  # Python's built-in database library
import numpy as np  # For working with vectors/embeddings
import json  # For converting Python objects to/from JSON text
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

DB_PATH = "lexirag.db"  # SQLite database file location

# ============================================
# 2. CHUNKS TABLE - Stores document pieces
# ============================================
# When you upload a PDF, it's split into chunks
# Each chunk has: id, document_name, text, vector_embedding

def init_db():
    """
    Initialize the chunks table (for document storage)
    
    WHY: When the app starts, we need the table to exist
    WHAT IT DOES:
    1. Connect to SQLite database (creates it if doesn't exist)
    2. Create 'chunks' table with 4 columns
    3. Close connection
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_name TEXT,
            chunk_text TEXT,
            embedding TEXT,
            chat_id INTEGER DEFAULT NULL
        )
    ''')
    conn.commit()
    conn.close()

def save_chunk(doc_name, chunk_text, embedding):
    """
    Save a SINGLE chunk to database
    
    PARAMETERS:
    - doc_name: filename (e.g., "resume.pdf")
    - chunk_text: the actual text
    - embedding: numpy array of numbers (converted to JSON string for storage)
    
    FLOW:
    1. Connect to database
    2. Insert row with 3 values
    3. Commit (save) changes
    4. Close connection
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chunks (doc_name, chunk_text, embedding) VALUES (?, ?, ?)",
        (doc_name, chunk_text, json.dumps(embedding.tolist()))
    )
    conn.commit()
    conn.close()

def get_all_chunks():
    """
    Retrieve ALL chunks from database
    
    RETURNS: List of dictionaries with id, doc_name, chunk_text, embedding
    
    WHY: Used for RAG - searching all documents for relevant chunks
    """
    conn = sqlite3.connect(DB_PATH)
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
    """
    Delete ALL chunks of a document
    
    EXAMPLE: User deletes "resume.pdf"
    -> All chunks from that document are removed
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chunks WHERE doc_name = ?", (doc_name,))
    conn.commit()
    conn.close()

def get_documents():
    """
    Get list of all unique document names
    
    RETURNS: ["resume.pdf", "cover_letter.pdf"]
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT doc_name FROM chunks")
    docs = [row[0] for row in cursor.fetchall()]
    conn.close()
    return docs

def save_chunks_batch(doc_name, chunks, embeddings):
    """
    Save MULTIPLE chunks at once (more efficient than save_chunk)
    
    PARAMETERS:
    - doc_name: filename
    - chunks: list of text pieces
    - embeddings: list of vectors (one per chunk)
    
    WHY: When uploading a 10-page PDF, it becomes 50 chunks
    Saving all 50 at once is faster than saving one at a time
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Pair up chunks with embeddings: [(chunk1, emb1), (chunk2, emb2), ...]
    data = [(doc_name, chunk, json.dumps(emb.tolist())) 
            for chunk, emb in zip(chunks, embeddings)]
    
    # executemany = insert multiple rows in one operation
    cursor.executemany(
        "INSERT INTO chunks (doc_name, chunk_text, embedding) VALUES (?, ?, ?)",
        data
    )
    conn.commit()
    conn.close()

# ============================================
# 3. USERS TABLE - Authentication (SECURED with bcrypt)
# ============================================

def init_users_table():
    """
    Create users table for storing usernames and HASHED passwords
    
    COLUMNS:
    - id: unique identifier
    - username: UNIQUE (no two users can have same username)
    - password: HASHED (never plaintext)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def create_user(username, password):
    """
    Register a new user with HASHED password using passlib
    
    passlib = library that handles password hashing
    Works on Windows WITHOUT needing Rust compiler
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Hash password using passlib
        hashed = pwd_context.hash(password)
        
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hashed)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Create user error: {e}")
        conn.close()
        return False

def verify_user(username, password):
    """
    Check if username and password are correct
    
    passlib.verify() compares plaintext with hash
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        stored_hash = result[0]
        return pwd_context.verify(password, stored_hash)
    return False

# ============================================
# 4. CHAT_SESSIONS TABLE - Chat rooms
# ============================================
# Each user can have multiple chats
# Each chat is a conversation with documents

def create_chat_session(username):
    """
    Create chat_sessions and chat_messages tables
    
    TABLES:
    1. chat_sessions: Stores chat rooms
       - Each chat has: id, username, chat_name, created_at
    
    2. chat_messages: Stores messages within chats
       - Each message has: id, chat_id, role (user/bot), content
    
    FOREIGN KEY: Links messages to specific chat
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            chat_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(username) REFERENCES users(username)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            role TEXT,
            content TEXT,
            FOREIGN KEY(chat_id) REFERENCES chat_sessions(id)
        )
    ''')
    conn.commit()
    conn.close()

def save_chat_message(chat_id, role, content):
    """
    Save a message to a chat
    
    EXAMPLE:
    - chat_id: 5
    - role: "user"
    - content: "What is RAG?"
    
    Saves this message to chat #5
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_messages (chat_id, role, content) VALUES (?, ?, ?)",
        (chat_id, role, content)
    )
    conn.commit()
    conn.close()

def get_chat_messages(chat_id):
    """
    Get all messages from a specific chat
    
    RETURNS: [{"role": "user", "content": "..."}, {"role": "bot", "content": "..."}]
    
    ORDER BY id = oldest first (chronological order)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM chat_messages WHERE chat_id = ? ORDER BY id", 
                  (chat_id,))
    messages = cursor.fetchall()
    conn.close()
    return [{"role": msg[0], "content": msg[1]} for msg in messages]

def get_user_chats(username):
    """
    Get all chats for a user
    
    RETURNS: [{"id": 1, "name": "resume.pdf", "created_at": "2026-06-28..."}, ...]
    
    ORDER BY created_at DESC = newest first
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, chat_name, created_at FROM chat_sessions WHERE username = ? ORDER BY created_at DESC", 
        (username,)
    )
    chats = cursor.fetchall()
    conn.close()
    return [{"id": chat[0], "name": chat[1], "created_at": chat[2]} for chat in chats]

def create_new_chat(username, chat_name):
    """
    Create a new chat for a user
    
    RETURNS: chat_id (the ID of the newly created chat)
    
    lastrowid = the ID that was just auto-generated by database
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_sessions (username, chat_name) VALUES (?, ?)", 
                  (username, chat_name))
    conn.commit()
    chat_id = cursor.lastrowid
    conn.close()
    return chat_id

def block_account(username):
    """Block account after multiple failed attempts"""
    conn = sqlite3.connect("lexirag.db")
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET blocked = 1 WHERE username = ?",
        (username,)
    )
    conn.commit()
    conn.close()

def is_blocked(username):
    """Check if account is blocked"""
    conn = sqlite3.connect("lexirag.db")
    cursor = conn.cursor()
    cursor.execute("SELECT blocked FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else False