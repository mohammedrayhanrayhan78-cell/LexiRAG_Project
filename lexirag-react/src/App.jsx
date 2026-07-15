import { useState, useEffect } from 'react';
import Login from './pages/Login';
import Signup from './pages/Signup';
import Chat from './pages/Chat';
import './App.css';

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [currentPage, setCurrentPage] = useState('login');

  useEffect(() => {
    const savedToken = localStorage.getItem('token');
    if (savedToken) {
      setToken(savedToken);
      setCurrentPage('chat');
    }
  }, []);

  const handleLogin = (newToken) => {
    setToken(newToken);
    localStorage.setItem('token', newToken);
    setCurrentPage('chat');
  };

  const handleLogout = () => {
    setToken(null);
    localStorage.removeItem('token');
    setCurrentPage('login');
  };

  if (currentPage === 'login') {
    return <Login onLoginSuccess={handleLogin} onSwitchToSignup={() => setCurrentPage('signup')} />;
  }

  if (currentPage === 'signup') {
    return <Signup onSignupSuccess={handleLogin} onSwitchToLogin={() => setCurrentPage('login')} />;
  }

  if (currentPage === 'chat') {
    return <Chat onLogout={handleLogout} username={localStorage.getItem('username') || 'user'} />;
}
}