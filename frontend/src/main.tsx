import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
/* Exact Gold Edition Sites CSS */
import './gold-globals.css'
import './gold-ai-studio-theme.css'
/* Minimal CineForge bridges only */
import './cineforge-bridge.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
