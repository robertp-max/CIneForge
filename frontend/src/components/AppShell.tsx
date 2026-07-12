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

const primaryNav: {
  id: Exclude<PageId, 'settings'>
  label: string
  short: string
  icon: string
}[] = [
  { id: 'overview', label: 'Overview', short: 'Overview', icon: '▦' },
  { id: 'storyboard', label: 'Storyboard', short: 'Board', icon: '▤' },
  { id: 'story', label: 'Story & chapters', short: 'Story', icon: '▱' },
  { id: 'characters', label: 'Characters', short: 'Cast', icon: '♙' },
  { id: 'voices', label: 'Voices', short: 'Voices', icon: '♬' },
  { id: 'images', label: 'Starting images', short: 'Images', icon: '▧' },
  { id: 'routing', label: 'Model routing', short: 'Routing', icon: '◈' },
  { id: 'workflows', label: 'Workflows', short: 'Flows', icon: '◇' },
  { id: 'exports', label: 'Exports', short: 'Export', icon: '↓' },
]

const pageLabels: Record<PageId, string> = {
  overview: 'Overview',
  storyboard: 'Storyboard',
  story: 'Story & Chapters',
  characters: 'Characters',
  voices: 'Voices',
  images: 'Starting Images',
  routing: 'Model Routing',
  workflows: 'Workflows',
  exports: 'Exports',
  settings: 'Project Settings',
}

type AppShellProps = {
  activePage: PageId
  backendStatus: string
  projectId: string
  projectName?: string
  shotCount?: number
  runtimeLabel?: string
  runtimeDetail?: string
  onNavigate: (page: PageId) => void
  onRefreshStatus?: () => void
  onSaveDraft?: () => void
  onPreviewAnimatic?: () => void
  children: ReactNode
}

