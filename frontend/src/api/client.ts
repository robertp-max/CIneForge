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

export type RuntimeStatus = {
  status: string
  environment: string
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
    supported_states: string[]
  }
  disabled_actions: Record<string, string>
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
}
