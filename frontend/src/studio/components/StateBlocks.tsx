import type { ReactNode } from 'react'

export function LoadingState({ title = 'Loading…', detail }: { title?: string; detail?: string }) {
  return (
    <div className="loading-block" role="status" aria-live="polite">
      <strong>{title}</strong>
      {detail ? <p>{detail}</p> : null}
    </div>
  )
}

export function EmptyState({
  title,
  detail,
  action,
}: {
  title: string
  detail?: string
  action?: ReactNode
}) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      {detail ? <p>{detail}</p> : null}
      {action}
    </div>
  )
}

export function ErrorState({
  title = 'Request failed',
  detail,
  onRetry,
}: {
  title?: string
  detail?: string
  onRetry?: () => void
}) {
  return (
    <div className="error-block" role="alert">
      <strong>{title}</strong>
      {detail ? <p>{detail}</p> : null}
      {onRetry ? (
        <button type="button" className="secondary-button touch-target" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  )
}

export function UnavailableState({
  title,
  detail,
}: {
  title: string
  detail: string
}) {
  return (
    <div className="panel disabled-future">
      <h2>{title}</h2>
      <p>{detail}</p>
      <button type="button" disabled aria-describedby="unavailable-explanation" className="touch-target">
        API unavailable
      </button>
      <small id="unavailable-explanation">
        This control is disabled because the backend did not expose the endpoint or returned no data.
        No background action is performed.
      </small>
    </div>
  )
}
