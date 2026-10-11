import React, { useState, useEffect } from 'react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import RetroWindow from '../components/RetroWindow';
import RetroButton from '../components/RetroButton';
import RetroField from '../components/RetroField';
import { SparkleIcon, SmileyIcon, BoltIcon, WarningIcon, FileDocIcon } from '../components/RetroIcons';
import { loginUser } from '../api';

export default function Login({ sessionExpiredMsg = '', onClearExpiredMsg }) {
  const navigate = useNavigate();
  const location = useLocation();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(sessionExpiredMsg || (location.state?.message || ''));
  const [loading, setLoading] = useState(false);
  const [retryCountdown, setRetryCountdown] = useState(0);

  useEffect(() => {
    if (sessionExpiredMsg) {
      setError(sessionExpiredMsg);
      if (onClearExpiredMsg) onClearExpiredMsg();
    }
  }, [sessionExpiredMsg, onClearExpiredMsg]);

  useEffect(() => {
    if (retryCountdown <= 0) return;
    const timer = setInterval(() => {
      setRetryCountdown((prev) => (prev > 1 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [retryCountdown]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!username.trim() || !password) {
      setError('Please enter both username and password.');
      return;
    }

    setLoading(true);
    try {
      await loginUser(username.trim(), password);
      navigate('/chat', { replace: true });
    } catch (err) {
      if (err.status === 429 && err.retryAfter) {
        setRetryCountdown(err.retryAfter);
        setError(`Too many attempts. Rate limited for ${err.retryAfter}s.`);
      } else {
        setError(err.message || 'Invalid username or password.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      padding: '36px 20px 72px',
      position: 'relative',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
    }}>
      {/* Decorative background stars & smileys */}
      <SparkleIcon size={26} style={{ position: 'absolute', left: '6%', top: '90px' }} />
      <SparkleIcon size={18} style={{ position: 'absolute', left: '28%', top: '40px' }} />
      <SparkleIcon size={24} style={{ position: 'absolute', right: '8%', top: '110px' }} />
      <SparkleIcon size={20} style={{ position: 'absolute', right: '25%', bottom: '70px' }} />
      <SmileyIcon size={40} style={{ position: 'absolute', left: '4%', bottom: '70px' }} />
      <SmileyIcon size={34} style={{ position: 'absolute', right: '5%', top: '48%' }} />

      {/* Main wrapper */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'center',
        alignItems: 'flex-start',
        gap: '36px',
        width: '100%',
        maxWidth: '1200px',
        position: 'relative',
        zIndex: 1,
      }}>
        {/* Left Side Panel (.deco hidden < 1000px) */}
        <div className="deco" style={{ flex: '0 0 280px', display: 'flex', flexDirection: 'column', gap: '24px', marginTop: '110px' }}>
          <RetroWindow title="What it does" variant="red">
            <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <div style={{ fontWeight: 800, fontSize: '14px', marginBottom: '4px' }}>Auto-routing</div>
                <div style={{ fontSize: '13px', lineHeight: '1.4' }}>Groq or Gemini is picked for each question.</div>
              </div>
              <div style={{ borderTop: '1px dashed var(--ink)', paddingTop: '12px' }}>
                <div style={{ fontWeight: 800, fontSize: '14px', marginBottom: '4px' }}>Regional languages</div>
                <div style={{ fontSize: '13px', lineHeight: '1.4' }}>Hindi, Kannada, Tamil, Telugu and English, detected for you.</div>
              </div>
              <div style={{ borderTop: '1px dashed var(--ink)', paddingTop: '12px' }}>
                <div style={{ fontWeight: 800, fontSize: '14px', marginBottom: '4px' }}>Scanned PDFs</div>
                <div style={{ fontSize: '13px', lineHeight: '1.4' }}>OCR kicks in when plain text extraction finds nothing.</div>
              </div>
              <div style={{ borderTop: '1px dashed var(--ink)', paddingTop: '12px' }}>
                <div style={{ fontWeight: 800, fontSize: '14px', marginBottom: '4px' }}>Source citations</div>
                <div style={{ fontSize: '13px', lineHeight: '1.4' }}>Every answer points back to the document it came from.</div>
              </div>
            </div>
          </RetroWindow>
        </div>

        {/* Center Panel (Login Form) */}
        <div style={{ flex: '0 1 480px', minWidth: '320px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '20px' }}>
          {/* Logo Header */}
          <div style={{ textAlign: 'center', marginBottom: '4px' }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '10px' }}>
              <BoltIcon size={36} />
              <h1 style={{
                margin: 0,
                fontFamily: 'var(--font-display)',
                fontWeight: 800,
                fontSize: '44px',
                letterSpacing: '-0.02em',
                lineHeight: 1
              }}>
                LexiRAG
              </h1>
            </div>
            <p style={{
              margin: '12px 0 0',
              fontSize: '15px',
              fontWeight: 500,
              maxWidth: '420px',
              lineHeight: '1.4'
            }}>
              Upload your documents and chat with them. Ask in English, Hindi, Kannada, Tamil or Telugu.
            </p>
          </div>

          {/* Login Window */}
          <RetroWindow title="Login" variant="red" style={{ width: '100%' }}>
            <form onSubmit={handleSubmit} style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {error && (
                <div style={{
                  padding: '10px 14px',
                  background: 'var(--red)',
                  color: 'var(--cream-light)',
                  border: 'var(--border)',
                  borderRadius: '3px',
                  fontSize: '13px',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}>
                  <WarningIcon size={18} />
                  <span>{error}</span>
                </div>
              )}

              {retryCountdown > 0 && (
                <div style={{
                  padding: '10px 14px',
                  background: 'var(--yellow)',
                  color: 'var(--ink)',
                  border: 'var(--border)',
                  borderRadius: '3px',
                  fontSize: '13px',
                  fontWeight: 700,
                  textAlign: 'center'
                }}>
                  Rate limit active: retry in {retryCountdown}s
                </div>
              )}

              <RetroField
                label="Username"
                id="login-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. rayhan"
                required
                autoComplete="username"
                disabled={loading || retryCountdown > 0}
              />

              <RetroField
                label="Password"
                id="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••"
                required
                autoComplete="current-password"
                disabled={loading || retryCountdown > 0}
              />

              <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
                <RetroButton
                  type="submit"
                  disabled={loading || retryCountdown > 0}
                  style={{ flex: 1 }}
                >
                  {loading ? 'Entering...' : 'Enter'}
                </RetroButton>
                <RetroButton
                  variant="alt"
                  type="button"
                  onClick={() => navigate('/signup')}
                  style={{ flex: 1 }}
                >
                  Create account
                </RetroButton>
              </div>

              <div style={{
                textAlign: 'center',
                fontSize: '12px',
                color: 'rgba(59, 30, 23, 0.7)',
                marginTop: '4px'
              }}>
                Login and signup are limited to 5 tries per minute.
              </div>
            </form>
          </RetroWindow>

          {/* Heads up Window (Privacy note & rate limits) */}
          <RetroWindow title="Heads up" variant="amber" style={{ width: '100%' }}>
            <div style={{ padding: '16px 20px', fontSize: '13px', lineHeight: '1.45', display: 'flex', gap: '12px', alignItems: 'center' }}>
              <WarningIcon size={28} />
              <div>
                <strong>Privacy &amp; Security:</strong> Your document text is sent to Groq or Gemini to answer questions. Login and signup are limited to 5 tries per minute.
              </div>
            </div>
          </RetroWindow>
        </div>

        {/* Right Side Panel (.deco hidden < 1000px) */}
        <div className="deco" style={{ flex: '0 0 260px', display: 'flex', flexDirection: 'column', gap: '24px', marginTop: '130px' }}>
          <RetroWindow title="Docs" variant="lilac">
            <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {['Lease.pdf', 'Notes.txt', 'Contract.pdf', 'Scan.pdf'].map((doc) => (
                <div key={doc} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  padding: '8px 12px',
                  background: 'var(--cream-light)',
                  border: '1.5px solid var(--ink)',
                  borderRadius: '3px',
                  fontSize: '13px',
                  fontWeight: 600
                }}>
                  <FileDocIcon size={18} />
                  <span>{doc}</span>
                </div>
              ))}
            </div>
          </RetroWindow>
        </div>
      </div>
    </div>
  );
}
