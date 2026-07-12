import { useEffect, useId, useState, type ReactNode } from 'react'
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

const navItems: {
  id: PageId
  label: string
  short: string
  icon: string
  badge?: string
}[] = [
  { id: 'overview', label: 'Overview', short: 'Overview', icon: '▦' },
  { id: 'storyboard', label: 'Storyboard', short: 'Board', icon: '▤', badge: '27' },
  { id: 'story', label: 'Story & chapters', short: 'Story', icon: '▱' },
  { id: 'characters', label: 'Characters', short: 'Cast', icon: '♙' },
  { id: 'voices', label: 'Voices', short: 'Voices', icon: '♬' },
  { id: 'images', label: 'Starting images', short: 'Images', icon: '▧' },
  { id: 'routing', label: 'Model routing', short: 'Routing', icon: '◈' },
  { id: 'workflows', label: 'Workflows', short: 'Flows', icon: '◇' },
  { id: 'exports', label: 'Exports', short: 'Export', icon: '↓' },
  { id: 'settings', label: 'Project settings', short: 'Settings', icon: '⚙' },
]

type AppShellProps = {
  activePage: PageId
  backendStatus: string
  projectId: string
  onNavigate: (page: PageId) => void
  onRefreshStatus?: () => void
  children: ReactNode
}

export function AppShell({
  activePage,
  backendStatus,
  projectId,
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
            ▷
          </div>
          <div>
            <strong>CineForge</strong>
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

        <button type="button" className="project-switcher touch-target" title={projectId}>
          <span className="project-avatar">AJ</span>
          <span>
            <strong>A New Journey</strong>
            <small>Storyboard Phase A</small>
          </span>
          <span aria-hidden="true">⌄</span>
        </button>

        <nav id={navId} aria-label="Primary navigation">
          <span className="sidebar-section-label">Project</span>
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
                <span className="nav-icon" aria-hidden="true">
                  {item.icon}
                </span>
                <span className="nav-label-full">{item.label}</span>
                <span className="nav-label-short">{item.short}</span>
                {item.badge ? <span className="nav-badge">{item.badge}</span> : null}
              </button>
            )
          })}
        </nav>

        <div className="sidebar-footer">
          <button type="button" className="settings-entry touch-target" onClick={() => handleNavigate('settings')}>
            <span className="nav-icon" aria-hidden="true">⚙</span>
            <span>Project settings</span>
          </button>
          <div className="runtime-card">
            <span className="live-dot" aria-hidden="true" />
            <strong>ComfyUI ready</strong>
            <small>RTX 5090 Laptop · 24 GB</small>
          </div>
          <div className="user-card">
            <span className="user-avatar">RP</span>
            <span>
              <strong>Robert</strong>
              <small>Producer</small>
            </span>
            <span aria-hidden="true">•••</span>
          </div>
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
            <div className="breadcrumb" aria-label="Breadcrumb">
              <span>Projects</span>
              <span aria-hidden="true">›</span>
              <span>A New Journey</span>
              <span aria-hidden="true">›</span>
              <strong>{activeLabel}</strong>
              <span className="phase-badge">Phase A</span>
            </div>
          </div>
          <div className="topbar-status">
            <button type="button" className="icon-button touch-target" aria-label="Search">
              ⌕
            </button>
            <button type="button" className="icon-button touch-target" aria-label="Notifications">
              ◦
            </button>
            <StatusBadge status={backendStatus} label={`Backend ${backendStatus}`} />
            {onRefreshStatus ? (
              <button type="button" className="ghost-button touch-target status-refresh" onClick={onRefreshStatus}>
                Refresh
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
