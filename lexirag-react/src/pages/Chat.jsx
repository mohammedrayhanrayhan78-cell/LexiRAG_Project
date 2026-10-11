import React, { useState, useEffect, useRef, useCallback, memo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import RetroWindow from '../components/RetroWindow';
import RetroButton from '../components/RetroButton';
import RetroField from '../components/RetroField';
import RetroDialog from '../components/RetroDialog';
import {
  BoltIcon,
  FolderIcon,
  FileDocIcon,
  WarningIcon,
  SparkleIcon
} from '../components/RetroIcons';
import {
  API_BASE,
  getToken,
  getUsername,
  clearToken,
  fetchChats,
  createChat,
  renameChat,
  deleteChat,
  fetchMessages,
  fetchDocuments,
  uploadDocument,
  deleteDocument,
  deleteAccount,
  pingHealth
} from '../api';

// Safe markdown renderer component (Phase B6)
const SafeMarkdown = memo(function SafeMarkdown({ content }) {
  return (
    <ReactMarkdown
      components={{
        a: ({ node, ...props }) => (
          <a {...props} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--red)', fontWeight: 600 }} />
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
});

// Memoized message item component (Phase B7)
const MessageItem = memo(function MessageItem({ msg }) {
  const isUser = msg.role === 'user';

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: isUser ? 'flex-end' : 'flex-start',
        width: '100%',
        margin: '6px 0',
      }}
    >
      <div
        style={{
          maxWidth: '85%',
          padding: '12px 16px',
          background: isUser ? 'var(--yellow)' : 'var(--field)',
          border: 'var(--border)',
          borderRadius: '4px',
          boxShadow: '2px 2px 0 var(--ink)',
          fontSize: '14px',
          lineHeight: '1.5',
          wordBreak: 'break-word',
        }}
      >
        {isUser ? (
          <div style={{ whiteSpace: 'pre-wrap', fontWeight: 500 }}>{msg.content}</div>
        ) : (
          <SafeMarkdown content={msg.content} />
        )}
      </div>

      {!isUser && (msg.provider || msg.source || msg.sources) && (
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '4px', fontSize: '11px', fontWeight: 600 }}>
          {msg.provider && (
            <span className="chip model" style={{ textTransform: 'capitalize', minHeight: '22px', padding: '0 8px' }}>
              {msg.provider}
            </span>
          )}
          {(msg.source || (msg.sources && msg.sources.length > 0)) && (
            <span style={{ color: 'rgba(59, 30, 23, 0.7)' }}>
              Source: {msg.source || msg.sources.join(', ')}
            </span>
          )}
        </div>
      )}
    </div>
  );
});

