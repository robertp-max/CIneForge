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

/* Runtime last word: beats every sheet including .studio-prefixed bridge green. */
const deGreen = document.createElement('style')
deGreen.setAttribute('data-degreen', '1')
deGreen.textContent = `
:root{--mint:#a8c7fa!important;--mint-dark:#233348!important;--success:#a8c7fa!important;--green:#a8c7fa!important}
html body .production-phase-rail>button.current,
html body .production-phase-rail>button[aria-current=step],
html body .production-phase-rail>button[aria-selected=true],
html body .studio .production-phase-rail>button.current,
html body .studio .production-phase-rail>button[aria-current=step],
html body .studio .production-phase-rail>button[aria-selected=true],
html body .app-shell .production-phase-rail>button.current{
  border-color:#5b7aa8!important;background:#1a2434!important;background-color:#1a2434!important;
  background-image:none!important;box-shadow:inset 0 0 0 1px rgba(168,199,250,.12)!important}
html body .production-phase-rail>button.current>span,
html body .production-phase-rail>button[aria-current=step]>span,
html body .production-phase-rail>button[aria-selected=true]>span,
html body .studio .production-phase-rail>button.current>span,
html body .studio .production-phase-rail>button[aria-current=step]>span,
html body .studio .production-phase-rail>button[aria-selected=true]>span{
  border-color:#6b8fc4!important;background:#24344f!important;background-color:#24344f!important;
  background-image:none!important;color:#a8c7fa!important}
html body .production-phase-rail>button.current small,
html body .studio .production-phase-rail>button.current small{color:#9bb6df!important}
html body .production-phase-rail>button.current b,
html body .studio .production-phase-rail>button.current b{color:#e8eef8!important}
.phase-qa-checks li>span,.phase-qa-checks li.passed>span,li.passed>span,.qa-pass,.phase-one-metrics .qa-pass,.phase-metric .qa-pass{
  background:#1e2a3c!important;background-color:#1e2a3c!important;color:#a8c7fa!important;
  border-color:#5b7aa8!important}
.phase-count-pill,.design-available-pill,.phase-workspace-meta>span,.phase-workspace-meta-pill,
.summary-icon.mint,.status-pill[data-status=ready],.status-pill[data-status=approved],.status-pill[data-status=complete]{
  border-color:#4a5f7d!important;background:#1e2a3c!important;color:#a8c7fa!important;background-image:none!important}
.gpu>i,.sidebar-bottom .gpu>i{background:#a8c7fa!important;box-shadow:0 0 10px rgba(168,199,250,.45)!important}
.phase-one-complete-message{border-color:#3d4f6a!important;background:#1a2434!important;background-image:none!important}
.phase-continuity,.phase-continuity-note{border-left-color:#5b7aa8!important;background:#1a2434!important}
.phase-wave i,.phase-audio-wave i{background:#a8c7fa!important}
.eyebrow,.phase-document span,.phase-document>div>span{color:#a8c7fa!important}
.project-progress>i,.progress>i{background:linear-gradient(90deg,#7baaf7,#a8c7fa)!important}
`
document.head.appendChild(deGreen)

/* DOM pass: rewrite computed pure-green paint on critical nodes after load. */
function scrubGreenPaint() {
  const targets = document.querySelectorAll(
    '.production-phase-rail > button.current, .production-phase-rail > button.current > span, .phase-qa-checks li.passed > span, .gpu > i, .phase-count-pill, .design-available-pill, .summary-icon.mint',
  )
  targets.forEach((el) => {
    const node = el as HTMLElement
    const cs = getComputedStyle(node)
    const bg = cs.backgroundColor
    const m = bg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
    if (!m) return
    const r = Number(m[1])
    const g = Number(m[2])
    const b = Number(m[3])
    if (g > r + 15 && g > b + 10 && g > 70) {
      node.style.setProperty('background', '#1a2434', 'important')
      node.style.setProperty('background-color', '#1a2434', 'important')
      node.style.setProperty('background-image', 'none', 'important')
      node.style.setProperty('color', '#a8c7fa', 'important')
      node.style.setProperty('border-color', '#5b7aa8', 'important')
    }
  })
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    scrubGreenPaint()
    window.setTimeout(scrubGreenPaint, 500)
    window.setTimeout(scrubGreenPaint, 1500)
  })
} else {
  scrubGreenPaint()
  window.setTimeout(scrubGreenPaint, 500)
  window.setTimeout(scrubGreenPaint, 1500)
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
