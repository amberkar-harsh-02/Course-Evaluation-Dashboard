import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './index.css'

import App from './App.jsx'
import Dashboard from './Dashboard.jsx'
import Help from './Help.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter basename="/course-eval">
      <Routes>
        {/* App acts as the Master Wrapper for all pages */}
        <Route path="/" element={<App />}>
          <Route index element={<Help />} />
          <Route path="dashboard" element={<Dashboard />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)