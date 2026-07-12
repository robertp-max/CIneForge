import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type ReactNode,
} from 'react'
import {
  ApiError,
  api,
  type Readiness,
  type Shot,
  type StoryboardAggregate,
  type VoiceSourceMode,
} from '../api/client'

export type LoadState = 'idle' | 'loading' | 'ready' | 'error' | 'empty'

type StudioContextValue = {
  backendStatus: string
  projectId: string
  setProjectId: (value: string) => void
  storyId: string
  setStoryId: (value: string) => void
  data: StoryboardAggregate | null
  readiness: Readiness | null
  message: string
  setMessage: (value: string) => void
  loadState: LoadState
  error: string | null
  selectedShot: Shot | null
  setSelectedShot: (shot: Shot | null) => void
  animaticOpen: boolean
  setAnimaticOpen: (open: boolean) => void
  busy: boolean
  reload: (id?: string) => Promise<void>
  createStory: (event: FormEvent<HTMLFormElement>) => Promise<void>
  loadExistingStory: (storyId: string) => Promise<void>
  addHierarchy: (kind: 'chapter' | 'scene' | 'shot') => Promise<void>
  addCharacter: (payload: { name: string; role?: string; description?: string }) => Promise<void>
  addVoice: (payload: {
    name: string
    source_type: VoiceSourceMode
    consent_confirmed: boolean
    consent_required: boolean
    language?: string
    notes?: string
  }) => Promise<void>
  saveShot: (shotId: string, payload: Record<string, unknown>) => Promise<void>
  approvePlan: (approvedBy: string) => Promise<void>
  updateStoryFields: (payload: Record<string, unknown>) => Promise<void>
}

const StudioContext = createContext<StudioContextValue | null>(null)

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) return error.message
  return fallback
}

