import numpy as np
import requests
import json
from database import get_all_chunks
from embeddings import detect_language

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def find_relevant_chunks(query_embedding, top_k=4):
    all_chunks = get_all_chunks()
    if not all_chunks:
        return []
    
    scored = []
    for chunk in all_chunks:
        score = cosine_similarity(query_embedding, chunk["embedding"])
        scored.append((score, chunk))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    return [chunk for score, chunk in scored[:top_k]]

def ask_gemma_stream(question, context_chunks):
    if not context_chunks:
        yield "No relevant documents found. Please upload a document first."
        return

    lang_code, lang_name = detect_language(question)
    
    context = "\n\n".join([f"[From: {c['doc_name']}]\n{c['chunk_text']}" for c in context_chunks])

    if lang_code == 'en':
        lang_instruction = "Answer in English."
    else:
        lang_instruction = f"The user is asking in {lang_name}. Answer in {lang_name} language."

    prompt = f"""You are a helpful assistant. Answer the question using ONLY the context provided below.
If the answer is not in the context, say so in the same language as the question.
{lang_instruction}

Context:
{context}

Question: {question}

Answer:"""

    response = requests.post("http://localhost:11434/api/generate", json={
        "model": "gemma2:2b",
        "prompt": prompt,
        "stream": True
    }, stream=True)
    
    for line in response.iter_lines():
        if line:
            data = json.loads(line)
            if "response" in data:
                yield data["response"]
            if data.get("done"):
                break