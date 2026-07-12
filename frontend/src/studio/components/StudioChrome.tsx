import type { ReactNode } from 'react'
import { useStudio } from '../StudioState'
import { AnimaticModal } from './AnimaticModal'

/**
 * Thin host chrome: loading/error/message/animatic only.
 * Page titles and action bars are owned by each ported prototype page.
 */
export function StudioChrome({ children }: { title?: string; description?: string; children: ReactNode }) {
  const { data, message, busy, reload, animaticOpen, setAnimaticOpen, loadState, error } = useStudio()

  return (
    <div className="studio-host" aria-busy={busy || loadState === 'loading'}>
      {message && !/demo plan is loaded/i.test(message) ? (
        <p className="studio-message" role="status" aria-live="polite">
          {message}
        </p>
      ) : null}

      {loadState === 'loading' ? (
        <div className="loading-block" role="status">
          <strong>Loading planning data…</strong>
          <p>Fetching aggregate hierarchy and backend readiness gates.</p>
        </div>
      ) : null}

      {loadState === 'error' && error ? (
        <div className="error-block" role="alert">
          <strong>Unable to load studio data</strong>
          <p>{error}</p>
          <button type="button" className="btn secondary" onClick={() => void reload()}>
            Retry
          </button>
        </div>
      ) : null}

      {loadState !== 'loading' ? children : null}

      {animaticOpen && data ? <AnimaticModal data={data} onClose={() => setAnimaticOpen(false)} /> : null}
    </div>
  )
}
