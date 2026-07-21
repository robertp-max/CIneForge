/**
 * Exact structural port of prototype VoicesPage (pagesAssets.tsx / pagesAssets.source.tsx)
 * adapted to production studio context + voice profile / recipe / preview / consent APIs.
 *
 * DOM hierarchy matches the ZIP prototype + screenshot 172742:
 * page-title (VOICE ASSIGNMENT + Consent policy / Add voice profile) →
 * voice-provider-discovery strip (factual Qwen/ElevenLabs/Parler status pills) →
 * voice-summary strip (Profiles / Shot coverage / Unresolved / Consent holds) →
 * voice-layout → voice-grid cards (icon, Waveform decorative, tags, dl, footer) |
 * entity-drawer (VOICE PROFILE header, voice-hero + Waveform, Profile / Recipes / Add tabs).
 *
 * Production create/update/archive + eight setup modes + consented source upload +
 * recipes + provider-safe preview + approval stay wired via api client only
 * (no mock / project store; no cloning; no final audio generation).
 * Discovery is GET-only and never requests previews.
 */
import { useCallback, useEffect, useMemo, useState, type FormEvent, type KeyboardEvent } from 'react'
import {
  api,
  ApiError,
  PARLER_UNAVAILABLE_MESSAGE,
  VOICE_SETUP_MODE_LABELS,
  VOICE_SETUP_MODES,
  type PlanningMediaAsset,
  type RuntimeCatalogModelVariant,
  type Voice,
  type VoicePreview,
  type VoicePreviewJob,
  type VoiceProviderEvidence,
  type VoiceRecipe,
  type VoiceRoutingRecommendation,
  type VoiceSetupMode,
} from '../../api/client'
import { formatDate } from '../../components/formatDate'
import { Button, Empty, Icon, PageTitle, StatusPill } from '../proto/ui'
import { useStudio } from '../StudioState'
import { EmptyState, ErrorState, LoadingState } from '../components/StateBlocks'

const WAVEFORM_BARS = [8, 15, 22, 12, 28, 18, 10, 24, 30, 17, 12, 26, 19, 9, 16, 25, 13, 21, 8, 18]

/** Terminal preview-job statuses — polling must stop when any of these is reached. */
const PREVIEW_JOB_TERMINAL = new Set<VoicePreviewJob['status']>(['complete', 'failed', 'canceled'])

const PREVIEW_API_UNAVAILABLE_MESSAGE =
  'Voice preview API is unavailable on this backend.'

const PREVIEW_JOB_TRACKING_UNAVAILABLE_MESSAGE =
  'Voice preview job tracking is unavailable until a durable preview worker is configured.'

function isPreviewJobTerminal(status: VoicePreviewJob['status'] | undefined): boolean {
  return status != null && PREVIEW_JOB_TERMINAL.has(status)
}

function isParlerSetupMode(mode: string | null | undefined): boolean {
  return (mode || '').toLowerCase() === 'parler_local_voice_design'
}

function parlerUnavailableFromDiscovery(
  evidence: VoiceProviderEvidence | null | undefined,
): string | null {
  if (!evidence) return null
  const status = (evidence.status || '').toLowerCase()
  const available =
    status === 'available' ||
    status === 'ready' ||
    status === 'ok' ||
    evidence.details?.available === true
  if (available) return null
  return (evidence.message || '').trim() || PARLER_UNAVAILABLE_MESSAGE
}

/**
 * Selectable create modes: exact eight Phase 1 modes from VOICE_SETUP_MODES.
 * Defensively exclude any clone-named mode (e.g. qwen_voice_clone must never appear).
 */
const SELECTABLE_VOICE_SETUP_MODES = VOICE_SETUP_MODES.filter(
  (mode) => !String(mode).toLowerCase().includes('clone'),
)

function modeRequiresConsent(mode: VoiceSetupMode | string): boolean {
  return mode === 'user_provided_consented'
}

/**
 * Backend DESIGN_RECIPE_MODES — modes with recipe/design identity fields.
 * Includes qwen_custom_voice (preset speaker recipe field).
 */
function modeRequiresDesign(mode: VoiceSetupMode | string): boolean {
  return (
    mode === 'qwen_voice_design' ||
    mode === 'qwen_custom_voice' ||
    mode === 'elevenlabs_voice_design' ||
    mode === 'parler_local_voice_design'
  )
}

/** Free-text voice design description required (CustomVoice uses preset speaker instead). */
function modeRequiresDesignDescription(mode: VoiceSetupMode | string): boolean {
  return (
    mode === 'qwen_voice_design' ||
    mode === 'elevenlabs_voice_design' ||
    mode === 'parler_local_voice_design'
  )
}

function modeRequiresPresetSpeaker(mode: VoiceSetupMode | string): boolean {
  return mode === 'qwen_custom_voice'
}

function modeRequiresProviderReference(mode: VoiceSetupMode | string): boolean {
  return mode === 'existing_provider_voice'
}

function customVoiceSpeakerFrom(voice: Voice): string {
  const meta = voice.design_metadata_json
  if (!meta || typeof meta !== 'object') return ''
  const raw = meta.custom_voice_speaker
  return typeof raw === 'string' ? raw.trim() : ''
}

function errorText(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback
}

/** First non-empty reason; used for factual disabled control titles. */
function firstReason(...reasons: Array<string | false | null | undefined>): string | undefined {
  for (const reason of reasons) {
    if (typeof reason === 'string' && reason.trim()) return reason
  }
  return undefined
}

function approvalPillLabel(state: string): string {
  const normalized = (state || 'draft').toLowerCase()
  if (normalized === 'approved') return 'Approved'
  if (normalized === 'blocked' || normalized === 'rejected') return 'Blocked'
  if (normalized === 'review' || normalized === 'in_review') return 'Review'
  return 'Draft'
}

/** Card / drawer source label aligned to prototype chrome (still rooted in setup_mode). */
function sourceTypeLabel(voice: Voice): string {
  const mode = voice.setup_mode as VoiceSetupMode
  if (mode === 'placeholder') return 'Placeholder voice'
  if (mode === 'user_provided_consented') return 'User-provided / consented'
  if (
    mode === 'qwen_voice_design' ||
    mode === 'qwen_custom_voice' ||
    mode === 'elevenlabs_voice_design' ||
    mode === 'parler_local_voice_design' ||
    mode === 'existing_provider_voice'
  ) {
    return 'Synthetic voice'
  }
  if (mode === 'manual') return 'Manual profile'
  const raw = (voice.source_type || '').toLowerCase()
  if (raw.includes('placeholder')) return 'Placeholder voice'
  if (raw.includes('user')) return 'User-provided / consented'
  if (raw.includes('synthetic')) return 'Synthetic voice'
  return VOICE_SETUP_MODE_LABELS[mode] ?? voice.setup_mode
}

function genderPresentation(voice: Voice): string {
  return voice.gender_presentation?.trim() || voice.presentation?.trim() || ''
}

function voiceIconSuffix(id: string): string {
  return id.split('-').at(-1) || 'default'
}

/** Decorative waveform only — never real audio. Matches prototype pagesAssets Waveform. */
function Waveform({ active = false }: { active?: boolean }) {
  return (
    <div
      className={`waveform${active ? ' playing' : ''}`}
      role="img"
      aria-label="Decorative waveform placeholder"
      title="Decorative placeholder only — not real audio"
    >
      {WAVEFORM_BARS.map((height, index) => (
        <i key={index} className="wave-bar" style={{ height: `${height}px` }} />
      ))}
    </div>
  )
}

/** Display labels for discovery provider ids — never invent connection state. */
function discoveryProviderLabel(provider: string): string {
  const key = (provider || '').trim().toLowerCase()
  const labels: Record<string, string> = {
    placeholder: 'Placeholder',
    manual: 'Manual',
    existing_provider_voice: 'Existing provider',
    qwen: 'Qwen',
    qwen_custom_voice: 'Qwen custom',
    elevenlabs: 'ElevenLabs',
    parler: 'Parler',
    user_provided_consented: 'User-provided',
  }
  if (labels[key]) return labels[key]
  return provider
    .replace(/_/g, ' ')
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(' ')
}

/** Humanize API status for pills — never remaps to Connected. */
function discoveryStatusPill(status: string | null | undefined): string {
  if (!status || !status.trim()) return 'Unknown'
  return status
    .replace(/_/g, ' ')
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(' ')
}

function isQwenDiscoveryProvider(provider: string): boolean {
  const key = (provider || '').trim().toLowerCase()
  return key === 'qwen' || key === 'qwen_custom_voice' || key.startsWith('qwen')
}

function isParlerDiscoveryProvider(provider: string): boolean {
  return (provider || '').trim().toLowerCase().includes('parler')
}