export default function Chat() {
  const navigate = useNavigate();
  const { chatId: routeChatId } = useParams();
  const username = getUsername();

  // State
  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState(routeChatId ? parseInt(routeChatId, 10) : null);
  const [messages, setMessages] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [detectedLanguage, setDetectedLanguage] = useState('auto-detect');
  const [backendWakingUp, setBackendWakingUp] = useState(false);
  const [isOffline, setIsOffline] = useState(typeof navigator !== 'undefined' ? !navigator.onLine : false);
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    const handleOnline = () => setIsOffline(false);
    const handleOffline = () => setIsOffline(true);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Modal dialog states
  const [dialogState, setDialogState] = useState({ isOpen: false, type: null, target: null, message: '' });
  const [renameInput, setRenameInput] = useState({ isOpen: false, chatId: null, name: '' });

  const abortControllerRef = useRef(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  // Initial load: wake up backend, fetch chats
  useEffect(() => {
    let isMounted = true;

    async function init() {
      try {
        const ok = await pingHealth();
        if (!ok && isMounted) {
          setBackendWakingUp(true);
        }
      } catch {
        if (isMounted) setBackendWakingUp(true);
      }

      try {
        const userChats = await fetchChats();
        if (!isMounted) return;
        setChats(userChats);
        setBackendWakingUp(false);

        if (userChats.length > 0) {
          const targetId = routeChatId ? parseInt(routeChatId, 10) : userChats[0].id;
          const found = userChats.find((c) => c.id === targetId) || userChats[0];
          setActiveChatId(found.id);
        }
      } catch (err) {
        if (isMounted && err.status !== 401) {
          setErrorMessage('Could not load chats. Server may be starting up...');
        }
      }
    }

    init();
    return () => { isMounted = false; };
  }, [routeChatId]);

  // Load active chat's messages and documents
  useEffect(() => {
    if (!activeChatId) {
      setMessages([]);
      setDocuments([]);
      return;
    }

    let isMounted = true;
    async function loadChatData() {
      try {
        const [msgsRes, docs] = await Promise.all([
          fetchMessages(activeChatId).catch(() => ({ messages: [] })),
          fetchDocuments(activeChatId).catch(() => []),
        ]);
        if (!isMounted) return;
        setMessages(msgsRes.messages || []);
        setDocuments(docs);
      } catch (err) {
        console.error('Failed to load chat data:', err);
      }
    }

    loadChatData();
    return () => { isMounted = false; };
  }, [activeChatId]);

  // Actions
  const handleLogout = () => {
    clearToken();
    navigate('/login', { replace: true });
  };

  const handleCreateChat = async () => {
    try {
      const res = await createChat('New Chat');
      const newChat = { id: res.chat_id, name: res.chat_name, created_at: new Date().toISOString() };
      setChats((prev) => [newChat, ...prev]);
      setActiveChatId(newChat.id);
      navigate(`/chat/${newChat.id}`);
      setMobileMenuOpen(false);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to create chat.');
    }
  };

  const handleStartRename = (chat, e) => {
    e.stopPropagation();
    setRenameInput({ isOpen: true, chatId: chat.id, name: chat.name });
  };

  const handleSaveRename = async () => {
    if (!renameInput.name.trim()) return;
    try {
      await renameChat(renameInput.chatId, renameInput.name.trim());
      setChats((prev) =>
        prev.map((c) => (c.id === renameInput.chatId ? { ...c, name: renameInput.name.trim() } : c))
      );
      setRenameInput({ isOpen: false, chatId: null, name: '' });
    } catch (err) {
      setErrorMessage(err.message || 'Failed to rename chat.');
    }
  };

  const handleDeleteChatConfirm = (chat, e) => {
    e.stopPropagation();
    setDialogState({
      isOpen: true,
      type: 'delete_chat',
      target: chat.id,
      message: `Delete chat "${chat.name}" and all its documents and messages?`,
    });
  };

  const handleDeleteDocConfirm = (docName) => {
    setDialogState({
      isOpen: true,
      type: 'delete_doc',
      target: docName,
      message: `Delete document "${docName}" from this chat?`,
    });
  };

  const handleDeleteAccountConfirm = () => {
    setDialogState({
      isOpen: true,
      type: 'delete_account',
      target: null,
      message: 'Are you sure you want to delete your entire account and all data? This cannot be undone.',
    });
  };

  const handleDialogConfirm = async () => {
    const { type, target } = dialogState;
    setDialogState({ isOpen: false, type: null, target: null, message: '' });

    try {
      if (type === 'delete_chat') {
        await deleteChat(target);
        const remaining = chats.filter((c) => c.id !== target);
        setChats(remaining);
        if (activeChatId === target) {
          const next = remaining.length > 0 ? remaining[0].id : null;
          setActiveChatId(next);
          if (next) navigate(`/chat/${next}`);
          else navigate('/chat');
        }
      } else if (type === 'delete_doc') {
        await deleteDocument(activeChatId, target);
        setDocuments((prev) => prev.filter((d) => d !== target));
      } else if (type === 'delete_account') {
        await deleteAccount();
        navigate('/login', { replace: true });
      }
    } catch (err) {
      setErrorMessage(err.message || 'Action failed.');
    }
  };

  // Upload handling (PDF & TXT only, size check, OCR notice)
  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !activeChatId) return;
    e.target.value = '';

    const lower = file.name.toLowerCase();
    const isPdf = lower.endsWith('.pdf') || file.type === 'application/pdf';
    const isTxt = lower.endsWith('.txt') || file.type === 'text/plain';

    if (!isPdf && !isTxt) {
      setErrorMessage('Unsupported format. Only PDF and TXT files are accepted.');
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      setErrorMessage('File size exceeds the 10MB limit.');
      return;
    }

    setUploading(true);
    setErrorMessage('');
    try {
      await uploadDocument(activeChatId, file);
      setDocuments((prev) => (prev.includes(file.name) ? prev : [...prev, file.name]));
      // Update chat name if it's default
      const current = chats.find((c) => c.id === activeChatId);
      if (current && (current.name === 'New Chat' || current.name === 'Chat')) {
        await renameChat(activeChatId, file.name);
        setChats((prev) =>
          prev.map((c) => (c.id === activeChatId ? { ...c, name: file.name } : c))
        );
      }
    } catch (err) {
      setErrorMessage(err.message || 'Upload failed. File might be corrupted or empty.');
    } finally {
      setUploading(false);
    }
  };

  // Streaming ask question
  const handleAsk = async (e) => {
    e.preventDefault();
    if (!question.trim() || !activeChatId || loading) return;

    const userPrompt = question.trim();
    setQuestion('');
    setErrorMessage('');

    // Append user message immediately
    const userMsg = { role: 'user', content: userPrompt };
    setMessages((prev) => [...prev, userMsg]);

    // Prepare bot placeholder
    const botMsgId = Date.now();
    const initialBotMsg = { id: botMsgId, role: 'bot', content: '', provider: null, sources: [] };
    setMessages((prev) => [...prev, initialBotMsg]);

    setLoading(true);
    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch(`${API_BASE}/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getToken()}`,
        },
        body: JSON.stringify({
          question: userPrompt,
          chat_id: activeChatId,
          mode: 'auto',
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        if (response.status === 401) {
          clearToken();
          navigate('/login', { replace: true });
          return;
        }
        const errJson = await response.json().catch(() => ({}));
        throw new Error(errJson.detail || 'Failed to query assistant.');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let botContent = '';
      let botProvider = null;
      let botSources = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // keep last incomplete line in buffer

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data:')) continue;
          const jsonStr = trimmed.slice(5).trim();
          if (!jsonStr) continue;

          try {
            const event = JSON.parse(jsonStr);

            if (event.type === 'token') {
              botContent += event.text;
              setMessages((prev) =>
                prev.map((m) => (m.id === botMsgId ? { ...m, content: botContent } : m))
              );
            } else if (event.type === 'sources') {
              botSources = event.sources || [];
              setMessages((prev) =>
                prev.map((m) => (m.id === botMsgId ? { ...m, sources: botSources } : m))
              );
            } else if (event.type === 'metadata' || event.type === 'done') {
              if (event.provider) botProvider = event.provider;
              if (event.sources) botSources = event.sources;
              if (event.detected_language) setDetectedLanguage(event.detected_language);
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === botMsgId
                    ? { ...m, provider: botProvider, sources: botSources }
                    : m
                )
              );
            } else if (event.type === 'error') {
              botContent += `\n\n[Error: ${event.error || 'Connection dropped. Please retry.'}]`;
              setMessages((prev) =>
                prev.map((m) => (m.id === botMsgId ? { ...m, content: botContent } : m))
              );
            }
          } catch {
            // ignore non-json SSE lines
          }
        }
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        setMessages((prev) =>
          prev.map((m) => (m.id === botMsgId ? { ...m, content: m.content + ' [Stopped by user]' } : m))
        );
      } else {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === botMsgId
              ? { ...m, content: m.content || 'An error occurred while answering. Please try again.' }
              : m
          )
        );
        setErrorMessage(err.message || 'Stream interrupted.');
      }
    } finally {
      setLoading(false);
      abortControllerRef.current = null;
    }
  };

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  const activeChat = chats.find((c) => c.id === activeChatId);

  return (
    <div style={{
      minHeight: '100vh',
      padding: '20px 24px 48px',
      display: 'flex',
      flexDirection: 'column',
      gap: '20px',
      position: 'relative',
    }}>
      {/* Top Navigation Bar */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '14px',
        width: '100%',
        maxWidth: '1360px',
        margin: '0 auto',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <RetroButton
            className="deco-mobile-toggle"
            variant="alt"
            size="sm"
            style={{ display: 'none' }}
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            ariaLabel="Toggle Sidebar"
          >
            ☰
          </RetroButton>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <BoltIcon size={32} />
            <span style={{
              fontFamily: 'var(--font-display)',
              fontWeight: 800,
              fontSize: '28px',
              letterSpacing: '-0.02em',
              lineHeight: 1
            }}>
              LexiRAG
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px' }}>
          <span className="chip" style={{ minHeight: '32px' }}>
            Language: {detectedLanguage}
          </span>
          <RetroButton variant="alt" size="sm" onClick={handleLogout}>
            Log out
          </RetroButton>
        </div>
      </div>

      {/* Backend cold start wake-up banner */}
      {backendWakingUp && (
        <div style={{
          maxWidth: '1360px',
          margin: '0 auto',
          width: '100%',
          padding: '12px 16px',
          background: 'var(--yellow)',
          border: 'var(--border)',
          borderRadius: '4px',
          boxShadow: 'var(--shadow-btn)',
          fontWeight: 700,
          fontSize: '13px',
          display: 'flex',
          alignItems: 'center',
          gap: '10px'
        }}>
          <WarningIcon size={20} />
          <span>Server is waking up (Render free-tier cold start), this can take up to a minute...</span>
        </div>
      )}

      {/* Offline indicator banner */}
      {isOffline && (
        <div style={{
          maxWidth: '1360px',
          margin: '0 auto',
          width: '100%',
          padding: '12px 16px',
          background: 'var(--red)',
          color: 'var(--cream-light)',
          border: 'var(--border)',
          borderRadius: '4px',
          boxShadow: 'var(--shadow-btn)',
          fontWeight: 700,
          fontSize: '13px',
          display: 'flex',
          alignItems: 'center',
          gap: '10px'
        }}>
          <WarningIcon size={20} />
          <span>You appear to be offline. Network requests will fail until connection is restored.</span>
        </div>
      )}

      {/* Main 3-Column Content Layout */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'stretch',
        gap: '20px',
        width: '100%',
        maxWidth: '1360px',
        margin: '0 auto',
        flex: 1,
      }}>
        {/* Left Column: My Chats & Who Answers */}
        <div style={{
          flex: '0 0 280px',
          display: 'flex',
          flexDirection: 'column',
          gap: '20px',
          minWidth: '260px',
        }}>
          {/* Chats Window */}
          <RetroWindow title="My chats" variant="amber">
            <div style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <RetroButton onClick={handleCreateChat} style={{ width: '100%' }}>
                + New chat
              </RetroButton>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '280px', overflowY: 'auto' }}>
                {chats.length === 0 ? (
                  <div style={{ fontSize: '13px', color: 'rgba(59, 30, 23, 0.6)', padding: '8px 0', textAlign: 'center' }}>
                    No chats yet
                  </div>
                ) : (
                  chats.map((chat) => (
                    <div
                      key={chat.id}
                      className={`chatrow ${chat.id === activeChatId ? 'on' : ''}`}
                      onClick={() => {
                        setActiveChatId(chat.id);
                        navigate(`/chat/${chat.id}`);
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: 1 }}>
                        <FolderIcon size={20} />
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {chat.name}
                        </span>
                      </div>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        <button
                          type="button"
                          onClick={(e) => handleStartRename(chat, e)}
                          title="Rename"
                          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '2px', fontSize: '12px' }}
                        >
                          ✎
                        </button>
                        <button
                          type="button"
                          onClick={(e) => handleDeleteChatConfirm(chat, e)}
                          title="Delete"
                          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '2px', fontSize: '12px', color: 'var(--red)' }}
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </RetroWindow>

          {/* Who Answers Window (Groq & Gemini ONLY - Phase B5) */}
          <RetroWindow title="Who answers" variant="lilac">
            <div style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ padding: '8px 10px', background: 'var(--cream-light)', border: '1.5px solid var(--ink)', borderRadius: '3px' }}>
                <div style={{ fontWeight: 800, fontSize: '13px', color: 'var(--red)' }}>Groq</div>
                <div style={{ fontSize: '12px' }}>for quick English questions</div>
              </div>
              <div style={{ padding: '8px 10px', background: 'var(--cream-light)', border: '1.5px solid var(--ink)', borderRadius: '3px' }}>
                <div style={{ fontWeight: 800, fontSize: '13px', color: '#1a73e8' }}>Gemini</div>
                <div style={{ fontSize: '12px' }}>for regional languages (Hindi, Kannada, Tamil, Telugu)</div>
              </div>
            </div>
          </RetroWindow>

          {/* Account & Data Management Window */}
          <RetroWindow title="Account" variant="red">
            <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ fontSize: '13px', fontWeight: 600 }}>User: {username}</div>
              <RetroButton
                variant="danger"
                size="sm"
                onClick={handleDeleteAccountConfirm}
                style={{ width: '100%' }}
              >
                Delete account &amp; data
              </RetroButton>
            </div>
          </RetroWindow>
        </div>

        {/* Center Column: Chat Messages & Input */}
        <div style={{
          flex: '1 1 500px',
          display: 'flex',
          flexDirection: 'column',
          minWidth: '320px',
        }}>
          <RetroWindow
            title={activeChat ? activeChat.name : 'Select a Chat'}
            variant="red"
            style={{ height: '100%', minHeight: '620px', display: 'flex', flexDirection: 'column' }}
          >
            {/* Messages Display Area */}
            <div style={{
              flex: 1,
              padding: '16px',
              overflowY: 'auto',
              maxHeight: '520px',
              display: 'flex',
              flexDirection: 'column',
              background: 'var(--cream-light)',
            }}>
              {messages.length === 0 ? (
                <div style={{
                  margin: 'auto',
                  textAlign: 'center',
                  padding: '32px 16px',
                  color: 'rgba(59, 30, 23, 0.75)',
                  maxWidth: '380px'
                }}>
                  <SparkleIcon size={32} style={{ margin: '0 auto 12px' }} />
                  <div style={{ fontWeight: 800, fontSize: '16px', marginBottom: '6px' }}>Nothing here yet</div>
                  <div style={{ fontSize: '13px', lineHeight: '1.4' }}>
                    Ask a question about the documents in this chat and the answer shows up here with sources attached.
                  </div>
                </div>
              ) : (
                messages.map((m, idx) => (
                  <MessageItem key={m.id || idx} msg={m} />
                ))
              )}
              {loading && !messages.some((m) => m.role === 'bot' && m.content) && (
                <div style={{ fontSize: '13px', fontStyle: 'italic', color: 'rgba(59, 30, 23, 0.7)', padding: '8px' }}>
                  Thinking &amp; streaming response...
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Error banner if any */}
            {errorMessage && (
              <div style={{
                padding: '8px 14px',
                background: 'var(--red)',
                color: 'var(--cream-light)',
                fontSize: '12px',
                fontWeight: 600,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}>
                <span>{errorMessage}</span>
                <button
                  type="button"
                  onClick={() => setErrorMessage('')}
                  style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', fontWeight: 800 }}
                >
                  ✕
                </button>
              </div>
            )}

            {/* Input Form */}
            <form onSubmit={handleAsk} style={{
              padding: '14px',
              borderTop: 'var(--border)',
              background: 'var(--cream)',
              display: 'flex',
              gap: '10px',
              alignItems: 'center'
            }}>
              <input
                type="text"
                className="fld"
                placeholder={activeChatId ? "Ask a question about your documents..." : "Create or select a chat first"}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                disabled={!activeChatId}
                style={{ flex: 1 }}
              />
              {loading ? (
                <RetroButton variant="danger" type="button" onClick={handleStop}>
                  Stop
                </RetroButton>
              ) : (
                <RetroButton type="submit" disabled={!activeChatId || !question.trim()}>
                  Send
                </RetroButton>
              )}
            </form>
          </RetroWindow>
        </div>

        {/* Right Column: Documents Attached to Active Chat */}
        <div style={{
          flex: '0 0 280px',
          display: 'flex',
          flexDirection: 'column',
          gap: '20px',
          minWidth: '260px',
        }}>
          {/* Documents Window */}
          <RetroWindow title="Documents" variant="red">
            <div style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {/* Upload Button */}
              <label style={{ display: 'block', width: '100%' }}>
                <input
                  type="file"
                  accept=".pdf,.txt"
                  onChange={handleFileUpload}
                  disabled={!activeChatId || uploading}
                  style={{ display: 'none' }}
                />
                <span className="btn" style={{
                  width: '100%',
                  pointerEvents: (!activeChatId || uploading) ? 'none' : 'auto',
                  opacity: (!activeChatId || uploading) ? 0.6 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px'
                }}>
                  {uploading ? 'Reading file...' : '+ Upload file'}
                </span>
              </label>

              {uploading && (
                <div style={{
                  padding: '8px',
                  background: 'var(--yellow)',
                  border: '1px solid var(--ink)',
                  borderRadius: '3px',
                  fontSize: '11px',
                  lineHeight: '1.3'
                }}>
                  Reading file / scanned pages are read with OCR...
                </div>
              )}

              {/* Document list */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '300px', overflowY: 'auto' }}>
                {documents.length === 0 ? (
                  <div style={{ fontSize: '13px', color: 'rgba(59, 30, 23, 0.6)', textAlign: 'center', padding: '12px 0' }}>
                    No documents attached yet.
                  </div>
                ) : (
                  documents.map((doc) => (
                    <div
                      key={doc}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '8px 10px',
                        background: 'var(--cream-light)',
                        border: '1.5px solid var(--ink)',
                        borderRadius: '3px',
                        fontSize: '13px',
                        fontWeight: 600,
                        gap: '8px'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0 }}>
                        <FileDocIcon size={16} />
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {doc}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleDeleteDocConfirm(doc)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--red)', fontWeight: 800 }}
                        title="Delete document"
                      >
                        ✕
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          </RetroWindow>

          {/* Heads Up Privacy Note */}
          <RetroWindow title="Heads up" variant="amber">
            <div style={{ padding: '14px', fontSize: '12px', lineHeight: '1.45', display: 'flex', gap: '8px' }}>
              <WarningIcon size={20} />
              <span>Your document text is sent to Groq or Gemini to answer questions.</span>
            </div>
          </RetroWindow>
        </div>
      </div>

      {/* Retro Confirm Modal */}
      <RetroDialog
        isOpen={dialogState.isOpen}
        title="Confirm action"
        message={dialogState.message}
        danger={dialogState.type === 'delete_account' || dialogState.type === 'delete_chat'}
        confirmText="Confirm"
        onConfirm={handleDialogConfirm}
        onCancel={() => setDialogState({ isOpen: false, type: null, target: null, message: '' })}
      />

      {/* Rename Chat Modal */}
      {renameInput.isOpen && (
        <div style={{
          position: 'fixed',
          inset: 0,
          backgroundColor: 'rgba(59, 30, 23, 0.45)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          padding: '16px',
        }}>
          <RetroWindow title="Rename chat" variant="amber" style={{ width: '100%', maxWidth: '380px' }}>
            <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <RetroField
                label="New chat name"
                id="rename-chat"
                value={renameInput.name}
                onChange={(e) => setRenameInput((p) => ({ ...p, name: e.target.value }))}
                autoFocus
              />
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                <RetroButton variant="alt" onClick={() => setRenameInput({ isOpen: false, chatId: null, name: '' })}>
                  Cancel
                </RetroButton>
                <RetroButton onClick={handleSaveRename}>
                  Save
                </RetroButton>
              </div>
            </div>
          </RetroWindow>
        </div>
      )}
    </div>
  );
}