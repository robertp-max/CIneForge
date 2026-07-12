import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './styles.css'
/* Prototype ZIP visual system (direct port of globals.css without Tailwind). */
import './studio/proto/prototype-shell.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
