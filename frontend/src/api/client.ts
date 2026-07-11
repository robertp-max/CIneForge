const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000'

export const API_BASE_URL =
  import.meta.env.VITE_CINEFORGE_API_BASE_URL?.replace(/\/$/, '') ?? DEFAULT_API_BASE_URL

export type Project = {
  id: string
  name: string
  description: string | null
  created_at: string
  persistence: string
}

export type Campaign = {
  id: string
  project_id: string
  name: string
  target_duration_sec: number | null
  created_at: string
  persistence: string
}

export type Job = {
  id: string
  status: string
  detail: string
  workflow_run_id: string | null
  comfy_prompt_id: string | null
  error_message: string | null
}

export type HealthResponse = Record<string, unknown> & {
  status?: string
}

export type RootStatus = {
  app: string
  status: string
  message: string
  docs_url: string
  frontend_dev_url: string
  generation_enabled: boolean
  prompt_submission_publicly_accessible: boolean
  current_phase: string
}

export type RuntimeStatus = {
  status: string
  environment: string
  current_phase: string
  comfyui: HealthResponse
  object_info: {
    status: string
    available: boolean
    class_count: number | null
    error: string | null
  }
  gpu: HealthResponse
  ffmpeg: HealthResponse
  queue: {
    worker_enabled: boolean
    submission_enabled: boolean
    controlled_submission_enabled: boolean
    public_submission_enabled: boolean
    supported_states: string[]
  }
  disabled_actions: Record<string, string>
}

export type Story = {
  id: string
  project_id: string
  title: string
  base_story: string
  target_duration_sec: number
  logline: string | null
  synopsis: string | null
  approval_state: string
}

export type StoryboardAggregate = {
  story: Story
  chapters: Array<{
    id: string
    order_index: number
    title: string
    summary: string | null
    duration_sec: number
    scenes: Array<{
      id: string
      order_index: number
      title: string
      summary: string | null
      duration_sec: number
      shots: Array<{
        id: string
        order_index: number
        display_label: string
        title: string
        duration_sec: number
        duration_override_reason: string | null
        visual_description: string | null
        approval_state: string
        production_status: string
        blocked_reason: string | null
        continuity_source_shot_id: string | null
        narration: string | null
      }>
    }>
  }>
  characters: Array<{ id: string; name: string; role: string | null; approval_state: string }>
  voices: Array<{ id: string; name: string; source_type: string; consent_confirmed: boolean; approval_state: string }>
}

export type Readiness = {
  ready: boolean
  planned_duration_sec: number
  target_duration_sec: number
  discrepancy_sec: number
  reasons: Array<{ code: string; message: string; entity_id: string | null; blocking: boolean }>
}

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, detail: unknown) {
    super(formatApiError(status, detail))
    this.status = status
    this.detail = detail
  }
}

function formatApiError(status: number, detail: unknown): string {
  if (typeof detail === 'string') {
    return detail
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === 'object' && 'msg' in item) {
          return String(item.msg)
        }
        return JSON.stringify(item)
      })
      .join(', ')
  }

  if (detail && typeof detail === 'object' && 'detail' in detail) {
    return formatApiError(status, (detail as { detail: unknown }).detail)
  }

  return `Request failed with status ${status}`
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...init?.headers,
      },
    })
  } catch (error) {
    throw new Error(
      `Backend unreachable at ${API_BASE_URL}. Start FastAPI or update VITE_CINEFORGE_API_BASE_URL. ${
        error instanceof Error ? error.message : ''
      }`,
      { cause: error },
    )
  }

  const contentType = response.headers.get('content-type') ?? ''
  const body = contentType.includes('application/json') ? await response.json() : await response.text()

  if (!response.ok) {
    throw new ApiError(response.status, body)
  }

  return body as T
}

export const api = {
  rootStatus: () => request<RootStatus>('/'),
  health: () => request<HealthResponse>('/health'),
  comfyHealth: () => request<HealthResponse>('/health/comfy'),
  gpuHealth: () => request<HealthResponse>('/health/gpu'),
  ffmpegHealth: () => request<HealthResponse>('/health/ffmpeg'),
  runtimeStatus: () => request<RuntimeStatus>('/runtime/status'),
  listProjects: () => request<Project[]>('/projects'),
  createProject: (payload: { name: string; description?: string | null }) =>
    request<Project>('/projects', { method: 'POST', body: JSON.stringify(payload) }),
  getProject: (projectId: string) => request<Project>(`/projects/${projectId}`),
  listCampaigns: (projectId?: string) =>
    request<Campaign[]>(projectId ? `/campaigns?project_id=${projectId}` : '/campaigns'),
  createCampaign: (payload: {
    project_id: string
    name: string
    target_duration_sec?: number | null
  }) => request<Campaign>('/campaigns', { method: 'POST', body: JSON.stringify(payload) }),
  getCampaign: (campaignId: string) => request<Campaign>(`/campaigns/${campaignId}`),
  listJobs: (limit = 25) => request<Job[]>(`/jobs?limit=${limit}`),
  getJob: (jobId: string) => request<Job>(`/jobs/${jobId}`),
  listStories: (projectId?: string) => request<Story[]>(projectId ? `/storyboard/stories?project_id=${projectId}` : '/storyboard/stories'),
  createStory: (payload: { project_id: string; title: string; base_story: string; target_duration_sec: number }) =>
    request<Story>('/storyboard/stories', { method: 'POST', body: JSON.stringify(payload) }),
  updateStory: (storyId: string, payload: Record<string, unknown>) =>
    request<Story>(`/storyboard/stories/${storyId}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  aggregate: (storyId: string) => request<StoryboardAggregate>(`/storyboard/stories/${storyId}/aggregate`),
  readiness: (storyId: string) => request<Readiness>(`/storyboard/stories/${storyId}/readiness`),
  createChapter: (storyId: string, payload: { title: string; summary?: string; order_index: number }) =>
    request(`/storyboard/stories/${storyId}/chapters`, { method: 'POST', body: JSON.stringify(payload) }),
  createScene: (chapterId: string, payload: { title: string; summary?: string; order_index: number }) =>
    request(`/storyboard/chapters/${chapterId}/scenes`, { method: 'POST', body: JSON.stringify(payload) }),
  createShot: (sceneId: string, payload: { title: string; duration_sec: number; duration_override_reason?: string; order_index: number; visual_description?: string }) =>
    request(`/storyboard/scenes/${sceneId}/shots`, { method: 'POST', body: JSON.stringify(payload) }),
  updateShot: (shotId: string, payload: Record<string, unknown>) =>
    request(`/storyboard/shots/${shotId}`, { method: 'PUT', body: JSON.stringify(payload) }),
  createCharacter: (storyId: string, payload: { name: string; role?: string }) =>
    request(`/storyboard/stories/${storyId}/characters`, { method: 'POST', body: JSON.stringify(payload) }),
  createVoice: (storyId: string, payload: { name: string; source_type: string; consent_confirmed: boolean; consent_required: boolean }) =>
    request(`/storyboard/stories/${storyId}/voices`, { method: 'POST', body: JSON.stringify(payload) }),
  approveStoryboard: (storyId: string, approvedBy: string) =>
    request(`/storyboard/stories/${storyId}/approve`, { method: 'POST', body: JSON.stringify({ approved_by: approvedBy }) }),
}
