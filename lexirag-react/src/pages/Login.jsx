import { useState } from 'react';
import axios from 'axios';
import '../styles/Auth.css';

/**
 * LOGIN COMPONENT
 * 
 * Allows user to log in with username + password
 * Returns JWT token that lasts 7 days
 * 
 * PROPS:
 * - onLoginSuccess: function to call after successful login (pass token)
 * - onSwitchToSignup: function to switch to signup page
 */
export default function Login({ onLoginSuccess, onSwitchToSignup }) {
  // ============================================
  // STATE VARIABLES
  // ============================================
  
  const [username, setUsername] = useState('');     // Username input
  const [password, setPassword] = useState('');     // Password input
  const [error, setError] = useState('');           // Error message
  const [loading, setLoading] = useState(false);    // Is logging in?
  
  // API endpoint
  const API = '';
  
  // ============================================
  // FUNCTION - Handle form submission
  // ============================================
  /**
   * POST /login
   * 
   * FLOW:
   * 1. User enters username + password
   * 2. Send to backend
   * 3. Backend: Hash password + compare with stored hash
   * 4. If match: Generate JWT token, return it
   * 5. If no match: Return 401 Unauthorized
   * 
   * On success: Save token to localStorage, call onLoginSuccess
   */
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // POST to login endpoint
      const res = await axios.post(
        `${API}/login`,
        {
          username: username,
          password: password
        }
      );
      
      // ✅ Save username to localStorage
      localStorage.setItem('username', username);
      
      // ✅ Save JWT token to localStorage
      // This token will be sent in ALL future requests
      localStorage.setItem('token', res.data.token);
      
      // Call parent component's success handler
      // This typically switches to Chat component
      onLoginSuccess(res.data.token);
    } catch (err) {
      // Handle errors
      const errorMessage = err.response?.data?.detail || 'Login failed';
      setError(errorMessage);
      console.error('Login error:', errorMessage);
    }
    
    setLoading(false);
  };
  
  // ============================================
  // RENDER
  // ============================================
  return (
    <div className="auth-container">
      <div className="auth-box">
        <h1>⚡ LexiRAG</h1>
        <p>Login to your account</p>
        
        <form onSubmit={handleSubmit}>
          {/* Username Input */}
          <input
            type="text"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            disabled={loading}
          />
          
          {/* Password Input */}
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            disabled={loading}
          />
          
          {/* Error Message */}
          {error && <p className="error">❌ {error}</p>}
          
          {/* Submit Button */}
          <button type="submit" disabled={loading}>
            {loading ? '⏳ Logging in...' : '🔓 Login'}
          </button>
        </form>
        
        {/* Link to Signup */}
        <p>
          Don't have an account?{' '}
          <a
            onClick={onSwitchToSignup}
            style={{ cursor: 'pointer', color: '#7c6af7', fontWeight: 'bold' }}
          >
            Sign up
          </a>
        </p>
      </div>
    </div>
  );
}
