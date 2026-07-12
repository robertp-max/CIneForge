import { useCallback, useEffect, useState } from 'react'
import { api } from './api/client'
import { AppShell, type PageId } from './components/AppShell'
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

function normalizeBackendStatus(value: string | undefined): string {
  const status = (value ?? 'unknown').toLowerCase()
  if (status === 'ok' || status === 'healthy' || status === 'up' || status === 'ready') return 'ok'
  if (status === 'degraded' || status === 'partial') return 'degraded'
  if (status === 'disabled') return 'disabled'
  if (status === 'checking' || status === 'loading') return 'checking'
  return 'unavailable'
}

function readStudioRoute(): { projectId: string; page: PageId } {
  const match = window.location.pathname.match(/^\/projects\/([^/]+)\/studio\/([^/]+)\/?$/)
  if (!match) return { projectId: DEFAULT_PROJECT_ID, page: 'overview' }

  const [, projectId, route] = match
  return {
    projectId: decodeURIComponent(projectId || DEFAULT_PROJECT_ID),
    page: ROUTE_TO_PAGE[route] ?? 'overview',
  }
}

function studioPath(projectId: string, page: PageId): string {
  return `/projects/${encodeURIComponent(projectId || DEFAULT_PROJECT_ID)}/studio/${PAGE_TO_ROUTE[page]}`
}

function App() {
  const [routeState, setRouteState] = useState(readStudioRoute)
  const [backendStatus, setBackendStatus] = useState('checking')
  const activePage = routeState.page

  const navigate = useCallback(
    (page: PageId, options?: { replace?: boolean }) => {
      const next = { projectId: routeState.projectId || DEFAULT_PROJECT_ID, page }
      const path = studioPath(next.projectId, page)
      const method = options?.replace ? 'replaceState' : 'pushState'
      if (window.location.pathname !== path) {
        window.history[method]({ page, projectId: next.projectId }, '', path)
      }
      setRouteState(next)
    },
    [routeState.projectId],
  )

  const refreshBackendStatus = useCallback(async () => {
    try {
      const health = await api.health()
      setBackendStatus(normalizeBackendStatus(health.status))
    } catch {
      setBackendStatus('unavailable')
    }
  }, [])

  useEffect(() => {
    const route = readStudioRoute()
    const canonical = studioPath(route.projectId, route.page)
    if (window.location.pathname !== canonical) {
      window.history.replaceState({ page: route.page, projectId: route.projectId }, '', canonical)
    }

    const onPopState = () => setRouteState(readStudioRoute())
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

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

  return (
    <AppShell
      activePage={activePage}
      backendStatus={backendStatus}
      projectId={routeState.projectId}
      onNavigate={navigate}
      onRefreshStatus={() => void refreshBackendStatus()}
    >
      <StoryboardStudio
        page={activePage}
        backendStatus={backendStatus}
        onNavigate={navigate}
      />
    </AppShell>
  )
}

export default App