export function StudioProvider({
  backendStatus,
  children,
}: {
  backendStatus: string
  children: ReactNode
}) {
  const [projectId, setProjectId] = useState('')
  const [storyId, setStoryId] = useState('')
  const [data, setData] = useState<StoryboardAggregate | null>(null)
  const [readiness, setReadiness] = useState<Readiness | null>(null)
  const [message, setMessage] = useState(
    'Choose an existing project and create or load a Storyboard Phase 1 story. Server state is canonical.',
  )
  const [loadState, setLoadState] = useState<LoadState>('empty')
  const [error, setError] = useState<string | null>(null)
  const [selectedShot, setSelectedShot] = useState<Shot | null>(null)
  const [animaticOpen, setAnimaticOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  const reload = useCallback(async (id = storyId) => {
    if (!id) {
      setLoadState('empty')
      setData(null)
      setReadiness(null)
      return
    }

    setBusy(true)
    setLoadState('loading')
    setError(null)
    try {
      const [aggregate, nextReadiness] = await Promise.all([api.aggregate(id), api.readiness(id)])
      setData(aggregate)
      setReadiness(nextReadiness)
      setStoryId(aggregate.story.id)
      setProjectId(aggregate.story.project_id)
      setLoadState('ready')
      setMessage('Live planning data loaded from the CineForge backend.')
      setSelectedShot((current) => {
        if (!current) return null
        for (const chapter of aggregate.chapters) {
          for (const scene of chapter.scenes) {
            const match = scene.shots.find((shot) => shot.id === current.id)
            if (match) return match
          }
        }
        return null
      })
    } catch (err) {
      const text = errorMessage(err, 'Unable to load storyboard data.')
      setError(text)
      setLoadState('error')
      setMessage(text)
    } finally {
      setBusy(false)
    }
  }, [storyId])

  useEffect(() => {
    // No localStorage canonical state — session memory only until user loads a story.
  }, [])

  const createStory = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault()
      const form = new FormData(event.currentTarget)
      setBusy(true)
      setError(null)
      try {
        const story = await api.createStory({
          project_id: String(form.get('project_id') ?? '').trim(),
          title: String(form.get('title') ?? '').trim(),
          base_story: String(form.get('base_story') ?? '').trim(),
          target_duration_sec: Number(form.get('target_duration_sec')),
        })
        setProjectId(story.project_id)
        setStoryId(story.id)
        await reload(story.id)
        setMessage(`Created planning story “${story.title}”. No rendering was started.`)
      } catch (err) {
        const text = errorMessage(err, 'Could not create story.')
        setError(text)
        setMessage(text)
        setLoadState('error')
      } finally {
        setBusy(false)
      }
    },
    [reload],
  )

  const loadExistingStory = useCallback(
    async (nextStoryId: string) => {
      const id = nextStoryId.trim()
      if (!id) {
        setMessage('Enter a story UUID to load.')
        return
      }
      setStoryId(id)
      await reload(id)
    },
    [reload],
  )

  const addHierarchy = useCallback(
    async (kind: 'chapter' | 'scene' | 'shot') => {
      if (!data) return
      const title = window.prompt(`New ${kind} title`)
      if (!title?.trim()) return

      setBusy(true)
      try {
        if (kind === 'chapter') {
          await api.createChapter(data.story.id, {
            title: title.trim(),
            order_index: data.chapters.length,
          })
        }

        if (kind === 'scene') {
          const chapter = data.chapters[data.chapters.length - 1] ?? data.chapters[0]
          if (!chapter) throw new Error('Create a chapter before adding a scene.')
          await api.createScene(chapter.id, {
            title: title.trim(),
            order_index: chapter.scenes.length,
          })
        }

        if (kind === 'shot') {
          const chapter = data.chapters[data.chapters.length - 1] ?? data.chapters[0]
          const scene = chapter?.scenes[chapter.scenes.length - 1] ?? chapter?.scenes[0]
          if (!scene) throw new Error('Create a scene before adding a shot.')
          const durationRaw = window.prompt('Shot duration in seconds (normal range 6–12)', '8')
          const duration = Number(durationRaw)
          if (!Number.isFinite(duration) || duration <= 0) {
            throw new Error('Shot duration must be a positive number.')
          }
          const reason =
            duration < 6 || duration > 12
              ? window.prompt('Override reason is required outside 6–12 seconds') ?? ''
              : undefined
          if ((duration < 6 || duration > 12) && !reason?.trim()) {
            throw new Error('Override reason is required for durations outside 6–12 seconds.')
          }
          await api.createShot(scene.id, {
            title: title.trim(),
            duration_sec: duration,
            duration_override_reason: reason?.trim() || undefined,
            order_index: scene.shots.length,
          })
        }

        await reload()
        setMessage(`Added ${kind}. Planning hierarchy updated on the server.`)
      } catch (err) {
        const text = errorMessage(err, 'Could not add planning item.')
        setMessage(text)
        setError(text)
      } finally {
        setBusy(false)
      }
    },
    [data, reload],
  )

  const addCharacter = useCallback(
    async (payload: { name: string; role?: string; description?: string }) => {
      if (!data) return
      setBusy(true)
      try {
        await api.createCharacter(data.story.id, payload)
        await reload()
        setMessage(`Character “${payload.name}” saved. No image generation was started.`)
      } catch (err) {
        const text = errorMessage(err, 'Could not add character.')
        setMessage(text)
        setError(text)
      } finally {
        setBusy(false)
      }
    },
    [data, reload],
  )

  const addVoice = useCallback(
    async (payload: {
      name: string
      source_type: VoiceSourceMode
      consent_confirmed: boolean
      consent_required: boolean
      language?: string
      notes?: string
    }) => {
      if (!data) return
      setBusy(true)
      try {
        await api.createVoice(data.story.id, payload)
        await reload()
        setMessage(
          `Voice profile “${payload.name}” saved as planning data. Cloning and audio generation were not performed.`,
        )
      } catch (err) {
        const text = errorMessage(err, 'Could not add voice profile.')
        setMessage(text)
        setError(text)
      } finally {
        setBusy(false)
      }
    },
    [data, reload],
  )

  const saveShot = useCallback(
    async (shotId: string, payload: Record<string, unknown>) => {
      setBusy(true)
      try {
        await api.updateShot(shotId, payload)
        await reload()
        setMessage('Shot details saved to the backend.')
      } catch (err) {
        const text = errorMessage(err, 'Could not save shot.')
        setMessage(text)
        setError(text)
      } finally {
        setBusy(false)
      }
    },
    [reload],
  )

  const approvePlan = useCallback(
    async (approvedBy: string) => {
      if (!data) return
      setBusy(true)
      try {
        await api.approveStoryboard(data.story.id, approvedBy)
        await reload()
        setMessage(
          'Production plan approved. No timeline slot, queue job, ComfyUI submission, or FFmpeg job was created.',
        )
      } catch (err) {
        if (err instanceof ApiError) {
          setMessage(
            'Approval blocked by backend readiness gates. Review the readiness reasons returned by the server.',
          )
        } else {
          setMessage(errorMessage(err, 'Approval failed.'))
        }
        setError(errorMessage(err, 'Approval failed.'))
      } finally {
        setBusy(false)
      }
    },
    [data, reload],
  )

  const updateStoryFields = useCallback(
    async (payload: Record<string, unknown>) => {
      if (!data) return
      setBusy(true)
      try {
        await api.updateStory(data.story.id, payload)
        await reload()
        setMessage('Story fields updated on the server.')
      } catch (err) {
        const text = errorMessage(err, 'Could not update story.')
        setMessage(text)
        setError(text)
      } finally {
        setBusy(false)
      }
    },
    [data, reload],
  )

  const value = useMemo<StudioContextValue>(
    () => ({
      backendStatus,
      projectId,
      setProjectId,
      storyId,
      setStoryId,
      data,
      readiness,
      message,
      setMessage,
      loadState,
      error,
      selectedShot,
      setSelectedShot,
      animaticOpen,
      setAnimaticOpen,
      busy,
      reload,
      createStory,
      loadExistingStory,
      addHierarchy,
      addCharacter,
      addVoice,
      saveShot,
      approvePlan,
      updateStoryFields,
    }),
    [
      backendStatus,
      projectId,
      storyId,
      data,
      readiness,
      message,
      loadState,
      error,
      selectedShot,
      animaticOpen,
      busy,
      reload,
      createStory,
      loadExistingStory,
      addHierarchy,
      addCharacter,
      addVoice,
      saveShot,
      approvePlan,
      updateStoryFields,
    ],
  )

  return <StudioContext.Provider value={value}>{children}</StudioContext.Provider>
}

export function useStudio(): StudioContextValue {
  const ctx = useContext(StudioContext)
  if (!ctx) {
    throw new Error('useStudio must be used within StudioProvider')
  }
  return ctx
}
