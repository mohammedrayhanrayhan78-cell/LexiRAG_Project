import numpy as np
import requests
import json
import os
from database import get_all_chunks
from embeddings import detect_language

# API Keys - add your actual keys here
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "GROQ_API_KEY_HERE")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "GEMINI_API_KEY_HERE")

def classify_complexity(question):
    """
    Decide if a question is SIMPLE or COMPLEX
    
    WHY: Route simple questions to fast cloud models (Groq/Gemini)
    and complex questions to Ollama (local, more compute time available)
    
    LOGIC:
    - Word count > 15 = likely complex (multi-part question)
    - Certain keywords indicate deep reasoning needed
    """
    word_count = len(question.split())
    
    complex_keywords = [
        'compare', 'explain in detail', 'analyze', 'why does', 'why is',
        'how does', 'difference between', 'pros and cons', 'summarize',
        'evaluate', 'relationship between', 'implications', 'in depth'
    ]
    
    question_lower = question.lower()
    
    # If long question OR contains complex reasoning keywords = complex
    if word_count > 15 or any(kw in question_lower for kw in complex_keywords):
        return 'complex'
    
    return 'simple'

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

FORMATTING RULES:
- Use markdown formatting to make answers easy to scan
- Use bullet points (-) for lists of items, features, or steps
- Use **bold** for key terms or important values
- Use short paragraphs (2-3 sentences max) instead of long blocks of text
- Use numbered lists for sequential steps
- Keep it clean and structured, not one giant paragraph

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
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:streamGenerateContent?alt=sse&key={GEMINI_API_KEY}",
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

# --- MAIN ROUTER (AUTO-SELECTS MODEL) ---
def ask_llm_stream(question, context_chunks, mode="auto"):
    """
    If mode="auto", automatically pick the best model:
    - Complex questions -> Ollama (local)
    - Simple English questions -> Groq (fast)
    - Simple regional language questions -> Gemini (strong multilingual)
    
    If mode is explicitly set (manual override), respect it.
    """
    if mode == "auto":
        complexity = classify_complexity(question)
        lang_code, _ = detect_language(question)

        if complexity == 'complex':
            selected_mode = 'ollama'
        elif lang_code != 'en':
            selected_mode = 'gemini'
        else:
            selected_mode = 'groq'
    else:
        selected_mode = mode

    if selected_mode == "groq":
        yield from ask_groq_stream(question, context_chunks)
    elif selected_mode == "gemini":
        yield from ask_gemini_stream(question, context_chunks)
    else:
        yield from ask_ollama_stream(question, context_chunks)