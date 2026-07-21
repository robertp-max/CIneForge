/**
 * Gold Sites density port of VoicesPage:
 * voice-summary → voice-layout → voice-grid cards | entity-drawer
 * (matches CineForge_Gold_Edition/components/pagesAssets.tsx VoicesPage hierarchy)
 *
 * Live API only: create/update/archive, eight setup modes, consented source upload,
 * recipes, provider-safe preview, and approval. No cloning or final audio generation.
 */
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
} from 'react'
import {
  api,
  VOICE_SETUP_MODE_LABELS,
  VOICE_SETUP_MODES,
  type PlanningMediaAsset,
  type Voice,
  type VoicePreview,
  type VoiceRecipe,
  type VoiceSetupMode,
} from '../../api/client'
import { formatDate } from '../../components/formatDate'
import { useStudio } from '../StudioState'
import { EmptyState, ErrorState, LoadingState } from '../components/StateBlocks'

const WAVEFORM_BARS = [8, 15, 22, 12, 28, 18, 10, 24, 30, 17, 12, 26, 19, 9, 16, 25, 13, 21, 8, 18]

type VoiceIconName = 'mic' | 'play' | 'close' | 'check' | 'warning' | 'plus' | 'lock' | 'edit'

function VoiceIcon({ name, size = 18 }: { name: VoiceIconName; size?: number }) {
  const paths: Record<VoiceIconName, ReactNode> = {
    mic: (
      <>
        <rect x="9" y="2" width="6" height="12" rx="3" />
        <path d="M5 10a7 7 0 0 0 14 0M12 17v5M8 22h8" />
      </>
    ),
    play: <path d="m8 5 11 7-11 7z" />,
    close: (
      <>
        <path d="M6 6l12 12M18 6 6 18" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    warning: (
      <>
        <path d="M12 3 2 20h20L12 3z" />
        <path d="M12 9v5M12 17h.01" />
      </>
    ),
    plus: <path d="M12 5v14M5 12h14" />,
    lock: (
      <>
        <rect x="5" y="11" width="14" height="10" rx="2" />
        <path d="M8 11V8a4 4 0 0 1 8 0v3" />
      </>
    ),
    edit: (
      <>
        <path d="M12 20h9" />
        <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" />
      </>
    ),
  }
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  )
}

function modeRequiresConsent(mode: VoiceSetupMode): boolean {
  return mode === 'user_provided_consented'
}

function modeRequiresDesign(mode: VoiceSetupMode): boolean {
  return (
    mode === 'qwen_voice_design' ||
    mode === 'elevenlabs_voice_design' ||
    mode === 'parler_local_voice_design'
  )
}

function errorText(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback
}

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

