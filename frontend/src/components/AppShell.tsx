import { useEffect, useId, useState, type ReactNode } from 'react'
import type { Project } from '../api/client'
import { Icon, type IconName } from './ui'

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
  icon: IconName
}[] = [
  { id: 'overview', label: 'Overview', short: 'Overview', icon: 'grid' },
  { id: 'storyboard', label: 'Storyboard', short: 'Board', icon: 'film' },
  { id: 'story', label: 'Story & chapters', short: 'Story', icon: 'book' },
  { id: 'characters', label: 'Characters', short: 'Cast', icon: 'people' },
  { id: 'voices', label: 'Voices', short: 'Voices', icon: 'mic' },
  { id: 'images', label: 'Starting images', short: 'Images', icon: 'image' },
  { id: 'routing', label: 'Model routing', short: 'Routing', icon: 'cpu' },
  { id: 'workflows', label: 'Workflows', short: 'Flows', icon: 'layers' },
  { id: 'exports', label: 'Exports', short: 'Export', icon: 'download' },
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
  projects?: Project[]
  projectsError?: string | null
  shotCount?: number
  runtimeLabel?: string
  runtimeDetail?: string
  onNavigate: (page: PageId) => void
  onSelectProject?: (projectId: string) => void
  onRefreshStatus?: () => void
  onSaveDraft?: () => void
  onPreviewAnimatic?: () => void
  children: ReactNode
}

function projectInitials(name: string): string {
  const parts = name.split(/\s+/).filter(Boolean)
  if (!parts.length) return 'PR'
  // Match prototype “AJ” for multi-word titles (first + last token).
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0] ?? ''}${parts[parts.length - 1][0] ?? ''}`.toUpperCase()
}

export function AppShell({
  activePage,
  backendStatus,
  projectId,
  projectName = 'A New Journey',
  projects = [],
  projectsError = null,
  shotCount,
  runtimeLabel = 'Runtime status',
  runtimeDetail = 'Checking backend…',
  onNavigate,
  onSelectProject,
  onRefreshStatus,
  onSaveDraft,
  onPreviewAnimatic,
  children,
}: AppShellProps) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [projectMenuOpen, setProjectMenuOpen] = useState(false)
  const navId = useId()
  const activeLabel = pageLabels[activePage] ?? 'Studio'
  const initials = projectInitials(projectName)

  useEffect(() => {
    if (!mobileNavOpen && !searchOpen && !notificationsOpen && !projectMenuOpen) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMobileNavOpen(false)
        setSearchOpen(false)
        setNotificationsOpen(false)
        setProjectMenuOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [mobileNavOpen, searchOpen, notificationsOpen, projectMenuOpen])

  const handleNavigate = (page: PageId) => {
    onNavigate(page)
    setMobileNavOpen(false)
    setSearchOpen(false)
    setNotificationsOpen(false)
    setProjectMenuOpen(false)
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      <aside className={`sidebar ${mobileNavOpen ? 'sidebar-open' : ''}`} aria-label="Studio sidebar">
        <button type="button" className="brand" onClick={() => handleNavigate('overview')}>
          <span className="brand-mark" aria-hidden="true">
            <Icon name="play" size={15} />
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
          <Icon name="close" size={16} />
        </button>

        <div className="project-switch-wrap">
          <button
            type="button"
            className="project-switcher touch-target"
            title={projectId}
            aria-expanded={projectMenuOpen}
            onClick={() => setProjectMenuOpen((open) => !open)}
          >
            <span className="project-avatar">{initials}</span>
            <span>
              <strong>{projectName}</strong>
              <small>Storyboard Phase A</small>
            </span>
            <Icon name="chevron" size={14} />
          </button>
          {projectMenuOpen ? (
            <div className="popover project-pop" role="menu">
              {projects.length ? (
                projects.map((project) => (
                  <button
                    key={project.id}
                    type="button"
                    role="menuitem"
                    className={project.id === projectId ? 'active' : ''}
                    onClick={() => {
                      onSelectProject?.(project.id)
                      setProjectMenuOpen(false)
                    }}
                  >
                    <span className="project-avatar">{projectInitials(project.name)}</span>
                    <span>
                      <b>{project.name}</b>
                      <small className="mono">{project.id.slice(0, 8)}…</small>
                    </span>
                    {project.id === projectId ? <Icon name="check" size={14} /> : null}
                  </button>
                ))
              ) : (
                <p className="form-hint" style={{ padding: 10, margin: 0 }}>
                  {projectsError
                    ? projectsError
                    : 'No projects returned from GET /projects. Demo plan remains available offline.'}
                </p>
              )}
            </div>
          ) : null}
        </div>

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
                  <Icon name={item.icon} size={16} />
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
              <Icon name="settings" size={16} />
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
            <Icon name="more" size={14} />
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
              <Icon name="menu" size={18} />
            </button>
            <div className="breadcrumb" aria-label="Breadcrumb">
              <span>Projects</span>
              <Icon name="chevron" size={13} />
              <span>{projectName}</span>
              <Icon name="chevron" size={13} />
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
              <Icon name="search" size={16} />
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
              <Icon name="bell" size={16} />
            </button>
            {onSaveDraft ? (
              <button type="button" className="secondary-button touch-target" onClick={onSaveDraft}>
                Save draft
              </button>
            ) : null}
            {onPreviewAnimatic ? (
              <button type="button" className="primary-button touch-target" onClick={onPreviewAnimatic}>
                <Icon name="play" size={14} /> Preview animatic
              </button>
            ) : null}
            {/* Backend health stays in the sidebar runtime card to match prototype topbar chrome. */}
            <span className="sr-only">
              Backend {backendStatus}
              {onRefreshStatus ? (
                <button type="button" onClick={onRefreshStatus}>
                  Refresh status
                </button>
              ) : null}
            </span>
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
                <Icon name="close" size={16} />
              </button>
            </header>
            <button type="button" onClick={() => handleNavigate('images')}>
              <span className="note-icon warning" aria-hidden="true">
                <Icon name="warning" size={14} />
              </span>
              <span>
                <b>Starting image blocked</b>
                <small>Review shots still need approved references.</small>
              </span>
            </button>
            <button type="button" onClick={() => handleNavigate('voices')}>
              <span className="note-icon" aria-hidden="true">
                <Icon name="mic" size={14} />
              </span>
              <span>
                <b>Voice consent missing</b>
                <small>User-provided voices require explicit consent.</small>
              </span>
            </button>
            <button type="button" onClick={() => handleNavigate('routing')}>
              <span className="note-icon" aria-hidden="true">
                <Icon name="cpu" size={14} />
              </span>
              <span>
                <b>Model gap detected</b>
                <small>Check routing catalog for missing evidence.</small>
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
                  <Icon name="close" size={16} />
                </button>
              </header>
              <div className="modal-body">
                <p className="form-hint">Jump to a studio surface.</p>
                <div className="search-results">
                  {primaryNav.map((item) => (
                    <button key={item.id} type="button" onClick={() => handleNavigate(item.id)}>
                      <span>
                        <b>{item.label}</b>
                        <small>Page</small>
                      </span>
                      <Icon name="arrow" size={14} />
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
