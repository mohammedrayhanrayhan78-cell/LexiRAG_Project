# ⚡ LexiRAG — Local AI Document Assistant

> Ask questions about your documents. Completely offline. No API keys. No internet needed.

LexiRAG is an offline RAG (Retrieval Augmented Generation) system that lets you upload PDFs and ask questions about them in natural language — including Indian regional languages like Hindi, Kannada, Tamil, and Telugu.

Built with a real RAG pipeline: local embeddings, vector similarity search, and a locally running LLM via Ollama.

---

## Features

- **100% Offline** — No internet required after setup. Your documents never leave your machine.
- **Regional Language Support** — Ask questions in Hindi, Kannada, Tamil, Telugu, or English.
- **Streaming Answers** — Responses stream token by token like ChatGPT.
- **Source Citations** — Every answer shows which document it came from.
- **Document Management** — Upload multiple PDFs, delete them anytime.
- **Clean Dark UI** — Cyberpunk-themed interface, mobile responsive.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, Vanilla JS |
| Backend | Python, FastAPI |
| Local LLM | Ollama + Gemma 2B |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Vector Storage | SQLite (cosine similarity search) |
| PDF Processing | pdfplumber |
| Language Detection | langdetect |

---

## How It Works

```
User uploads PDF
      ↓
Extract text (pdfplumber)
      ↓
Split into 300-word chunks with overlap
      ↓
Generate embeddings locally (sentence-transformers)
      ↓
Store chunks + embeddings in SQLite
      ↓
User asks a question
      ↓
Convert question to embedding
      ↓
Find top 4 most similar chunks (cosine similarity)
      ↓
Send question + context to Ollama (Gemma 2B)
      ↓
Stream answer back with source citation
```

---

## Setup & Run

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.ai) installed

### 1. Clone the repo
```bash
git clone https://github.com/mohammedrayhanrayhan78-cell/LexiRAG_Project.git
cd LexiRAG_Project
```

### 2. Create virtual environment
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux
```

### 3. Install dependencies
```bash
pip install fastapi uvicorn pdfplumber sentence-transformers langdetect numpy requests
```

### 4. Download embedding model
```bash
python -c "from huggingface_hub import snapshot_download; snapshot_download('sentence-transformers/all-MiniLM-L6-v2', local_dir='./models/all-MiniLM-L6-v2')"
```

### 5. Pull Gemma 2B via Ollama
```bash
ollama pull gemma2:2b
```

### 6. Start Ollama (separate terminal)
```bash
ollama serve
```

### 7. Start FastAPI backend
```bash
uvicorn main:app --reload
```

### 8. Open the app
Open `index.html` in your browser. That's it.

---

## Project Structure

```
LexiRAG/
├── main.py          # FastAPI backend, all API routes
├── database.py      # SQLite operations (save, retrieve, delete chunks)
├── embeddings.py    # Sentence transformer model, language detection
├── rag.py           # Cosine similarity search, Ollama streaming
├── index.html       # Frontend UI
├── models/          # Local embedding model
├── uploads/         # Uploaded documents
└── lexirag.db       # SQLite database
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/upload` | Upload and process a PDF/TXT file |
| POST | `/ask` | Ask a question (streaming SSE response) |
| GET | `/documents` | List all uploaded documents |
| DELETE | `/document/{name}` | Delete a document |
| GET | `/health` | Health check |

---

## Roadmap

- [x] Core RAG pipeline
- [x] Streaming responses
- [x] Regional language support
- [x] Document management (upload/delete)
- [ ] GCP Cloud deployment
- [ ] Mobile app (React Native)
- [ ] Multi-document Q&A
- [ ] Audio input support

---

## Built By

**Mohammed Rayhan** — 1st Year CSE Student, REVA University, Bengaluru  
DSA Club Coordinator | Generative AI + Cloud enthusiast

> *"Spend time on RAG since it can be one life-changing project."* — Senior advice that started this.

---

## License

MIT License — free to use, modify, and distribute.