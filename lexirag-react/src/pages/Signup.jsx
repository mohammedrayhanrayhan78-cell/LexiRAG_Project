import { useState } from 'react';
import axios from 'axios';
import '../styles/Auth.css';

/**
 * SIGNUP COMPONENT
 * 
 * Allows user to create new account with username + password
 * Returns JWT token that lasts 7 days
 * 
 * PROPS:
 * - onSignupSuccess: function to call after successful signup (pass token)
 * - onSwitchToLogin: function to switch to login page
 */
export default function Signup({ onSignupSuccess, onSwitchToLogin }) {
  // ============================================
  // STATE VARIABLES
  // ============================================
  
  const [username, setUsername] = useState('');           // Username input
  const [password, setPassword] = useState('');           // Password input
  const [confirmPassword, setConfirmPassword] = useState(''); // Confirm password
  const [error, setError] = useState('');                 // Error message
  const [loading, setLoading] = useState(false);          // Is signing up?
  
  // API endpoint
  const API = '';
  
  // ============================================
  // FUNCTION - Handle form submission
  // ============================================
  /**
   * POST /signup
   * 
   * FLOW:
   * 1. User enters username + password + confirm password
   * 2. Check passwords match
   * 3. Send to backend
   * 4. Backend: Hash password, save to database
   * 5. Generate JWT token, return it
   * 
   * On success: Save token to localStorage, call onSignupSuccess
   */
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    // Client-side validation
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);

    try {
      // POST to signup endpoint
      const res = await axios.post(
        `${API}/signup`,
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
      onSignupSuccess(res.data.token);
    } catch (err) {
      // Handle errors
      const errorMessage = err.response?.data?.detail || 'Signup failed';
      setError(errorMessage);
      console.error('Signup error:', errorMessage);
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
        <p>Create your account</p>
        
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
          
          {/* Confirm Password Input */}
          <input
            type="password"
            placeholder="Confirm Password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            disabled={loading}
          />
          
          {/* Error Message */}
          {error && <p className="error">❌ {error}</p>}
          
          {/* Submit Button */}
          <button type="submit" disabled={loading}>
            {loading ? '⏳ Creating account...' : '✅ Sign up'}
          </button>
        </form>
        
        {/* Link to Login */}
        <p>
          Already have an account?{' '}
          <a
            onClick={onSwitchToLogin}
            style={{ cursor: 'pointer', color: '#7c6af7', fontWeight: 'bold' }}
          >
            Login
          </a>
        </p>
      </div>
    </div>
  );
}