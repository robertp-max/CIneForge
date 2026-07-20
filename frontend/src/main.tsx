import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
/* Gold Edition visual system (exact Sites CSS stack, adapted for Vite). */
import './gold-globals.css'
import './gold-ai-studio-theme.css'
/* Minimal bridges for remaining CineForge-only class names not in Gold CSS. */
import './cineforge-bridge.css'
/* Last: kill forest-green boxes; AI Studio blue mint accents. */
import './kill-green.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
