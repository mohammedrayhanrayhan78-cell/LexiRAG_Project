# ⚡ LexiRAG

**Offline-capable RAG (Retrieval-Augmented Generation) document chat application** — upload your documents and ask questions in natural language, including regional Indian languages.

---

## 🎯 What is LexiRAG?

LexiRAG lets you upload PDF/TXT documents and have natural conversations with them. It combines local, offline AI with cloud-powered models, automatically choosing the best one for each question — no manual configuration needed.

---

## ✨ Key Features

- **🔀 Multi-LLM Auto-Routing** — The system automatically selects the right model per question:
  - Simple queries → **Groq** (llama-3.3-70b, fast) for English, **Gemini** for regional languages
  - Complex, multi-part queries → **Ollama** (Gemma 2B, runs 100% locally/offline)
- **🌐 Regional Language Support** — Hindi, Kannada, Tamil, Telugu, and English, auto-detected
- **📄 Smart PDF Processing** — Text extraction via `pdfplumber`, with automatic OCR fallback (`pytesseract`) for scanned/image-based PDFs
- **🔒 Chat-Scoped Document Isolation** — Documents and conversations are isolated per chat and per user
- **⚡ Streaming Responses** — Token-by-token streaming via Server-Sent Events (SSE)
- **📚 Source Citations** — Every answer references the exact document it came from
- **📝 Structured Answers** — Responses are formatted with markdown (bullet points, bold, headings) for readability, rendered via `react-markdown`
- **💾 Session Persistence** — Active chat stays open across page refreshes
- **🎨 Clean, Dark, Responsive, Full-Width UI** — Built with React + Vite

---

## 🔒 Security

LexiRAG went through a 10-point security audit and hardening pass:

| Protection | Implementation |
|---|---|
| Rate Limiting | `slowapi` + **Redis-backed storage** — 5/min on login & signup, 20/hour on upload, ask, and chat creation (persists across server restarts) |
| XSS Prevention | Backend sanitization (`html.escape`) on all user-supplied chat names |
| Auth | JWT-based, 7-day expiry, with graceful `401` handling (no server crashes on expired tokens) |
| Password Storage | `passlib` with `pbkdf2_sha256` hashing (no Rust dependency, Windows-friendly) |
| SQL Injection | Fully parameterized queries |
| CSRF / Path Traversal | Blocked via CORS policy and route validation |
| API Key Management | `.env` file (git-ignored), never hardcoded |
| Corrupted File Handling | Uploads that fail extraction return a clean `400` error instead of crashing the server |

---

## 🛠️ Tech Stack

**Backend:** FastAPI · SQLite · pdfplumber · pytesseract (OCR) · sentence-transformers (`all-MiniLM-L6-v2`) · JWT · slowapi · Redis

**Frontend:** React (Vite) · Axios · react-markdown

**LLMs:**
- 🦙 **Ollama** (Gemma 2B) — local, offline, privacy-first
- ⚡ **Groq** (llama-3.3-70b-versatile) — fast cloud inference
- ✨ **Gemini** (2.5-flash) — strong multilingual support

---

## 🏗️ Architecture
---
```
User → React (built as static files) served directly by FastAPI on one port
                              ↓
                        FastAPI Backend → SQLite (chunks/chats/users)
                              ↓
                  Auto-Router (complexity + language)
                    ↓          ↓           ↓
                 Ollama      Groq       Gemini
                (local)    (cloud)     (cloud)
```

> Frontend and backend are served from a single port — the React app is built (`npm run build`) and mounted as static files by FastAPI, so only one deployment target / tunnel is needed.

---

## 📁 Project Structure

```
LexiRAG_Project/
├── main.py              # FastAPI app, routes, auth, static file mount
├── database.py           # SQLite operations, password hashing
├── embeddings.py          # sentence-transformers, language detection
├── rag.py                 # RAG pipeline, LLM routing, prompts
├── requirements.txt
├── .env                   # API keys (git-ignored)
└── lexirag-react/          # React frontend (Vite)
    ├── src/
    │   ├── pages/          # Chat.jsx, Login.jsx, Signup.jsx
    │   └── styles/
    └── dist/                # Production build (git-ignored, generated)
```

## 🚀 Getting Started

### Backend
```bash
# Activate virtual environment
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Add API keys to .env
GROQ_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here
REDIS_URL=your_redis_connection_string

# Run server
uvicorn main:app --reload
```

### Frontend
```bash
cd lexirag-react
npm install
npm run build      # generates dist/, served automatically by FastAPI at localhost:8000
```

### Ollama (for offline mode)
```bash
ollama serve
ollama pull gemma2:2b
```

---

## 📌 Known Limitations

- Gemini free-tier quota is limited
- Groq models are periodically deprecated by the provider — verify model name at [console.groq.com](https://console.groq.com/docs/deprecations)
- Document upload/embedding generation is CPU-bound; very large PDFs may take noticeably longer

---

## 🗺️ Roadmap

- [ ] Deploy backend to Azure for Students
- [ ] CI/CD pipeline (GitHub Actions → Azure)
- [ ] Background job queue (Redis + task queue) for non-blocking document processing
- [ ] Multiple file upload in one go
- [ ] Self-hosted Ollama on Raspberry Pi / Orange Pi

---

## 👤 Author

**Mohammed Rayhan** — B.Tech CSE, REVA University, Bengaluru

[GitHub](https://github.com/mohammedrayhanrayhan78-cell/LexiRAG_Project)