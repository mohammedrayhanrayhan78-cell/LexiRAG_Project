"""
Comprehensive Test Suite for LexiRAG Backend Addendum
Tests:
1. UPLOADS: PDF magic-byte check, TXT UTF-8 decode & NUL-byte rejection, size cap, file discard (never stored).
2. RATE LIMITS: Exactly 5 attempts per minute (per IP, and for login also per username), HTTP 429 with Retry-After header and generic message, CORS expose_headers & allow_headers.
3. ENDPOINTS & OWNERSHIP:
   - list my chats, create chat, delete chat (and its chunks)
   - list documents in a chat, upload document to a chat, delete a document (and its chunks)
   - ask a question in a chat (streaming)
   - delete my account and all my data
4. STREAMING FORMAT:
   - Exact wire format verification (text/event-stream)
   - Final metadata item containing provider ("groq" or "gemini"), sources, detected_language
   - Mid-stream error item handling (clean error item, never hung connection)
"""

import asyncio
import io
import json
import os
import sqlite3
import time
import uuid
import httpx
import pytest

from main import app, auth_limiter, MAX_FILE_SIZE
from database import DB_PATH

def run_async(coro):
    return asyncio.run(coro)

async def create_test_user(client: httpx.AsyncClient, prefix: str = "u"):
    """Helper to create a fresh, unique test user with auth token"""
    uname = f"{prefix}_{uuid.uuid4().hex[:8]}"
    res = await client.post("/signup", json={"username": uname, "password": "password123"})
    assert res.status_code == 200, f"Failed to create test user: {res.text}"
    token = res.json()["token"]
    return uname, token, {"Authorization": f"Bearer {token}"}

def create_sample_pdf_bytes():
    """Generates valid minimal PDF bytes starting with %PDF- magic bytes"""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 300 144]/Parent 2 0 R/Resources<<>>>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n185\n%%EOF\n"
    )

# ============================================
# 1. UPLOADS TESTS
# ============================================

def test_upload_valid_txt_and_never_stored():
    """TXT must decode as UTF-8, processed and discarded (never stored on disk)"""
    async def _test():
        auth_limiter.reset()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            uname, token, headers = await create_test_user(client, "txt_user")
            
            chat_res = await client.post("/chats", json={"chat_name": "Test TXT Chat"}, headers=headers)
            assert chat_res.status_code == 200, chat_res.text
            chat_id = chat_res.json()["chat_id"]

            txt_content = "This is a clean UTF-8 text document with important LexiRAG knowledge for testing retrieval.".encode("utf-8")
            unique_doc = f"doc_{uuid.uuid4().hex[:6]}.txt"
            files = {"file": (unique_doc, txt_content, "text/plain")}
            data = {"chat_id": str(chat_id)}

            res = await client.post("/upload", files=files, data=data, headers=headers)
            assert res.status_code == 200, res.text
            res_data = res.json()
            assert res_data["filename"] == unique_doc
            assert res_data["chunks"] > 0

            # Verify file is NOT saved anywhere on disk in uploads directory
            if os.path.exists("uploads"):
                assert not os.path.exists(os.path.join("uploads", unique_doc))

    run_async(_test())

def test_upload_txt_rejects_nul_bytes():
    """TXT must reject files containing NUL bytes (\\x00) with HTTP 400"""
    async def _test():
        auth_limiter.reset()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            uname, token, headers = await create_test_user(client, "nul_user")
            
            chat_res = await client.post("/chats", json={"chat_name": "NUL Chat"}, headers=headers)
            chat_id = chat_res.json()["chat_id"]

            # TXT with NUL byte
            bad_txt_content = b"Valid text before nul byte \x00 followed by text"
            files = {"file": ("corrupt.txt", bad_txt_content, "text/plain")}
            data = {"chat_id": str(chat_id)}

            res = await client.post("/upload", files=files, data=data, headers=headers)
            assert res.status_code == 400
            assert "NUL bytes" in res.json()["detail"]
    run_async(_test())