export function AppShell({
  activePage,
  backendStatus,
  projectId,
  projectName = 'A New Journey',
  shotCount,
  runtimeLabel = 'ComfyUI ready',
  runtimeDetail = 'RTX 5090 Laptop · 24 GB',
  onNavigate,
  onRefreshStatus,
  onSaveDraft,
  onPreviewAnimatic,
  children,
}: AppShellProps) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const navId = useId()
  const activeLabel = pageLabels[activePage] ?? 'Studio'
  const initials = projectName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('') || 'AJ'

  useEffect(() => {
    if (!mobileNavOpen && !searchOpen && !notificationsOpen) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMobileNavOpen(false)
        setSearchOpen(false)
        setNotificationsOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [mobileNavOpen, searchOpen, notificationsOpen])

  const handleNavigate = (page: PageId) => {
    onNavigate(page)
    setMobileNavOpen(false)
    setSearchOpen(false)
    setNotificationsOpen(false)
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      <aside className={`sidebar ${mobileNavOpen ? 'sidebar-open' : ''}`} aria-label="Studio sidebar">
        <button type="button" className="brand" onClick={() => handleNavigate('overview')}>
          <span className="brand-mark" aria-hidden="true">
            ▷
          </span>
          <span>
            <strong>CineForge</strong>
          </span>
        </button>
        <button
          type="button"
          className="sidebar-close touch-target"
          aria-label="Close navigation"
          onClick={() => setMobileNavOpen(false)}
        >
          ×
        </button>

        <button type="button" className="project-switcher touch-target" title={projectId}>
          <span className="project-avatar">{initials}</span>
          <span>
            <strong>{projectName}</strong>
            <small>Storyboard Phase A</small>
          </span>
          <span aria-hidden="true">⌄</span>
        </button>

        <nav id={navId} aria-label="Primary navigation">
          <span className="sidebar-section-label">Project</span>
          {primaryNav.map((item) => {
            const isActive = item.id === activePage
            const badge = item.id === 'storyboard' && typeof shotCount === 'number' ? String(shotCount) : null
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
                {badge ? <span className="nav-badge">{badge}</span> : null}
              </button>
            )
          })}
        </nav>

        <div className="sidebar-footer">
          <button
            type="button"
            className={`settings-entry touch-target ${activePage === 'settings' ? 'active' : ''}`}
            onClick={() => handleNavigate('settings')}
            aria-current={activePage === 'settings' ? 'page' : undefined}
          >
            <span className="nav-icon" aria-hidden="true">
              ⚙
            </span>
            <span>Project settings</span>
          </button>
          <div className="runtime-card" title={`Backend ${backendStatus}`}>
            <span className="live-dot" aria-hidden="true" />
            <span>
              <strong>{runtimeLabel}</strong>
              <small>{runtimeDetail}</small>
            </span>
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
              <span>{projectName}</span>
              <span aria-hidden="true">›</span>
              <strong>{activeLabel}</strong>
              <span className="phase-badge">Phase A</span>
            </div>
          </div>
          <div className="topbar-status">
            <button
              type="button"
              className="icon-button touch-target"
              aria-label="Search project"
              onClick={() => {
                setSearchOpen(true)
                setNotificationsOpen(false)
              }}
            >
              ⌕
            </button>
            <button
              type="button"
              className="icon-button touch-target has-dot"
              aria-label="Open notifications"
              onClick={() => {
                setNotificationsOpen((open) => !open)
                setSearchOpen(false)
              }}
            >
              ◦
            </button>
            {onSaveDraft ? (
              <button type="button" className="secondary-button touch-target" onClick={onSaveDraft}>
                Save draft
              </button>
            ) : null}
            {onPreviewAnimatic ? (
              <button type="button" className="primary-button touch-target" onClick={onPreviewAnimatic}>
                ▷ Preview animatic
              </button>
            ) : null}
            <StatusBadge status={backendStatus} label={`Backend ${backendStatus}`} />
            {onRefreshStatus ? (
              <button type="button" className="ghost-button touch-target status-refresh" onClick={onRefreshStatus}>
                Refresh
              </button>
            ) : null}
          </div>
        </header>

        {notificationsOpen ? (
          <aside className="notification-drawer" aria-label="Notifications">
            <header>
              <div>
                <span className="eyebrow">Notifications</span>
                <h2>Review queue</h2>
              </div>
              <button
                type="button"
                className="icon-button touch-target"
                aria-label="Close notifications"
                onClick={() => setNotificationsOpen(false)}
              >
                ×
              </button>
            </header>
            <button type="button" onClick={() => handleNavigate('images')}>
              <span className="note-icon warning" aria-hidden="true">
                !
              </span>
              <span>
                <b>Starting image blocked</b>
                <small>Review shots still need approved references.</small>
              </span>
            </button>
            <button type="button" onClick={() => handleNavigate('voices')}>
              <span className="note-icon" aria-hidden="true">
                ♬
              </span>
              <span>
                <b>Voice consent missing</b>
                <small>User-provided voices require explicit consent.</small>
              </span>
            </button>
            <button type="button" onClick={() => handleNavigate('routing')}>
              <span className="note-icon" aria-hidden="true">
                ◈
              </span>
              <span>
                <b>Model gap detected</b>
                <small>One recommended checkpoint is not installed.</small>
              </span>
            </button>
          </aside>
        ) : null}

        {searchOpen ? (
          <div className="modal-backdrop" role="presentation" onMouseDown={() => setSearchOpen(false)}>
            <div
              className="modal"
              role="dialog"
              aria-modal="true"
              aria-label={`Search ${projectName}`}
              onMouseDown={(event) => event.stopPropagation()}
            >
              <header>
                <h2>Search {projectName}</h2>
                <button
                  type="button"
                  className="icon-button"
                  aria-label="Close search"
                  onClick={() => setSearchOpen(false)}
                >
                  ×
                </button>
              </header>
              <div className="modal-body">
                <p className="form-hint">
                  Jump to a studio surface. Full entity search requires loaded planning data.
                </p>
                <div className="search-results">
                  {primaryNav.map((item) => (
                    <button key={item.id} type="button" onClick={() => handleNavigate(item.id)}>
                      <span>
                        <b>{item.label}</b>
                        <small>Page</small>
                      </span>
                      <span aria-hidden="true">→</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ) : null}

        <main id="main-content" className="main-content" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  )
}
