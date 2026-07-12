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

export type Shot = {
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
  prompt_positive?: string | null
  prompt_negative?: string | null
  camera_notes?: string | null
  lighting_notes?: string | null
  technical_notes?: string | null
}

export type Scene = {
  id: string
  order_index: number
  title: string
  summary: string | null
  duration_sec: number
  shots: Shot[]
}

export type Chapter = {
  id: string
  order_index: number
  title: string
  summary: string | null
  duration_sec: number
  scenes: Scene[]
}

export type Character = {
  id: string
  name: string
  role: string | null
  approval_state: string
  description?: string | null
  visual_notes?: string | null
  continuity_notes?: string | null
}

/** Exact eight voice source modes exposed by the Voice UI. */
export const VOICE_SOURCE_MODES = [
  'placeholder',
  'stock_library',
  'user_provided',
  'narration',
  'dialogue',
  'voiceover',
  'ambient',
  'tts_synthetic',
] as const

export type VoiceSourceMode = (typeof VOICE_SOURCE_MODES)[number]

export const VOICE_SOURCE_MODE_LABELS: Record<VoiceSourceMode, string> = {
  placeholder: 'Placeholder',
  stock_library: 'Stock library',
  user_provided: 'User-provided sample',
  narration: 'Narration',
  dialogue: 'Character dialogue',
  voiceover: 'Voiceover',
  ambient: 'Ambient / background',
  tts_synthetic: 'Synthetic TTS (planning)',
}

export type Voice = {
  id: string
  name: string
  source_type: string
  consent_confirmed: boolean
  approval_state: string
  consent_required?: boolean
  language?: string | null
  notes?: string | null
  preview_available?: boolean
  provider?: string | null
}

export type StoryboardAggregate = {
  story: Story
  chapters: Chapter[]
  characters: Character[]
  voices: Voice[]
}

export type ReadinessReason = {
  code: string
  message: string
  entity_id: string | null
  blocking: boolean
}

export type Readiness = {
  ready: boolean
  planned_duration_sec: number
  target_duration_sec: number
  discrepancy_sec: number
  reasons: ReadinessReason[]
}

export type StartingImagePlan = {
  id: string
  story_id: string
  shot_id: string | null
  character_id: string | null
  label: string
  purpose: string
  aspect_ratio: string | null
  approval_state: string
  asset_status: string
  notes: string | null
  generation_allowed: boolean
}

export type ModelRouteProposal = {
  id: string
  capability: string
  recommended_model: string | null
  recommended_provider: string | null
  status: string
  evidence: string | null
  notes: string | null
  verified: boolean
}

export type WorkflowRegistryEntry = {
  id: string
  name: string
  category: string
  installed: boolean | null
  validated: boolean | null
  benchmarked: boolean | null
  status: string
  evidence: string | null
  disabled_reason: string | null
}

export type StorySettings = {
  story_id: string
  duration_min_sec: number
  duration_max_sec: number
  approval_policy: string
  continuity_policy: string
  consent_policy: string
  aspect_ratio: string
  render_approval_required: boolean
  generation_enabled: boolean
  notes: string | null
}

export type VoicePreviewResult = {
  voice_id: string
  status: string
  message: string
  preview_url: string | null
  provider: string | null
  generation_performed: boolean
}

export type ExportLinks = {
  json_url: string
  shot_list_csv_url: string
  pdf_available: boolean
  edl_available: boolean
  render_package_available: boolean
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
          return String((item as { msg: unknown }).msg)
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

/** Soft GET helper: returns null for 404/405/501 so pages can show truthful unavailable states. */
async function optionalRequest<T>(path: string, init?: RequestInit): Promise<T | null> {
  try {
    return await request<T>(path, init)
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 405 || error.status === 501)) {
      return null
    }
    throw error
  }
}

export function exportJsonUrl(storyId: string): string {
  return `${API_BASE_URL}/storyboard/stories/${storyId}/export.json`
}

