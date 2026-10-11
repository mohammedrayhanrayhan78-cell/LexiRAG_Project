# ============================================
# MAIN.PY - LexiRAG FastAPI Backend (PRODUCTION READY)
# ============================================
# This is the HEART of LexiRAG
# SECURITY: JWT verification, password hashing, chat isolation, rate limits
# ============================================

# ============================================
# 1. IMPORTS - Bringing in all tools we need
# ============================================

from dotenv import load_dotenv
load_dotenv()
import html
import io
import os
import json
from db import get_connection, init_schema
import time
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import jwt
import numpy as np
import pdfplumber
import pytesseract
from PIL import Image

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Import all database functions
from database import (
    init_db, init_users_table, save_chunk, delete_document, 
    get_documents, save_chunks_batch, create_user, verify_user, 
    save_chat_message, get_chat_messages, get_user_chats, create_new_chat,
    get_chat_owner, delete_chat_and_chunks, delete_chat_document,
    delete_user_document, get_chat_documents, delete_user_account, DB_PATH
)
from embeddings import get_embedding, get_embeddings_batch, detect_language
from rag import (
    find_relevant_chunks, ask_llm_stream, classify_complexity,
    LLMUnavailable, GENERIC_LLM_ERROR
)

# Tesseract: use TESSERACT_CMD if set (e.g. a Windows path in .env); otherwise rely on PATH (Linux/Docker)
_tesseract_cmd = os.getenv("TESSERACT_CMD")
if _tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd

# OCR languages (needs the matching Tesseract language packs; Dockerfile installs them)
OCR_LANGS = os.getenv("OCR_LANGS", "eng+hin+kan+tam+tel")
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", 100))   # pages read per PDF
MAX_OCR_PAGES = int(os.getenv("MAX_OCR_PAGES", 15))    # scanned pages OCR'd per PDF (CPU protection)

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
# 3. RATE LIMITING ENGINE (IP & USERNAME SPECIFIC)
# ============================================

class AuthRateLimiter:
    """
    Manages rate limits for authentication endpoints (per-IP and per-username).
    Strictly limits attempts (e.g., exactly 5 attempts per minute).
    Returns accurate Retry-After values.
    Uses Redis if available, with robust fallback to thread-safe in-memory sliding window.
    """
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_client = None
        if redis_url:
            try:
                import redis
                client = redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
                client.ping()
                self.redis_client = client
            except Exception:
                self.redis_client = None
        self._memory_store = defaultdict(list)
        self._lock = threading.Lock()

    def get_retry_after(self, key: str, limit: int = 5, window: int = 60) -> int:
        now = time.time()
        if self.redis_client:
            try:
                redis_key = f"lexi_rl:{key}"
                pipe = self.redis_client.pipeline()
                pipe.zremrangebyscore(redis_key, 0, now - window)
                pipe.zcard(redis_key)
                pipe.zrange(redis_key, 0, 0, withscores=True)
                _, count, oldest = pipe.execute()
                if count >= limit:
                    oldest_ts = oldest[0][1] if oldest else (now - window)
                    return max(1, int(oldest_ts + window - now))
                return 0
            except Exception:
                pass

        with self._lock:
            timestamps = [t for t in self._memory_store[key] if t > now - window]
            self._memory_store[key] = timestamps
            if len(timestamps) >= limit:
                oldest_ts = timestamps[0]
                return max(1, int(oldest_ts + window - now))
            return 0

    def record_attempt(self, key: str, window: int = 60):
        now = time.time()
        if self.redis_client:
            try:
                redis_key = f"lexi_rl:{key}"
                pipe = self.redis_client.pipeline()
                pipe.zadd(redis_key, {str(now): now})
                pipe.expire(redis_key, window + 1)
                pipe.execute()
                return
            except Exception:
                pass

        with self._lock:
            self._memory_store[key].append(now)

    def reset(self, key: Optional[str] = None):
        """Helper to clear rate limit state (useful in tests)"""
        if self.redis_client and key:
            try:
                self.redis_client.delete(f"lexi_rl:{key}")
            except Exception:
                pass
        with self._lock:
            if key:
                self._memory_store.pop(key, None)
            else:
                self._memory_store.clear()

