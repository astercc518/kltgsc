import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';
import { initAnalytics } from '@/lib/analytics';

// Plausible init — no-op in dev / when no domain configured. Set
// VITE_PLAUSIBLE_DOMAIN at build time to enable.
initAnalytics();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
