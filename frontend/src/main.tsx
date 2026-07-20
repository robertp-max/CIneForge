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

/* Runtime last word: inject after paint so cached/HMR sheets cannot re-green checkmarks. */
const deGreen = document.createElement('style')
deGreen.setAttribute('data-degreen', '1')
deGreen.textContent = `
:root{--mint:#a8c7fa!important;--success:#a8c7fa!important;--green:#a8c7fa!important}
.phase-qa-checks li>span,.phase-qa-checks li.passed>span,li.passed>span,.qa-pass,.phase-one-metrics .qa-pass{
  background:#1e2a3c!important;background-color:#1e2a3c!important;color:#a8c7fa!important;
  border-color:#5b7aa8!important;border-top-color:#5b7aa8!important;border-right-color:#5b7aa8!important;
  border-bottom-color:#5b7aa8!important;border-left-color:#5b7aa8!important;outline-color:#a8c7fa!important}
.production-phase-rail>button.current,.production-phase-rail>button[aria-current=step]{
  border-color:#5b7aa8!important;background:#1a2434!important;background-image:none!important}
.production-phase-rail>button.current>span,.production-phase-rail>button[aria-current=step]>span{
  border-color:#6b8fc4!important;background:#24344f!important;color:#a8c7fa!important}
.gpu>i{background:#a8c7fa!important;box-shadow:0 0 10px rgba(168,199,250,.45)!important}
`
document.head.appendChild(deGreen)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