export function exportShotListCsvUrl(storyId: string): string {
  return `${API_BASE_URL}/storyboard/stories/${storyId}/shot-list.csv`
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

  listStories: (projectId?: string) =>
    request<Story[]>(projectId ? `/storyboard/stories?project_id=${projectId}` : '/storyboard/stories'),
  createStory: (payload: {
    project_id: string
    title: string
    base_story: string
    target_duration_sec: number
  }) => request<Story>('/storyboard/stories', { method: 'POST', body: JSON.stringify(payload) }),
  updateStory: (storyId: string, payload: Record<string, unknown>) =>
    request<Story>(`/storyboard/stories/${storyId}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  getStory: (storyId: string) => request<Story>(`/storyboard/stories/${storyId}`),
  aggregate: (storyId: string) => request<StoryboardAggregate>(`/storyboard/stories/${storyId}/aggregate`),
  readiness: (storyId: string) => request<Readiness>(`/storyboard/stories/${storyId}/readiness`),

  createChapter: (storyId: string, payload: { title: string; summary?: string; order_index: number }) =>
    request(`/storyboard/stories/${storyId}/chapters`, { method: 'POST', body: JSON.stringify(payload) }),
  updateChapter: (chapterId: string, payload: Record<string, unknown>) =>
    request(`/storyboard/chapters/${chapterId}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  createScene: (chapterId: string, payload: { title: string; summary?: string; order_index: number }) =>
    request(`/storyboard/chapters/${chapterId}/scenes`, { method: 'POST', body: JSON.stringify(payload) }),
  updateScene: (sceneId: string, payload: Record<string, unknown>) =>
    request(`/storyboard/scenes/${sceneId}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  createShot: (
    sceneId: string,
    payload: {
      title: string
      duration_sec: number
      duration_override_reason?: string
      order_index: number
      visual_description?: string
    },
  ) => request(`/storyboard/scenes/${sceneId}/shots`, { method: 'POST', body: JSON.stringify(payload) }),
  updateShot: (shotId: string, payload: Record<string, unknown>) =>
    request(`/storyboard/shots/${shotId}`, { method: 'PUT', body: JSON.stringify(payload) }),

  createCharacter: (storyId: string, payload: { name: string; role?: string; description?: string }) =>
    request<Character>(`/storyboard/stories/${storyId}/characters`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateCharacter: (characterId: string, payload: Record<string, unknown>) =>
    optionalRequest<Character>(`/storyboard/characters/${characterId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  listCharacters: (storyId: string) =>
    optionalRequest<Character[]>(`/storyboard/stories/${storyId}/characters`),

  createVoice: (
    storyId: string,
    payload: {
      name: string
      source_type: VoiceSourceMode | string
      consent_confirmed: boolean
      consent_required: boolean
      language?: string
      notes?: string
    },
  ) =>
    request<Voice>(`/storyboard/stories/${storyId}/voices`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateVoice: (voiceId: string, payload: Record<string, unknown>) =>
    optionalRequest<Voice>(`/storyboard/voices/${voiceId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  listVoices: (storyId: string) => optionalRequest<Voice[]>(`/storyboard/stories/${storyId}/voices`),
  /** Provider-safe preview: never clones or generates final audio automatically. */
  previewVoice: (voiceId: string, payload?: { text?: string }) =>
    optionalRequest<VoicePreviewResult>(`/storyboard/voices/${voiceId}/preview`, {
      method: 'POST',
      body: JSON.stringify(payload ?? {}),
    }),

  listStartingImages: (storyId: string) =>
    optionalRequest<StartingImagePlan[]>(`/storyboard/stories/${storyId}/starting-images`),
  createStartingImage: (
    storyId: string,
    payload: {
      label: string
      purpose: string
      shot_id?: string | null
      character_id?: string | null
      aspect_ratio?: string
      notes?: string
    },
  ) =>
    optionalRequest<StartingImagePlan>(`/storyboard/stories/${storyId}/starting-images`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateStartingImage: (imageId: string, payload: Record<string, unknown>) =>
    optionalRequest<StartingImagePlan>(`/storyboard/starting-images/${imageId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  listModelRoutes: (storyId: string) =>
    optionalRequest<ModelRouteProposal[]>(`/storyboard/stories/${storyId}/model-routes`),
  listWorkflows: (storyId?: string) =>
    optionalRequest<WorkflowRegistryEntry[]>(
      storyId ? `/storyboard/stories/${storyId}/workflows` : '/runtime/workflows',
    ),

  getSettings: (storyId: string) =>
    optionalRequest<StorySettings>(`/storyboard/stories/${storyId}/settings`),
  updateSettings: (storyId: string, payload: Record<string, unknown>) =>
    optionalRequest<StorySettings>(`/storyboard/stories/${storyId}/settings`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  approveStoryboard: (storyId: string, approvedBy: string) =>
    request(`/storyboard/stories/${storyId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approved_by: approvedBy }),
    }),

  exportLinks: (storyId: string): ExportLinks => ({
    json_url: exportJsonUrl(storyId),
    shot_list_csv_url: exportShotListCsvUrl(storyId),
    pdf_available: false,
    edl_available: false,
    render_package_available: false,
  }),
}
