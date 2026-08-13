import { Suspense, lazy } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import Footer from './components/Footer.jsx';
import Navbar from './components/Navbar.jsx';
import HomePage from './pages/HomePage.jsx';
import { useAuth } from './context/AuthContext.jsx';

// The landing page loads eagerly; everything else is split out. The charting
// library alone is a large share of the bundle, and a farmer on a rural
// connection should not download it just to read the home page.
const ChatPage = lazy(() => import('./pages/ChatPage.jsx'));
const Dashboard = lazy(() => import('./pages/Dashboard.jsx'));
const PricePage = lazy(() => import('./pages/PricePage.jsx'));
const LoginPage = lazy(() => import('./pages/LoginPage.jsx'));
const ProfilePage = lazy(() => import('./pages/ProfilePage.jsx'));

const PageFallback = () => (
  <div className="p-12 text-center text-sm opacity-60">Loading… लोड हो रहा है…</div>
);

function RequireAuth({ children }) {
  const { isAuthenticated, loading } = useAuth();
  // Redirecting before the stored session has been validated would bounce a
  // signed-in farmer to the login page on every hard refresh.
  if (loading) return <div className="p-12 text-center text-sm opacity-60">Loading…</div>;
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="flex-1">
        <Suspense fallback={<PageFallback />}>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/prices" element={<PricePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/profile"
              element={
                <RequireAuth>
                  <ProfilePage />
                </RequireAuth>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </main>
      <Footer />
    </div>
  );
}
