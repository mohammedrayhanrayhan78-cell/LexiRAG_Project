# ⚡ LexiRAG

**Cloud-Ready RAG (Retrieval-Augmented Generation) document intelligence platform** — upload documents and ask questions in natural language, with intelligent routing across English and regional Indian languages.

---

## 🎯 What is LexiRAG?

LexiRAG lets you upload PDF and TXT documents and have natural, contextual conversations with them. It automatically routes queries between high-performance cloud LLMs:
- **English queries** → **Groq** (`llama-3.3-70b-versatile`) for sub-second responses.
- **Regional language queries** → **Google Gemini** (`gemini-2.5-flash`) for nuanced multilingual comprehension (Hindi, Kannada, Tamil, Telugu).
- **Automatic Fallback** → If the primary provider experiences downtime or rate limits, requests fail over seamlessly without mixing responses.

---

## 🔒 Privacy Notice

**Honest Privacy Note:**
LexiRAG does NOT store your uploaded files on disk. Documents are parsed in-memory into text chunks and vector embeddings, and the raw files are immediately discarded. However, to generate answers to your queries, **relevant document text snippets and your question are transmitted to third-party cloud LLM providers (Groq or Google Gemini)**. Do not upload confidential or sensitive personal data that should not be processed by third-party AI APIs.

---

## ✨ Key Features

- **🔀 Smart LLM Auto-Routing** — Groq for lightning-fast English retrieval; Gemini for regional Indic languages; automatic resilient failover.
- **🌐 Regional Language Support** — Hindi, Kannada, Tamil, Telugu, and English with automatic language detection.
- **📄 Smart Document Processing** — In-memory PDF extraction (`pdfplumber`) with OCR fallback (`pytesseract`) for scanned pages, plus UTF-8 TXT support.
- **💾 Cloud Persistence & Portability** — Centralized database abstraction (`db.py`) supporting Neon PostgreSQL in production and local SQLite for development.
- **🔒 Chat & User Isolation** — Strict ownership checks across all chats, documents, and queries. Full data deletion on account removal.
- **🛡️ Hardened Security** — Rate-limited auth (5/min per IP and username with `Retry-After`), spoof-proof client IP resolution via `TRUSTED_PROXY_HOPS`, JWT authentication with timezone-aware expiration and claim validation, and security headers (`nosniff`, `no-referrer`, `no-store`).
- **⚡ Fast Vectorized Retrieval** — Stacked `float32` matrix multiplication and `numpy.argpartition` for accelerated top-k chunk ranking.
- **📡 Streaming Responses** — Real-time Server-Sent Events (SSE) streaming with active provider attribution and source file citations.

---

## 🛠️ Tech Stack

**Backend:**
- FastAPI · Pydantic · PyJWT · passlib (PBKDF2)
- psycopg 3 (`psycopg_pool`) for PostgreSQL / Neon
- SQLite (local development fallback)
- fastembed (`all-MiniLM-L6-v2` ONNX) · NumPy
- pdfplumber · pytesseract (OCR) · langdetect
- slowapi (Redis or thread-safe in-memory sliding window)

**Frontend:**
- React (Vite) · react-markdown · Self-hosted typography

**Cloud Providers:**
- Groq Cloud API
- Google Gemini API
- Neon Serverless PostgreSQL
- Render Cloud Platform

---

## ☁️ Deployment Architecture (Render)

LexiRAG is deployed on Render as two decoupled services defined in `render.yaml`:

1. **`lexirag-api` (Docker Web Service)**:
   - Runs the FastAPI application inside a container with Python 3.11 and Tesseract OCR language packs.
   - Connects to Neon PostgreSQL via `DATABASE_URL` with connection pooling (`sslmode=require`, `prepare_threshold=None`).
   - Health check endpoint: `/healthz`.

2. **`lexirag-web` (Static Site)**:
   - Hosts the compiled React/Vite single-page application from `lexirag-react/`.
   - Communicates with `lexirag-api` via `VITE_API_URL`.
   - Protected with Content-Security-Policy and modern security headers.

> ⏱️ **Free-Tier Cold Starts:**
> Render's free tier spins down inactive web services after 15 minutes of inactivity. When a request arrives after spin-down, the backend takes approximately **30 to 50 seconds** to wake up. The frontend automatically pings `/healthz` on load with retry and exponential backoff to wake the service cleanly.

---

## ⚙️ Environment Variables

Configure the following environment variable names (never commit secrets to Git):

### Backend (`lexirag-api` / `.env`)
| Variable Name | Required | Description |
|---|---|---|
| `JWT_SECRET_KEY` | **Yes** | Cryptographic secret for signing JWTs (32+ characters) |
| `DATABASE_URL` | **Yes (Prod)** | Neon PostgreSQL connection URI (`postgresql://...`) |
| `GROQ_API_KEY` | **Yes** | Groq Cloud API key for English queries |
| `GEMINI_API_KEY` | **Yes** | Google Gemini API key for regional queries |
| `ALLOWED_ORIGINS` | **Yes (Prod)** | Comma-separated allowed frontend origins |
| `ENV` | No | Set to `prod` in production (disables `/docs` and OpenAPI) |
| `DATABASE_PATH` | No | Local SQLite database file path (default `lexirag.db`) |
| `TRUSTED_PROXY_HOPS` | No | Number of trusted reverse proxy hops (default `1` for Render) |
| `JWT_EXPIRE_HOURS` | No | Token expiration duration in hours (default `24`) |
| `REDIS_URL` | No | Optional Redis connection string for persistent rate limiting |
| `TESSERACT_CMD` | No | Path to Tesseract binary (Windows local dev only) |
| `OCR_LANGS` | No | Tesseract languages (default `eng+hin+kan+tam+tel`) |

### Frontend (`lexirag-web` / `.env`)
| Variable Name | Required | Description |
|---|---|---|
| `VITE_API_URL` | **Yes** | Public URL of the backend API (e.g. `https://lexirag-api.onrender.com`) |

---

## 🚀 Local Development

### 1. Backend Setup
```bash
# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Configure environment
cp .env.example .env
# Fill in JWT_SECRET_KEY, GROQ_API_KEY, GEMINI_API_KEY in .env

# Run database tests
python -m pytest -q

# Start FastAPI server
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### 2. Frontend Setup
```bash
cd lexirag-react
npm install
npm run dev
```

---

## 👤 Author

**Mohammed Rayhan** — B.Tech CSE, REVA University, Bengaluru  
[GitHub Repository](https://github.com/mohammedrayhanrayhan78-cell/LexiRAG_Project)