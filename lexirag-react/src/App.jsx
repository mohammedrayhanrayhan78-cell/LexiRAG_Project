import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import Login from './pages/Login';
import Signup from './pages/Signup';
import Chat from './pages/Chat';
import { getToken, clearToken, onAuthExpired, isAuthenticated, pingHealth } from './api';
import './App.css';

// Route guard requiring valid authentication
function AuthGuard({ children }) {
  const authed = isAuthenticated();
  const location = useLocation();

  if (!authed) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return children;
}

// Redirects logged-in users away from auth pages
function GuestGuard({ children }) {
  const authed = isAuthenticated();
  if (authed) {
    return <Navigate to="/chat" replace />;
  }
  return children;
}

function AppRoutes() {
  const navigate = useNavigate();
  const [sessionExpiredMsg, setSessionExpiredMsg] = useState('');

  useEffect(() => {
    // Wake up backend in background on initial load
    pingHealth();

    // Listen for any 401 unauthenticated response across the app
    const unsubscribe = onAuthExpired(() => {
      setSessionExpiredMsg('Session expired. Please log in again.');
      navigate('/login', { replace: true });
    });

    return unsubscribe;
  }, [navigate]);

  return (
    <Routes>
      <Route
        path="/login"
        element={
          <GuestGuard>
            <Login
              sessionExpiredMsg={sessionExpiredMsg}
              onClearExpiredMsg={() => setSessionExpiredMsg('')}
            />
          </GuestGuard>
        }
      />
      <Route
        path="/signup"
        element={
          <GuestGuard>
            <Signup />
          </GuestGuard>
        }
      />
      <Route
        path="/chat"
        element={
          <AuthGuard>
            <Chat />
          </AuthGuard>
        }
      />
      <Route
        path="/chat/:chatId"
        element={
          <AuthGuard>
            <Chat />
          </AuthGuard>
        }
      />
      {/* Fallback redirect */}
      <Route
        path="*"
        element={<Navigate to={isAuthenticated() ? "/chat" : "/login"} replace />}
      />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}