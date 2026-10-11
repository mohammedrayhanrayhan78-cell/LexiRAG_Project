// ============================================
// API.JS - Centralized LexiRAG API Client
// ============================================
// - Reads public API URL from import.meta.env.VITE_API_URL
// - Keeps JWT in memory with sessionStorage as reload fallback (never localStorage)
// - Handles 401 by clearing token and triggering session expiration handler
// ============================================

export const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

// In-memory token storage initialized from sessionStorage
let inMemoryToken = typeof window !== 'undefined' ? sessionStorage.getItem('lexirag_token') : null;
let inMemoryUsername = typeof window !== 'undefined' ? sessionStorage.getItem('lexirag_user') : null;

// Session expired listeners
const authListeners = new Set();

export function onAuthExpired(callback) {
  authListeners.add(callback);
  return () => authListeners.delete(callback);
}

function notifyAuthExpired() {
  clearToken();
  authListeners.forEach((cb) => {
    try { cb(); } catch (e) { console.error('Auth listener error:', e); }
  });
}

export function getToken() {
  if (!inMemoryToken && typeof window !== 'undefined') {
    inMemoryToken = sessionStorage.getItem('lexirag_token');
  }
  return inMemoryToken;
}

export function setToken(token, username = null) {
  inMemoryToken = token;
  if (typeof window !== 'undefined') {
    if (token) {
      sessionStorage.setItem('lexirag_token', token);
    } else {
      sessionStorage.removeItem('lexirag_token');
    }
  }
  if (username) {
    inMemoryUsername = username;
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('lexirag_user', username);
    }
  }
}

export function getUsername() {
  if (!inMemoryUsername && typeof window !== 'undefined') {
    inMemoryUsername = sessionStorage.getItem('lexirag_user');
  }
  return inMemoryUsername || 'User';
}

export function clearToken() {
  inMemoryToken = null;
  inMemoryUsername = null;
  if (typeof window !== 'undefined') {
    sessionStorage.removeItem('lexirag_token');
    sessionStorage.removeItem('lexirag_user');
    localStorage.removeItem('token');
    localStorage.removeItem('username');
  }
}

export function isAuthenticated() {
  return Boolean(getToken());
}

/**
 * Standard fetch wrapper with automatic JWT header, 401 handling, and error unpacking
 */
export async function apiFetch(path, options = {}) {
  const url = `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
  const headers = { ...(options.headers || {}) };

  const token = getToken();
  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url, { ...options, headers });

  if (response.status === 401) {
    notifyAuthExpired();
    const errorData = await response.json().catch(() => ({}));
    const error = new Error(errorData.detail || 'Session expired');
    error.status = 401;
    throw error;
  }

  if (response.status === 429) {
    const retryAfter = response.headers.get('Retry-After');
    const errorData = await response.json().catch(() => ({}));
    const error = new Error(errorData.detail || 'Too many requests. Please try again later.');
    error.status = 429;
    error.retryAfter = retryAfter ? parseInt(retryAfter, 10) : 60;
    throw error;
  }

  return response;
}

// Background wake-up ping for Render free tier
export async function pingHealth() {
  try {
    const res = await fetch(`${API_BASE}/healthz`);
    return res.ok;
  } catch {
    return false;
  }
}

// Auth API
export async function loginUser(username, password) {
  const res = await apiFetch('/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Invalid username or password');
  }
  const data = await res.json();
  setToken(data.token, data.username || username);
  return data;
}

export async function signupUser(username, password) {
  const res = await apiFetch('/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Could not create account');
  }
  const data = await res.json();
  setToken(data.token, data.username || username);
  return data;
}

export async function deleteAccount() {
  const res = await apiFetch('/account', { method: 'DELETE' });
  if (!res.ok) {
    throw new Error('Could not delete account');
  }
  clearToken();
  return true;
}

// Chats API
export async function fetchChats() {
  const res = await apiFetch('/chats');
  if (!res.ok) throw new Error('Failed to load chats');
  const data = await res.json();
  return data.chats || [];
}

export async function createChat(chatName) {
  const res = await apiFetch('/chats', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_name: chatName }),
  });
  if (!res.ok) throw new Error('Failed to create chat');
  return res.json();
}

export async function renameChat(chatId, newName) {
  const res = await apiFetch(`/chats/${chatId}/rename`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_name: newName }),
  });
  if (!res.ok) throw new Error('Failed to rename chat');
  return res.json();
}

export async function deleteChat(chatId) {
  const res = await apiFetch(`/chats/${chatId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete chat');
  return res.json();
}

export async function fetchMessages(chatId) {
  const res = await apiFetch(`/chats/${chatId}/messages`);
  if (!res.ok) throw new Error('Failed to load messages');
  return res.json();
}

// Documents API
export async function fetchDocuments(chatId) {
  const res = await apiFetch(`/chats/${chatId}/documents`);
  if (!res.ok) throw new Error('Failed to load documents');
  const data = await res.json();
  return data.documents || [];
}

export async function uploadDocument(chatId, file) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('chat_id', String(chatId));

  const res = await apiFetch(`/chats/${chatId}/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to upload document');
  }
  return res.json();
}

export async function deleteDocument(chatId, docName) {
  const res = await apiFetch(`/chats/${chatId}/documents/${encodeURIComponent(docName)}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete document');
  return res.json();
}
