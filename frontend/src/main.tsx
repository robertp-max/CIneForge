import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
/* Gold Edition visual system (exact Sites CSS stack, adapted for Vite). */
import './gold-globals.css'
import './gold-ai-studio-theme.css'
/* Minimal bridges for remaining CineForge-only class names not in Gold CSS. */
import './cineforge-bridge.css'
/* Optional page density sheets when present. */
import './images-sites-density.css'
import './projects-sites-density.css'
/* PIXEL Phase 5: prompt package layout density (Gold Sites). */
import './phase5-prompt-density.css'
/* LAST: force AI Studio blue accents — never forest/mint green (must win cascade). */
import './kill-green.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
