import { useState, useEffect } from 'react';
import axios from 'axios';
import '../styles/Chat.css';
import ReactMarkdown from 'react-markdown';

/**
 * CHAT COMPONENT - Main chat interface
 * 
 * FEATURES:
 * - Multiple chats per user
 * - Upload documents per chat (auto-rename chat to filename)
 * - Ask questions about documents
 * - Switch between LLM modes (Ollama, Groq, Gemini)
 * - All requests include JWT token for security
 * - Gets username from localStorage (set during login)
 * 
 * PROPS:
 * - onLogout: function to call when user logs out
 */
export default function Chat({ onLogout }) {
  // ============================================
  // STATE VARIABLES
  // ============================================
  
  const [documents, setDocuments] = useState([]);  // Docs in current chat
  const [messages, setMessages] = useState([]);    // Messages in current chat
  const [question, setQuestion] = useState('');    // User's current input
  const [loading, setLoading] = useState(false);   // Is LLM responding?
  const [chats, setChats] = useState([]);          // All chats for user
  const [currentChatId, setCurrentChatId] = useState(null); // Active chat ID
  const [chatRenamed, setChatRenamed] = useState({}); // Track if chat was already renamed
  
  // API BASE URL - Works on localhost AND ngrok
  // If you need ngrok: change to 'https://octopus-domestic-clicker.ngrok-free.dev'
  const API = '';
  
  // ============================================
  // HELPER - Get username from localStorage
  // ============================================
  /**
   * Get username saved during login
   * Username is used in GET /chats/{username} request
   */
  const getUsername = () => {
    return localStorage.getItem('username');
  };
  
  // ============================================
  // HELPER - Get JWT token from localStorage
  // ============================================
  /**
   * Get JWT token saved during login
   * Token is used in Authorization header for all requests
   */
  const getToken = () => {
    return localStorage.getItem('token');
  };
  
  // ============================================
  // HELPER - Get Authorization header with token
  // ============================================
  /**
   * Create header object with JWT token
   * Format: { 'Authorization': 'Bearer {token}' }
   * This is added to EVERY axios request
   */
  const getAuthHeader = () => {
    const token = getToken();
    return {
      'Authorization': `Bearer ${token}`
    };
  };
  
  // ============================================
  // HELPER - Extract first word from filename
  // ============================================
  /**
   * Get only the first word of filename
   * EXAMPLE: "Dr_Kalyana_Kumar_Recommendation_Letter.pdf" → "Dr_Kalyana_Kumar"
   * This keeps chat names short and readable
   */
  const getShortFilename = (filename) => {
    // Remove file extension first
    const nameWithoutExt = filename.split('.').slice(0, -1).join('.');
    
    // Take only first meaningful part (before underscore or space)
    // If there are underscores, take everything up to 3rd underscore
    // This gives us a good balance
    const parts = nameWithoutExt.split('_');
    
    // If filename has underscores, take first 3 parts
    if (parts.length > 1) {
      return parts.slice(0, 3).join('_'); // e.g., "Dr_Kalyana_Kumar"
    }
    
    // Otherwise just return the name (or first 30 chars if very long)
    return nameWithoutExt.substring(0, 30);
  };
  
  // ============================================
  // EFFECT 1 - Load chats when component mounts
  // ============================================
  /**
   * Runs ONCE when Chat component is created
   * Loads all chats for the logged-in user
   */
  useEffect(() => {
    loadChats();
  }, []);
  
  // ============================================
  // EFFECT 2 - Load documents when chat changes
  // ============================================
  /**
   * Runs when currentChatId changes
   * Fetches list of documents in the selected chat
   */
  useEffect(() => {
    if (currentChatId) {
      fetchDocuments();
    }
  }, [currentChatId]);
  
  // ============================================
  // FUNCTION - Load all chats for current user
  // ============================================
  /**
   * GET /chats/{username}
   * 
   * ENDPOINT: Retrieve all chats for logged-in user
   * SECURITY: Requires JWT token + username must match token's username
   * RETURNS: Array of chats with id, name, created_at
   * 
   * FLOW:
   * 1. Get username and token from localStorage
   * 2. Send GET request with token in Authorization header
   * 3. If successful = update chats state
   * 4. If fails = log error (user not logged in or token expired)
   */
  const loadChats = async () => {
    try {
      const token = getToken();
      const username = getUsername();
      
      // Security check: must have both token and username
      if (!token || !username) {
        console.error('No token or username. User may not be logged in.');
        return;
      }
      
      // GET request to fetch chats
      const res = await axios.get(
        `${API}/chats/${username}`,
        {
          headers: getAuthHeader()  // ✅ SEND TOKEN HERE
        }
      );
      
      // Update state with chats list
      // Update state with chats list
      const chatList = res.data.chats || [];
      setChats(chatList);
      
      // Restore last-open chat after refresh, if it still exists
      const savedChatId = localStorage.getItem('lastChatId');
      if (savedChatId && chatList.some(c => c.id === parseInt(savedChatId))) {
        switchChat(parseInt(savedChatId));
      }
    } catch (err) {
      console.error('Failed to load chats:', err.message);
      // Don't show alert - just log silently in case token expired
    }
  };
  
  // ============================================
  // FUNCTION - Create new chat
  // ============================================
  /**
   * POST /chats/new
   * 
   * ENDPOINT: Create new chat for logged-in user
   * SECURITY: Requires JWT token
   * RETURNS: chat_id (integer) to use for uploads/messages
   * 
   * FLOW:
   * 1. Send POST request with username and chat_name
   * 2. Backend creates chat in database
   * 3. Returns chat_id
   * 4. Set as current chat
   * 5. Reload chat list
   */
  const createNewChat = async () => {
    // Ask user to confirm before creating new chat
    if (!window.confirm('Create a new chat?')) return;
    
    try {
      const username = getUsername();
      
      if (!username) {
        alert('Not logged in. Please refresh and login again.');
        return;
      }
      
      // POST request to create new chat
      const res = await axios.post(
        `${API}/chats/new`,
        {
          username: username,
          chat_name: 'New Chat'
        },
        {
          headers: getAuthHeader()  // ✅ SEND TOKEN HERE
        }
      );
      
      // Set this chat as current
      setCurrentChatId(res.data.chat_id);
      localStorage.setItem('lastChatId', res.data.chat_id);  // Remember for refresh
      setMessages([]); // Clear messages
      
      // Track that this chat has NOT been renamed yet
      setChatRenamed(prev => ({
        ...prev,
        [res.data.chat_id]: false
      }));
      
      // Reload chat list to show new chat
      await loadChats();
    } catch (err) {
      console.error('Failed to create chat:', err.message);
      alert(`Failed to create chat: ${err.message}`);
    }
  };
  
  // ============================================
  // FUNCTION - Switch to different chat
  // ============================================
  /**
   * GET /chats/{chat_id}/messages
   * 
   * ENDPOINT: Retrieve all messages from a specific chat
   * SECURITY: Requires JWT token (user must be logged in)
   * RETURNS: Array of messages with role (user/bot) and content
   * 
   * FLOW:
   * 1. Send GET request for chat's messages
   * 2. Convert message format to match state structure
   * 3. Update messages state to show in UI
   */
  const switchChat = async (chatId) => {
    try {
      // GET request to fetch messages for this chat
      const res = await axios.get(
        `${API}/chats/${chatId}/messages`,
        {
          headers: getAuthHeader()  // ✅ SEND TOKEN HERE
        }
      );
      
      // Set this as current chat
      setCurrentChatId(chatId);
      localStorage.setItem('lastChatId', chatId);  // Remember for refresh
      
      // Convert messages: {role, content} -> {type, text}
      const formattedMessages = res.data.messages.map(m => ({
        type: m.role,      // "user" or "bot"
        text: m.content    // actual message text
      }));
      
      setMessages(formattedMessages);
    } catch (err) {
      console.error('Failed to load chat messages:', err.message);
    }
  };
  
  // ============================================
  // FUNCTION - Load documents in current chat
  // ============================================
  /**
   * GET /documents/{chat_id}
   * 
   * ENDPOINT: Retrieve all documents uploaded to this chat
   * SECURITY: Only shows docs from THIS chat (chat isolation)
   * Returns: Array of document filenames
   * 
   * FLOW:
   * 1. Send GET request with current chat_id
   * 2. Backend returns list of documents in that chat
   * 3. Update documents state
   */
  const fetchDocuments = async () => {
    if (!currentChatId) return; // Only run if chat is selected
    
    try {
      // GET request to fetch documents for this chat
      const res = await axios.get(
        `${API}/documents/${currentChatId}`,
        {
          headers: getAuthHeader()  // ✅ SEND TOKEN HERE
        }
      );
      
      // Update state with document list
      setDocuments(res.data.documents || []);
    } catch (err) {
      console.error('Failed to load documents:', err.message);
    }
  };
  
  // ============================================
  // FUNCTION - Handle file selection and upload
  // ============================================
  /**
   * POST /upload
   * POST /chats/{chat_id}/rename (ONLY on first upload)
   * 
   * FLOW:
   * 1. User selects PDF/TXT file
   * 2. POST to /upload with chat_id
   * 3. Backend: Extract text, split chunks, generate embeddings, save to DB
   * 4. IF this is the first document → POST to /rename to auto-rename chat
   * 5. Reload documents and chats
   * 
   * SECURITY: chat_id ensures documents stay in this chat only
   * 
   * SMART RENAME: Only rename on FIRST document upload
   * Using getShortFilename() to keep chat name short
   */
  const handleFileSelect = async (e) => {
    const file = e.target.files[0];
    
    // Validation
    if (!file) return;
    if (!currentChatId) {
      alert('Create a chat first');
      return;
    }
    
    // Create FormData for file upload
    const formData = new FormData();
    formData.append('file', file);
    formData.append('chat_id', currentChatId);
    
    try {
      // Step 1: Upload document
      console.log(`Uploading ${file.name}...`);
      await axios.post(
        `${API}/upload`,
        formData,
        {
          headers: {
            ...getAuthHeader()  // ✅ SEND TOKEN HERE
          }
        }
      );
      
      // Clear file input
      document.getElementById('fileInput').value = '';
      
      // Step 2: Reload documents to show the uploaded file
      await fetchDocuments();
      
      // Step 3: Auto-rename chat ONLY on first upload
      // Check if this chat has already been renamed
      if (!chatRenamed[currentChatId]) {
        // Get short filename (first few words only)
        const shortName = getShortFilename(file.name);
        
        await axios.post(
          `${API}/chats/${currentChatId}/rename`,
          { chat_name: shortName },
          {
            headers: getAuthHeader()  // ✅ SEND TOKEN HERE
          }
        );
        
        // Mark this chat as renamed (don't rename again)
        setChatRenamed(prev => ({
          ...prev,
          [currentChatId]: true
        }));
      }
      
      // Step 4: Reload chats to show new name
      await loadChats();
      
      alert('✅ Document added!');
    } catch (err) {
      console.error('Upload failed:', err.message);
      alert(`Upload failed: ${err.message}`);
    }
  };
  
  // ============================================
  // FUNCTION - Delete entire chat
  // ============================================
  /**
   * DELETE /chats/{chat_id}
   * 
   * ENDPOINT: Delete chat and all its messages
   * SECURITY: Requires JWT token
   * 
   * FLOW:
   * 1. Ask user for confirmation
   * 2. Send DELETE request
   * 3. Reload chat list
   * 4. Clear current chat
   */
  const deleteChat = async (chatId, e) => {
    e.stopPropagation(); // Don't trigger switchChat
    
    // Ask user to confirm
    if (!window.confirm('Delete this chat and all messages?')) return;
    
    try {
      // DELETE request to remove chat
      await axios.delete(
        `${API}/chats/${chatId}`,
        {
          headers: getAuthHeader()  // ✅ SEND TOKEN HERE
        }
      );
      
      // Reload chat list
      await loadChats();
      
      // Clear current selection
      setMessages([]);
      setCurrentChatId(null);
      localStorage.removeItem('lastChatId');  // Clear saved chat
      setDocuments([]);
    } catch (err) {
      console.error('Delete failed:', err.message);
      alert('Failed to delete chat');
    }
  };
  
  // ============================================
  // FUNCTION - Delete single document
  // ============================================
  /**
   * DELETE /document/{doc_name}
   * 
   * ENDPOINT: Delete specific document
   * SECURITY: Requires JWT token
   * 
   * FLOW:
   * 1. Ask user for confirmation
   * 2. Send DELETE request with doc_name
   * 3. Reload documents to show it's gone
   */
  const deleteDocument = async (docName) => {
    if (!window.confirm(`Delete ${docName}?`)) return;
    
    try {
      // DELETE request to remove document
      await axios.delete(
        `${API}/document/${encodeURIComponent(docName)}`,
        {
          headers: getAuthHeader()  // ✅ SEND TOKEN HERE
        }
      );
      
      // Reload documents to show it's deleted
      await fetchDocuments();
    } catch (err) {
      console.error('Delete failed:', err.message);
      alert('Failed to delete document');
    }
  };
  
  // ============================================
  // FUNCTION - Send question to LLM
  // ============================================
  /**
   * POST /ask
   * POST /chats/{chat_id}/message (x2)
   * 
   * RAG PIPELINE:
   * 1. User types question + presses Send
   * 2. Save user message to database
   * 3. Send question to LLM with relevant document chunks
   * 4. LLM returns answer (streaming, token by token)
   * 5. Save bot response to database
   * 
   * SECURITY: chat_id ensures only docs from THIS chat are searched
   * 
   * STREAMING: Response comes as Server-Sent Events (SSE)
   * Each token arrives in format: data: {type: "token", text: "word"}
   */
  const sendQuestion = async () => {
    // Validation
    if (!question.trim()) return; // Empty question
    if (!currentChatId) {
      alert('Create a chat first');
      return;
    }
    
    // ---- STEP 1: Add user message to UI immediately ----
    const userMessage = question;
    setMessages(prev => [...prev, {
      type: 'user',
      text: userMessage
    }]);
    
    // ---- STEP 2: Save user message to database ----
    try {
      await axios.post(
        `${API}/chats/${currentChatId}/message`,
        {
          role: 'user',
          content: userMessage
        },
        {
          headers: getAuthHeader()  // ✅ SEND TOKEN HERE
        }
      );
    } catch (err) {
      console.error('Failed to save user message:', err.message);
    }
    
    // Clear input for next message
    setQuestion('');
    setLoading(true); // Show typing indicator
    
    try {
      // ---- STEP 3: Send question to LLM ----
      const res = await axios.post(
        `${API}/ask`,
        {
          question: userMessage,
          chat_id: currentChatId   // Only search docs in this chat
        },
        {
          headers: getAuthHeader()  // ✅ SEND TOKEN HERE
        }
      );
      
      // ---- STEP 4: Parse streaming response ----
      // Response format: "data: {json}\ndata: {json}\n..."
      let fullResponse = '';
      const text = res.data;
      const lines = text.split('\n');
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const json = JSON.parse(line.substring(6));
            if (json.type === 'token') {
              fullResponse += json.text; // Append token to response
            }
          } catch (e) {
            // Skip malformed JSON lines
          }
        }
      }
      
      // ---- STEP 5: Add bot message to UI ----
      setMessages(prev => [...prev, {
        type: 'bot',
        text: fullResponse || 'No response'
      }]);
      
      // ---- STEP 6: Save bot message to database ----
      try {
        await axios.post(
          `${API}/chats/${currentChatId}/message`,
          {
            role: 'bot',
            content: fullResponse || 'No response'
          },
          {
            headers: getAuthHeader()  // ✅ SEND TOKEN HERE
          }
        );
      } catch (err) {
        console.error('Failed to save bot message:', err.message);
      }
    } catch (err) {
      console.error('Question failed:', err.message);
      setMessages(prev => [...prev, {
        type: 'bot',
        text: `❌ Error: ${err.message}`
      }]);
    }
    
    setLoading(false); // Hide typing indicator
  };
  
  // ============================================
  // RENDER
  // ============================================
  return (
    <div className="chat-container">
      {/* LEFT SIDEBAR - Documents & AI Mode */}
      <div className="chat-sidebar-left">
        <div className="chat-header">
          <h1>⚡ LexiRAG</h1>
          <button onClick={onLogout} className="logout-btn">Logout</button>
        </div>
        
        {/* Document Upload */}
        <h2>Add Sources</h2>
        <input
          type="file"
          id="fileInput"
          onChange={handleFileSelect}
          accept=".pdf,.txt"
          style={{ display: 'none' }}
        />
        <button
          onClick={() => document.getElementById('fileInput').click()}
          className="upload-btn"
        >
          📄 Add Document
        </button>
        
        {/* Document List */}
        <h2>Documents</h2>
        <div className="doc-list">
          {documents.length === 0 ? (
            <div style={{ fontSize: '12px', color: '#666', padding: '10px' }}>
              No documents
            </div>
          ) : (
            documents.map((doc) => (
              <div key={doc} className="doc-item-wrapper">
                <div className="doc-item">📄 {doc}</div>
                <button
                  onClick={() => deleteDocument(doc)}
                  className="delete-icon-btn"
                >
                  🗑️
                </button>
              </div>
            ))
          )}
        </div>
      </div>
      
      {/* MAIN CHAT AREA - Messages */}
      <div className="chat-main">
        <div className="messages">
          {messages.length === 0 ? (
            <div className="empty-state">
              <h3>Start a conversation</h3>
              <p>Create a chat and upload a document to begin</p>
            </div>
          ) : (
            <>
              {messages.map((msg, i) => (
                <div key={i} className={`message ${msg.type}`}>
                  {msg.type === 'bot' ? (
                    <ReactMarkdown>{msg.text}</ReactMarkdown>
                  ) : (
                    msg.text
                  )}
                </div>
              ))}
              {loading && (
                <div className="message bot">
                  <span>🤖</span>
                </div>
              )}
            </>
          )}
        </div>
        
        {/* Input Area */}
        <div className="input-area">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendQuestion()}
            placeholder="Ask a question about your document..."
            disabled={loading}
          />
          <button
            onClick={sendQuestion}
            disabled={loading}
            className="send-btn"
          >
            {loading ? '⏳' : '➤'}
          </button>
        </div>
      </div>
      
      {/* RIGHT SIDEBAR - Chat List */}
      <div className="chat-sidebar-right">
        <h2>Chats</h2>
        <button onClick={createNewChat} className="new-chat-btn">
          ➕ New Chat
        </button>
        <div className="chat-list">
          {chats.length === 0 ? (
            <div style={{ fontSize: '12px', color: '#666', padding: '10px' }}>
              No chats yet
            </div>
          ) : (
            chats.map((chat) => (
              <div key={chat.id} className="chat-item-wrapper">
                <div
                  className={`chat-item ${currentChatId === chat.id ? 'active' : ''}`}
                  onClick={() => switchChat(chat.id)}
                >
                  {chat.name}
                </div>
                <button
                  onClick={(e) => deleteChat(chat.id, e)}
                  className="delete-icon-btn"
                >
                  🗑️
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}