/**
 * Factual secondary message under each discovery pill.
 * Parler unavailable → exact PARLER_UNAVAILABLE_MESSAGE.
 * Qwen without evidence → "not reported" (never invent "not installed").
 */
function discoveryProviderMessage(item: VoiceProviderEvidence): string | null {
  const provider = (item.provider || '').trim().toLowerCase()
  const status = (item.status || '').trim().toLowerCase()
  const apiMessage = item.message?.trim() || ''

  if (isParlerDiscoveryProvider(provider)) {
    if (status !== 'available') return PARLER_UNAVAILABLE_MESSAGE
    return apiMessage || null
  }

  if (isQwenDiscoveryProvider(provider)) {
    // Prefer API message; never invent "not installed" when evidence is thin.
    if (apiMessage) return apiMessage
    return 'not reported'
  }

  return apiMessage || null
}

type DiscoveryLoadState = 'loading' | 'ready' | 'unavailable'

type CreateDraft = {
  name: string
  mode: VoiceSetupMode
  language: string
  notes: string
  provider: string
  providerVoiceReference: string
  customVoiceSpeaker: string
  characterId: string
  consentConfirmed: boolean
  sourceAssetId: string
  sourceFile: File | null
}

const EMPTY_CREATE: CreateDraft = {
  name: 'New placeholder voice',
  mode: 'placeholder',
  language: 'en',
  notes: '',
  provider: '',
  providerVoiceReference: '',
  customVoiceSpeaker: '',
  characterId: '',
  consentConfirmed: false,
  sourceAssetId: '',
  sourceFile: null,
}

type DrawerTab = 'profile' | 'recipes' | 'create'

