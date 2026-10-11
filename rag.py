import numpy as np
import requests
import json
import os
import logging
from database import get_all_chunks
from embeddings import detect_language

logger = logging.getLogger("lexirag.rag")

# API keys come from environment variables only (never hard-code them)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def classify_complexity(question):
    """
    Decide if a question is SIMPLE or COMPLEX
    
    WHY: Route simple questions to fast cloud models (Groq/Gemini)
    (kept for compatibility; routing now depends on language, with automatic fallback)
    
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

# ============================================
# LLM PROVIDERS (Groq + Gemini) with safe fallback
# ============================================

class LLMUnavailable(Exception):
    """Raised when no provider could answer. The message is always safe to show to users."""

GENERIC_LLM_ERROR = "The AI service is temporarily unavailable. Please try again in a moment."
NO_CONTEXT_MESSAGE = "No relevant documents found. Please upload a document first."
CONNECT_TIMEOUT = 5
READ_TIMEOUT = 60


def _stream_groq(prompt):
    """Yield tokens from Groq. Raises LLMUnavailable (with a safe message) on any failure."""
    if not GROQ_API_KEY:
        raise LLMUnavailable("groq key missing")
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
            stream=True,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)
        )
    except requests.RequestException as e:
        logger.warning("groq request failed: %s", type(e).__name__)
        raise LLMUnavailable("groq unreachable") from None

    with response:
        if response.status_code != 200:
            logger.warning("groq returned status %s", response.status_code)
            raise LLMUnavailable("groq bad status")
        try:
            for line in response.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8")
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    delta = json.loads(data_str)["choices"][0]["delta"]
                except (ValueError, KeyError, IndexError):
                    continue
                if delta.get("content"):
                    yield delta["content"]
        except requests.RequestException as e:
            logger.warning("groq stream interrupted: %s", type(e).__name__)
            raise LLMUnavailable("groq stream interrupted") from None


def _stream_gemini(prompt):
    """Yield tokens from Gemini. Key is sent in a header (never in the URL, so it cannot leak into errors)."""
    if not GEMINI_API_KEY:
        raise LLMUnavailable("gemini key missing")
    try:
        response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:streamGenerateContent?alt=sse",
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": GEMINI_API_KEY
            },
            json={"contents": [{"parts": [{"text": prompt}]}]},
            stream=True,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)
        )
    except requests.RequestException as e:
        logger.warning("gemini request failed: %s", type(e).__name__)
        raise LLMUnavailable("gemini unreachable") from None

    with response:
        if response.status_code != 200:
            logger.warning("gemini returned status %s", response.status_code)
            raise LLMUnavailable("gemini bad status")
        try:
            for line in response.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8")
                if not line.startswith("data: "):
                    continue
                try:
                    parts = json.loads(line[6:])["candidates"][0]["content"]["parts"]
                except (ValueError, KeyError, IndexError):
                    continue
                text = "".join(p.get("text", "") for p in parts)
                if text:
                    yield text
        except requests.RequestException as e:
            logger.warning("gemini stream interrupted: %s", type(e).__name__)
            raise LLMUnavailable("gemini stream interrupted") from None


PROVIDERS = {"groq": _stream_groq, "gemini": _stream_gemini}


# --- MAIN ROUTER (AUTO-SELECTS MODEL, FALLS BACK AUTOMATICALLY) ---
def ask_llm_stream(question, context_chunks, mode="auto", info=None):
    """
    Stream an answer.

    - mode="auto": non-English questions -> Gemini (strong multilingual),
      everything else -> Groq (fast). If the chosen provider fails BEFORE
      sending any text, the other provider is tried automatically.
    - mode="groq" / "gemini": that provider first, the other as fallback.
      Any other value (including the removed "ollama") behaves like "groq".
    - `info` (optional dict) receives {"provider": <provider that actually answered>}.
    - On total failure raises LLMUnavailable with a user-safe message.
    """
    if info is None:
        info = {}

    if not context_chunks:
        yield NO_CONTEXT_MESSAGE
        return

    prompt = build_prompt(question, context_chunks)

    if mode == "auto":
        lang_code, _ = detect_language(question)
        first = "gemini" if lang_code != "en" else "groq"
    elif mode in PROVIDERS:
        first = mode
    else:
        first = "groq"

    order = [first] + [p for p in PROVIDERS if p != first]

    for provider in order:
        started = False
        try:
            for token in PROVIDERS[provider](prompt):
                if not started:
                    started = True
                    info["provider"] = provider
                yield token
            if started:
                return
        except LLMUnavailable:
            if started:
                # Failed halfway: do not mix two models in one answer
                raise LLMUnavailable(GENERIC_LLM_ERROR) from None
            continue

    raise LLMUnavailable(GENERIC_LLM_ERROR)
