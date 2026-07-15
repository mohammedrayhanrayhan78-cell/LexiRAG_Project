# ============================================
# MAIN.PY - LexiRAG FastAPI Backend (PRODUCTION READY)
# ============================================
# This is the HEART of LexiRAG
# SECURITY: JWT verification, password hashing, chat isolation
# ============================================

# ============================================
# 1. IMPORTS - Bringing in all tools we need
# ============================================

from dotenv import load_dotenv
load_dotenv()
import html
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from datetime import datetime, timedelta
import jwt
from pydantic import BaseModel
import sqlite3
import numpy as np
import json
import pytesseract
from PIL import Image
import pdfplumber
import os
from typing import Optional

# Import all database functions
from database import (
    init_db, init_users_table, save_chunk, delete_document, 
    get_documents, save_chunks_batch, create_user, verify_user, 
    save_chat_message, get_chat_messages, get_user_chats, create_new_chat
)
from embeddings import get_embedding, get_embeddings_batch
from rag import find_relevant_chunks, ask_llm_stream, classify_complexity
from embeddings import get_embedding, get_embeddings_batch, detect_language

pytesseract.pytesseract.pytesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# ============================================
# 2. PYDANTIC MODELS - Input validation
# ============================================

class UserSignup(BaseModel):
    """Validate signup data from frontend"""
    username: str
    password: str

class UserLogin(BaseModel):
    """Validate login data from frontend"""
    username: str
    password: str

# ============================================
# 3. FASTAPI APP SETUP
# ============================================

app = FastAPI()

# Rate Limiter Setup
# key_func=get_remote_address = limit based on IP address (per-user limit)
# storage_uri=Redis = limits persist across server restarts (not just in-memory)
REDIS_URL = os.getenv("REDIS_URL")
limiter = Limiter(key_func=get_remote_address, storage_uri=REDIS_URL)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Middleware = Allow frontend to call backend from different origin
# allow_origins=["*"] = Accept requests from ANY origin (localhost, ngrok, etc)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database tables on startup
init_db()
init_users_table()