export function VoicesPage() {
  const { data, addVoice, busy, reload, setMessage } = useStudio()
  const voices = useMemo(() => data?.voices ?? [], [data?.voices])
  const shots = useMemo(
    () => data?.chapters.flatMap((chapter) => chapter.scenes.flatMap((scene) => scene.shots)) ?? [],
    [data?.chapters],
  )

  const [selectedId, setSelectedId] = useState('')
  const [playing, setPlaying] = useState('')
  const [edit, setEdit] = useState(false)
  const [drawerTab, setDrawerTab] = useState<DrawerTab>('profile')
  const [createDraft, setCreateDraft] = useState<CreateDraft>(EMPTY_CREATE)
  const [sourceAssets, setSourceAssets] = useState<PlanningMediaAsset[]>([])

  const [actionBusy, setActionBusy] = useState(false)
  const [pageError, setPageError] = useState<string | null>(null)
  const [pageNote, setPageNote] = useState<string | null>(null)
  const [approvedBy, setApprovedBy] = useState('')
  const [allowWithoutPreview, setAllowWithoutPreview] = useState(true)

  const [recipes, setRecipes] = useState<VoiceRecipe[]>([])
  const [previews, setPreviews] = useState<VoicePreview[]>([])
  const [resourcesLoading, setResourcesLoading] = useState(false)
  const [recipeProvider, setRecipeProvider] = useState('')
  const [recipeModel, setRecipeModel] = useState('')
  const [recipeName, setRecipeName] = useState('')
  const [recipeDescription, setRecipeDescription] = useState('')
  const [previewText, setPreviewText] = useState(
    'CineForge provider-safe voice preview. Planning only.',
  )
  /** User-started preview job only — never set from mount/select auto-effects. */
  const [activePreviewJob, setActivePreviewJob] = useState<VoicePreviewJob | null>(null)
  /** Factual unavailability from an explicit request or job-tracking poll. */
  const [previewApiUnavailable, setPreviewApiUnavailable] = useState<string | null>(null)

  /** Factual GET /voices/providers/discovery only — never previews. */
  const [discoveryProviders, setDiscoveryProviders] = useState<VoiceProviderEvidence[]>([])
  const [discoveryLoadState, setDiscoveryLoadState] = useState<DiscoveryLoadState>('loading')

  /** Advisory only — never written into assigned provider / profile fields. */
  const [routingRecommendation, setRoutingRecommendation] =
    useState<VoiceRoutingRecommendation | null>(null)
  const [routingVariantId, setRoutingVariantId] = useState('')
  const [routingVariants, setRoutingVariants] = useState<RuntimeCatalogModelVariant[]>([])
  const [routingBusy, setRoutingBusy] = useState(false)
  const [routingError, setRoutingError] = useState<string | null>(null)
  const [routingUnavailable, setRoutingUnavailable] = useState(false)

  const projectId = data?.story.project_id ?? ''
  const loadedStoryId = data?.story.id ?? ''
  const previewJobInFlight =
    activePreviewJob != null && !isPreviewJobTerminal(activePreviewJob.status)
  const actionsBusy = busy || actionBusy || previewJobInFlight
  const busyReason = busy
    ? 'A studio save or reload is already in progress.'
    : actionBusy
      ? 'A voice action is already in progress.'
      : previewJobInFlight
        ? `Preview job ${activePreviewJob?.job_id ?? ''} is ${activePreviewJob?.status ?? 'running'}.`
        : null
  const editReason = !edit
    ? 'Turn on edit (pencil) to change profile fields and save via PATCH /voices/profiles/{id}.'
    : null

  const effectiveSelectedId = voices.some((voice) => voice.id === selectedId)
    ? selectedId
    : (voices[0]?.id ?? '')
  const selected = voices.find((voice) => voice.id === effectiveSelectedId) ?? null
  const selectedLocked = selected?.approval_state === 'approved'
  const lockedReason = selectedLocked
    ? 'Approved profiles are immutable in Phase 1. Create a new profile to change identity or routing fields.'
    : null
  const fieldsDisabledReason = firstReason(busyReason, lockedReason, editReason)
  const coverage = selected
    ? shots.filter((shot) => shot.narration_voice_profile_id === selected.id).length
    : 0

  const shotCoverage = shots.filter((shot) => Boolean(shot.narration_voice_profile_id)).length
  const unresolvedShots = shots.length - shotCoverage
  const consentHolds = voices.filter(
    (voice) => voice.consent_required && !voice.consent_confirmed,
  ).length

  const parlerEvidence =
    discoveryProviders.find((item) => isParlerDiscoveryProvider(item.provider)) ?? null
  const parlerUnavailableReason =
    selected && isParlerSetupMode(selected.setup_mode)
      ? parlerUnavailableFromDiscovery(parlerEvidence)
      : null

  const createConsentRequired = modeRequiresConsent(createDraft.mode)
  const createReason = firstReason(
    busyReason,
    !createDraft.name.trim() &&
      'Enter a profile name before creating via POST /voices/stories/{id}/profiles.',
    createConsentRequired &&
      !createDraft.consentConfirmed &&
      'Confirm consent before saving a user-provided voice source.',
    modeRequiresProviderReference(createDraft.mode) &&
      (!createDraft.provider.trim() || !createDraft.providerVoiceReference.trim()) &&
      'Provider and provider voice reference are required for an existing provider voice.',
    modeRequiresPresetSpeaker(createDraft.mode) &&
      !createDraft.customVoiceSpeaker.trim() &&
      'Choose a preset Qwen CustomVoice speaker identifier. Reference-audio cloning is not accepted.',
    modeRequiresDesignDescription(createDraft.mode) &&
      !createDraft.notes.trim() &&
      'A voice design description is required for this setup mode.',
    createDraft.mode === 'user_provided_consented' &&
      !createDraft.sourceAssetId &&
      !createDraft.notes.trim() &&
      'Upload or select a managed voice source, or record a source description.',
  )
  const uploadSourceReason = firstReason(
    busyReason,
    createDraft.mode !== 'user_provided_consented' &&
      'Managed source upload is only available for user_provided_consented profiles.',
    !createDraft.consentConfirmed && 'Confirm consent before uploading a managed voice source.',
    !createDraft.sourceFile && 'Choose an audio file (.wav, .mp3, .ogg, or .flac) before upload.',
    !projectId && 'Project id is required to upload a managed voice source.',
  )
  const saveReason = firstReason(busyReason, lockedReason, editReason)
  const approveReason = firstReason(
    busyReason,
    lockedReason,
    selected &&
      modeRequiresConsent(selected.setup_mode) &&
      !selected.consent_confirmed &&
      'Confirm consent on this user-provided profile before approving.',
    !approvedBy.trim() &&
      'Enter an approval audit name before approving via POST /voices/profiles/{id}/approve.',
  )
  const archiveReason = firstReason(
    busyReason,
    lockedReason,
    !selected && 'Select a voice profile to archive.',
  )
  const recipeReason = firstReason(
    busyReason,
    lockedReason,
    !selected && 'Select a voice profile first.',
    !(recipeProvider || selected?.provider || '').trim() &&
      'Enter a provider before saving recipe metadata via POST /voices/profiles/{id}/recipes.',
  )
  /** Factual disabled titles only — generation never auto-fires when these clear. */
  const previewRequestReason = firstReason(
    !selected && 'Select a voice profile first.',
    !previewText.trim() && 'Enter preview text before requesting a provider-safe preview job.',
    busyReason,
    lockedReason,
    previewApiUnavailable,
    parlerUnavailableReason,
  )
  const effectiveRecipeProvider = recipeProvider || selected?.provider || ''

  const refreshSourceAssets = useCallback(async () => {
    if (!projectId) return
    try {
      const result = await api.listVoiceSourceAssets(projectId)
      setSourceAssets(result?.items ?? [])
    } catch (error) {
      setPageError(errorText(error, 'Could not load managed voice source assets.'))
    }
  }, [projectId])

  /** Read-only list of recipes + previews for the selected profile. Never requests generation. */
  const loadVoiceResources = useCallback(async (voiceId: string) => {
    if (!voiceId) {
      setRecipes([])
      setPreviews([])
      return
    }
    setResourcesLoading(true)
    try {
      const [nextRecipes, nextPreviews] = await Promise.all([
        api.listVoiceRecipes(voiceId),
        api.listVoicePreviews(voiceId),
      ])
      setRecipes(nextRecipes ?? [])
      setPreviews(nextPreviews ?? [])
    } catch (error) {
      setPageError(errorText(error, 'Could not load recipes and previews.'))
    } finally {
      setResourcesLoading(false)
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => void refreshSourceAssets(), 0)
    return () => window.clearTimeout(timer)
  }, [refreshSourceAssets])

  // listVoicePreviews on select is OK (read-only). Never call requestVoicePreview here.
  useEffect(() => {
    const timer = window.setTimeout(() => void loadVoiceResources(effectiveSelectedId), 0)
    return () => window.clearTimeout(timer)
  }, [effectiveSelectedId, loadVoiceResources])

  /**
   * Poll getVoicePreviewJob ONLY after an explicit user-started job and stop on terminal status.
   * Never starts a preview; never runs on mount/selection alone.
   * Stale jobs for other profiles are cleared in selectVoice / onAddClick (not in an effect).
   */
  useEffect(() => {
    const jobId = activePreviewJob?.job_id
    const status = activePreviewJob?.status
    if (!jobId || isPreviewJobTerminal(status)) return

    let canceled = false
    let timer = 0

    const poll = async () => {
      try {
        const next = await api.getVoicePreviewJob(jobId)
        if (canceled) return
        if (!next) {
          setPreviewApiUnavailable(PREVIEW_JOB_TRACKING_UNAVAILABLE_MESSAGE)
          setActivePreviewJob((current) =>
            current
              ? {
                  ...current,
                  status: 'failed',
                  error_message: PREVIEW_JOB_TRACKING_UNAVAILABLE_MESSAGE,
                  message: PREVIEW_JOB_TRACKING_UNAVAILABLE_MESSAGE,
                }
              : current,
          )
          setPageNote(PREVIEW_JOB_TRACKING_UNAVAILABLE_MESSAGE)
          setMessage(PREVIEW_JOB_TRACKING_UNAVAILABLE_MESSAGE)
          return
        }
        setActivePreviewJob(next)
        if (isPreviewJobTerminal(next.status)) {
          const detail =
            next.message ||
            next.error_message ||
            `Preview job ${next.job_id} finished with status ${next.status}.`
          setPageNote(detail)
          setMessage(detail)
          if (next.voice_profile_id) {
            await loadVoiceResources(next.voice_profile_id)
          }
          return
        }
        timer = window.setTimeout(() => void poll(), 1250)
      } catch (error) {
        if (canceled) return
        const text = errorText(error, PREVIEW_JOB_TRACKING_UNAVAILABLE_MESSAGE)
        if (error instanceof ApiError && (error.status === 503 || error.status === 501)) {
          setPreviewApiUnavailable(text)
        }
        setActivePreviewJob((current) =>
          current
            ? {
                ...current,
                status: 'failed',
                error_message: text,
                message: text,
              }
            : current,
        )
        setPageError(text)
        setMessage(text)
      }
    }

    timer = window.setTimeout(() => void poll(), 500)
    return () => {
      canceled = true
      window.clearTimeout(timer)
    }
  }, [activePreviewJob?.job_id, activePreviewJob?.status, loadVoiceResources, setMessage])

  useEffect(() => {
    let cancelled = false
    const timer = window.setTimeout(() => {
      void (async () => {
        try {
          // Read-only discovery — never requests previews or loads models.
          const result = await api.listVoiceProviderDiscovery()
          if (cancelled) return
          if (!result?.providers?.length) {
            setDiscoveryProviders([])
            setDiscoveryLoadState('unavailable')
            return
          }
          setDiscoveryProviders(result.providers)
          setDiscoveryLoadState('ready')
        } catch {
          if (cancelled) return
          // Soft offline / unreachable — keep 8-mode create UI intact.
          setDiscoveryProviders([])
          setDiscoveryLoadState('unavailable')
        }
      })()
    }, 0)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    const timer = window.setTimeout(() => {
      void (async () => {
        try {
          const catalog = await api.runtimeCatalog()
          if (cancelled) return
          setRoutingVariants(catalog?.model_variants ?? [])
        } catch {
          if (!cancelled) setRoutingVariants([])
        }
      })()
    }, 0)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [])

  if (!data) return null

  function selectVoice(voice: Voice) {
    setSelectedId(voice.id)
    setDrawerTab('profile')
    setEdit(false)
    setPageError(null)
    setRecipeProvider(voice.provider ?? '')
    // Clear advisory rec + preview job UI on selection change (never apply rec to profile).
    setRoutingRecommendation(null)
    setRoutingError(null)
    setRoutingUnavailable(false)
    setActivePreviewJob((current) =>
      current && current.voice_profile_id !== voice.id ? null : current,
    )
    setPreviewApiUnavailable(null)
  }

  function routingActionLabel(action: VoiceRoutingRecommendation['action']): string {
    if (action === 'recommend_qwen') return 'Recommend Qwen'
    if (action === 'keep_native') return 'Keep native speech'
    if (action === 'keep_approved') return 'Keep approved assignment'
    return 'No recommendation'
  }

  async function fetchRoutingRecommendation() {
    if (!loadedStoryId) return
    setRoutingBusy(true)
    setRoutingError(null)
    setRoutingUnavailable(false)
    try {
      // Always pass approved flag from current assignment — never overwrite approved profiles.
      const approved = selected?.approval_state === 'approved'
      const result = await api.recommendVoiceRouting({
        story_id: loadedStoryId,
        model_variant_id: routingVariantId || null,
        existing_assignment_approved: approved,
        existing_provider: selected?.provider ?? null,
      })
      if (result == null) {
        setRoutingRecommendation(null)
        setRoutingUnavailable(true)
        setMessage(
          'Voice routing recommendation API is unavailable. Assigned provider was not changed.',
        )
        return
      }
      setRoutingRecommendation(result)
      setMessage(
        approved
          ? 'Routing recommendation loaded as advisory only — approved assignment was not modified.'
          : `Routing recommendation: ${routingActionLabel(result.action)}. Assigned provider was not changed.`,
      )
    } catch (error) {
      const text = errorText(error, 'Could not load voice routing recommendation.')
      setRoutingError(text)
      setRoutingRecommendation(null)
      setMessage(text)
    } finally {
      setRoutingBusy(false)
    }
  }

  function onCardKeyDown(event: KeyboardEvent<HTMLElement>, voice: Voice) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      selectVoice(voice)
    }
  }

  function playPlaceholder(id: string) {
    setPlaying((current) => (current === id ? '' : id))
    if (playing !== id) {
      setMessage('Playing local placeholder sample — decorative only, not real audio.')
      window.setTimeout(() => setPlaying(''), 2400)
    }
  }

  function onAddClick() {
    setDrawerTab('create')
    setCreateDraft({ ...EMPTY_CREATE })
    setEdit(true)
    setPageError(null)
    setPageNote(null)
    setRoutingRecommendation(null)
    setRoutingError(null)
    setRoutingUnavailable(false)
    setActivePreviewJob(null)
    setPreviewApiUnavailable(null)
    setMessage('Complete the eight-mode setup form to create a planning voice profile.')
  }

  async function onCreate(event: FormEvent) {
    event.preventDefault()
    setPageError(null)
    setPageNote(null)
    if (createReason) {
      setMessage(createReason)
      return
    }
    const draft = createDraft

    const saved = await addVoice({
      name: draft.name.trim(),
      setup_mode: draft.mode,
      character_id: draft.characterId || null,
      consent_required: modeRequiresConsent(draft.mode),
      consent_confirmed: modeRequiresConsent(draft.mode) ? draft.consentConfirmed : false,
      consent_notes: modeRequiresConsent(draft.mode)
        ? 'Confirmed in CineForge Storyboard Studio.'
        : undefined,
      language: draft.language.trim() || undefined,
      // Free-text design modes map notes → design_description; other modes use usage_notes.
      // qwen_custom_voice may optionally store usage notes (speaker is the required recipe field).
      usage_notes: modeRequiresDesignDescription(draft.mode)
        ? undefined
        : draft.notes.trim() || undefined,
      provider: modeRequiresProviderReference(draft.mode) ? draft.provider.trim() : undefined,
      provider_voice_reference: modeRequiresProviderReference(draft.mode)
        ? draft.providerVoiceReference.trim()
        : undefined,
      design_description: modeRequiresDesignDescription(draft.mode)
        ? draft.notes.trim()
        : undefined,
      // qwen_custom_voice: preset speaker only — never reference audio / clone payload.
      custom_voice_speaker: modeRequiresPresetSpeaker(draft.mode)
        ? draft.customVoiceSpeaker.trim()
        : undefined,
      source_asset_id:
        draft.mode === 'user_provided_consented' && draft.sourceAssetId ? draft.sourceAssetId : null,
      source_description:
        draft.mode === 'user_provided_consented' ? draft.notes.trim() || undefined : undefined,
    })
    if (!saved) return
    setCreateDraft({ ...EMPTY_CREATE })
    setDrawerTab('profile')
    setEdit(false)
  }

  async function uploadSource() {
    if (uploadSourceReason) {
      setMessage(uploadSourceReason)
      return
    }
    if (!createDraft.sourceFile || !createDraft.consentConfirmed) return
    setActionBusy(true)
    setPageError(null)
    try {
      const result = await api.uploadVoiceSourceAsset(projectId, createDraft.sourceFile, true)
      if (!result) throw new Error('Managed voice-source upload is unavailable on this backend.')
      setCreateDraft((prev) => ({
        ...prev,
        sourceAssetId: result.asset.id,
        notes:
          prev.notes ||
          `Consented managed source: ${result.asset.original_filename ?? createDraft.sourceFile?.name}`,
      }))
      await refreshSourceAssets()
      const note = result.duplicate_of_existing
        ? 'The matching managed voice source already existed and was reused by asset ID.'
        : 'The consented voice source was stored as a managed planning asset.'
      setPageNote(note)
      setMessage(`${note} No voice cloning or generation was performed.`)
    } catch (error) {
      const text = errorText(error, 'Could not upload the managed voice source.')
      setPageError(text)
      setMessage(text)
    } finally {
      setActionBusy(false)
    }
  }

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selected || selectedLocked || !edit) return
    const form = new FormData(event.currentTarget)
    setActionBusy(true)
    setPageError(null)
    setPageNote(null)
    try {
      const emptyToNull = (value: FormDataEntryValue | null) => {
        const text = String(value ?? '').trim()
        return text || null
      }
      // setup_mode is display-locked after create for Phase 1 safety (backend may still accept PATCH).
      // Never PATCH clone/reference-audio fields — CustomVoice remains preset-speaker only.
      const consentChecked = form.get('consent_confirmed') === 'on'
      const updated = await api.updateVoice(selected.id, {
        name: String(form.get('name') || selected.name).trim() || selected.name,
        character_id: emptyToNull(form.get('character_id')),
        provider: emptyToNull(form.get('provider')) ?? undefined,
        provider_voice_reference: emptyToNull(form.get('provider_voice_reference')) ?? undefined,
        language: emptyToNull(form.get('language')),
        accent: emptyToNull(form.get('accent')),
        gender_presentation: emptyToNull(form.get('gender_presentation')),
        presentation: emptyToNull(form.get('gender_presentation')),
        tone: emptyToNull(form.get('tone')),
        speaking_directions: emptyToNull(form.get('speaking_directions')),
        pacing: emptyToNull(form.get('pacing')),
        energy: emptyToNull(form.get('energy')),
        pronunciation_notes: emptyToNull(form.get('pronunciation_notes')),
        preview_text: emptyToNull(form.get('preview_text')),
        design_description: emptyToNull(form.get('design_description')) ?? undefined,
        source_description: emptyToNull(form.get('source_description')),
        usage_notes: emptyToNull(form.get('usage_notes')),
        consent_confirmed: consentChecked,
        consent_required:
          modeRequiresConsent(selected.setup_mode) || consentChecked
            ? true
            : selected.consent_required,
      })
      if (!updated) throw new Error('Voice profile editing is unavailable on this backend.')
      await reload(loadedStoryId)
      setPageNote('Voice profile changes were saved to the backend.')
      setMessage('Voice profile changes saved. No audio was generated.')
      setEdit(false)
    } catch (error) {
      const text = errorText(error, 'Could not update the voice profile.')
      setPageError(text)
      setMessage(text)
    } finally {
      setActionBusy(false)
    }
  }

  async function approveProfile() {
    if (!selected || !approvedBy.trim() || selectedLocked) return
    if (modeRequiresConsent(selected.setup_mode) && !selected.consent_confirmed) {
      setMessage('Confirm consent on this user-provided profile before approving.')
      return
    }
    setActionBusy(true)
    setPageError(null)
    setPageNote(null)
    try {
      const result = await api.approveVoice(selected.id, approvedBy.trim(), allowWithoutPreview)
      if (!result) throw new Error('Voice approval is unavailable on this backend.')
      await reload(loadedStoryId)
      const warnings = result.warnings.length ? ` Warnings: ${result.warnings.join(' ')}` : ''
      setPageNote(`Voice profile approved by ${result.approved_by}.${warnings}`)
      setMessage(`Voice profile approved. No preview or final audio was generated.${warnings}`)
    } catch (error) {
      const text = errorText(error, 'Could not approve the voice profile.')
      setPageError(text)
      setMessage(text)
    } finally {
      setActionBusy(false)
    }
  }

  async function archiveSelectedVoice() {
    if (!selected || selectedLocked) return
    if (!window.confirm(`Archive voice profile “${selected.name}”?`)) return
    setActionBusy(true)
    setPageError(null)
    setPageNote(null)
    try {
      const result = await api.deleteVoice(selected.id, 'Archived from Voice coverage.')
      if (result === null) throw new Error('Voice profile archive API is unavailable on this backend.')
      await reload(loadedStoryId)
      setSelectedId('')
      setPageNote(`Voice profile “${selected.name}” archived.`)
      setMessage(`Voice profile “${selected.name}” archived.`)
    } catch (error) {
      const text = errorText(error, 'Could not archive the voice profile.')
      setPageError(text)
      setMessage(text)
    } finally {
      setActionBusy(false)
    }
  }

  async function createRecipe(event: FormEvent) {
    event.preventDefault()
    if (!selected || selectedLocked || !effectiveRecipeProvider.trim()) return
    setActionBusy(true)
    setPageError(null)
    try {
      const recipe = await api.createVoiceRecipe(selected.id, {
        provider: effectiveRecipeProvider.trim(),
        model: recipeModel.trim() || null,
        recipe_name: recipeName.trim() || null,
        description: recipeDescription.trim() || null,
      })
      if (!recipe) throw new Error('Voice recipe creation is unavailable on this backend.')
      setRecipeModel('')
      setRecipeName('')
      setRecipeDescription('')
      await loadVoiceResources(selected.id)
      await reload(loadedStoryId)
      setPageNote('Voice recipe metadata saved. No provider was invoked.')
    } catch (error) {
      setPageError(errorText(error, 'Could not save the voice recipe.'))
    } finally {
      setActionBusy(false)
    }
  }

  /** Explicit button-only entry point — never called from useEffect/mount/select/approve. */
  async function requestPreview() {
    if (!selected || selectedLocked || !previewText.trim() || previewJobInFlight) return
    if (previewApiUnavailable || parlerUnavailableReason) return
    setActionBusy(true)
    setPageError(null)
    setPageNote(null)
    setPreviewApiUnavailable(null)
    try {
      const result = await api.requestVoicePreview(selected.id, previewText.trim())
      if (!result) {
        setPreviewApiUnavailable(PREVIEW_API_UNAVAILABLE_MESSAGE)
        setPageError(PREVIEW_API_UNAVAILABLE_MESSAGE)
        setMessage(`${PREVIEW_API_UNAVAILABLE_MESSAGE} No audio was generated.`)
        return
      }
      setActivePreviewJob(result)
      const detail =
        result.message || result.error_message || `Preview job ${result.job_id} is ${result.status}.`
      setPageNote(detail)
      setMessage(detail)
      // Terminal immediately (or already complete): refresh list once; no poll needed.
      if (isPreviewJobTerminal(result.status)) {
        await loadVoiceResources(selected.id)
      }
      // Non-terminal: polling effect watches activePreviewJob and stops on terminal.
    } catch (error) {
      const text = errorText(error, 'Voice preview is unavailable.')
      const isParlerMessage =
        text.includes(PARLER_UNAVAILABLE_MESSAGE) || text === PARLER_UNAVAILABLE_MESSAGE
      if (
        isParlerMessage ||
        (error instanceof ApiError && (error.status === 503 || error.status === 501))
      ) {
        setPreviewApiUnavailable(isParlerMessage ? PARLER_UNAVAILABLE_MESSAGE : text)
      }
      setActivePreviewJob(null)
      setPageError(text)
      setMessage(`${text} No audio was generated.`)
    } finally {
      setActionBusy(false)
    }
  }

  async function togglePreview(preview: VoicePreview) {
    if (selectedLocked) return
    setActionBusy(true)
    setPageError(null)
    try {
      const result = await api.selectVoicePreview(preview.id, !preview.selected)
      if (!result) throw new Error('Voice preview selection is unavailable on this backend.')
      await loadVoiceResources(preview.voice_profile_id)
      await reload(loadedStoryId)
      setPageNote(result.selected ? 'Persisted preview selected.' : 'Persisted preview selection cleared.')
    } catch (error) {
      setPageError(errorText(error, 'Could not update preview selection.'))
    } finally {
      setActionBusy(false)
    }
  }

  return (
    <div className="page">
      <PageTitle
        eyebrow="VOICE ASSIGNMENT"
        title="Voices"
        description="Plan narration and character delivery without cloning or generating final audio."
        aside={
          <div className="page-actions">
            <Button
              type="button"
              icon="lock"
              onClick={() =>
                setMessage(
                  'User-provided voices require a managed source, explicit consent confirmation, and usage notes. Voice cloning and final audio generation are not exposed in Storyboard Phase 1.',
                )
              }
            >
              Consent policy
            </Button>
            <Button type="button" variant="primary" icon="plus" onClick={onAddClick}>
              Add voice profile
            </Button>
          </div>
        }
      />

      <section
        className="voice-provider-discovery"
        aria-label="Voice provider discovery status"
        aria-live="polite"
      >
        <header>
          <span className="eyebrow">Provider discovery</span>
          <small>Configuration evidence only — no previews or model loads</small>
        </header>
        {discoveryLoadState === 'loading' ? (
          <p className="voice-provider-discovery-empty">Checking providers…</p>
        ) : discoveryLoadState === 'unavailable' ? (
          <p className="voice-provider-discovery-empty">Provider discovery unavailable</p>
        ) : (
          <ul className="voice-provider-discovery-list">
            {discoveryProviders.map((item) => {
              const message = discoveryProviderMessage(item)
              const pill = discoveryStatusPill(item.status)
              return (
                <li key={item.provider}>
                  <b>{discoveryProviderLabel(item.provider)}</b>
                  <StatusPill status={pill} />
                  {message ? <small title={message}>{message}</small> : null}
                </li>
              )
            })}
          </ul>
        )}
      </section>

      <div className="voice-summary" aria-label="Voice coverage summary">
        <div>
          <span>Profiles</span>
          <b>{voices.length}</b>
        </div>
        <div>
          <span>Shot coverage</span>
          <b>
            {shotCoverage}/{shots.length}
          </b>
        </div>
        <div>
          <span>Unresolved</span>
          <b>{unresolvedShots}</b>
        </div>
        <div>
          <span>Consent holds</span>
          <b>{consentHolds}</b>
        </div>
        <p>
          <Icon name="warning" /> Final voice generation happens only after storyboard approval.
        </p>
      </div>

      {pageError ? <ErrorState title="Voice workflow error" detail={pageError} /> : null}
      {pageNote ? (
        <p className="notice info" role="status">
          {pageNote}
        </p>
      ) : null}

      <div className="voice-layout">
        {!voices.length ? (
          <Empty
            title="No voice profiles"
            detail="Add a planning voice using one of the eight source modes."
            action={
              <Button type="button" variant="primary" icon="plus" onClick={onAddClick}>
                Add voice profile
              </Button>
            }
          />
        ) : (
          <div className="voice-grid">
            {voices.map((voice) => {
              const assignedCharacter = data.characters.find(
                (character) => character.id === voice.character_id,
              )
              const linkedShots = shots.filter(
                (shot) => shot.narration_voice_profile_id === voice.id,
              ).length
              const selectedCard = effectiveSelectedId === voice.id && drawerTab !== 'create'
              return (
                <article
                  key={voice.id}
                  role="button"
                  tabIndex={0}
                  className={selectedCard ? 'selected' : undefined}
                  aria-pressed={selectedCard}
                  onClick={() => selectVoice(voice)}
                  onKeyDown={(event) => onCardKeyDown(event, voice)}
                >
                  <header>
                    <span className={`voice-icon voice-${voiceIconSuffix(voice.id)}`}>
                      <Icon name="mic" />
                    </span>
                    <span>
                      <small>{sourceTypeLabel(voice)}</small>
                      <b>{voice.name}</b>
                    </span>
                    <StatusPill status={approvalPillLabel(voice.approval_state)} />
                  </header>

                  <Waveform active={playing === voice.id} />

                  <div className="voice-tags">
                    <span>{voice.language?.trim() || 'English'}</span>
                    <span>{voice.accent?.trim() || 'Neutral'}</span>
                    <span>{voice.tone?.trim() || sourceTypeLabel(voice)}</span>
                  </div>

                  <dl>
                    <div>
                      <dt>Provider</dt>
                      <dd>{voice.provider?.trim() || 'Unassigned'}</dd>
                    </div>
                    <div>
                      <dt>Assigned</dt>
                      <dd>{assignedCharacter?.name ?? 'Unassigned'}</dd>
                    </div>
                    <div>
                      <dt>Narration</dt>
                      <dd>{linkedShots} shots</dd>
                    </div>
                  </dl>

                  <footer>
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation()
                        playPlaceholder(voice.id)
                      }}
                      title="Decorative placeholder only — not real audio"
                    >
                      <Icon name={playing === voice.id ? 'close' : 'play'} />
                      {playing === voice.id ? 'Stop' : 'Preview'}
                    </button>
                    {voice.consent_confirmed || !voice.consent_required ? (
                      <span className="safe">
                        <Icon name="check" />
                        Source clear
                      </span>
                    ) : (
                      <span className="unsafe">
                        <Icon name="warning" />
                        Consent required
                      </span>
                    )}
                  </footer>
                </article>
              )
            })}
          </div>
        )}

        <aside className="entity-drawer" aria-label="Voice profile drawer">
          <header>
            <div>
              <span className="eyebrow">VOICE PROFILE</span>
              <h2>
                {drawerTab === 'create'
                  ? 'Add voice profile'
                  : selected?.name ?? 'No profile selected'}
              </h2>
            </div>
            {drawerTab !== 'create' && selected ? (
              <StatusPill status={approvalPillLabel(selected.approval_state)} />
            ) : null}
            {drawerTab !== 'create' && selected ? (
              <button
                type="button"
                className="icon-button"
                onClick={() => setEdit((value) => !value)}
                aria-label={edit ? 'Exit edit mode' : 'Edit voice'}
                disabled={Boolean(lockedReason) || actionsBusy}
                title={
                  firstReason(
                    busyReason,
                    lockedReason,
                    edit ? 'Exit edit mode' : 'Enable profile field edits',
                  ) ?? undefined
                }
              >
                <Icon name={edit ? 'check' : 'edit'} />
              </button>
            ) : null}
          </header>

          {drawerTab !== 'create' && selected ? (
            <div className="voice-hero" aria-label="Preview player">
              <span className="voice-icon">
                <Icon name="mic" size={24} />
              </span>
              <div>
                <Waveform active={playing === selected.id} />
                <Button
                  type="button"
                  variant="quiet"
                  icon="play"
                  onClick={() => playPlaceholder(selected.id)}
                  title="Decorative placeholder only — not real audio"
                >
                  Play sample
                </Button>
              </div>
            </div>
          ) : null}

          <div className="tabs small-tabs" role="tablist" aria-label="Voice drawer sections">
            <button
              type="button"
              className={drawerTab === 'profile' ? 'active' : undefined}
              role="tab"
              aria-selected={drawerTab === 'profile'}
              onClick={() => setDrawerTab('profile')}
            >
              Profile
            </button>
            <button
              type="button"
              className={drawerTab === 'recipes' ? 'active' : undefined}
              role="tab"
              aria-selected={drawerTab === 'recipes'}
              onClick={() => setDrawerTab('recipes')}
              disabled={!selected}
              title={!selected ? 'Select a voice profile to inspect recipes and previews.' : undefined}
            >
              Recipes
            </button>
            <button
              type="button"
              className={drawerTab === 'create' ? 'active' : undefined}
              role="tab"
              aria-selected={drawerTab === 'create'}
              onClick={onAddClick}
            >
              Add
            </button>
          </div>

          {drawerTab === 'create' ? (
            <form className="form-stack compact" onSubmit={(event) => void onCreate(event)}>
              <p className="form-hint">
                Select one of the eight production setup modes. Saving writes planning metadata only
                via POST /voices/stories/{'{story_id}'}/profiles — no cloning or final audio.
              </p>
              <fieldset style={{ border: 0, margin: 0, padding: 0 }}>
                <legend className="eyebrow">Source mode ({SELECTABLE_VOICE_SETUP_MODES.length})</legend>
                <div className="mode-grid" role="group" aria-label="Voice source modes">
                  {SELECTABLE_VOICE_SETUP_MODES.map((item) => (
                    <button
                      key={item}
                      type="button"
                      className={`mode-option ${createDraft.mode === item ? 'selected' : ''}`}
                      aria-pressed={createDraft.mode === item}
                      onClick={() =>
                        setCreateDraft((prev) => ({
                          ...prev,
                          mode: item,
                          // Reset mode-specific fields when switching so clone/source data cannot leak.
                          consentConfirmed: modeRequiresConsent(item)
                            ? prev.consentConfirmed
                            : false,
                          sourceFile: modeRequiresConsent(item) ? prev.sourceFile : null,
                          sourceAssetId: modeRequiresConsent(item) ? prev.sourceAssetId : '',
                          customVoiceSpeaker: modeRequiresPresetSpeaker(item)
                            ? prev.customVoiceSpeaker
                            : '',
                          provider: modeRequiresProviderReference(item) ? prev.provider : '',
                          providerVoiceReference: modeRequiresProviderReference(item)
                            ? prev.providerVoiceReference
                            : '',
                        }))
                      }
                      disabled={actionsBusy}
                      title={busyReason ?? undefined}
                    >
                      {VOICE_SETUP_MODE_LABELS[item]}
                      <small>{item}</small>
                    </button>
                  ))}
                </div>
              </fieldset>
              <label>
                Profile name
                <input
                  required
                  value={createDraft.name}
                  onChange={(event) =>
                    setCreateDraft((prev) => ({ ...prev, name: event.target.value }))
                  }
                  disabled={actionsBusy}
                  title={busyReason ?? undefined}
                  autoComplete="off"
                />
              </label>
              <label>
                Character assignment
                <select
                  value={createDraft.characterId}
                  onChange={(event) =>
                    setCreateDraft((prev) => ({ ...prev, characterId: event.target.value }))
                  }
                  disabled={actionsBusy}
                  title={busyReason ?? undefined}
                >
                  <option value="">Unassigned</option>
                  {data.characters.map((character) => (
                    <option key={character.id} value={character.id}>
                      {character.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Language
                <input
                  value={createDraft.language}
                  onChange={(event) =>
                    setCreateDraft((prev) => ({ ...prev, language: event.target.value }))
                  }
                  disabled={actionsBusy}
                  title={busyReason ?? undefined}
                />
              </label>
              {modeRequiresDesign(createDraft.mode) ? (
                <p className="form-hint">
                  {modeRequiresPresetSpeaker(createDraft.mode)
                    ? 'Design-recipe mode (qwen_custom_voice): preset speaker is the required recipe field — not free-text design and not cloning.'
                    : 'Design-recipe mode: language plus an editable voice design description are the planning fields. No clone or reference-audio upload.'}
                </p>
              ) : null}
              {modeRequiresProviderReference(createDraft.mode) ? (
                <div className="form-stack compact">
                  <p className="form-hint">
                    Existing provider voice requires both a provider id and a provider voice
                    reference. No cloning or reference-audio upload is used in this mode.
                  </p>
                  <div className="form-grid">
                    <label>
                      Provider
                      <input
                        required
                        value={createDraft.provider}
                        onChange={(event) =>
                          setCreateDraft((prev) => ({ ...prev, provider: event.target.value }))
                        }
                        disabled={actionsBusy}
                        title={busyReason ?? undefined}
                      />
                    </label>
                    <label>
                      Provider voice reference
                      <input
                        required
                        value={createDraft.providerVoiceReference}
                        onChange={(event) =>
                          setCreateDraft((prev) => ({
                            ...prev,
                            providerVoiceReference: event.target.value,
                          }))
                        }
                        disabled={actionsBusy}
                        title={busyReason ?? undefined}
                      />
                    </label>
                  </div>
                </div>
              ) : null}
              {modeRequiresPresetSpeaker(createDraft.mode) ? (
                <div className="form-stack compact">
                  <p className="form-hint">
                    Qwen CustomVoice is preset speakers only — not cloning. Do not attach reference
                    audio or clone files; enter a known preset speaker identifier.
                  </p>
                  <label>
                    Preset Qwen speaker identifier
                    <input
                      required
                      value={createDraft.customVoiceSpeaker}
                      onChange={(event) =>
                        setCreateDraft((prev) => ({
                          ...prev,
                          customVoiceSpeaker: event.target.value,
                        }))
                      }
                      disabled={actionsBusy}
                      title={busyReason ?? undefined}
                      placeholder="Preset speaker only — no reference audio"
                      autoComplete="off"
                    />
                  </label>
                </div>
              ) : null}
              {modeRequiresDesignDescription(createDraft.mode) ? (
                <p className="form-hint">
                  {createDraft.mode === 'qwen_voice_design'
                    ? 'Qwen voice design uses language plus an editable voice description. No clone or reference-audio input.'
                    : createDraft.mode === 'parler_local_voice_design'
                      ? 'Local Parler voice design stores a text description only. If Parler is unavailable the backend reports that factually — nothing is installed automatically.'
                      : 'Voice design stores a free-text description as planning metadata only. No cloning.'}
                </p>
              ) : null}
              {createDraft.mode === 'user_provided_consented' ? (
                <div className="notice warning form-stack compact">
                  <strong>Managed consented source</strong>
                  <p className="form-hint">
                    Consent must be confirmed before create or approve. Upload stores a managed
                    planning asset id only — this is not voice cloning.
                  </p>
                  <label className="checkbox-row">
                    <input
                      type="checkbox"
                      checked={createDraft.consentConfirmed}
                      onChange={(event) =>
                        setCreateDraft((prev) => ({
                          ...prev,
                          consentConfirmed: event.target.checked,
                        }))
                      }
                      disabled={actionsBusy}
                      title={busyReason ?? undefined}
                      required
                    />
                    <span>I confirm rights/consent for this user-provided voice sample.</span>
                  </label>
                  <label>
                    Audio source (.wav, .mp3, .ogg, or .flac; up to 50 MB)
                    <input
                      type="file"
                      accept="audio/wav,audio/x-wav,audio/mpeg,audio/ogg,audio/flac,.wav,.mp3,.ogg,.flac"
                      disabled={actionsBusy || !createDraft.consentConfirmed}
                      title={
                        !createDraft.consentConfirmed
                          ? 'Confirm consent before choosing a managed voice source file.'
                          : (busyReason ?? undefined)
                      }
                      onChange={(event) =>
                        setCreateDraft((prev) => ({
                          ...prev,
                          sourceFile: event.target.files?.[0] ?? null,
                        }))
                      }
                    />
                  </label>
                  <Button
                    type="button"
                    disabled={Boolean(uploadSourceReason)}
                    title={uploadSourceReason}
                    onClick={() => void uploadSource()}
                  >
                    Upload consented managed source
                  </Button>
                  <label>
                    Managed source asset
                    <select
                      value={createDraft.sourceAssetId}
                      onChange={(event) =>
                        setCreateDraft((prev) => ({ ...prev, sourceAssetId: event.target.value }))
                      }
                      disabled={actionsBusy}
                      title={busyReason ?? undefined}
                    >
                      <option value="">No managed source selected</option>
                      {sourceAssets.map((asset) => (
                        <option key={asset.id} value={asset.id}>
                          {asset.original_filename ?? asset.id} · {asset.approval_state}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              ) : null}
              <label>
                {modeRequiresDesignDescription(createDraft.mode)
                  ? 'Voice design description'
                  : createDraft.mode === 'user_provided_consented'
                    ? 'Managed source description'
                    : modeRequiresPresetSpeaker(createDraft.mode)
                      ? 'Usage notes (optional)'
                      : 'Usage notes'}
                <textarea
                  required={modeRequiresDesignDescription(createDraft.mode)}
                  value={createDraft.notes}
                  onChange={(event) =>
                    setCreateDraft((prev) => ({ ...prev, notes: event.target.value }))
                  }
                  disabled={actionsBusy}
                  title={busyReason ?? undefined}
                  placeholder={
                    modeRequiresDesignDescription(createDraft.mode)
                      ? 'Describe accent, age, tone, pacing, and delivery for this design mode.'
                      : undefined
                  }
                />
              </label>
              <div className="page-actions">
                <Button
                  type="button"
                  onClick={() => setDrawerTab('profile')}
                  disabled={actionsBusy}
                  title={busyReason ?? undefined}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  disabled={Boolean(createReason)}
                  title={createReason}
                >
                  Save voice profile
                </Button>
              </div>
              <p className="notice info">
                Voice cloning and final audio generation are not exposed in Storyboard Phase 1.
              </p>
            </form>
          ) : null}

          {drawerTab === 'profile' ? (
            !selected ? (
              <EmptyState
                title="No profile selected"
                detail="Create or select a voice profile to manage it."
              />
            ) : (
              <form
                key={selected.id}
                className="form-stack compact"
                onSubmit={(event) => void saveProfile(event)}
              >
                <label>
                  Setup mode
                  <input
                    value={
                      VOICE_SETUP_MODE_LABELS[selected.setup_mode as VoiceSetupMode]
                        ? `${VOICE_SETUP_MODE_LABELS[selected.setup_mode as VoiceSetupMode]} (${selected.setup_mode})`
                        : `${sourceTypeLabel(selected)} (${selected.setup_mode})`
                    }
                    disabled
                    title="Setup mode is fixed after create; create a new profile to change mode. qwen_voice_clone is not a supported mode."
                  />
                </label>

                <label>
                  Name
                  <input
                    name="name"
                    defaultValue={selected.name}
                    disabled={Boolean(fieldsDisabledReason)}
                    title={fieldsDisabledReason}
                    required
                  />
                </label>

                <div className="form-grid">
                  <label>
                    Provider
                    <input
                      name="provider"
                      defaultValue={selected.provider ?? ''}
                      disabled={Boolean(fieldsDisabledReason)}
                      title={fieldsDisabledReason}
                      required={modeRequiresProviderReference(selected.setup_mode)}
                    />
                  </label>
                  <label>
                    Language
                    <input
                      name="language"
                      defaultValue={selected.language ?? ''}
                      disabled={Boolean(fieldsDisabledReason)}
                      title={fieldsDisabledReason}
                    />
                  </label>
                </div>

                {modeRequiresProviderReference(selected.setup_mode) ? (
                  <label>
                    Provider voice reference
                    <input
                      name="provider_voice_reference"
                      defaultValue={selected.provider_voice_reference ?? ''}
                      disabled={Boolean(fieldsDisabledReason)}
                      title={fieldsDisabledReason}
                      required
                    />
                  </label>
                ) : null}

                {modeRequiresPresetSpeaker(selected.setup_mode) ? (
                  <div className="form-stack compact">
                    <p className="form-hint">
                      Qwen CustomVoice is preset speakers only — not cloning. Reference-audio and
                      clone file inputs are not available on edit.
                    </p>
                    <label>
                      Preset Qwen speaker identifier
                      <input
                        value={customVoiceSpeakerFrom(selected) || '—'}
                        disabled
                        title="Preset speaker is fixed after create for Phase 1. Create a new profile to change speaker."
                      />
                    </label>
                  </div>
                ) : null}

                {modeRequiresDesignDescription(selected.setup_mode) ? (
                  <label>
                    Voice design description
                    <textarea
                      name="design_description"
                      defaultValue={selected.design_description ?? ''}
                      disabled={Boolean(fieldsDisabledReason)}
                      title={fieldsDisabledReason}
                    />
                  </label>
                ) : null}

                <div className="form-grid">
                  <label>
                    Accent
                    <input
                      name="accent"
                      defaultValue={selected.accent ?? ''}
                      disabled={Boolean(fieldsDisabledReason)}
                      title={fieldsDisabledReason}
                    />
                  </label>
                  <label>
                    Gender presentation
                    <input
                      name="gender_presentation"
                      defaultValue={genderPresentation(selected)}
                      disabled={Boolean(fieldsDisabledReason)}
                      title={fieldsDisabledReason}
                    />
                  </label>
                </div>

                <label>
                  Tone / style
                  <input
                    name="tone"
                    defaultValue={selected.tone ?? ''}
                    disabled={Boolean(fieldsDisabledReason)}
                    title={fieldsDisabledReason}
                  />
                </label>

                <label>
                  Speaking directions
                  <textarea
                    name="speaking_directions"
                    defaultValue={selected.speaking_directions ?? ''}
                    disabled={Boolean(fieldsDisabledReason)}
                    title={fieldsDisabledReason}
                  />
                </label>

                <div className="form-grid">
                  <label>
                    Pacing
                    <input
                      name="pacing"
                      defaultValue={selected.pacing ?? ''}
                      disabled={Boolean(fieldsDisabledReason)}
                      title={fieldsDisabledReason}
                    />
                  </label>
                  <label>
                    Energy
                    <input
                      name="energy"
                      defaultValue={selected.energy ?? ''}
                      disabled={Boolean(fieldsDisabledReason)}
                      title={fieldsDisabledReason}
                    />
                  </label>
                </div>

                <label>
                  Pronunciation notes
                  <input
                    name="pronunciation_notes"
                    defaultValue={selected.pronunciation_notes ?? ''}
                    disabled={Boolean(fieldsDisabledReason)}
                    title={fieldsDisabledReason}
                  />
                </label>

                <label>
                  Sample script
                  <textarea
                    name="preview_text"
                    defaultValue={selected.preview_text ?? ''}
                    disabled={Boolean(fieldsDisabledReason)}
                    title={fieldsDisabledReason}
                  />
                </label>

                <label>
                  Character assignment
                  <select
                    name="character_id"
                    defaultValue={selected.character_id ?? ''}
                    disabled={Boolean(fieldsDisabledReason)}
                    title={fieldsDisabledReason}
                  >
                    <option value="">Unassigned</option>
                    {data.characters.map((character) => (
                      <option key={character.id} value={character.id}>
                        {character.name}
                      </option>
                    ))}
                  </select>
                </label>

                <label>
                  Source
                  <input
                    name="source_description"
                    defaultValue={selected.source_description ?? ''}
                    disabled={Boolean(fieldsDisabledReason)}
                    title={fieldsDisabledReason}
                  />
                </label>

                <label>
                  Usage notes
                  <textarea
                    name="usage_notes"
                    defaultValue={selected.usage_notes ?? ''}
                    disabled={Boolean(fieldsDisabledReason)}
                    title={fieldsDisabledReason}
                  />
                </label>

                {modeRequiresConsent(selected.setup_mode) ? (
                  <div className="notice warning form-stack compact">
                    <strong>Consent required</strong>
                    <p className="form-hint" style={{ margin: 0 }}>
                      User-provided voices require confirmed consent before create and before
                      approve. Save consent here, then approve.
                    </p>
                    <label className="checkbox-row">
                      <input
                        type="checkbox"
                        name="consent_confirmed"
                        defaultChecked={selected.consent_confirmed}
                        disabled={Boolean(fieldsDisabledReason)}
                        title={fieldsDisabledReason}
                        required
                      />
                      <span>I confirm rights/consent for this user-provided voice sample.</span>
                    </label>
                  </div>
                ) : (
                  <label className="checkbox-row">
                    <input
                      type="checkbox"
                      name="consent_confirmed"
                      defaultChecked={selected.consent_confirmed}
                      disabled={Boolean(fieldsDisabledReason)}
                      title={fieldsDisabledReason}
                    />
                    <span>Consent confirmed</span>
                  </label>
                )}

                {/*
                  Routing recommendation is advisory display only.
                  Never patches provider / assignment fields from the response,
                  and approved profiles always send existing_assignment_approved.
                */}
                <div
                  className="notice info form-stack compact"
                  aria-label="Routing recommendation"
                  style={{ marginTop: 8 }}
                >
                  <strong>Routing recommendation</strong>
                  <p className="form-hint" style={{ margin: 0 }}>
                    Separate from the assigned provider above. Checking a model never overwrites
                    an approved voice assignment.
                  </p>
                  <dl className="detail-list" style={{ margin: 0 }}>
                    <div>
                      <dt>Assigned provider</dt>
                      <dd>{selected.provider?.trim() || 'Unassigned'}</dd>
                    </div>
                    <div>
                      <dt>Assignment status</dt>
                      <dd>{approvalPillLabel(selected.approval_state)}</dd>
                    </div>
                  </dl>
                  <label>
                    Generation model variant (optional)
                    <select
                      value={routingVariantId}
                      onChange={(event) => {
                        setRoutingVariantId(event.target.value)
                        // Clear prior advisory result when the model under review changes.
                        setRoutingRecommendation(null)
                        setRoutingError(null)
                      }}
                      disabled={actionsBusy || routingBusy}
                      title="Used only for capability lookup — does not change the assigned voice."
                    >
                      <option value="">No variant selected</option>
                      {routingVariants.map((variant) => (
                        <option key={variant.id} value={variant.id}>
                          {variant.variant_name}
                          {variant.native_voice_capability
                            ? ` · native voice: ${variant.native_voice_capability}`
                            : ''}
                        </option>
                      ))}
                    </select>
                  </label>
                  <Button
                    type="button"
                    disabled={actionsBusy || routingBusy || !loadedStoryId}
                    title={
                      !loadedStoryId
                        ? 'Story id is required to call POST /voices/routing/recommend.'
                        : busyReason ?? undefined
                    }
                    onClick={() => void fetchRoutingRecommendation()}
                  >
                    {routingBusy ? 'Checking routing…' : 'Check routing recommendation'}
                  </Button>
                  {routingUnavailable ? (
                    <p className="form-hint" style={{ margin: 0 }}>
                      Recommendations appear when the routing API provides them (POST
                      /voices/routing/recommend). Assigned provider was left unchanged.
                    </p>
                  ) : null}
                  {routingError ? (
                    <p className="form-hint" role="alert" style={{ margin: 0 }}>
                      {routingError}
                    </p>
                  ) : null}
                  {routingRecommendation ? (
                    <div className="recommendation" role="status">
                      <Icon name="spark" />
                      <p>
                        <b>
                          {routingActionLabel(routingRecommendation.action)}
                          {routingRecommendation.recommend_qwen ? ' · Qwen suggested' : ''}
                        </b>{' '}
                        {routingRecommendation.rationale}
                        {routingRecommendation.provider_suggestion
                          ? ` Suggested provider: ${routingRecommendation.provider_suggestion}.`
                          : ''}
                        {routingRecommendation.blocked_reason
                          ? ` (${routingRecommendation.blocked_reason})`
                          : ''}
                        {' '}
                        Native voice capability:{' '}
                        {routingRecommendation.native_voice_capability || 'unknown'}.
                        {selectedLocked
                          ? ' Approved assignment is immutable — this panel is display-only.'
                          : ' Display only — provider field was not updated.'}
                      </p>
                    </div>
                  ) : null}
                </div>

                <p className="form-hint">
                  Assigned to {coverage} shot{coverage === 1 ? '' : 's'}. Final voice generation
                  happens only after storyboard approval.
                </p>

                {selectedLocked ? (
                  <p className="notice info">{lockedReason}</p>
                ) : (
                  <Button
                    type="submit"
                    variant="primary"
                    disabled={Boolean(saveReason)}
                    title={saveReason}
                  >
                    Save profile edits
                  </Button>
                )}

                <Button
                  type="button"
                  disabled={Boolean(archiveReason)}
                  title={archiveReason}
                  onClick={() => void archiveSelectedVoice()}
                >
                  Archive voice profile
                </Button>

                <label>
                  Approval audit name
                  <input
                    value={approvedBy}
                    onChange={(event) => setApprovedBy(event.target.value)}
                    disabled={Boolean(firstReason(busyReason, lockedReason))}
                    title={firstReason(busyReason, lockedReason)}
                    placeholder="Your name or production role"
                  />
                </label>
                <label className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={allowWithoutPreview}
                    onChange={(event) => setAllowWithoutPreview(event.target.checked)}
                    disabled={Boolean(firstReason(busyReason, lockedReason))}
                    title={firstReason(busyReason, lockedReason)}
                  />
                  <span>Allow approval without a preview when this setup mode permits it</span>
                </label>
                <Button
                  type="button"
                  variant="primary"
                  disabled={Boolean(approveReason)}
                  title={approveReason}
                  onClick={() => void approveProfile()}
                >
                  {selectedLocked ? 'Profile approved' : 'Approve voice profile'}
                </Button>
              </form>
            )
          ) : null}

          {drawerTab === 'recipes' ? (
            !selected ? (
              <EmptyState
                title="No profile selected"
                detail="Select a profile to inspect recipes and previews."
              />
            ) : resourcesLoading ? (
              <LoadingState title="Loading recipes and previews…" />
            ) : (
              <div className="form-stack compact">
                <form
                  className="form-stack compact"
                  onSubmit={(event) => void createRecipe(event)}
                >
                  <h3>Create recipe</h3>
                  <p className="form-hint">
                    Recipe creation stores metadata only. Preview generation is an explicit request
                    and currently returns the backend&apos;s truthful unavailable response when no
                    durable worker is configured.
                  </p>
                  <div className="form-grid">
                    <label>
                      Provider
                      <input
                        required
                        value={effectiveRecipeProvider}
                        onChange={(event) => setRecipeProvider(event.target.value)}
                        disabled={Boolean(firstReason(busyReason, lockedReason))}
                        title={firstReason(busyReason, lockedReason)}
                      />
                    </label>
                    <label>
                      Model (optional)
                      <input
                        value={recipeModel}
                        onChange={(event) => setRecipeModel(event.target.value)}
                        disabled={Boolean(firstReason(busyReason, lockedReason))}
                        title={firstReason(busyReason, lockedReason)}
                      />
                    </label>
                  </div>
                  <label>
                    Recipe name
                    <input
                      value={recipeName}
                      onChange={(event) => setRecipeName(event.target.value)}
                      disabled={Boolean(firstReason(busyReason, lockedReason))}
                      title={firstReason(busyReason, lockedReason)}
                    />
                  </label>
                  <label>
                    Description
                    <textarea
                      value={recipeDescription}
                      onChange={(event) => setRecipeDescription(event.target.value)}
                      disabled={Boolean(firstReason(busyReason, lockedReason))}
                      title={firstReason(busyReason, lockedReason)}
                    />
                  </label>
                  <button
                    type="submit"
                    className="secondary-button"
                    disabled={Boolean(recipeReason)}
                    title={recipeReason}
                  >
                    Save recipe metadata
                  </button>
                </form>

                {recipes.length ? (
                  <ul className="kv-list">
                    {recipes.map((recipe) => (
                      <li key={recipe.id}>
                        <span>
                          {recipe.recipe_name || 'Unnamed recipe'} · {recipe.provider}
                          {recipe.model ? ` / ${recipe.model}` : ''}
                        </span>
                        <strong>{formatDate(recipe.created_at)}</strong>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="form-hint">No recipe metadata is persisted for this profile.</p>
                )}

                <h3>Explicit preview request</h3>
                <label>
                  Preview text
                  <textarea
                    value={previewText}
                    onChange={(event) => setPreviewText(event.target.value)}
                    disabled={Boolean(firstReason(busyReason, lockedReason))}
                    title={firstReason(busyReason, lockedReason)}
                    maxLength={2000}
                  />
                </label>
                <button
                  type="button"
                  className="secondary-button"
                  disabled={Boolean(previewRequestReason)}
                  title={
                    previewRequestReason ??
                    'Request a provider-safe preview job via POST /voices/profiles/{id}/previews. Never auto-runs.'
                  }
                  onClick={() => void requestPreview()}
                >
                  {previewJobInFlight
                    ? `Preview job ${activePreviewJob?.status ?? 'running'}…`
                    : 'Request provider-safe preview'}
                </button>
                {activePreviewJob ? (
                  <p className="form-hint" role="status">
                    Job {activePreviewJob.job_id}: {activePreviewJob.status}
                    {activePreviewJob.message || activePreviewJob.error_message
                      ? ` — ${activePreviewJob.message || activePreviewJob.error_message}`
                      : ''}
                    {previewJobInFlight ? ' (polling until terminal status)' : ''}
                  </p>
                ) : null}
                {parlerUnavailableReason ? (
                  <p className="parler-unavailable" role="status">
                    {parlerUnavailableReason}
                  </p>
                ) : null}
                <p className="form-hint">
                  Preview generation runs only when you click this button. Selection loads the
                  persisted preview list only. Job status is polled only after a user-started job
                  and stops on complete, failed, or canceled. Approve/plan never generates audio.
                </p>

                <h3>Persisted preview records</h3>
                {previews.length ? (
                  <ul className="kv-list">
                    {previews.map((preview) => {
                      const selectReason = firstReason(
                        busyReason,
                        lockedReason,
                        preview.rejected && 'This preview was rejected and cannot be selected.',
                        !preview.planning_media_asset_id &&
                          'Preview has no planning media asset id to select.',
                      )
                      return (
                        <li key={preview.id}>
                          <span>
                            {preview.provider ?? 'Unknown provider'} ·{' '}
                            {preview.preview_text ?? 'No preview text'} · asset{' '}
                            {preview.planning_media_asset_id ?? 'missing'}
                          </span>
                          <button
                            type="button"
                            className="ghost-button"
                            disabled={Boolean(selectReason)}
                            title={selectReason}
                            aria-pressed={preview.selected}
                            onClick={() => void togglePreview(preview)}
                          >
                            {preview.rejected
                              ? 'Rejected'
                              : preview.selected
                                ? 'Clear selection'
                                : 'Select preview'}
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                ) : (
                  <p className="form-hint">
                    No preview records exist for this profile. Nothing is synthesized automatically.
                  </p>
                )}
              </div>
            )
          ) : null}
        </aside>
      </div>
    </div>
  )
}
