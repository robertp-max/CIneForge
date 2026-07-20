import { useEffect, type ReactNode } from 'react'
import { setShellTopbarActions } from '../../components/shellTopbarActions'
import { useStudio } from '../StudioState'
import { AnimaticModal } from './AnimaticModal'

/**
 * Sites Gold pages render title chrome inside each page (PageTitle / phase contract).
 * StudioChrome only wires topbar actions + loading/error/animatic — no extra banners.
 */
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
    message,
    busy,
    reload,
    animaticOpen,
    setAnimaticOpen,
    setMessage,
    loadState,
    error,
  } = useStudio()

  // Sites puts Save draft / Preview animatic in the AppShell topbar — register handlers here.
  useEffect(() => {
    setShellTopbarActions({
      canPreview: Boolean(data),
      saveDraft: () => {
        setMessage('Draft state is current in the browser session. Server data remains canonical.')
      },
      previewAnimatic: () => setAnimaticOpen(true),
    })
    return () => setShellTopbarActions(null)
  }, [data, setAnimaticOpen, setMessage])

  // Keep a11y name for the workspace without painting Sites-unlike chrome.
  void title
  void description

  return (
    <section className="studio page sites-studio" aria-busy={busy || loadState === 'loading'}>
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

      {/* Transient notices only — never a permanent "Loaded…" banner under the title. */}
      {message && loadState !== 'loading' && !message.startsWith('Loaded the selected') ? (
        <p className="studio-message" role="status" aria-live="polite">
          {message}
        </p>
      ) : null}

      {loadState !== 'loading' ? children : null}

      {animaticOpen && data ? <AnimaticModal data={data} onClose={() => setAnimaticOpen(false)} /> : null}
    </section>
  )
}
