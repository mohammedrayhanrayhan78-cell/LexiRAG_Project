"""Provider routing + fallback tests (no network, no API keys needed)."""
import os
import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-not-for-production-0123456789")

import rag
from rag import ask_llm_stream, LLMUnavailable, GENERIC_LLM_ERROR

CHUNKS = [{"doc_name": "a.txt", "chunk_text": "hello world", "similarity": 1.0}]


def _ok(name):
    def gen(prompt):
        yield f"{name}-answer"
    return gen


def _fail(prompt):
    raise LLMUnavailable("down")
    yield  # pragma: no cover


def _patch(monkeypatch, groq, gemini):
    monkeypatch.setitem(rag.PROVIDERS, "groq", groq)
    monkeypatch.setitem(rag.PROVIDERS, "gemini", gemini)


def test_english_goes_to_groq(monkeypatch):
    _patch(monkeypatch, _ok("groq"), _ok("gemini"))
    info = {}
    assert "".join(ask_llm_stream("What is the notice period for the lease?", CHUNKS, info=info)) == "groq-answer"
    assert info["provider"] == "groq"


def test_hindi_goes_to_gemini(monkeypatch):
    _patch(monkeypatch, _ok("groq"), _ok("gemini"))
    info = {}
    list(ask_llm_stream("\u0921\u093f\u092a\u0949\u091c\u093c\u093f\u091f \u0915\u092c \u0935\u093e\u092a\u0938 \u092e\u093f\u0932\u0947\u0917\u093e? \u0915\u0943\u092a\u092f\u093e \u092c\u0924\u093e\u0907\u090f\u0964", CHUNKS, info=info))
    assert info["provider"] == "gemini"


def test_groq_down_falls_back_to_gemini(monkeypatch):
    _patch(monkeypatch, _fail, _ok("gemini"))
    info = {}
    assert "".join(ask_llm_stream("What is this?", CHUNKS, mode="groq", info=info)) == "gemini-answer"
    assert info["provider"] == "gemini"


def test_both_down_raises_safe_message(monkeypatch):
    _patch(monkeypatch, _fail, _fail)
    with pytest.raises(LLMUnavailable) as e:
        list(ask_llm_stream("What is this?", CHUNKS))
    assert str(e.value) == GENERIC_LLM_ERROR


def test_legacy_ollama_mode_uses_groq(monkeypatch):
    _patch(monkeypatch, _ok("groq"), _ok("gemini"))
    info = {}
    list(ask_llm_stream("What is this?", CHUNKS, mode="ollama", info=info))
    assert info["provider"] == "groq"


def test_midstream_failure_does_not_mix_models(monkeypatch):
    def half(prompt):
        yield "partial"
        raise LLMUnavailable("cut")
    _patch(monkeypatch, half, _ok("gemini"))
    out = []
    with pytest.raises(LLMUnavailable):
        for t in ask_llm_stream("What is this?", CHUNKS, mode="groq"):
            out.append(t)
    assert out == ["partial"]


def test_missing_secret_key_refuses_to_start(tmp_path):
    import subprocess, sys
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    env = {k: v for k, v in os.environ.items() if k not in ("JWT_SECRET_KEY", "SECRET_KEY")}
    env["PYTHONPATH"] = repo_dir
    r = subprocess.run([sys.executable, "-c", "import main"], env=env, capture_output=True, text=True,
                       cwd=str(tmp_path))
    assert r.returncode != 0 and "JWT_SECRET_KEY" in r.stderr
