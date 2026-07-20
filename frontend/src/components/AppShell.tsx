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

export type ShellView = 'projects' | 'new-project' | 'studio'

const navItems: {
  id: PageId
  label: string
  short: string
  icon: string
  badge?: string
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

type AppShellProps = {
  activePage: PageId
  backendStatus: string
  projectId: string
  projectName: string
  projectCount: number
  view: ShellView
  onNavigate: (page: PageId) => void
  onOpenProjects: () => void
  onCreateProject: () => void
  onRefreshStatus?: () => void
  children: ReactNode
}

export function AppShell({
  activePage,
  backendStatus,
  projectId,
  projectName,
  projectCount,
  view,
  onNavigate,
  onOpenProjects,
  onCreateProject,
  onRefreshStatus,
  children,
}: AppShellProps) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [projectMenuOpen, setProjectMenuOpen] = useState(false)
  const [profileMenuOpen, setProfileMenuOpen] = useState(false)
  const navId = useId()
  const sidebarId = useId()
  const isStudio = view === 'studio'
  const activeLabel =
    view === 'projects'
      ? 'Projects'
      : view === 'new-project'
        ? 'Create project'
        : activePage === 'settings'
          ? 'Project settings'
          : navItems.find((item) => item.id === activePage)?.label ?? 'Studio'
  const projectInitials = projectName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('') || 'PR'

  useEffect(() => {
    if (!mobileNavOpen && !projectMenuOpen && !profileMenuOpen) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMobileNavOpen(false)
        setProjectMenuOpen(false)
        setProfileMenuOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [mobileNavOpen, profileMenuOpen, projectMenuOpen])

  const handleNavigate = (page: PageId) => {
    onNavigate(page)
    setMobileNavOpen(false)
    setProjectMenuOpen(false)
    setProfileMenuOpen(false)
  }

  const handleWorkspaceNavigate = (action: () => void) => {
    action()
    setMobileNavOpen(false)
    setProjectMenuOpen(false)
    setProfileMenuOpen(false)
  }

  return (
    <div className={`app-shell ${sidebarCollapsed ? 'sidebar-is-collapsed' : ''}`}>
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      <aside
        id={sidebarId}
        className={`sidebar ${sidebarCollapsed ? 'sidebar-collapsed' : ''} ${mobileNavOpen ? 'sidebar-open' : ''}`}
        aria-label="Studio sidebar"
      >
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            ▷
          </div>
          <div>
            <strong>CineForge</strong>
          </div>
          <button
            type="button"
            className="sidebar-collapse"
            aria-label={sidebarCollapsed ? 'Expand navigation' : 'Collapse navigation'}
            aria-pressed={sidebarCollapsed}
            onClick={() => setSidebarCollapsed((collapsed) => !collapsed)}
          >
            <span aria-hidden="true">{sidebarCollapsed ? '›' : '‹'}</span>
          </button>
          <button
            type="button"
            className="sidebar-close touch-target"
            aria-label="Close navigation"
            onClick={() => setMobileNavOpen(false)}
          >
            ×
          </button>
        </div>

        {/* Gold Edition order: brand → workspace → project switcher → project nav → bottom */}
        <span className="sidebar-section-label sidebar-workspace-label">Workspace</span>
        <nav className="sidebar-workspace-nav" aria-label="Workspace navigation">
          <button
            type="button"
            className={`nav-item touch-target ${view === 'projects' ? 'active' : ''}`}
            aria-current={view === 'projects' ? 'page' : undefined}
            onClick={() => handleWorkspaceNavigate(onOpenProjects)}
          >
            <span className="nav-icon" aria-hidden="true">▣</span>
            <span className="nav-label-full">Projects</span>
            <span className="nav-badge">{projectCount}</span>
          </button>
        </nav>

        <div className="project-switch-wrap">
          <button
            type="button"
            className="project-switcher touch-target"
            title={projectId}
            aria-expanded={projectMenuOpen}
            onClick={() => {
              setProjectMenuOpen((open) => !open)
              setProfileMenuOpen(false)
            }}
          >
            <span className="project-avatar">{projectInitials}</span>
            <span>
              <strong>{projectName}</strong>
              <small>{isStudio ? 'Seven-phase production' : 'Select a project'}</small>
            </span>
            <span aria-hidden="true">⌄</span>
          </button>
          {projectMenuOpen ? (
            <div className="sidebar-popover project-popover" role="menu" aria-label="Projects">
              <button type="button" role="menuitem" onClick={() => handleWorkspaceNavigate(onOpenProjects)}>
                <span className="nav-icon" aria-hidden="true">▣</span>
                <span>
                  <strong>All projects</strong>
                  <small>{projectCount} in this workspace</small>
                </span>
                <span aria-hidden="true">›</span>
              </button>
              <button type="button" role="menuitem" className="active" onClick={() => setProjectMenuOpen(false)}>
                <span className="project-avatar">{projectInitials}</span>
                <span>
                  <strong>{projectName}</strong>
                  <small>Current project</small>
                </span>
                <span aria-hidden="true">✓</span>
              </button>
              <button type="button" role="menuitem" onClick={() => handleWorkspaceNavigate(onCreateProject)}>
                <span className="nav-icon" aria-hidden="true">＋</span>
                <span>
                  <strong>New project</strong>
                  <small>Guided three-step setup</small>
                </span>
                <span aria-hidden="true">›</span>
              </button>
            </div>
          ) : null}
        </div>

        <div className="sidebar-project-nav-section">
          <span className="sidebar-section-label sidebar-project-label">Production</span>
          <nav id={navId} className="sidebar-project-nav" aria-label="Primary navigation">
            {navItems.map((item) => {
              const isActive = isStudio && item.id === activePage
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
        </div>

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
          <div className="user-menu-wrap">
            <button
              type="button"
              className="user-card"
              aria-label="Robert, Producer"
              aria-expanded={profileMenuOpen}
              onClick={() => {
                setProfileMenuOpen((open) => !open)
                setProjectMenuOpen(false)
              }}
            >
              <span className="user-avatar">RP</span>
              <span>
                <strong>Robert</strong>
                <small>Producer</small>
              </span>
              <span aria-hidden="true">•••</span>
            </button>
            {profileMenuOpen ? (
              <div className="sidebar-popover profile-popover" role="menu" aria-label="Profile">
                <div>
                  <strong>Robert</strong>
                  <small>Local producer profile</small>
                </div>
                <button type="button" role="menuitem" onClick={() => handleNavigate('settings')}>
                  Project settings
                </button>
              </div>
            ) : null}
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
              aria-controls={sidebarId}
              onClick={() => setMobileNavOpen((open) => !open)}
            >
              <span className="sr-only">Open navigation</span>
              <span aria-hidden="true">☰</span>
            </button>
            <div className="breadcrumb" aria-label="Breadcrumb">
              <span>Projects</span>
              {view === 'new-project' ? (
                <>
                  <span aria-hidden="true">›</span>
                  <strong>{activeLabel}</strong>
                </>
              ) : null}
              {isStudio ? (
                <>
                  <span aria-hidden="true">›</span>
                  <span>{projectName}</span>
                  <span aria-hidden="true">›</span>
                  <strong>{activeLabel}</strong>
                  <span className="phase-badge">7 PHASES</span>
                </>
              ) : null}
            </div>
          </div>
          <div className="topbar-status">
            <button type="button" className="icon-button touch-target" aria-label="Search workspace">
              ⌕
            </button>
            {view === 'projects' ? (
              <button type="button" className="primary-button topbar-new-project" onClick={onCreateProject}>
                ＋ New project
              </button>
            ) : null}
            {isStudio ? <button type="button" className="icon-button touch-target" aria-label="Notifications">◦</button> : null}
            {isStudio ? <StatusBadge status={backendStatus} label={`Backend ${backendStatus}`} /> : null}
            {isStudio && onRefreshStatus ? <button type="button" className="ghost-button touch-target status-refresh" onClick={onRefreshStatus}>Refresh</button> : null}
          </div>
        </header>

        <main id="main-content" className="main-content" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  )
}