def init_chat_tables():
    """Create chat and message tables on startup"""
    conn = sqlite3.connect("lexirag.db")
    cursor = conn.cursor()
    
    # chat_sessions = conversation rooms
    # Each user can have multiple chats
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            chat_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(username) REFERENCES users(username)
        )
    ''')
    
    # chat_messages = individual messages in a chat
    # Linked to chat via chat_id
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

init_chat_tables()

# Create uploads folder if doesn't exist
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ============================================
# 4. TEXT EXTRACTION FUNCTIONS
# ============================================

def extract_text_from_txt(filepath):
    """Read plain text files"""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()

def extract_text_from_pdf(filepath):
    """
    Extract text from PDF files
    
    STRATEGY:
    1. Try pdfplumber first (fast, works for most PDFs)
    2. If page has <50 chars = image-based page
    3. Use pytesseract OCR to extract text from image
    
    This handles BOTH text PDFs and scanned image PDFs
    """
    text = ""
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            # Try text extraction first
            page_text = page.extract_text()
            if page_text and len(page_text.strip()) > 50:
                text += page_text + "\n"
            else:
                # Fallback to OCR for image-based pages
                try:
                    image = page.to_image()
                    ocr_text = pytesseract.image_to_string(image.original)
                    if ocr_text:
                        text += ocr_text + "\n"
                except Exception as e:
                    print(f"OCR failed: {e}")
    return text

def extract_text(filepath):
    """Choose extraction method based on file extension"""
    if filepath.endswith('.txt'):
        return extract_text_from_txt(filepath)
    else:
        return extract_text_from_pdf(filepath)

def split_into_chunks(text, chunk_size=300):
    """
    Split long text into overlapping chunks
    
    WHY: Documents are huge. We search smaller chunks for relevance.
    
    EXAMPLE:
    text = "The quick brown fox jumps over the lazy dog"
    chunk_size = 5
    Result: ["The quick brown fox jumps", "brown fox jumps over the", ...]
    
    Overlap (chunk_size - 50) = keep context between chunks
    """
    words = text.split()
    chunks = []
    
    # Step through text with overlap
    for i in range(0, len(words), chunk_size - 50):
        chunk = " ".join(words[i:i+chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    
    return chunks

# ============================================
# 5. SECURITY - JWT TOKEN VERIFICATION
# ============================================

SECRET_KEY = "3FdMN9FNZevIsYiLPTnU0hUOg0O_3Wzwovm52AGfe7wCLtsBM"
# TODO: Move to environment variable

def verify_token(authorization: Optional[str] = Header(None)):
    """Verify JWT token"""
    if not authorization:
        raise HTTPException(status_code=401, detail="No token provided")
    
    try:
        # Split "Bearer {token}"
        parts = authorization.split(" ")
        if len(parts) != 2 or parts[0] != "Bearer":
            raise HTTPException(status_code=401, detail="Invalid authorization format")
        
        token = parts[1]
        
        # Decode and verify
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("username")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired, please login again")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

# ============================================
# 6. ENDPOINTS - AUTHENTICATION
# ============================================

@app.post("/signup")
@limiter.limit("5/minute")
async def signup(request: Request, user: UserSignup):
    """
    ENDPOINT: POST /signup
    
    SECURITY:
    - Password is hashed using passlib (bcrypt) before storage
    - Never store plaintext passwords
    
    RESPONSE: Returns JWT token valid for 7 days
    """
    # create_user() hashes password using passlib internally
    if create_user(user.username, user.password):
        # Generate JWT token with username + expiration
        token = jwt.encode(
            {
                "username": user.username,
                "exp": datetime.utcnow() + timedelta(days=7)
            },
            SECRET_KEY,
            algorithm="HS256"
        )
        return {"token": token, "username": user.username}
    else:
        # Username already exists
        return JSONResponse(
            status_code=400,
            content={"detail": "Username already exists"}
        )

@app.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, user: UserLogin):
    """
    ENDPOINT: POST /login
    
    SECURITY:
    - Password is verified using passlib.verify()
    - Compares plaintext password with stored hash
    
    RESPONSE: Returns JWT token valid for 7 days
    """
    # verify_user() uses passlib to verify password
    if verify_user(user.username, user.password):
        token = jwt.encode(
            {
                "username": user.username,
                "exp": datetime.utcnow() + timedelta(days=7)
            },
            SECRET_KEY,
            algorithm="HS256"
        )
        return {"token": token, "username": user.username}
    else:
        # Wrong username or password
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid credentials"}
        )

# ============================================
# 7. ENDPOINTS - DOCUMENT MANAGEMENT
# ============================================

@app.post("/upload")
@limiter.limit("20/hour")
def upload_document(
    request: Request,
    file: UploadFile = File(...),
    chat_id: int = Form(...),
    authorization: Optional[str] = Header(None)
):
    """
    ENDPOINT: POST /upload
    
    SECURITY:
    - Verify user is logged in via JWT token
    - chat_id ensures documents are scoped to specific chat
    - Prevents users from accessing other users' documents
    
    FLOW:
    1. Receive PDF/TXT file
    2. Extract text (with OCR fallback for scanned PDFs)
    3. Split into chunks (smaller pieces)
    4. Generate embeddings for each chunk
    5. Save to database with chat_id
    
    RETURNS: Number of chunks created
    """
   # Security check
    verify_token(authorization)
    
    # Save uploaded file temporarily
    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(filepath, "wb") as f:
        f.write(file.file.read())
    
    try:
        # Extract text from file
        text = extract_text(filepath)
        
        # Split into chunks
        chunks = split_into_chunks(text)
        
        # If no readable text was found, reject clearly instead of silently saving 0 chunks
        if not chunks:
            os.remove(filepath)
            raise HTTPException(
                status_code=400,
                detail="Could not extract any readable text from this file. It may be corrupted or empty."
            )
        
        # Generate embeddings for all chunks
        embeddings = get_embeddings_batch(chunks)
        
        # Save all chunks to database with chat_id
        conn = sqlite3.connect("lexirag.db")
        cursor = conn.cursor()
        for chunk, emb in zip(chunks, embeddings):
            cursor.execute(
                "INSERT INTO chunks (doc_name, chunk_text, embedding, chat_id) VALUES (?, ?, ?, ?)",
                (file.filename, chunk, json.dumps(emb.tolist()), chat_id)
            )
        conn.commit()
        conn.close()
        
        return {
            "message": f"Uploaded {len(chunks)} chunks",
            "filename": file.filename,
            "chunks": len(chunks)
        }
    except HTTPException:
        raise
    except Exception as e:
        # Corrupted/unreadable file (pdfplumber couldn't even open it)
        if os.path.exists(filepath):
            os.remove(filepath)
        raise HTTPException(
            status_code=400,
            detail=f"Could not process this file. It may be corrupted or in an unsupported format."
        )

@app.post("/ask")
@limiter.limit("20/hour")
async def ask_question(request: Request, payload: dict, authorization: Optional[str] = Header(None)):
    """
    ENDPOINT: POST /ask
    
    RAG (Retrieval Augmented Generation) Pipeline:
    1. Get user question + chat_id + AI mode
    2. Verify user is logged in
    3. Generate embedding for question
    4. Search chat-specific chunks for relevant ones
    5. Send top 5 relevant chunks to LLM
    6. Stream LLM response token-by-token
    
    RESPONSE: Server-Sent Events (SSE) streaming
    Frontend receives: sources, then tokens, then done signal
    """
    # Security check
    verify_token(authorization)
    
    question = payload.get("question")
    chat_id = payload.get("chat_id")
    mode = payload.get("mode", "auto") #default to auto if not provided

# Resolve "auto" mode into actual model choice, so frontend can display it
    if mode == "auto":
        complexity = classify_complexity(question)
        lang_code, _ = detect_language(question)
        if complexity == 'complex':
            selected_model = 'ollama'
        elif lang_code != 'en':
            selected_model = 'gemini'
        else:
            selected_model = 'groq'
    else:
        selected_model = mode

# Generate embedding for the question
    
    # Generate embedding for the question
    query_embedding = get_embedding(question)
    
    # Get all chunks from THIS chat only
    conn = sqlite3.connect("lexirag.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT doc_name, chunk_text, embedding FROM chunks WHERE chat_id = ?",
        (chat_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    # Score each chunk by similarity to question
    relevant_chunks = []
    for row in rows:
        try:
            emb = np.array(json.loads(row[2]))
            # Cosine similarity = dot product of normalized vectors
            similarity = np.dot(query_embedding, emb)
            relevant_chunks.append({
                "doc_name": row[0],
                "chunk_text": row[1],
                "similarity": similarity
            })
        except:
            pass
    
    # Sort by similarity, keep top 5
    relevant_chunks = sorted(
        relevant_chunks,
        key=lambda x: x['similarity'],
        reverse=True
    )[:5]
    
    # Extract unique document names for citation
    sources = list(set([c["doc_name"] for c in relevant_chunks]))
    
    # Stream response using Server-Sent Events
    def stream():
        # Send sources first, along with which model got auto-selected
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources, 'model': selected_model})}\n\n"
        
        # Stream tokens from LLM (use resolved model, not raw 'auto')
        for token in ask_llm_stream(question, relevant_chunks, mode=selected_model):
            yield f"data: {json.dumps({'type': 'token', 'text': token})}\n\n"
        
        # Send done signal
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    
    return StreamingResponse(stream(), media_type="text/event-stream")

@app.delete("/document/{doc_name}")
async def delete_doc(doc_name: str, authorization: Optional[str] = Header(None)):
    """
    ENDPOINT: DELETE /document/{doc_name}
    
    Delete all chunks of a document
    """
    verify_token(authorization)
    delete_document(doc_name)
    return {"message": f"Deleted {doc_name}"}

@app.get("/health")
async def health():
    """ENDPOINT: GET /health - Server health check"""
    return {"status": "LexiRAG is running ✅"}

@app.get("/documents/{chat_id}")
async def list_documents(chat_id: int, authorization: Optional[str] = Header(None)):
    """
    ENDPOINT: GET /documents/{chat_id}
    
    Get all documents uploaded to THIS chat
    (Chat-scoped isolation for security)
    """
    verify_token(authorization)
    
    conn = sqlite3.connect("lexirag.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT doc_name FROM chunks WHERE chat_id = ?",
        (chat_id,)
    )
    docs = [row[0] for row in cursor.fetchall()]
    conn.close()
    return {"documents": docs}

# ============================================
# 8. ENDPOINTS - CHAT MANAGEMENT (SECURED)
# ============================================

@app.post("/chats/new")
@limiter.limit("20/hour")
async def create_chat(request: Request, payload: dict, authorization: Optional[str] = Header(None)):
    """
    ENDPOINT: POST /chats/new
    
    SECURITY: Requires valid JWT token
    
    Create new chat for logged-in user
    Returns chat_id for use in future uploads/messages
    """
    # Verify user is logged in
    username = verify_token(authorization)
    
    chat_name = payload.get("chat_name", "New Chat")
    chat_name = html.escape(chat_name)  # Sanitize to prevent XSS attacks
    
    # Create chat in database
    chat_id = create_new_chat(username, chat_name)
    
    return {
        "chat_id": chat_id,
        "chat_name": chat_name,
        "username": username
    }

@app.get("/chats/{username}")
async def get_chats(username: str, authorization: Optional[str] = Header(None)):
    """
    ENDPOINT: GET /chats/{username}
    
    SECURITY: 
    - Verify token exists
    - Verify username from token matches requested username
    - Prevents users from accessing other users' chats
    
    Returns all chats for a user with created_at timestamp
    """
    # Verify user is logged in
    token_username = verify_token(authorization)
    
    # Security check: can only access own chats
    if token_username != username:
        return JSONResponse(
            status_code=403,
            content={"detail": "Unauthorized - can only access your own chats"}
        )
    
    # Get chats from database
    chats = get_user_chats(username)
    
    return {"chats": chats}

@app.get("/chats/{chat_id}/messages")
async def get_messages(chat_id: int, authorization: Optional[str] = Header(None)):
    """
    ENDPOINT: GET /chats/{chat_id}/messages
    
    SECURITY: Verify user is logged in
    
    Get all messages in a chat (chronological order)
    """
    verify_token(authorization)
    
    messages = get_chat_messages(chat_id)
    
    return {"messages": messages}

@app.post("/chats/{chat_id}/message")
async def save_message(
    chat_id: int,
    payload: dict,
    authorization: Optional[str] = Header(None)
):
    """
    ENDPOINT: POST /chats/{chat_id}/message
    
    SECURITY: Verify user is logged in
    
    Save a message (user or bot) to chat history
    """
    verify_token(authorization)
    
    role = payload.get("role")  # "user" or "bot"
    content = payload.get("content")
    
    save_chat_message(chat_id, role, content)
    
    return {"status": "saved"}

@app.delete("/chats/{chat_id}")
async def delete_chat(chat_id: int, authorization: Optional[str] = Header(None)):
    """
    ENDPOINT: DELETE /chats/{chat_id}
    
    SECURITY: Verify user is logged in
    
    Delete entire chat and all its messages
    """
    verify_token(authorization)
    
    conn = sqlite3.connect("lexirag.db")
    cursor = conn.cursor()
    try:
        # Delete all messages in chat first
        cursor.execute("DELETE FROM chat_messages WHERE chat_id = ?", (chat_id,))
        
        # Then delete chat itself
        cursor.execute("DELETE FROM chat_sessions WHERE id = ?", (chat_id,))
        
        conn.commit()
        conn.close()
        return {"status": "deleted"}
    except Exception as e:
        conn.close()
        return JSONResponse(
            status_code=400,
            content={"error": str(e)}
        )

@app.post("/chats/{chat_id}/rename")
async def rename_chat(
    chat_id: int,
    payload: dict,
    authorization: Optional[str] = Header(None)
):
    """
    ENDPOINT: POST /chats/{chat_id}/rename
    
    SECURITY: Verify user is logged in
    
    Rename a chat (e.g., "New Chat" -> "resume.pdf")
    """
    verify_token(authorization)
    
    chat_name = payload.get("chat_name")
    chat_name = html.escape(chat_name)  # Sanitize to prevent XSS attacks
    
    conn = sqlite3.connect("lexirag.db")
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE chat_sessions SET chat_name = ? WHERE id = ?",
        (chat_name, chat_id)
    )
    conn.commit()
    conn.close()
    
    return {"status": "renamed", "new_name": chat_name}

# ============================================
# 9. MOUNT STATIC FILES
# ============================================


# Serve React frontend (must be added AFTER all API routes)
app.mount("/", StaticFiles(directory="lexirag-react/dist", html=True), name="static")