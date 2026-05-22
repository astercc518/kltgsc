/**
 * TG1.AI — Landing application root.
 *
 * Layout host for the React Router tree. Provides:
 *   - <LangProvider> for i18n (5 languages, persisted to localStorage)
 *   - <Outlet /> for the child route page (Home / Docs / Changelog / Legal)
 *
 * Header + Footer are mounted *inside* page components rather than here
 * so individual routes can opt out (e.g. /legal/* pages may want a
 * simpler chrome later) without prop-drilling.
 *
 * The legacy single-file 917-line App.tsx that lived here has been split
 * into src/pages/Home.tsx + src/sections/*. See git log for the rewrite.
 */
import { Outlet } from 'react-router-dom';
import { LangProvider } from './i18n';

export default function App() {
  return (
    <LangProvider>
      <Outlet />
    </LangProvider>
  );
}
