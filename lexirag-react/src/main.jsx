import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

// Self-hosted typography (no external Google Fonts requests)
import '@fontsource/space-grotesk/400.css';
import '@fontsource/space-grotesk/500.css';
import '@fontsource/space-grotesk/700.css';

import '@fontsource/bricolage-grotesque/700.css';
import '@fontsource/bricolage-grotesque/800.css';

import '@fontsource/silkscreen/400.css';
import '@fontsource/silkscreen/700.css';

import '@fontsource/noto-sans-devanagari/400.css';
import '@fontsource/noto-sans-devanagari/700.css';

import '@fontsource/noto-sans-kannada/400.css';
import '@fontsource/noto-sans-kannada/700.css';

import '@fontsource/noto-sans-tamil/400.css';
import '@fontsource/noto-sans-tamil/700.css';

import '@fontsource/noto-sans-telugu/400.css';
import '@fontsource/noto-sans-telugu/700.css';

import './styles/retro.css';
import './index.css';
import App from './App.jsx';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>
);