REDIS_URL = os.getenv("REDIS_URL")
auth_limiter = AuthRateLimiter(REDIS_URL)

def get_client_ip(request: Request) -> str:
    """Extract client IP from headers (proxy/ngrok friendly) or direct connection"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"

# ============================================
# 4. FASTAPI APP SETUP & CORS
# ============================================

IS_PROD = os.getenv("ENV", "dev").lower() == "prod"
app = FastAPI(
    docs_url=None if IS_PROD else "/docs",
    redoc_url=None if IS_PROD else "/redoc",
    openapi_url=None if IS_PROD else "/openapi.json",
)

# SlowAPI Limiter for other general routes
def init_slowapi_limiter():
    storage_uri = "memory://"
    if REDIS_URL:
        try:
            import redis
            client = redis.from_url(REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
            client.ping()
            storage_uri = REDIS_URL
        except Exception:
            storage_uri = "memory://"
    return Limiter(key_func=get_remote_address, storage_uri=storage_uri, headers_enabled=False)

limiter = init_slowapi_limiter()
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    retry_after = "60"
    if hasattr(exc, "retry_after") and exc.retry_after:
        retry_after = str(int(exc.retry_after))
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests. Please try again later.",
            "error": "Too many requests. Please try again later."
        },
        headers={"Retry-After": retry_after}
    )

# Exact origins only, comma-separated in ALLOWED_ORIGINS (e.g. https://lexirag-web.onrender.com)
ALLOWED_ORIGINS = [o.strip() for o in os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:8000"
).split(",") if o.strip()]

# CORS Middleware:
# Exposes Retry-After and explicitly allows Authorization header
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,  # we use Bearer tokens, not cookies
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Retry-After"],
)

# Initialize database tables on startup
init_db()
init_users_table()

def init_chat_tables():
    """Create chat and message tables on startup"""
    init_schema()

init_chat_tables()

# ============================================
# 5. TEXT EXTRACTION & IN-MEMORY FILE PROCESSING
# ============================================
# SIZE CAP: Configurable via MAX_FILE_SIZE, default 10MB
# Both PDF and TXT are processed completely in memory and discarded immediately.
# Files are NEVER stored on disk.
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 10 * 1024 * 1024))

def _ocr_image(image):
    """OCR one page image; falls back to English-only if a language pack is missing."""
    try:
        return pytesseract.image_to_string(image, lang=OCR_LANGS)
    except Exception:
        try:
            return pytesseract.image_to_string(image, lang="eng")
        except Exception:
            return ""

def extract_text_from_pdf_bytes(file_bytes: bytes) -> str:
    """Extract text from in-memory PDF bytes with OCR fallback (page-capped)"""
    text = ""
    ocr_pages = 0
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages[:MAX_PDF_PAGES]:
            page_text = page.extract_text()
            if page_text and len(page_text.strip()) > 50:
                text += page_text + "\n"
            elif ocr_pages < MAX_OCR_PAGES:
                ocr_pages += 1
                try:
                    ocr_text = _ocr_image(page.to_image().original)
                    if ocr_text:
                        text += ocr_text + "\n"
                except Exception:
                    pass
    return text

async def process_file_content(file: UploadFile) -> tuple[str, str]:
    """
    Validates file type (PDF/TXT) and size cap, extracts text into memory,
    and returns (filename, extracted_text).
    PDF requires magic-byte check (%PDF).
    TXT must decode as UTF-8 and contains NO NUL bytes (\x00).
    Both are processed and discarded, never saved to disk.
    """
    filename = file.filename or ""
    lower_name = filename.lower()
    
    if not (lower_name.endswith(".pdf") or lower_name.endswith(".txt")):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Only PDF (.pdf) and TXT (.txt) files are accepted."
        )
    
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum allowed size of {MAX_FILE_SIZE // (1024 * 1024)}MB."
        )
    if len(content) == 0:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty."
        )
    
    if lower_name.endswith(".pdf"):
        # Magic bytes check for PDF (%PDF)
        if not content.startswith(b"%PDF"):
            raise HTTPException(
                status_code=400,
                detail="Invalid PDF file: Missing %PDF magic bytes."
            )
        try:
            text = extract_text_from_pdf_bytes(content)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Could not process PDF file: {str(e)}"
            )
    else:
        # TXT file processing: UTF-8 decode & NUL byte check
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Invalid TXT file: File must be valid UTF-8 encoded text."
            )
        if "\x00" in text:
            raise HTTPException(
                status_code=400,
                detail="Invalid TXT file: File cannot contain NUL bytes."
            )
            
    return filename, text

def split_into_chunks(text, chunk_size=300):
    """Split long text into overlapping chunks"""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - 50):
        chunk = " ".join(words[i:i+chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks

# ============================================
# 6. SECURITY - JWT TOKEN & CHAT OWNERSHIP
# ============================================

# REQUIRED: no default value. The app refuses to start without a strong secret.
SECRET_KEY = os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY")
if not SECRET_KEY or len(SECRET_KEY) < 32:
    raise RuntimeError(
        "JWT_SECRET_KEY is missing or too short (need at least 32 characters). "
        "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
    )

def verify_token(authorization: Optional[str] = Header(None)) -> str:
    """Verify JWT token and return authenticated username"""
    if not authorization:
        raise HTTPException(status_code=401, detail="No token provided")
    
    try:
        parts = authorization.split(" ")
        if len(parts) != 2 or parts[0] != "Bearer":
            raise HTTPException(status_code=401, detail="Invalid authorization format")
        
        token = parts[1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        username = payload.get("username")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired, please login again")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

def verify_chat_ownership(chat_id: int, username: str) -> None:
    """Ensure that the chat exists and is owned by the authenticated user"""
    owner = get_chat_owner(chat_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    if owner != username:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this chat")

# ============================================
# 7. ENDPOINTS - AUTHENTICATION & RATE LIMITS
# ============================================

@app.post("/signup")
async def signup(request: Request, user: UserSignup):
    """
    ENDPOINT: POST /signup
    Rate limited to exactly 5 attempts per minute per IP.
    Returns HTTP 429 with Retry-After header and generic message when exceeded.
    """
    client_ip = get_client_ip(request)
    ip_key = f"signup:ip:{client_ip}"
    
    retry_after = auth_limiter.get_retry_after(ip_key, limit=5, window=60)
    if retry_after > 0:
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Too many requests. Please try again later.",
                "error": "Too many requests. Please try again later."
            },
            headers={"Retry-After": str(retry_after)}
        )
    auth_limiter.record_attempt(ip_key, window=60)

    if create_user(user.username, user.password):
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
        return JSONResponse(
            status_code=400,
            content={"detail": "Username already exists"}
        )

@app.post("/login")
async def login(request: Request, user: UserLogin):
    """
    ENDPOINT: POST /login
    Rate limited to exactly 5 attempts per minute per IP, AND also per username.
    Returns HTTP 429 with Retry-After header and generic message when exceeded.
    """
    client_ip = get_client_ip(request)
    normalized_user = (user.username or "").strip().lower()
    ip_key = f"login:ip:{client_ip}"
    user_key = f"login:user:{normalized_user}"

    retry_ip = auth_limiter.get_retry_after(ip_key, limit=5, window=60)
    retry_user = auth_limiter.get_retry_after(user_key, limit=5, window=60) if normalized_user else 0

    if retry_ip > 0 or retry_user > 0:
        retry_after = max(retry_ip, retry_user)
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Too many requests. Please try again later.",
                "error": "Too many requests. Please try again later."
            },
            headers={"Retry-After": str(retry_after)}
        )

    auth_limiter.record_attempt(ip_key, window=60)
    if normalized_user:
        auth_limiter.record_attempt(user_key, window=60)

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
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid credentials"}
        )

# ============================================
# 8. ENDPOINTS - DOCUMENT MANAGEMENT
# ============================================

@app.post("/upload")
@limiter.limit("20/hour")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    chat_id: int = Form(...),
    authorization: Optional[str] = Header(None)
):
    """
    ENDPOINT: POST /upload
    Uploads a PDF or TXT file to a specific chat with ownership verification.
    File is processed in-memory and discarded, never saved to disk.
    """
    username = verify_token(authorization)
    verify_chat_ownership(chat_id, username)

    filename, text = await process_file_content(file)
    chunks = split_into_chunks(text)
    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="Could not extract any readable text from this file. It may be corrupted or empty."
        )

    embeddings = get_embeddings_batch(chunks)
    save_chunks_batch(filename, chunks, embeddings, chat_id=chat_id)

    return {
        "message": f"Uploaded {len(chunks)} chunks",
        "filename": filename,
        "chunks": len(chunks)
    }

@app.post("/chats/{chat_id}/documents")
@app.post("/chats/{chat_id}/upload")
@limiter.limit("20/hour")
async def upload_document_to_chat(
    request: Request,
    chat_id: int,
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None)
):
    """Direct chat-scoped document upload route for modern UI"""
    return await upload_document(request=request, file=file, chat_id=chat_id, authorization=authorization)

@app.get("/documents/{chat_id}")
@app.get("/chats/{chat_id}/documents")
async def list_documents(chat_id: int, authorization: Optional[str] = Header(None)):
    """
    ENDPOINT: GET /documents/{chat_id} & GET /chats/{chat_id}/documents
    Get all documents uploaded to THIS chat with ownership verification.
    """
    username = verify_token(authorization)
    verify_chat_ownership(chat_id, username)
    docs = get_chat_documents(chat_id)
    return {"documents": docs}

@app.delete("/chats/{chat_id}/documents/{doc_name}")
@app.delete("/chats/{chat_id}/document/{doc_name}")
async def delete_chat_doc(chat_id: int, doc_name: str, authorization: Optional[str] = Header(None)):
    """
    ENDPOINT: DELETE /chats/{chat_id}/documents/{doc_name}
    Deletes all chunks of a document scoped to a specific chat with ownership verification.
    """
    username = verify_token(authorization)
    verify_chat_ownership(chat_id, username)
    delete_chat_document(chat_id, doc_name)
    return {"message": f"Deleted {doc_name}", "status": "deleted"}

@app.delete("/document/{doc_name}")
async def delete_doc(doc_name: str, authorization: Optional[str] = Header(None)):
    """
    ENDPOINT: DELETE /document/{doc_name}
    Deletes chunks of doc_name across chats owned by the authenticated user.
    """
    username = verify_token(authorization)
    delete_user_document(username, doc_name)
    return {"message": f"Deleted {doc_name}"}

# ============================================
# 9. ENDPOINTS - CHAT MANAGEMENT
# ============================================

@app.get("/chats")
async def list_my_chats(authorization: Optional[str] = Header(None)):
    """
    ENDPOINT: GET /chats
    List all chats for the authenticated user (token-derived identity).
    """
    username = verify_token(authorization)
    chats = get_user_chats(username)
    return {"chats": chats}

@app.get("/chats/{username}")
async def get_chats(username: str, authorization: Optional[str] = Header(None)):
    """
    ENDPOINT: GET /chats/{username}
    List all chats for a specific username (with strict ownership check).
    """
    token_username = verify_token(authorization)
    if token_username != username:
        return JSONResponse(
            status_code=403,
            content={"detail": "Unauthorized - can only access your own chats"}
        )
    chats = get_user_chats(username)
    return {"chats": chats}

@app.post("/chats")
@app.post("/chats/new")
@limiter.limit("20/hour")
async def create_chat(request: Request, payload: dict, authorization: Optional[str] = Header(None)):
    """
    ENDPOINT: POST /chats & POST /chats/new
    Create new chat for authenticated user.
    """
    username = verify_token(authorization)
    chat_name = payload.get("chat_name", "New Chat")
    chat_name = html.escape(chat_name)
    chat_id = create_new_chat(username, chat_name)
    return {
        "chat_id": chat_id,
        "chat_name": chat_name,
        "username": username
    }

@app.delete("/chats/{chat_id}")
async def delete_chat(chat_id: int, authorization: Optional[str] = Header(None)):
    """
    ENDPOINT: DELETE /chats/{chat_id}
    Delete chat, all its messages, AND all its chunks with strict ownership check.
    """
    username = verify_token(authorization)
    verify_chat_ownership(chat_id, username)
    delete_chat_and_chunks(chat_id)
    return {"status": "deleted"}

@app.get("/chats/{chat_id}/messages")
async def get_messages(chat_id: int, authorization: Optional[str] = Header(None)):
    """Get all messages in a chat (with ownership check)"""
    username = verify_token(authorization)
    verify_chat_ownership(chat_id, username)
    messages = get_chat_messages(chat_id)
    return {"messages": messages}

@app.post("/chats/{chat_id}/message")
async def save_message(
    chat_id: int,
    payload: dict,
    authorization: Optional[str] = Header(None)
):
    """Save message in chat (with ownership check)"""
    username = verify_token(authorization)
    verify_chat_ownership(chat_id, username)
    role = payload.get("role")
    content = payload.get("content")
    save_chat_message(chat_id, role, content)
    return {"status": "saved"}

@app.post("/chats/{chat_id}/rename")
async def rename_chat(
    chat_id: int,
    payload: dict,
    authorization: Optional[str] = Header(None)
):
    """Rename a chat (with ownership check)"""
    username = verify_token(authorization)
    verify_chat_ownership(chat_id, username)
    chat_name = payload.get("chat_name", "Chat")
    chat_name = html.escape(chat_name)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE chat_sessions SET chat_name = ? WHERE id = ?", (chat_name, chat_id))
    conn.commit()
    conn.close()
    return {"status": "renamed", "new_name": chat_name}

# ============================================
# 10. ENDPOINTS - ACCOUNT DELETION
# ============================================

@app.delete("/account")
@app.delete("/users/me")
async def delete_my_account(authorization: Optional[str] = Header(None)):
    """
    ENDPOINT: DELETE /account & DELETE /users/me
    Deletes the authenticated user's account and ALL their data:
    - All document chunks in all their chats
    - All messages in all their chats
    - All chat sessions
    - The user record itself
    """
    username = verify_token(authorization)
    delete_user_account(username)
    return {
        "status": "deleted",
        "message": "Account and all associated data deleted successfully"
    }

# ============================================
# 11. ENDPOINTS - RAG STREAMING (POST /ask)
# ============================================

@app.post("/ask")
@limiter.limit("20/hour")
async def ask_question(request: Request, payload: dict, authorization: Optional[str] = Header(None)):
    """
    ENDPOINT: POST /ask
    Streams RAG response via Server-Sent Events (SSE).
    
    WIRE FORMAT SPECIFICATION:
    Content-Type: text/event-stream
    Messages:
    1. Sources item: data: {"type": "sources", "sources": [...], "model": "..."}\n\n
    2. Token items: data: {"type": "token", "text": "..."}\n\n
    3. Final metadata item: data: {"type": "metadata", "provider": "groq"|"gemini", "sources": [...], "detected_language": "..."}\n\n
    4. Done signal: data: {"type": "done", "provider": "groq"|"gemini", "sources": [...], "detected_language": "..."}\n\n
    5. Clean error item (if mid-stream failure occurs): data: {"type": "error", "error": "...", "detail": "..."}\n\n
    """
    username = verify_token(authorization)
    
    question = payload.get("question")
    chat_id = payload.get("chat_id")
    mode = payload.get("mode", "auto")

    if not question:
        raise HTTPException(status_code=400, detail="Question is required")
    if not chat_id:
        raise HTTPException(status_code=400, detail="chat_id is required")

    # Ownership verification on chat_id
    verify_chat_ownership(chat_id, username)

    # Detect language
    lang_code, detected_language = detect_language(question)

    # Resolve model choice
    if mode == "auto":
        selected_model = 'gemini' if lang_code != 'en' else 'groq'
    elif mode in ("groq", "gemini"):
        selected_model = mode
    else:
        selected_model = 'groq'  # unknown/legacy values (e.g. "ollama") -> Groq

    # Provider we try first; the real one is reported after streaming (fallback may switch it)
    provider = selected_model
    info = {}

    # Generate query embedding
    query_embedding = get_embedding(question)

    # Fetch chunks from THIS chat only
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT doc_name, chunk_text, embedding FROM chunks WHERE chat_id = ?",
        (chat_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    relevant_chunks = []
    for row in rows:
        try:
            emb = np.array(json.loads(row[2]))
            similarity = np.dot(query_embedding, emb)
            relevant_chunks.append({
                "doc_name": row[0],
                "chunk_text": row[1],
                "similarity": similarity
            })
        except Exception:
            pass

    relevant_chunks = sorted(
        relevant_chunks,
        key=lambda x: x['similarity'],
        reverse=True
    )[:5]

    sources = list(dict.fromkeys([c["doc_name"] for c in relevant_chunks]))

    def stream():
        try:
            # 1. Initial sources event
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources, 'model': selected_model})}\n\n"

            # 2. Token-by-token streaming
            for token in ask_llm_stream(question, relevant_chunks, mode=selected_model, info=info):
                yield f"data: {json.dumps({'type': 'token', 'text': token})}\n\n"

            provider_used = info.get("provider", provider)

            # 3. Final metadata item containing provider, sources, and detected language
            yield f"data: {json.dumps({'type': 'metadata', 'provider': provider_used, 'sources': sources, 'detected_language': detected_language, 'language': detected_language})}\n\n"

            # 4. Stream completion done signal
            yield f"data: {json.dumps({'type': 'done', 'provider': provider_used, 'sources': sources, 'detected_language': detected_language, 'language': detected_language})}\n\n"

        except LLMUnavailable as e:
            # Message is user-safe by construction (no URLs, keys or provider bodies)
            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'detail': str(e)})}\n\n"
        except Exception as e:
            # Never leak internals to the client; log only the exception type
            print(f"[ask] stream failed: {type(e).__name__}")
            yield f"data: {json.dumps({'type': 'error', 'error': GENERIC_LLM_ERROR, 'detail': GENERIC_LLM_ERROR})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")

@app.post("/chats/{chat_id}/ask")
@limiter.limit("20/hour")
async def ask_question_in_chat(
    request: Request,
    chat_id: int,
    payload: dict,
    authorization: Optional[str] = Header(None)
):
    """Direct chat-scoped ask endpoint"""
    payload_copy = dict(payload)
    payload_copy["chat_id"] = chat_id
    return await ask_question(request=request, payload=payload_copy, authorization=authorization)

# ============================================
# 12. HEALTH CHECK
# ============================================

@app.get("/health")
@app.get("/healthz")
async def health():
    """ENDPOINT: GET /health - Server health check"""
    return {"status": "LexiRAG is running ✅"}

# ============================================
# 13. MOUNT STATIC FILES
# ============================================

# Serve React frontend if dist directory exists (must be added AFTER all API routes)
# Opt-in only (local single-port mode). In cloud the frontend is a separate static site.
if os.getenv("SERVE_FRONTEND") == "1" and os.path.exists("lexirag-react/dist"):
    app.mount("/", StaticFiles(directory="lexirag-react/dist", html=True), name="static")