/** Decorative waveform only — never real audio. Matches Gold Sites Waveform. */
function Waveform({ active = false }: { active?: boolean }) {
  return (
    <div
      className={`waveform${active ? ' playing' : ''}`}
      role="img"
      aria-label="Decorative waveform placeholder"
      title="Decorative placeholder only — not real audio"
    >
      {WAVEFORM_BARS.map((height, index) => (
        <i key={index} style={{ height }} />
      ))}
    </div>
  )
}

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

  const projectId = data?.story.project_id ?? ''
  const loadedStoryId = data?.story.id ?? ''
  const actionsBusy = busy || actionBusy
  const busyReason = busy
    ? 'A studio save or reload is already in progress.'
    : actionBusy
      ? 'A voice action is already in progress.'
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

  const createConsentRequired = modeRequiresConsent(createDraft.mode)
  const createReason = firstReason(
    busyReason,
    !createDraft.name.trim() && 'Enter a profile name before creating a voice profile.',
    createConsentRequired &&
      !createDraft.consentConfirmed &&
      'Confirm consent before saving a user-provided voice source.',
    createDraft.mode === 'existing_provider_voice' &&
      (!createDraft.provider.trim() || !createDraft.providerVoiceReference.trim()) &&
      'Provider and provider voice reference are required for an existing provider voice.',
    createDraft.mode === 'qwen_custom_voice' &&
      !createDraft.customVoiceSpeaker.trim() &&
      'Choose a preset Qwen speaker identifier. Reference-audio cloning is not accepted.',
    modeRequiresDesign(createDraft.mode) &&
      !createDraft.notes.trim() &&
      'A voice design description is required for this setup mode.',
    createDraft.mode === 'user_provided_consented' &&
      !createDraft.sourceAssetId &&
      !createDraft.notes.trim() &&
      'Upload or select a managed voice source, or record a source description.',
  )
  const uploadSourceReason = firstReason(
    busyReason,
    !createDraft.consentConfirmed && 'Confirm consent before uploading a managed voice source.',
    !createDraft.sourceFile && 'Choose an audio file (.wav, .mp3, .ogg, or .flac) before upload.',
    !projectId && 'Project id is required to upload a managed voice source.',
  )
  const saveReason = firstReason(busyReason, lockedReason, editReason)
  const approveReason = firstReason(
    busyReason,
    lockedReason,
    !approvedBy.trim() && 'Enter an approval audit name before approving the voice profile.',
  )
  const archiveReason = firstReason(busyReason, lockedReason, !selected && 'Select a voice profile to archive.')
  const recipeReason = firstReason(
    busyReason,
    lockedReason,
    !selected && 'Select a voice profile first.',
    !(recipeProvider || selected?.provider || '').trim() &&
      'Enter a provider before saving recipe metadata.',
  )
  const previewRequestReason = firstReason(
    busyReason,
    lockedReason,
    !selected && 'Select a voice profile first.',
    !previewText.trim() && 'Enter preview text before requesting a provider-safe preview job.',
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

  useEffect(() => {
    const timer = window.setTimeout(() => void loadVoiceResources(effectiveSelectedId), 0)
    return () => window.clearTimeout(timer)
  }, [effectiveSelectedId, loadVoiceResources])

  if (!data) return null

  function selectVoice(voice: Voice) {
    setSelectedId(voice.id)
    setDrawerTab('profile')
    setEdit(false)
    setPageError(null)
    setRecipeProvider(voice.provider ?? '')
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
      usage_notes: draft.notes.trim() || undefined,
      provider: draft.mode === 'existing_provider_voice' ? draft.provider.trim() : undefined,
      provider_voice_reference:
        draft.mode === 'existing_provider_voice' ? draft.providerVoiceReference.trim() : undefined,
      design_description: modeRequiresDesign(draft.mode) ? draft.notes.trim() : undefined,
      custom_voice_speaker:
        draft.mode === 'qwen_custom_voice' ? draft.customVoiceSpeaker.trim() : undefined,
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
      const updated = await api.updateVoice(selected.id, {
        name: String(form.get('name') || selected.name).trim() || selected.name,
        character_id: emptyToNull(form.get('character_id')),
        provider: emptyToNull(form.get('provider')) ?? undefined,
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
        source_description: emptyToNull(form.get('source_description')),
        usage_notes: emptyToNull(form.get('usage_notes')),
        consent_confirmed: form.get('consent_confirmed') === 'on',
        consent_required:
          modeRequiresConsent(selected.setup_mode as VoiceSetupMode) ||
          form.get('consent_confirmed') === 'on'
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

  async function requestPreview() {
    if (!selected || selectedLocked || !previewText.trim()) return
    setActionBusy(true)
    setPageError(null)
    setPageNote(null)
    try {
      const result = await api.requestVoicePreview(selected.id, previewText.trim())
      if (!result) throw new Error('Voice preview API is unavailable on this backend.')
      const detail =
        result.message || result.error_message || `Preview job ${result.job_id} is ${result.status}.`
      setPageNote(detail)
      setMessage(detail)
      await loadVoiceResources(selected.id)
    } catch (error) {
      const text = errorText(error, 'Voice preview is unavailable.')
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
      <div className="page-title">
        <div>
          <span className="eyebrow">VOICE ASSIGNMENT</span>
          <h1>Voices</h1>
          <p>Plan narration and character delivery without cloning or generating final audio.</p>
        </div>
        <div className="page-actions">
          <button
            type="button"
            className="btn secondary"
            onClick={() =>
              setMessage(
                'User-provided voices require a managed source, explicit consent confirmation, and usage notes. Voice cloning and final audio generation are not exposed in Storyboard Phase 1.',
              )
            }
          >
            <VoiceIcon name="lock" size={15} />
            <span>Consent policy</span>
          </button>
          <button type="button" className="btn primary" onClick={onAddClick}>
            <VoiceIcon name="plus" size={15} />
            <span>Add voice profile</span>
          </button>
        </div>
      </div>

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
          <VoiceIcon name="warning" size={13} /> Final voice generation happens only after storyboard
          approval.
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
          <EmptyState
            title="No voice profiles"
            detail="Add a planning voice using one of the eight source modes."
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
                      <VoiceIcon name="mic" />
                    </span>
                    <span>
                      <small>{sourceTypeLabel(voice)}</small>
                      <b>{voice.name}</b>
                    </span>
                    <span
                      className="status-pill"
                      data-status={approvalPillLabel(voice.approval_state).toLowerCase()}
                    >
                      {approvalPillLabel(voice.approval_state)}
                    </span>
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
                      <VoiceIcon name={playing === voice.id ? 'close' : 'play'} size={13} />
                      {playing === voice.id ? 'Stop' : 'Preview'}
                    </button>
                    {voice.consent_confirmed || !voice.consent_required ? (
                      <span className="safe">
                        <VoiceIcon name="check" size={12} />
                        Source clear
                      </span>
                    ) : (
                      <span className="unsafe">
                        <VoiceIcon name="warning" size={12} />
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
              <span
                className="status-pill"
                data-status={approvalPillLabel(selected.approval_state).toLowerCase()}
              >
                {approvalPillLabel(selected.approval_state)}
              </span>
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
                <VoiceIcon name={edit ? 'check' : 'edit'} />
              </button>
            ) : null}
          </header>

          {drawerTab !== 'create' && selected ? (
            <div className="voice-hero" aria-label="Preview player">
              <span className="voice-icon">
                <VoiceIcon name="mic" size={24} />
              </span>
              <div>
                <Waveform active={playing === selected.id} />
                <button
                  type="button"
                  className="btn quiet"
                  onClick={() => playPlaceholder(selected.id)}
                  title="Decorative placeholder only — not real audio"
                >
                  <VoiceIcon name="play" size={15} />
                  <span>Play sample</span>
                </button>
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
                Select one of the eight production setup modes. Saving writes planning metadata only —
                no cloning or final audio.
              </p>
              <fieldset className="mode-fieldset">
                <legend className="eyebrow">Source mode (8)</legend>
                <div className="mode-grid" role="group" aria-label="Voice source modes">
                  {VOICE_SETUP_MODES.map((item) => (
                    <button
                      key={item}
                      type="button"
                      className={`mode-option ${createDraft.mode === item ? 'selected' : ''}`}
                      aria-pressed={createDraft.mode === item}
                      onClick={() =>
                        setCreateDraft((prev) => ({
                          ...prev,
                          mode: item,
                          consentConfirmed: modeRequiresConsent(item)
                            ? prev.consentConfirmed
                            : false,
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
              <div className="form-grid">
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
              </div>
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
              {createDraft.mode === 'existing_provider_voice' ? (
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
              ) : null}
              {createDraft.mode === 'qwen_custom_voice' ? (
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
                  />
                </label>
              ) : null}
              {createDraft.mode === 'user_provided_consented' ? (
                <div className="consent-box form-stack compact">
                  <strong>Managed consented source</strong>
                  <label className="check-row">
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
                    />
                    <span>I confirm rights/consent for this user-provided voice sample.</span>
                  </label>
                  <label>
                    Audio source (.wav, .mp3, .ogg, or .flac; up to 50 MB)
                    <input
                      type="file"
                      accept="audio/wav,audio/x-wav,audio/mpeg,audio/ogg,audio/flac,.wav,.mp3,.ogg,.flac"
                      disabled={actionsBusy}
                      title={busyReason ?? undefined}
                      onChange={(event) =>
                        setCreateDraft((prev) => ({
                          ...prev,
                          sourceFile: event.target.files?.[0] ?? null,
                        }))
                      }
                    />
                  </label>
                  <button
                    type="button"
                    className="btn secondary"
                    disabled={Boolean(uploadSourceReason)}
                    title={uploadSourceReason}
                    onClick={() => void uploadSource()}
                  >
                    <span>Upload consented managed source</span>
                  </button>
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
                {modeRequiresDesign(createDraft.mode)
                  ? 'Voice design description'
                  : createDraft.mode === 'user_provided_consented'
                    ? 'Managed source description'
                    : 'Usage notes'}
                <textarea
                  required={modeRequiresDesign(createDraft.mode)}
                  value={createDraft.notes}
                  onChange={(event) =>
                    setCreateDraft((prev) => ({ ...prev, notes: event.target.value }))
                  }
                  disabled={actionsBusy}
                  title={busyReason ?? undefined}
                />
              </label>
              <div className="page-actions">
                <button
                  type="button"
                  className="btn secondary"
                  onClick={() => setDrawerTab('profile')}
                  disabled={actionsBusy}
                  title={busyReason ?? undefined}
                >
                  <span>Cancel</span>
                </button>
                <button
                  type="submit"
                  className="btn primary"
                  disabled={Boolean(createReason)}
                  title={createReason}
                >
                  <span>Save voice profile</span>
                </button>
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
                  Source type
                  <input
                    value={sourceTypeLabel(selected)}
                    disabled
                    title="Setup mode is fixed after create; create a new profile to change mode."
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

                <label className="check-row">
                  <input
                    type="checkbox"
                    name="consent_confirmed"
                    defaultChecked={selected.consent_confirmed}
                    disabled={Boolean(fieldsDisabledReason)}
                    title={fieldsDisabledReason}
                  />
                  <span>Consent confirmed</span>
                </label>

                <div className="coverage-card">
                  <span>
                    Shot coverage <b>{coverage}</b>
                  </span>
                  <small>
                    Assigned to {coverage} shot{coverage === 1 ? '' : 's'}. Final voice generation
                    happens only after storyboard approval.
                  </small>
                </div>

                {selectedLocked ? (
                  <p className="notice info">{lockedReason}</p>
                ) : (
                  <button
                    type="submit"
                    className="btn primary"
                    disabled={Boolean(saveReason)}
                    title={saveReason}
                  >
                    <span>Save profile edits</span>
                  </button>
                )}

                <button
                  type="button"
                  className="btn secondary"
                  disabled={Boolean(archiveReason)}
                  title={archiveReason}
                  onClick={() => void archiveSelectedVoice()}
                >
                  <span>Archive voice profile</span>
                </button>

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
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={allowWithoutPreview}
                    onChange={(event) => setAllowWithoutPreview(event.target.checked)}
                    disabled={Boolean(firstReason(busyReason, lockedReason))}
                    title={firstReason(busyReason, lockedReason)}
                  />
                  <span>Allow approval without a preview when this setup mode permits it</span>
                </label>
                <button
                  type="button"
                  className="btn primary"
                  disabled={Boolean(approveReason)}
                  title={approveReason}
                  onClick={() => void approveProfile()}
                >
                  <span>{selectedLocked ? 'Profile approved' : 'Approve voice profile'}</span>
                </button>
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
                <form className="form-stack compact" onSubmit={(event) => void createRecipe(event)}>
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
                    className="btn secondary"
                    disabled={Boolean(recipeReason)}
                    title={recipeReason}
                  >
                    <span>Save recipe metadata</span>
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
                  className="btn secondary"
                  disabled={Boolean(previewRequestReason)}
                  title={previewRequestReason}
                  onClick={() => void requestPreview()}
                >
                  <span>Request provider-safe preview</span>
                </button>
                <p className="form-hint">
                  The public backend currently responds 503 until a durable isolated preview worker
                  is configured. This action never falls back to in-process generation and never
                  clones a voice.
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
