import { useCallback, useEffect, useState } from 'react'
import { api, type Project } from './api/client'
import { AppShell, type PageId, type ShellView } from './components/AppShell'
import { Projects } from './pages/Projects'
import { StoryboardStudio } from './pages/StoryboardStudio'

const DEFAULT_PROJECT_ID = 'a-new-journey'

const PAGE_TO_ROUTE: Record<PageId, string> = {
  overview: 'overview',
  storyboard: 'storyboard',
  story: 'story',
  characters: 'characters',
  voices: 'voices',
  images: 'starting-images',
  routing: 'model-routing',
  workflows: 'workflows',
  exports: 'exports',
  settings: 'settings',
}

const ROUTE_TO_PAGE: Record<string, PageId> = {
  overview: 'overview',
  storyboard: 'storyboard',
  story: 'story',
  characters: 'characters',
  voices: 'voices',
  'starting-images': 'images',
  images: 'images',
  'model-routing': 'routing',
  routing: 'routing',
  workflows: 'workflows',
  exports: 'exports',
  settings: 'settings',
}

type AppRoute =
  | { kind: 'projects' }
  | { kind: 'new-project' }
  | { kind: 'studio'; projectId: string; page: PageId }

type ParsedRoute = {
  route: AppRoute
  canonicalPath?: string
}

function normalizeBackendStatus(value: string | undefined): string {
  const status = (value ?? 'unknown').toLowerCase()
  if (status === 'ok' || status === 'healthy' || status === 'up' || status === 'ready') return 'ok'
  if (status === 'degraded' || status === 'partial') return 'degraded'
  if (status === 'disabled') return 'disabled'
  if (status === 'checking' || status === 'loading') return 'checking'
  return 'unavailable'
}

function studioPath(projectId: string, page: PageId): string {
  return `/projects/${encodeURIComponent(projectId || DEFAULT_PROJECT_ID)}/studio/${PAGE_TO_ROUTE[page]}`
}

function routePath(route: AppRoute): string {
  if (route.kind === 'projects') return '/projects'
  if (route.kind === 'new-project') return '/projects/new'
  return studioPath(route.projectId, route.page)
}

function readAppRoute(pathname = window.location.pathname): ParsedRoute {
  if (pathname === '/' || pathname === '') {
    return { route: { kind: 'projects' }, canonicalPath: '/projects' }
  }

  if (/^\/projects\/?$/.test(pathname)) {
    return { route: { kind: 'projects' } }
  }

  if (/^\/projects\/new\/?$/.test(pathname)) {
    return { route: { kind: 'new-project' } }
  }

  const studioMatch = pathname.match(/^\/projects\/([^/]+)\/studio\/([^/]+)\/?$/)
  if (studioMatch) {
    const [, encodedProjectId, routeSegment] = studioMatch
    try {
      const projectId = decodeURIComponent(encodedProjectId || DEFAULT_PROJECT_ID)
      const page = ROUTE_TO_PAGE[routeSegment]
      const route: AppRoute = { kind: 'studio', projectId, page: page ?? 'overview' }
      return page ? { route } : { route, canonicalPath: routePath(route) }
    } catch {
      return { route: { kind: 'projects' }, canonicalPath: '/projects' }
    }
  }

  return { route: { kind: 'projects' }, canonicalPath: '/projects' }
}

