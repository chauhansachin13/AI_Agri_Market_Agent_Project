import { useEffect, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';

import LanguageSwitcher from './LanguageSwitcher.jsx';
import { useAuth } from '../context/AuthContext.jsx';

const LINKS = [
  { to: '/', label: 'Home', hi: 'होम', end: true },
  { to: '/chat', label: 'Ask AI', hi: 'सवाल पूछें' },
  { to: '/dashboard', label: 'Mandi Board', hi: 'मंडी बोर्ड' },
  { to: '/prices', label: 'Trends', hi: 'रुझान' },
  { to: '/market', label: 'Marketplace', hi: 'बाज़ार' },
];

const THEME_KEY = 'agri.theme';

function readTheme() {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored) return stored;
  } catch {
    /* storage unavailable */
  }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export default function Navbar() {
  const { isAuthenticated, user, signOut } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState(readTheme);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      /* the choice simply will not survive a reload */
    }
  }, [theme]);

  // The header only earns its border and shadow once content is behind it.
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // A route change should always close the mobile menu, however it happened.
  useEffect(() => setOpen(false), [location.pathname]);

  const handleSignOut = () => {
    signOut();
    navigate('/');
  };

  const linkClass = ({ isActive }) =>
    `relative rounded-lg px-3 py-2 text-sm transition-colors duration-200 ${
      isActive
        ? 'font-semibold text-mandi-800 dark:text-mandi-300'
        : 'muted hover:text-soil-900 dark:hover:text-soil-100'
    }`;

  return (
    <header
      className={`sticky top-0 z-50 transition-all duration-300 ${
        scrolled
          ? 'border-b bg-[rgb(var(--surface))]/80 shadow-card backdrop-blur-xl'
          : 'border-b border-transparent'
      }`}
    >
      <nav className="container-page flex h-16 items-center gap-2">
        <NavLink to="/" className="flex shrink-0 items-center gap-2 font-bold tracking-tight">
          <span aria-hidden="true" className="text-xl">
            🌾
          </span>
          <span className="hidden sm:inline">Agri Market AI</span>
        </NavLink>

        <ul className="ml-6 hidden items-center gap-0.5 md:flex">
          {LINKS.map((link) => (
            <li key={link.to}>
              <NavLink to={link.to} end={link.end} className={linkClass}>
                {({ isActive }) => (
                  <>
                    {link.label}
                    {isActive && (
                      <span className="absolute inset-x-3 -bottom-px h-0.5 rounded-full bg-mandi-500" />
                    )}
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>

        <div className="ml-auto flex items-center gap-2">
          <div className="hidden sm:block">
            <LanguageSwitcher compact />
          </div>

          <button
            type="button"
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            className="btn-ghost h-9 w-9 p-0"
            aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            <span aria-hidden="true">{theme === 'dark' ? '☀️' : '🌙'}</span>
          </button>

          {isAuthenticated ? (
            <>
              <NavLink
                to="/profile"
                className="hidden max-w-[10rem] truncate text-sm hover:underline sm:block"
                title={user.name}
              >
                {user.name}
              </NavLink>
              <button type="button" onClick={handleSignOut} className="btn-ghost hidden sm:inline-flex">
                Sign out
              </button>
            </>
          ) : (
            <NavLink to="/login" className="btn-primary hidden sm:inline-flex">
              Sign in
            </NavLink>
          )}

          <button
            type="button"
            className="btn-ghost h-9 w-9 p-0 md:hidden"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
            aria-controls="mobile-nav"
            aria-label="Toggle navigation"
          >
            <span aria-hidden="true">{open ? '✕' : '☰'}</span>
          </button>
        </div>
      </nav>

      {open && (
        <div
          id="mobile-nav"
          className="border-t bg-[rgb(var(--surface))] px-4 pb-4 pt-2 md:hidden"
        >
          <ul className="space-y-0.5">
            {LINKS.map((link) => (
              <li key={link.to}>
                <NavLink
                  to={link.to}
                  end={link.end}
                  className={({ isActive }) =>
                    `block rounded-xl px-3 py-3 text-sm transition-colors ${
                      isActive
                        ? 'bg-mandi-50 font-semibold text-mandi-800 dark:bg-mandi-500/10 dark:text-mandi-300'
                        : 'hover:bg-soil-900/[0.04] dark:hover:bg-white/[0.06]'
                    }`
                  }
                >
                  {link.label} · <span lang="hi">{link.hi}</span>
                </NavLink>
              </li>
            ))}
          </ul>

          <div className="mt-3 border-t pt-3">
            <LanguageSwitcher />
          </div>

          <div className="mt-3">
            {isAuthenticated ? (
              <button type="button" onClick={handleSignOut} className="btn-ghost w-full">
                Sign out
              </button>
            ) : (
              <NavLink to="/login" className="btn-primary w-full">
                Sign in
              </NavLink>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