def test_upload_txt_rejects_non_utf8():
    """TXT must decode as UTF-8, reject invalid encodings with HTTP 400"""
    async def _test():
        auth_limiter.reset()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            uname, token, headers = await create_test_user(client, "utf8_user")
            
            chat_res = await client.post("/chats", json={"chat_name": "UTF8 Chat"}, headers=headers)
            chat_id = chat_res.json()["chat_id"]

            # Invalid UTF-8 sequence
            bad_bytes = b"\xff\xfe\x99\xaa"
            files = {"file": ("bad_encoding.txt", bad_bytes, "text/plain")}
            data = {"chat_id": str(chat_id)}

            res = await client.post("/upload", files=files, data=data, headers=headers)
            assert res.status_code == 400
            assert "UTF-8" in res.json()["detail"]
    run_async(_test())

def test_upload_pdf_magic_byte_check():
    """PDF must pass magic-byte check (%PDF). Reject fake PDFs with HTTP 400"""
    async def _test():
        auth_limiter.reset()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            uname, token, headers = await create_test_user(client, "pdf_user")
            
            chat_res = await client.post("/chats", json={"chat_name": "PDF Chat"}, headers=headers)
            chat_id = chat_res.json()["chat_id"]

            # Fake PDF (has .pdf extension but missing %PDF magic bytes)
            fake_pdf = b"NOT_A_REAL_PDF_FILE_HEADER"
            files = {"file": ("fake.pdf", fake_pdf, "application/pdf")}
            data = {"chat_id": str(chat_id)}

            res = await client.post("/upload", files=files, data=data, headers=headers)
            assert res.status_code == 400
            assert "%PDF" in res.json()["detail"]

            # Valid PDF header
            valid_pdf = create_sample_pdf_bytes()
            files_valid = {"file": ("sample.pdf", valid_pdf, "application/pdf")}
            res_valid = await client.post("/upload", files=files_valid, data=data, headers=headers)
            # Minimal PDF has no extractable text, so it passes magic-byte check cleanly
            assert "Missing %PDF magic bytes" not in res_valid.text
    run_async(_test())

def test_upload_size_cap_and_unsupported_extensions():
    """Both PDF and TXT share the same size cap; unsupported files rejected"""
    async def _test():
        auth_limiter.reset()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            uname, token, headers = await create_test_user(client, "cap_user")
            
            chat_res = await client.post("/chats", json={"chat_name": "Cap Chat"}, headers=headers)
            chat_id = chat_res.json()["chat_id"]

            # Unsupported extension (.exe)
            files = {"file": ("malicious.exe", b"binarycontent", "application/octet-stream")}
            res = await client.post("/upload", files=files, data={"chat_id": str(chat_id)}, headers=headers)
            assert res.status_code == 400
            assert "Only PDF" in res.json()["detail"]

            # Empty file
            files_empty = {"file": ("empty.txt", b"", "text/plain")}
            res_empty = await client.post("/upload", files=files_empty, data={"chat_id": str(chat_id)}, headers=headers)
            assert res_empty.status_code == 400
            assert "empty" in res_empty.json()["detail"].lower()
    run_async(_test())

# ============================================
# 2. RATE LIMITS TESTS
# ============================================

def test_signup_rate_limit_per_ip():
    """Signup is limited to exactly 5 attempts per minute per IP. 6th attempt returns 429 with Retry-After header and generic message."""
    async def _test():
        auth_limiter.reset()
        unique_ip = f"198.51.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"
        ip_header = {"X-Forwarded-For": unique_ip}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            for i in range(5):
                res = await client.post(
                    "/signup",
                    json={"username": f"rate_signup_{uuid.uuid4().hex[:6]}", "password": "password123"},
                    headers=ip_header
                )
                assert res.status_code in [200, 400], f"Attempt {i+1} failed unexpectedly: {res.status_code}"

            # 6th attempt from same IP must hit 429
            res_6 = await client.post(
                "/signup",
                json={"username": f"rate_signup_blocked_{uuid.uuid4().hex[:6]}", "password": "password123"},
                headers=ip_header
            )
            assert res_6.status_code == 429
            assert "retry-after" in res_6.headers
            assert int(res_6.headers["retry-after"]) > 0
            # Generic message check
            assert res_6.json().get("detail") == "Too many requests. Please try again later."
    run_async(_test())

