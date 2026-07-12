import { useEffect, useId, useState, type ReactNode } from 'react'
import { API_BASE_URL } from '../api/client'
import { StatusBadge } from './StatusBadge'

export type PageId =
  | 'overview'
  | 'storyboard'
  | 'story'
  | 'characters'
  | 'voices'
  | 'images'
  | 'routing'
  | 'workflows'
  | 'exports'
  | 'settings'

const navItems: { id: PageId; label: string; short: string }[] = [
  { id: 'overview', label: 'Overview', short: 'Overview' },
  { id: 'storyboard', label: 'Storyboard', short: 'Board' },
  { id: 'story', label: 'Story & Chapters', short: 'Story' },
  { id: 'characters', label: 'Characters', short: 'Cast' },
  { id: 'voices', label: 'Voices', short: 'Voices' },
  { id: 'images', label: 'Starting Images', short: 'Images' },
  { id: 'routing', label: 'Model Routing', short: 'Routing' },
  { id: 'workflows', label: 'Workflows', short: 'Flows' },
  { id: 'exports', label: 'Exports', short: 'Export' },
  { id: 'settings', label: 'Project Settings', short: 'Settings' },
]

type AppShellProps = {
  activePage: PageId
  backendStatus: string
  onNavigate: (page: PageId) => void
  onRefreshStatus?: () => void
  children: ReactNode
}

export function AppShell({
  activePage,
  backendStatus,
  onNavigate,
  onRefreshStatus,
  children,
}: AppShellProps) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const navId = useId()
  const activeLabel = navItems.find((item) => item.id === activePage)?.label ?? 'Studio'

  useEffect(() => {
    if (!mobileNavOpen) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileNavOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [mobileNavOpen])

  const handleNavigate = (page: PageId) => {
    onNavigate(page)
    setMobileNavOpen(false)
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      <aside className={`sidebar ${mobileNavOpen ? 'sidebar-open' : ''}`} aria-label="Studio sidebar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            CF
          </div>
          <div>
            <strong>CineForge</strong>
            <span>Storyboard Studio · Phase 1</span>
          </div>
          <button
            type="button"
            className="sidebar-close touch-target"
            aria-label="Close navigation"
            onClick={() => setMobileNavOpen(false)}
          >
            ×
          </button>
        </div>

        <nav id={navId} aria-label="Primary navigation">
          {navItems.map((item) => {
            const isActive = item.id === activePage
            return (
              <button
                type="button"
                key={item.id}
                className={`nav-item touch-target ${isActive ? 'active' : ''}`}
                aria-current={isActive ? 'page' : undefined}
                onClick={() => handleNavigate(item.id)}
              >
                <span className="nav-label-full">{item.label}</span>
                <span className="nav-label-short">{item.short}</span>
              </button>
            )
          })}
        </nav>

        <div className="sidebar-footer">
          <StatusBadge status="disabled" label="Rendering disabled" />
          <span>
            Planning ends with an approved editable production plan. No ComfyUI, queue, clone, or FFmpeg
            work is started from planning screens.
          </span>
        </div>
      </aside>

      {mobileNavOpen ? (
        <button
          type="button"
          className="nav-backdrop"
          aria-label="Dismiss navigation"
          onClick={() => setMobileNavOpen(false)}
        />
      ) : null}

      <div className="workspace">
        <header className="topbar">
          <div className="topbar-leading">
            <button
              type="button"
              className="mobile-nav-toggle touch-target"
              aria-expanded={mobileNavOpen}
              aria-controls={navId}
              onClick={() => setMobileNavOpen((open) => !open)}
            >
              <span className="sr-only">Open navigation</span>
              <span aria-hidden="true">☰</span>
            </button>
            <div>
              <span className="eyebrow">Environment</span>
              <strong>Production planning · {activeLabel}</strong>
            </div>
          </div>
          <div className="topbar-status">
            <span className="mono api-base" title={API_BASE_URL}>
              {API_BASE_URL}
            </span>
            <StatusBadge status={backendStatus} label={`Backend ${backendStatus}`} />
            {onRefreshStatus ? (
              <button type="button" className="ghost-button touch-target" onClick={onRefreshStatus}>
                Refresh status
              </button>
            ) : null}
          </div>
        </header>

        <main id="main-content" className="main-content" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  )
}
