import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './gold-globals.css'
import './gold-ai-studio-theme.css'
import './cineforge-bridge.css'
import './kill-green.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)