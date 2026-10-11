# LexiRAG backend (API only). The React frontend deploys separately as a static site.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    FASTEMBED_CACHE_DIR=/opt/fastembed

# Tesseract OCR with English + Indian language packs
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin tesseract-ocr-kan \
        tesseract-ocr-tam tesseract-ocr-tel \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Download the embedding model at build time so the first request is not slow
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/all-MiniLM-L6-v2', cache_dir='/opt/fastembed')"

COPY main.py rag.py database.py embeddings.py ./

RUN useradd --create-home appuser && chown -R appuser /app /opt/fastembed
USER appuser

# Render injects $PORT. Single worker keeps memory low.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
