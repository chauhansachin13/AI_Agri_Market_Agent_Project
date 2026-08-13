import { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';

import LanguageSwitcher from './LanguageSwitcher.jsx';
import { useAuth } from '../context/AuthContext.jsx';

const LINKS = [
  { to: '/', label: 'Home', hi: 'होम', end: true },
  { to: '/chat', label: 'Ask AI', hi: 'सवाल पूछें' },
  { to: '/dashboard', label: 'Mandi Board', hi: 'मंडी बोर्ड' },
  { to: '/prices', label: 'Trends', hi: 'रुझान' },
  { to: '/market', label: 'Marketplace', hi: 'बाज़ार' },
];

export default function Navbar() {
  const { isAuthenticated, user, signOut } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [dark, setDark] = useState(
    () => typeof window !== 'undefined' && document.documentElement.classList.contains('dark'),
  );

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
  }, [dark]);

  const handleSignOut = () => {
    signOut();
    navigate('/');
  };

  return (
    <header className="sticky top-0 z-40 border-b border-white/30 bg-white/70 backdrop-blur-md dark:border-white/10 dark:bg-soil-900/70">
      <nav className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3">
        <NavLink to="/" className="flex items-center gap-2 font-bold">
          <span aria-hidden="true" className="text-xl">
            🌾
          </span>
          <span className="hidden sm:inline">Agri Market AI</span>
        </NavLink>

        <ul className="ml-4 hidden gap-1 md:flex">
          {LINKS.map((link) => (
            <li key={link.to}>
              <NavLink
                to={link.to}
                end={link.end}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-2 text-sm transition-colors ${
                    isActive
                      ? 'bg-mandi-100 font-semibold text-mandi-800 dark:bg-white/10 dark:text-mandi-200'
                      : 'hover:bg-mandi-50 dark:hover:bg-white/5'
                  }`
                }
              >
                {link.label}
              </NavLink>
            </li>
          ))}
        </ul>

        <div className="ml-auto flex items-center gap-2">
          <LanguageSwitcher compact />
          <button
            type="button"
            onClick={() => setDark((value) => !value)}
            className="btn-ghost px-2.5 py-1.5 text-sm"
            aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {dark ? '☀️' : '🌙'}
          </button>

          {isAuthenticated ? (
            <>
              <NavLink to="/profile" className="hidden text-sm hover:underline sm:block">
                {user.name}
              </NavLink>
              <button type="button" onClick={handleSignOut} className="btn-ghost text-sm">
                Sign out
              </button>
            </>
          ) : (
            <NavLink to="/login" className="btn-primary text-sm">
              Sign in
            </NavLink>
          )}

          <button
            type="button"
            className="btn-ghost px-2.5 py-1.5 md:hidden"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
            aria-label="Toggle navigation"
          >
            ☰
          </button>
        </div>
      </nav>

      {open && (
        <ul className="border-t border-white/30 px-4 pb-3 md:hidden dark:border-white/10">
          {LINKS.map((link) => (
            <li key={link.to}>
              <NavLink
                to={link.to}
                end={link.end}
                onClick={() => setOpen(false)}
                className="block rounded-lg px-3 py-2.5 text-sm hover:bg-mandi-50 dark:hover:bg-white/5"
              >
                {link.label} · <span lang="hi">{link.hi}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      )}
    </header>
  );
}
