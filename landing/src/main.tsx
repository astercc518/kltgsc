import React from 'react';
import ReactDOM from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import { router } from './routes';
import { initAnalytics } from '@/lib/analytics';
import './index.css';

// Plausible init — no-op in dev / when no VITE_PLAUSIBLE_DOMAIN is set.
initAnalytics();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
);
