import numpy as np
import requests
import json
import os
from database import get_all_chunks
from embeddings import detect_language

# API Keys - add your actual keys here
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "grok_api_key_here")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "gemini_api_key_here")

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

def build_prompt(question, context_chunks):
    lang_code, lang_name = detect_language(question)
    context = "\n\n".join([f"[From: {c['doc_name']}]\n{c['chunk_text']}" for c in context_chunks])

    if lang_code == 'en':
        lang_instruction = "Answer in English."
    else:
        lang_instruction = f"The user is asking in {lang_name}. Answer in {lang_name} language."

    prompt = f"""You are LexiRAG, a humble, polite and helpful AI document assistant. 
Always be respectful, kind, and encouraging in your responses.
Answer the question using ONLY the context provided below.
If the answer is not in the context, politely say so in the same language as the question.
{lang_instruction}

Context:
{context}

Question: {question}

Answer:"""
    return prompt

# --- OLLAMA (fully offline) ---
def ask_ollama_stream(question, context_chunks):
    if not context_chunks:
        yield "No relevant documents found. Please upload a document first."
        return

    prompt = build_prompt(question, context_chunks)

    try:
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
    except Exception as e:
        yield f"Ollama error: {str(e)}. Make sure Ollama is running locally."

# --- GROQ (online, fast, free) ---
def ask_groq_stream(question, context_chunks):
    if not context_chunks:
        yield "No relevant documents found. Please upload a document first."
        return

    if not GROQ_API_KEY:
        yield "Groq API key not set."
        return

    prompt = build_prompt(question, context_chunks)

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "stream": True
            },
            stream=True
        )

        if response.status_code != 200:
            yield f"Groq Error: {response.text}"
            return

        for line in response.iter_lines():
            if line:
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0]["delta"]
                        if "content" in delta:
                            yield delta["content"]
                    except:
                        continue
    except Exception as e:
        yield f"Groq error: {str(e)}"

# --- GEMINI (online, powerful) ---
def ask_gemini_stream(question, context_chunks):
    if not context_chunks:
        yield "No relevant documents found. Please upload a document first."
        return

    if not GEMINI_API_KEY:
        yield "Gemini API key not set."
        return

    prompt = build_prompt(question, context_chunks)

    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:streamGenerateContent?alt=sse&key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}]
            },
            stream=True
        )

        if response.status_code != 200:
            yield f"Gemini Error: {response.text}"
            return

        for line in response.iter_lines():
            if line:
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        text = data["candidates"][0]["content"]["parts"][0]["text"]
                        yield text
                    except:
                        continue
    except Exception as e:
        yield f"Gemini error: {str(e)}"

# --- MAIN ROUTER ---
def ask_llm_stream(question, context_chunks, mode="ollama"):
    if mode == "groq":
        yield from ask_groq_stream(question, context_chunks)
    elif mode == "gemini":
        yield from ask_gemini_stream(question, context_chunks)
    else:
        yield from ask_ollama_stream(question, context_chunks)