import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, type Project } from './api/client'
import { AppShell, type PageId } from './components/AppShell'
import { StoryboardStudio } from './pages/StoryboardStudio'
import { StudioProvider } from './studio/StudioContext'
import { useStudio } from './studio/StudioState'
import { countShots } from './studio/utils'

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
  const pathMatch = window.location.pathname.match(/^\/projects\/([^/]+)\/studio\/([^/]+)\/?$/)
  if (pathMatch) {
    const [, projectId, route] = pathMatch
    return {
      projectId: decodeURIComponent(projectId || DEFAULT_PROJECT_ID),
      page: ROUTE_TO_PAGE[route] ?? 'overview',
    }
  }

  // Hash fallback for static hosts: #/overview or #/storyboard
  const hash = window.location.hash.replace(/^#\/?/, '')
  if (hash && ROUTE_TO_PAGE[hash]) {
    return { projectId: DEFAULT_PROJECT_ID, page: ROUTE_TO_PAGE[hash] }
  }
  if (hash && (hash === 'story' || hash in PAGE_TO_ROUTE)) {
    return { projectId: DEFAULT_PROJECT_ID, page: hash as PageId }
  }

  return { projectId: DEFAULT_PROJECT_ID, page: 'overview' }
}

function studioPath(projectId: string, page: PageId): string {
  return `/projects/${encodeURIComponent(projectId || DEFAULT_PROJECT_ID)}/studio/${PAGE_TO_ROUTE[page]}`
}

function StudioAppShell({
  activePage,
  backendStatus,
  projectId,
  projects,
  projectsError,
  runtimeLabel,
  runtimeDetail,
  onNavigate,
  onSelectProject,
  onRefreshStatus,
  children,
}: {
  activePage: PageId
  backendStatus: string
  projectId: string
  projects: Project[]
  projectsError: string | null
  runtimeLabel: string
  runtimeDetail: string
  onNavigate: (page: PageId) => void
  onSelectProject: (projectId: string) => void
  onRefreshStatus?: () => void
  children: React.ReactNode
}) {
  const { data, setAnimaticOpen, setMessage } = useStudio()
  const shotCount = useMemo(() => (data ? countShots(data.chapters) : undefined), [data])
  const apiProjectName = projects.find((project) => project.id === projectId)?.name
  const projectName = data?.story.title ?? apiProjectName ?? 'A New Journey'

  return (
    <AppShell
      activePage={activePage}
      backendStatus={backendStatus}
      projectId={projectId}
      projectName={projectName}
      projects={projects}
      projectsError={projectsError}
      shotCount={shotCount}
      runtimeLabel={runtimeLabel}
      runtimeDetail={runtimeDetail}
      onNavigate={onNavigate}
      onSelectProject={onSelectProject}
      onRefreshStatus={onRefreshStatus}
      onSaveDraft={() =>
        setMessage('Draft state is current in this browser session. Server data remains canonical when connected.')
      }
      onPreviewAnimatic={() => setAnimaticOpen(true)}
    >
      {children}
    </AppShell>
  )
}

function App() {
  const [routeState, setRouteState] = useState(readStudioRoute)
  const [backendStatus, setBackendStatus] = useState('checking')
  const [projects, setProjects] = useState<Project[]>([])
  const [projectsError, setProjectsError] = useState<string | null>(null)
  const [runtimeLabel, setRuntimeLabel] = useState('Runtime status')
  const [runtimeDetail, setRuntimeDetail] = useState('Checking backend…')
  const activePage = routeState.page

  const navigate = useCallback(
    (page: PageId, options?: { replace?: boolean; projectId?: string }) => {
      const nextProjectId = options?.projectId || routeState.projectId || DEFAULT_PROJECT_ID
      const next = { projectId: nextProjectId, page }
      const path = studioPath(next.projectId, page)
      const method = options?.replace ? 'replaceState' : 'pushState'
      if (window.location.pathname !== path) {
        window.history[method]({ page, projectId: next.projectId }, '', path)
      }
      setRouteState(next)
    },
    [routeState.projectId],
  )

  const selectProject = useCallback(
    (nextProjectId: string) => {
      navigate(activePage, { projectId: nextProjectId })
    },
    [activePage, navigate],
  )

  const refreshBackendStatus = useCallback(async () => {
    try {
      const [health, runtime] = await Promise.all([
        api.health(),
        api.runtimeStatus().catch(() => null),
      ])
      setBackendStatus(normalizeBackendStatus(runtime?.status || health.status))
      if (runtime) {
        const comfy = String(runtime.comfyui?.status ?? 'unknown')
        const gpu = runtime.gpu && typeof runtime.gpu === 'object' ? runtime.gpu : null
        const gpuName =
          gpu && 'name' in gpu && typeof gpu.name === 'string'
            ? gpu.name
            : gpu && 'gpu_name' in gpu && typeof gpu.gpu_name === 'string'
              ? gpu.gpu_name
              : null
        setRuntimeLabel(comfy === 'ok' || comfy === 'healthy' ? 'ComfyUI reachable' : `ComfyUI ${comfy}`)
        setRuntimeDetail(gpuName ? `${gpuName}` : `Phase ${runtime.current_phase ?? 'unknown'}`)
      } else {
        setRuntimeLabel(`Backend ${normalizeBackendStatus(health.status)}`)
        setRuntimeDetail('Runtime status unavailable')
      }
    } catch {
      setBackendStatus('unavailable')
      setRuntimeLabel('Backend unavailable')
      setRuntimeDetail('Start API or use local demo plan')
    }
  }, [])

  const refreshProjects = useCallback(async () => {
    try {
      const list = await api.listProjects()
      setProjects(list)
      setProjectsError(null)
    } catch (error) {
      setProjects([])
      setProjectsError(
        error instanceof Error
          ? `Projects API unavailable: ${error.message}`
          : 'Projects API unavailable.',
      )
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
    const initial = window.setTimeout(() => {
      void refreshBackendStatus()
      void refreshProjects()
    }, 0)
    const timer = window.setInterval(() => {
      void refreshBackendStatus()
    }, 30_000)
    return () => {
      window.clearTimeout(initial)
      window.clearInterval(timer)
    }
  }, [refreshBackendStatus, refreshProjects])

  return (
    <StudioProvider backendStatus={backendStatus} onNavigate={navigate}>
      <StudioAppShell
        activePage={activePage}
        backendStatus={backendStatus}
        projectId={routeState.projectId}
        projects={projects}
        projectsError={projectsError}
        runtimeLabel={runtimeLabel}
        runtimeDetail={runtimeDetail}
        onNavigate={navigate}
        onSelectProject={selectProject}
        onRefreshStatus={() => {
          void refreshBackendStatus()
          void refreshProjects()
        }}
      >
        <StoryboardStudio page={activePage} backendStatus={backendStatus} onNavigate={navigate} />
      </StudioAppShell>
    </StudioProvider>
  )
}

export default App
