import type { ReactNode } from 'react'
import { useStudio } from '../StudioState'
import { formatDuration } from '../utils'
import { AnimaticModal } from './AnimaticModal'

export function StudioChrome({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children: ReactNode
}) {
  const {
    data,
    readiness,
    message,
    busy,
    reload,
    animaticOpen,
    setAnimaticOpen,
    setMessage,
    loadState,
    error,
  } = useStudio()

  const planned = readiness?.planned_duration_sec ?? 0
  const target = data?.story.target_duration_sec ?? readiness?.target_duration_sec ?? 0

  return (
    <section className="studio page" aria-busy={busy || loadState === 'loading'}>
      <div className="studio-commandbar">
        <div>
          <span className="eyebrow">Production Phase A</span>
          <strong>A New Journey</strong>
          <small>
            {data
              ? `${formatDuration(target)} target · ${formatDuration(planned)} planned`
              : 'Guided storyboard planning workspace'}
          </small>
        </div>
        <div className="command-actions">
          <button
            type="button"
            className="ghost-button touch-target"
            onClick={() => {
              setMessage('Draft state is current in the browser session. Server data remains canonical.')
            }}
          >
            Save draft
          </button>
          <button
            type="button"
            className="primary-button touch-target"
            onClick={() => setAnimaticOpen(true)}
            disabled={!data}
            title="Timing prototype only — no video rendering"
          >
            ▷ Preview animatic
          </button>
        </div>
      </div>

      <header className="page-header studio-header">
        <div>
          <span className="eyebrow">Storyboard workspace</span>
          <h1>{title}</h1>
          <p>
            {data ? (
              <>
                <strong style={{ color: 'var(--text)' }}>{data.story.title}</strong>
                {' · '}
                {formatDuration(planned)} planned / {formatDuration(target)} target
                {' · '}
                {description}
              </>
            ) : (
              description
            )}
          </p>
        </div>
        <div className="page-actions">
          <button
            type="button"
            className="secondary-button touch-target"
            onClick={() => void reload()}
            disabled={busy || !data}
          >
            Continue review
          </button>
          <span className="readiness-chip">
            {readiness?.reasons.filter((reason) => reason.blocking).length ?? 0} blockers
          </span>
        </div>
      </header>

      <p className="studio-message" role="status" aria-live="polite">
        {message}
      </p>

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
          <button type="button" className="secondary-button" onClick={() => void reload()}>
            Retry
          </button>
        </div>
      ) : null}

      {loadState !== 'loading' ? children : null}

      {animaticOpen && data ? <AnimaticModal data={data} onClose={() => setAnimaticOpen(false)} /> : null}
    </section>
  )
}
