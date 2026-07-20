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

const navItems: { id: PageId; label: string; icon: string }[] = [
  { id: 'overview', label: 'Overview', icon: '▦' },
  { id: 'storyboard', label: 'Storyboard', icon: '▤' },
  { id: 'story', label: 'Story & chapters', icon: '▱' },
  { id: 'characters', label: 'Characters', icon: '♙' },
  { id: 'voices', label: 'Voices', icon: '♬' },
  { id: 'images', label: 'Starting images', icon: '▧' },
  { id: 'routing', label: 'Model routing', icon: '◈' },
  { id: 'workflows', label: 'Workflows', icon: '◇' },
  { id: 'exports', label: 'Exports', icon: '↓' },
]

const labels: Record<PageId | 'projects' | 'new-project', string> = {
  projects: 'Projects',
  'new-project': 'Create Project',
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
  projectName: string
  projectCount: number
  view: ShellView
  onNavigate: (page: PageId) => void
  onOpenProjects: () => void
  onCreateProject: () => void
  onRefreshStatus?: () => void
  children: ReactNode
}

function initials(name: string) {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join('') || 'CF'
  )
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
  const [mobile, setMobile] = useState(false)
  const [projectMenu, setProjectMenu] = useState(false)
  const [profile, setProfile] = useState(false)
  const [runtime, setRuntime] = useState(false)
  const navId = useId()
  const isStudio = view === 'studio'
  const projectInitials = initials(projectName)
  const activeLabel =
    view === 'projects'
      ? labels.projects
      : view === 'new-project'
        ? labels['new-project']
        : labels[activePage]

  useEffect(() => {
    if (!mobile && !projectMenu && !profile && !runtime) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMobile(false)
        setProjectMenu(false)
        setProfile(false)
        setRuntime(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [mobile, profile, projectMenu, runtime])

  useEffect(() => {
    const breakpoint = window.matchMedia('(max-width: 900px)')
    const closeAtDesktop = () => {
      if (!breakpoint.matches) setMobile(false)
    }
    breakpoint.addEventListener('change', closeAtDesktop)
    closeAtDesktop()
    return () => breakpoint.removeEventListener('change', closeAtDesktop)
  }, [])

  const goPage = (page: PageId) => {
    onNavigate(page)
    setMobile(false)
    setProjectMenu(false)
    setProfile(false)
    setRuntime(false)
  }

  const goWorkspace = (action: () => void) => {
    action()
    setMobile(false)
    setProjectMenu(false)
    setProfile(false)
    setRuntime(false)
  }

  return (
    <main className="app-shell">
      <a className="skip-link sr-only" href="#main-content">
        Skip to main content
      </a>

      <aside
        id="primary-navigation"
        className={`sidebar ${mobile ? 'mobile-open' : ''}`}
        aria-label="Primary navigation"
      >
        <button type="button" className="brand" onClick={() => goWorkspace(onOpenProjects)}>
          <span className="brand-mark" aria-hidden="true">
            ▷
          </span>
          <span>CineForge Studio</span>
        </button>

        <section className="sidebar-workspace-section" aria-label="Workspace navigation">
          <p className="nav-label">WORKSPACE</p>
          <nav className="workspace-nav">
            <button
              type="button"
              className={view === 'projects' ? 'active' : ''}
              onClick={() => goWorkspace(onOpenProjects)}
            >
              <span aria-hidden="true">▣</span>
              <span>Projects</span>
              <em>{projectCount}</em>
            </button>
          </nav>
        </section>

        <div className="project-switcher">
          <button
            type="button"
            className="project-switch"
            title={projectId}
            aria-expanded={projectMenu}
            onClick={() => {
              setProjectMenu((open) => !open)
              setProfile(false)
              setRuntime(false)
            }}
          >
            <span className="project-thumb">{projectInitials}</span>
            <span>
              <strong>{projectName}</strong>
              <small>{isStudio ? 'Seven-phase production plan' : 'Select a project'}</small>
            </span>
            <b aria-hidden="true">⌄</b>
          </button>
          {projectMenu ? (
            <div className="popover project-pop" role="menu">
              <button type="button" role="menuitem" onClick={() => goWorkspace(onOpenProjects)}>
                <span aria-hidden="true">▣</span>
                <span>
                  <b>All projects</b>
                  <small>{projectCount} in this workspace</small>
                </span>
                <span aria-hidden="true">›</span>
              </button>
              <button type="button" role="menuitem" onClick={() => setProjectMenu(false)}>
                <span className="project-thumb">{projectInitials}</span>
                <span>
                  <b>{projectName}</b>
                  <small>Current project</small>
                </span>
                <span aria-hidden="true">✓</span>
              </button>
              <button type="button" role="menuitem" onClick={() => goWorkspace(onCreateProject)}>
                <span aria-hidden="true">＋</span>
                <span>
                  <b>New project</b>
                  <small>Guided three-step setup</small>
                </span>
                <span aria-hidden="true">›</span>
              </button>
            </div>
          ) : null}
        </div>

        <section className="sidebar-project-section" aria-label="Current project navigation">
          <p className="nav-label project-nav-label">PRODUCTION</p>
          <nav id={navId} className="project-nav">
            {navItems.map((item) => {
              const active = isStudio && item.id === activePage
              return (
                <button
                  type="button"
                  key={item.id}
                  className={active ? 'active' : ''}
                  aria-current={active ? 'page' : undefined}
                  onClick={() => goPage(item.id)}
                >
                  <span aria-hidden="true">{item.icon}</span>
                  <span>{item.label}</span>
                </button>
              )
            })}
          </nav>
        </section>

        <div className="sidebar-bottom">
          <button
            type="button"
            className={isStudio && activePage === 'settings' ? 'active' : ''}
            onClick={() => goPage('settings')}
          >
            <span aria-hidden="true">⚙</span>
            <span>Project settings</span>
          </button>

          <button
            type="button"
            className="gpu"
            onClick={() => {
              setRuntime((open) => !open)
              setProfile(false)
              setProjectMenu(false)
            }}
          >
            <i aria-hidden="true" />
            <span>
              <strong>Local backend {backendStatus}</strong>
              <small>Planning only · no execution</small>
            </span>
          </button>
          {runtime ? (
            <div className="popover runtime-pop">
              <b>Runtime boundary</b>
              <p>ComfyUI submissions, model downloads, and rendering stay gated. This shell only shows local status.</p>
              {onRefreshStatus ? (
                <button
                  type="button"
                  onClick={() => {
                    setRuntime(false)
                    onRefreshStatus()
                  }}
                >
                  Refresh status ›
                </button>
              ) : null}
            </div>
          ) : null}

          <button
            type="button"
            className="user"
            onClick={() => {
              setProfile((open) => !open)
              setRuntime(false)
              setProjectMenu(false)
            }}
          >
            <span>RP</span>
            <span>
              <strong>Robert</strong>
              <small>Producer</small>
            </span>
            <span aria-hidden="true">•••</span>
          </button>
          {profile ? (
            <div className="popover profile-pop">
              <b>Robert</b>
              <small>Local producer profile</small>
              <button type="button" onClick={() => goPage('settings')}>
                Project settings
              </button>
            </div>
          ) : null}
        </div>
      </aside>

      {mobile ? (
        <button type="button" className="sidebar-scrim" aria-label="Close navigation" onClick={() => setMobile(false)} />
      ) : null}

      <section className="workspace">
        <header className="topbar">
          <div className="top-left">
            <button
              type="button"
              className="mobile-menu"
              aria-label="Toggle navigation"
              aria-expanded={mobile}
              aria-controls="primary-navigation"
              onClick={() => setMobile((open) => !open)}
            >
              ☰
            </button>
            <div className="crumbs">
              {view === 'projects' ? (
                <>
                  <strong>Projects</strong>
                  <span className="workspace-chip">WORKSPACE</span>
                </>
              ) : null}
              {view === 'new-project' ? (
                <>
                  <button type="button" onClick={() => goWorkspace(onOpenProjects)}>
                    Projects
                  </button>
                  <span aria-hidden="true">›</span>
                  <b>Create project</b>
                </>
              ) : null}
              {isStudio ? (
                <>
                  <button type="button" onClick={() => goWorkspace(onOpenProjects)}>
                    Projects
                  </button>
                  <span aria-hidden="true">›</span>
                  <strong>{projectName}</strong>
                  <span aria-hidden="true">›</span>
                  <b>{activeLabel}</b>
                  <span className="phase">7 PHASES</span>
                </>
              ) : null}
            </div>
          </div>
          <div className="top-actions">
            <button type="button" className="icon-button" aria-label="Search workspace">
              ⌕
            </button>
            {view === 'projects' ? (
              <button type="button" className="btn primary" onClick={onCreateProject}>
                ＋ New project
              </button>
            ) : null}
            {isStudio ? (
              <>
                <button type="button" className="icon-button has-dot" aria-label="Notifications">
                  ◦
                  <i />
                </button>
                <StatusBadge status={backendStatus} label={`Backend ${backendStatus}`} />
              </>
            ) : null}
          </div>
        </header>

        <div id="main-content" className="page-scroll" tabIndex={-1}>
          {children}
        </div>
      </section>
    </main>
  )
}