function App() {
  const [routeState, setRouteState] = useState<AppRoute>(() => readAppRoute().route)
  const [backendStatus, setBackendStatus] = useState('checking')
  const [projectName, setProjectName] = useState('A New Journey')
  const [selectedProjectId, setSelectedProjectId] = useState(DEFAULT_PROJECT_ID)
  const [projectCount, setProjectCount] = useState(0)

  const navigateTo = useCallback((route: AppRoute, options?: { replace?: boolean }) => {
    const path = routePath(route)
    const method = options?.replace ? 'replaceState' : 'pushState'
    if (window.location.pathname !== path) {
      window.history[method](route, '', path)
    }
    setRouteState(route)
  }, [])

  const navigateStudio = useCallback(
    (page: PageId) => {
      const projectId = routeState.kind === 'studio' ? routeState.projectId : selectedProjectId
      navigateTo({ kind: 'studio', projectId, page })
    },
    [navigateTo, routeState, selectedProjectId],
  )

  const openProject = useCallback(
    (projectId: string, name?: string) => {
      setSelectedProjectId(projectId)
      if (name) setProjectName(name)
      navigateTo({ kind: 'studio', projectId, page: 'overview' })
    },
    [navigateTo],
  )

  const handleProjectsLoaded = useCallback((projects: Project[]) => {
    setProjectCount(projects.length)
    setSelectedProjectId((currentId) => {
      if (currentId !== DEFAULT_PROJECT_ID) return currentId
      const preferred = projects.find((project) => project.name === 'A New Journey') ?? projects[0]
      if (!preferred) return currentId
      setProjectName(preferred.name)
      return preferred.id
    })
  }, [])

  useEffect(() => {
    let active = true
    void api.listProjects().then((projects) => {
      if (active) handleProjectsLoaded(projects)
    }).catch(() => {
      if (active) setProjectCount(0)
    })
    return () => {
      active = false
    }
  }, [handleProjectsLoaded])

  const refreshBackendStatus = useCallback(async () => {
    try {
      const health = await api.health()
      setBackendStatus(normalizeBackendStatus(health.status))
    } catch {
      setBackendStatus('unavailable')
    }
  }, [])

  useEffect(() => {
    const parsed = readAppRoute()
    if (parsed.canonicalPath && window.location.pathname !== parsed.canonicalPath) {
      window.history.replaceState(parsed.route, '', parsed.canonicalPath)
    }
    const onPopState = () => setRouteState(readAppRoute().route)
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  useEffect(() => {
    if (routeState.kind !== 'studio') return
    if (routeState.projectId === DEFAULT_PROJECT_ID) return

    let active = true
    void api
      .getProject(routeState.projectId)
      .then((project) => {
        if (active) {
          setProjectName(project.name)
          setSelectedProjectId(project.id)
        }
      })
      .catch(() => {
        if (active) setProjectName('Selected project')
      })
    return () => {
      active = false
    }
  }, [routeState])

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0 })
  }, [routeState])

  useEffect(() => {
    const initial = window.setTimeout(() => void refreshBackendStatus(), 0)
    const timer = window.setInterval(() => {
      void refreshBackendStatus()
    }, 30_000)
    return () => {
      window.clearTimeout(initial)
      window.clearInterval(timer)
    }
  }, [refreshBackendStatus])

  const shellView: ShellView =
    routeState.kind === 'studio' ? 'studio' : routeState.kind === 'new-project' ? 'new-project' : 'projects'
  const activePage = routeState.kind === 'studio' ? routeState.page : 'overview'
  const activeProjectId = routeState.kind === 'studio' ? routeState.projectId : selectedProjectId
  const activeProjectName =
    routeState.kind === 'studio' && routeState.projectId === DEFAULT_PROJECT_ID
      ? 'A New Journey'
      : projectName

  return (
    <AppShell
      activePage={activePage}
      backendStatus={backendStatus}
      projectId={activeProjectId}
      projectName={activeProjectName}
      projectCount={projectCount}
      view={shellView}
      onNavigate={navigateStudio}
      onOpenProjects={() => navigateTo({ kind: 'projects' })}
      onCreateProject={() => navigateTo({ kind: 'new-project' })}
      onRefreshStatus={() => void refreshBackendStatus()}
    >
      {routeState.kind === 'projects' ? (
        <Projects
          key="projects-list"
          mode="list"
          onCreateNew={() => navigateTo({ kind: 'new-project' })}
          onOpenProject={openProject}
          onProjectsLoaded={handleProjectsLoaded}
        />
      ) : null}
      {routeState.kind === 'new-project' ? (
        <Projects
          key="project-create"
          mode="create"
          onBackToProjects={() => navigateTo({ kind: 'projects' })}
          onOpenProject={openProject}
        />
      ) : null}
      {routeState.kind === 'studio' ? (
        <StoryboardStudio
          key={routeState.projectId}
          page={routeState.page}
          projectId={routeState.projectId}
          backendStatus={backendStatus}
          onNavigate={navigateStudio}
        />
      ) : null}
    </AppShell>
  )
}

export default App
