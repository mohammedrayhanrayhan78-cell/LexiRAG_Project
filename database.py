import sqlite3
import numpy as np
import json

DB_PATH = "lexirag.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_name TEXT,
            chunk_text TEXT,
            embedding TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_chunk(doc_name, chunk_text, embedding):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chunks (doc_name, chunk_text, embedding) VALUES (?, ?, ?)",
        (doc_name, chunk_text, json.dumps(embedding.tolist()))
    )
    conn.commit()
    conn.close()

def get_all_chunks():
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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chunks WHERE doc_name = ?", (doc_name,))
    conn.commit()
    conn.close()

def get_documents():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT doc_name FROM chunks")
    docs = [row[0] for row in cursor.fetchall()]
    conn.close()
    return docs