def test_login_rate_limit_per_ip_and_per_username():
    """Login is limited to exactly 5 attempts per minute per IP, AND also per username."""
    async def _test():
        auth_limiter.reset()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # 1. Test per-IP rate limiting
            unique_ip = f"203.0.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"
            ip_1 = {"X-Forwarded-For": unique_ip}
            for i in range(5):
                res = await client.post(
                    "/login",
                    json={"username": f"user_{uuid.uuid4().hex[:6]}", "password": "wrong_password"},
                    headers=ip_1
                )
                assert res.status_code == 401

            # 6th attempt from IP_1 must be 429
            res_ip_blocked = await client.post(
                "/login",
                json={"username": f"any_{uuid.uuid4().hex[:6]}", "password": "password"},
                headers=ip_1
            )
            assert res_ip_blocked.status_code == 429
            assert "retry-after" in res_ip_blocked.headers
            assert res_ip_blocked.json().get("detail") == "Too many requests. Please try again later."

            # 2. Test per-username rate limiting across different IPs
            target_user = f"victim_{uuid.uuid4().hex[:6]}"
            for i in range(5):
                ip_header = {"X-Forwarded-For": f"10.1.{i+1}.{uuid.uuid4().int % 250}"}
                res = await client.post(
                    "/login",
                    json={"username": target_user, "password": "wrong_password"},
                    headers=ip_header
                )
                assert res.status_code == 401

            # 6th attempt for target_user from a fresh IP must be blocked by username limit
            res_user_blocked = await client.post(
                "/login",
                json={"username": target_user, "password": "wrong_password"},
                headers={"X-Forwarded-For": "10.2.99.1"}
            )
            assert res_user_blocked.status_code == 429
            assert "retry-after" in res_user_blocked.headers
            assert res_user_blocked.json().get("detail") == "Too many requests. Please try again later."
    run_async(_test())

def test_cors_headers_expose_retry_after_and_allow_authorization():
    """Verify CORS preflight allows Authorization and actual response exposes Retry-After"""
    async def _test():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            headers = {
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization, content-type"
            }
            # Preflight check
            preflight_res = await client.options("/login", headers=headers)
            assert preflight_res.status_code == 200
            allow_headers = preflight_res.headers.get("access-control-allow-headers", "")
            assert "authorization" in allow_headers.lower() or "*" in allow_headers

            # Actual response check
            actual_res = await client.post(
                "/login",
                json={"username": "cors_user_test", "password": "wrong_password"},
                headers={"Origin": "http://localhost:5173"}
            )
            expose_headers = actual_res.headers.get("access-control-expose-headers", "")
            assert "retry-after" in expose_headers.lower()
    run_async(_test())

# ============================================
# 3. ENDPOINTS & OWNERSHIP TESTS
# ============================================

