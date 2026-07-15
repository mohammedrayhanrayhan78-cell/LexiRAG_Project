import { createContext, useState } from 'react';
import axios from 'axios';

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));
  const API = 'https://octopus-domestic-clicker.ngrok-free.dev';

  const signup = async (username, password) => {
    try {
      const res = await axios.post(`${API}/signup`, { username, password });
      setToken(res.data.token);
      setUser({ username });
      localStorage.setItem('token', res.data.token);
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data?.detail || 'Signup failed' };
    }
  };

  const login = async (username, password) => {
    try {
      const res = await axios.post(`${API}/login`, { username, password });
      setToken(res.data.token);
      setUser({ username });
      localStorage.setItem('token', res.data.token);
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data?.detail || 'Login failed' };
    }
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem('token');
  };

  return (
    <AuthContext.Provider value={{ user, token, signup, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};