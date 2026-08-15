import React from 'react';
import { MotionConfig } from 'framer-motion';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

import App from './App.jsx';
import { AuthProvider } from './context/AuthContext.jsx';
import { QueryProvider } from './context/QueryContext.jsx';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {/* Honour the OS "reduce motion" setting: framer-motion does not do this
        on its own, and entrance animations that start at opacity 0 would
        otherwise leave content invisible for anyone who has asked for less
        movement. With this, those users get the content immediately. */}
    <MotionConfig reducedMotion="user">
      <BrowserRouter>
        <AuthProvider>
          <QueryProvider>
            <App />
          </QueryProvider>
        </AuthProvider>
      </BrowserRouter>
    </MotionConfig>
  </React.StrictMode>,
);