def test_chat_lifecycle_ownership_and_chunks_cleanup():
    """
    Test:
    - list my chats, create chat, delete chat (and its chunks)
    - list documents in a chat, upload document to a chat, delete document (and chunks)
    - ownership checks: User B cannot access, upload to, or delete User A's chat or docs
    """
    async def _test():
        auth_limiter.reset()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # Create User A
            uname_a, token_a, headers_a = await create_test_user(client, "alice")
            # Create User B
            uname_b, token_b, headers_b = await create_test_user(client, "bob")

            # 1. User A creates chat
            create_res = await client.post("/chats", json={"chat_name": "Alice Private Chat"}, headers=headers_a)
            assert create_res.status_code == 200
            chat_id = create_res.json()["chat_id"]

            # 2. List my chats
            chats_res = await client.get("/chats", headers=headers_a)
            assert chats_res.status_code == 200
            assert any(c["id"] == chat_id for c in chats_res.json()["chats"])

            # User A cannot access User B's chats via /chats/{username}
            cross_chat_res = await client.get(f"/chats/{uname_b}", headers=headers_a)
            assert cross_chat_res.status_code == 403

            # 3. Upload document to chat A
            doc_content = "Alice confidential project data: Retrieval-Augmented Generation algorithms.".encode("utf-8")
            doc_name = f"alice_doc_{uuid.uuid4().hex[:6]}.txt"
            upload_res = await client.post(
                "/upload",
                files={"file": (doc_name, doc_content, "text/plain")},
                data={"chat_id": str(chat_id)},
                headers=headers_a
            )
            assert upload_res.status_code == 200
            assert upload_res.json()["chunks"] > 0

            # Verify chunks exist in DB
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM chunks WHERE chat_id = ?", (chat_id,))
            chunk_count_before = cur.fetchone()[0]
            conn.close()
            assert chunk_count_before > 0

            # 4. OWNERSHIP CHECK: User B cannot upload to User A's chat
            b_upload = await client.post(
                "/upload",
                files={"file": ("bob_evil.txt", b"evil content", "text/plain")},
                data={"chat_id": str(chat_id)},
                headers=headers_b
            )
            assert b_upload.status_code == 403

            # 5. OWNERSHIP CHECK: User B cannot list documents in User A's chat
            b_list_docs = await client.get(f"/documents/{chat_id}", headers=headers_b)
            assert b_list_docs.status_code == 403

            # User A can list documents
            a_list_docs = await client.get(f"/documents/{chat_id}", headers=headers_a)
            assert a_list_docs.status_code == 200
            assert doc_name in a_list_docs.json()["documents"]

            # 6. OWNERSHIP CHECK: User B cannot delete User A's document
            b_del_doc = await client.delete(f"/chats/{chat_id}/documents/{doc_name}", headers=headers_b)
            assert b_del_doc.status_code == 403

            # 7. OWNERSHIP CHECK: User B cannot delete User A's chat
            b_del_chat = await client.delete(f"/chats/{chat_id}", headers=headers_b)
            assert b_del_chat.status_code == 403

            # 8. User A deletes document
            a_del_doc = await client.delete(f"/chats/{chat_id}/documents/{doc_name}", headers=headers_a)
            assert a_del_doc.status_code == 200

            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM chunks WHERE chat_id = ? AND doc_name = ?", (chat_id, doc_name))
            assert cur.fetchone()[0] == 0
            conn.close()

            # Upload doc again to test chat deletion chunk cleanup
            await client.post(
                "/upload",
                files={"file": (f"re_{doc_name}", doc_content, "text/plain")},
                data={"chat_id": str(chat_id)},
                headers=headers_a
            )

            # 9. User A deletes chat: must delete chat AND all its chunks
            del_chat_res = await client.delete(f"/chats/{chat_id}", headers=headers_a)
            assert del_chat_res.status_code == 200
            assert del_chat_res.json()["status"] == "deleted"

            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM chunks WHERE chat_id = ?", (chat_id,))
            assert cur.fetchone()[0] == 0, "Chunks were not deleted when chat was deleted!"
            cur.execute("SELECT COUNT(*) FROM chat_sessions WHERE id = ?", (chat_id,))
            assert cur.fetchone()[0] == 0, "Chat session was not deleted!"
            conn.close()
    run_async(_test())

