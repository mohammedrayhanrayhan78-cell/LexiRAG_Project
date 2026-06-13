from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import pdfplumber
import os
import json
from database import init_db, save_chunk, delete_document, get_documents
from embeddings import get_embedding
from rag import find_relevant_chunks, ask_llm_stream

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def extract_text_from_pdf(filepath):
    text = ""
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def extract_text_from_txt(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()

def extract_text(filepath):
    if filepath.endswith('.txt'):
        return extract_text_from_txt(filepath)
    else:
        return extract_text_from_pdf(filepath)

def split_into_chunks(text, chunk_size=300):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - 50):
        chunk = " ".join(words[i:i+chunk_size])
        chunks.append(chunk)
    return chunks

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(filepath, "wb") as f:
        f.write(await file.read())
    
    text = extract_text(filepath)
    chunks = split_into_chunks(text)
    
    for chunk in chunks:
        embedding = get_embedding(chunk)
        save_chunk(file.filename, chunk, embedding)
    
    return {"message": f"Uploaded and processed {len(chunks)} chunks from {file.filename}"}

@app.post("/ask")
async def ask_question(payload: dict):
    question = payload.get("question")
    mode = payload.get("mode", "ollama")  # ollama / groq / gemini
    query_embedding = get_embedding(question)
    relevant_chunks = find_relevant_chunks(query_embedding)
    sources = list(set([c["doc_name"] for c in relevant_chunks]))

    def stream():
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
        for token in ask_llm_stream(question, relevant_chunks, mode=mode):
            yield f"data: {json.dumps({'type': 'token', 'text': token})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")

@app.delete("/document/{doc_name}")
async def delete_doc(doc_name: str):
    delete_document(doc_name)
    return {"message": f"Deleted {doc_name}"}

@app.get("/health")
async def health():
    return {"status": "LexiRAG is running"}

@app.get("/documents")
async def list_documents():
    docs = get_documents()
    return {"documents": docs}