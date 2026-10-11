import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import RetroWindow from '../components/RetroWindow';
import RetroButton from '../components/RetroButton';
import RetroField from '../components/RetroField';
import { SparkleIcon, SmileyIcon, BoltIcon, WarningIcon } from '../components/RetroIcons';
import { signupUser } from '../api';

export default function Signup() {
  const navigate = useNavigate();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [retryCountdown, setRetryCountdown] = useState(0);

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

    const cleanUsername = username.trim();
    if (!cleanUsername) {
      setError('Please choose a username.');
      return;
    }

    if (password.length < 10) {
      setError('Password must be at least 10 characters long.');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      await signupUser(cleanUsername, password);
      navigate('/chat', { replace: true });
    } catch (err) {
      if (err.status === 429 && err.retryAfter) {
        setRetryCountdown(err.retryAfter);
        setError(`Too many attempts. Rate limited for ${err.retryAfter}s.`);
      } else {
        setError(err.message || 'Could not create account. Username may already be taken.');
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
      <SparkleIcon size={26} style={{ position: 'absolute', left: '7%', top: '100px' }} />
      <SparkleIcon size={18} style={{ position: 'absolute', right: '30%', top: '36px' }} />
      <SparkleIcon size={22} style={{ position: 'absolute', right: '7%', bottom: '110px' }} />
      <SmileyIcon size={40} style={{ position: 'absolute', right: '4%', top: '90px' }} />
      <SmileyIcon size={34} style={{ position: 'absolute', left: '5%', bottom: '80px' }} />

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
          <RetroWindow title="3 easy steps" variant="red">
            <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                <div style={{
                  width: '24px',
                  height: '24px',
                  borderRadius: '50%',
                  background: 'var(--yellow)',
                  border: '1.5px solid var(--ink)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: 800,
                  fontSize: '12px',
                  flexShrink: 0
                }}>
                  1
                </div>
                <div>
                  <div style={{ fontWeight: 800, fontSize: '14px' }}>Make an account</div>
                  <div style={{ fontSize: '13px', lineHeight: '1.4' }}>Your chats and files belong to you alone.</div>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                <div style={{
                  width: '24px',
                  height: '24px',
                  borderRadius: '50%',
                  background: 'var(--yellow)',
                  border: '1.5px solid var(--ink)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: 800,
                  fontSize: '12px',
                  flexShrink: 0
                }}>
                  2
                </div>
                <div>
                  <div style={{ fontWeight: 800, fontSize: '14px' }}>Upload a PDF or TXT</div>
                  <div style={{ fontSize: '13px', lineHeight: '1.4' }}>Documents stay inside the chat you added them to.</div>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                <div style={{
                  width: '24px',
                  height: '24px',
                  borderRadius: '50%',
                  background: 'var(--yellow)',
                  border: '1.5px solid var(--ink)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: 800,
                  fontSize: '12px',
                  flexShrink: 0
                }}>
                  3
                </div>
                <div>
                  <div style={{ fontWeight: 800, fontSize: '14px' }}>Ask away</div>
                  <div style={{ fontSize: '13px', lineHeight: '1.4' }}>Answers stream in with the source attached.</div>
                </div>
              </div>
            </div>
          </RetroWindow>
        </div>

        {/* Center Panel (Signup Form) */}
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
              New here? Make an account and start chatting with your documents.
            </p>
          </div>

          {/* Signup Window */}
          <RetroWindow title="Sign up" variant="red" style={{ width: '100%' }}>
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
                label="Choose a username"
                id="signup-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. rayhan"
                required
                autoComplete="username"
                disabled={loading || retryCountdown > 0}
              />

              <RetroField
                label="Password (min. 10 chars)"
                id="signup-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                required
                autoComplete="new-password"
                disabled={loading || retryCountdown > 0}
              />

              <RetroField
                label="Confirm password"
                id="signup-confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••••••"
                required
                autoComplete="new-password"
                disabled={loading || retryCountdown > 0}
              />

              <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
                <RetroButton
                  type="submit"
                  disabled={loading || retryCountdown > 0}
                  style={{ flex: 1 }}
                >
                  {loading ? 'Creating...' : 'Create account'}
                </RetroButton>
                <RetroButton
                  variant="alt"
                  type="button"
                  onClick={() => navigate('/login')}
                  style={{ flex: 1 }}
                >
                  Back to login
                </RetroButton>
              </div>

              <div style={{
                textAlign: 'center',
                fontSize: '12px',
                color: 'rgba(59, 30, 23, 0.7)',
                marginTop: '4px'
              }}>
                Signup is limited to 5 tries per minute.
              </div>
            </form>
          </RetroWindow>

          {/* Heads up Window (Privacy note) */}
          <RetroWindow title="Heads up" variant="amber" style={{ width: '100%' }}>
            <div style={{ padding: '16px 20px', fontSize: '13px', lineHeight: '1.45', display: 'flex', gap: '12px', alignItems: 'center' }}>
              <WarningIcon size={28} />
              <div>
                <strong>Privacy Note:</strong> Your document text is sent to Groq or Gemini to answer questions.
              </div>
            </div>
          </RetroWindow>
        </div>

        {/* Right Side Panel (.deco hidden < 1000px) */}
        <div className="deco" style={{ flex: '0 0 260px', display: 'flex', flexDirection: 'column', gap: '24px', marginTop: '130px' }}>
          <RetroWindow title="Password tips" variant="amber">
            <div style={{ padding: '16px', fontSize: '13px', lineHeight: '1.4' }}>
              Pick something you don't use anywhere else. Minimum 10 characters. Signup is limited to 5 tries per minute.
            </div>
          </RetroWindow>
        </div>
      </div>
    </div>
  );
}