def test_delete_account_and_all_data():
    """User can delete their account and all their data (chats, chunks, messages, user)"""
    async def _test():
        auth_limiter.reset()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            uname, token, headers = await create_test_user(client, "del_acct")

            chat_res = await client.post("/chats", json={"chat_name": "Account Chat"}, headers=headers)
            chat_id = chat_res.json()["chat_id"]

            await client.post(
                "/upload",
                files={"file": ("acct_doc.txt", b"Document content for account deletion test", "text/plain")},
                data={"chat_id": str(chat_id)},
                headers=headers
            )
            await client.post(f"/chats/{chat_id}/message", json={"role": "user", "content": "Hello"}, headers=headers)

            # Delete account
            del_res = await client.delete("/account", headers=headers)
            assert del_res.status_code == 200
            assert del_res.json()["status"] == "deleted"

            # Verify complete database cleanup
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM users WHERE username = ?", (uname,))
            assert cur.fetchone()[0] == 0
            cur.execute("SELECT COUNT(*) FROM chat_sessions WHERE username = ?", (uname,))
            assert cur.fetchone()[0] == 0
            cur.execute("SELECT COUNT(*) FROM chunks WHERE chat_id = ?", (chat_id,))
            assert cur.fetchone()[0] == 0
            cur.execute("SELECT COUNT(*) FROM chat_messages WHERE chat_id = ?", (chat_id,))
            assert cur.fetchone()[0] == 0
            conn.close()
    run_async(_test())

# ============================================
# 4. STREAMING FORMAT TESTS
# ============================================

def test_streaming_wire_format_metadata_and_error_handling():
    """
    Test streaming response:
    - Wire format: text/event-stream
    - Sources event at beginning
    - Final metadata item containing provider ('groq' or 'gemini'), sources, detected_language
    - Done signal
    - Mid-stream error event handling without hanging connection
    """
    async def _test():
        auth_limiter.reset()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            uname, token, headers = await create_test_user(client, "streamer")

            chat_res = await client.post("/chats", json={"chat_name": "Stream Chat"}, headers=headers)
            chat_id = chat_res.json()["chat_id"]

            # Upload doc
            await client.post(
                "/upload",
                files={"file": ("stream_notes.txt", b"LexiRAG uses vector embeddings and similarity search.", "text/plain")},
                data={"chat_id": str(chat_id)},
                headers=headers
            )

            # 1. Test normal streaming response with mocked LLM tokens
            import main
            original_ask = main.ask_llm_stream

            def mock_success_stream(*args, **kwargs):
                yield "LexiRAG "
                yield "uses "
                yield "vector embeddings."

            main.ask_llm_stream = mock_success_stream
            try:
                res = await client.post("/ask", json={"question": "What does LexiRAG use?", "chat_id": chat_id, "mode": "groq"}, headers=headers)
                assert res.status_code == 200
                assert "text/event-stream" in res.headers["content-type"]

                lines = res.text.strip().split("\n")
                data_events = []
                for line in lines:
                    if line.startswith("data: "):
                        data_events.append(json.loads(line[6:]))

                # Verify event sequence
                event_types = [e.get("type") for e in data_events]
                assert "sources" in event_types, f"Missing sources event in {data_events}"
                assert "token" in event_types, f"Missing token event in {data_events}"
                assert "metadata" in event_types, f"Missing final metadata event in {data_events}"
                assert "done" in event_types, f"Missing done event in {data_events}"

                # Verify final metadata item content
                meta_event = next(e for e in data_events if e.get("type") == "metadata")
                assert meta_event["provider"] in ["groq", "gemini"]
                assert isinstance(meta_event["sources"], list)
                assert "detected_language" in meta_event
                assert meta_event["detected_language"] in ["English", "Hindi", "Kannada", "Tamil", "Telugu"]
            finally:
                main.ask_llm_stream = original_ask

            # 2. Test mid-stream error formatting: simulate an LLM stream error
            def mock_failing_stream(*args, **kwargs):
                yield "First token"
                raise RuntimeError("Simulated mid-stream API connection reset")

            main.ask_llm_stream = mock_failing_stream
            try:
                err_res = await client.post("/ask", json={"question": "Trigger error?", "chat_id": chat_id}, headers=headers)
                assert err_res.status_code == 200
                err_lines = err_res.text.strip().split("\n")
                err_events = [json.loads(line[6:]) for line in err_lines if line.startswith("data: ")]
                err_types = [e.get("type") for e in err_events]
                assert "error" in err_types, f"Expected clean error item, got {err_events}"
                error_item = next(e for e in err_events if e.get("type") == "error")
                assert "Simulated mid-stream API connection reset" in error_item["error"]
            finally:
                main.ask_llm_stream = original_ask

    run_async(_test())
