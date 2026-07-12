import { useCallback, useEffect, useMemo, useState, type FormEvent, type KeyboardEvent } from 'react'
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
import { Button, Icon, PageTitle, StatusPill } from '../../components/ui'
import { useStudio } from '../StudioState'
import { EmptyState, ErrorState, LoadingState } from '../components/StateBlocks'

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

function voiceModeLabel(voice: Voice): string {
  return VOICE_SETUP_MODE_LABELS[voice.setup_mode as VoiceSetupMode] ?? voice.setup_mode
}

function approvalPillLabel(state: string): string {
  const normalized = (state || 'draft').toLowerCase()
  const labels: Record<string, string> = {
    approved: 'Approved',
    draft: 'Draft',
    review: 'Review',
    in_review: 'Review',
    blocked: 'Blocked',
    rejected: 'Blocked',
    pending: 'Draft',
  }
  return labels[normalized] ?? state
}

function providerNote(voice: Voice): string {
  const parts = [
    voice.provider?.trim() || null,
    voice.provider_configuration_status?.trim()
      ? `config: ${voice.provider_configuration_status}`
      : null,
    voice.provider_voice_reference?.trim()
      ? `ref: ${voice.provider_voice_reference}`
      : null,
  ].filter(Boolean)
  return parts.length ? parts.join(' · ') : 'No provider configured'
}

type VoiceEditDraft = {
  voiceId: string
  name: string
  language: string
  notes: string
  sourceDescription: string
}

type DrawerTab = 'profile' | 'recipes' | 'create'

function DecorativeWaveform({ label = 'Decorative waveform placeholder' }: { label?: string }) {
  return (
    <div
      className="waveform"
      role="img"
      aria-label={label}
      title="Decorative placeholder only — not real audio"
    />
  )
}

export function VoicesPage() {
  const { data, addVoice, busy, reload, setMessage } = useStudio()
  const voices = useMemo(() => data?.voices ?? [], [data?.voices])
  const shots = useMemo(
    () => data?.chapters.flatMap((chapter) => chapter.scenes.flatMap((scene) => scene.shots)) ?? [],
    [data?.chapters],
  )
  const [selectedVoiceId, setSelectedVoiceId] = useState('')
  const [drawerTab, setDrawerTab] = useState<DrawerTab>('profile')
  const effectiveSelectedVoiceId = voices.some((voice) => voice.id === selectedVoiceId)
    ? selectedVoiceId
    : voices[0]?.id ?? ''
  const selectedVoice = voices.find((voice) => voice.id === effectiveSelectedVoiceId) ?? null

  const [name, setName] = useState('')
  const [mode, setMode] = useState<VoiceSetupMode>('placeholder')
  const [language, setLanguage] = useState('en')
  const [notes, setNotes] = useState('')
  const [provider, setProvider] = useState('')
  const [providerVoiceReference, setProviderVoiceReference] = useState('')
  const [customVoiceSpeaker, setCustomVoiceSpeaker] = useState('')
  const [characterId, setCharacterId] = useState('')
  const [consentConfirmed, setConsentConfirmed] = useState(false)
  const [sourceAssetId, setSourceAssetId] = useState('')
  const [sourceFile, setSourceFile] = useState<File | null>(null)
  const [sourceAssets, setSourceAssets] = useState<PlanningMediaAsset[]>([])

  const [editDraft, setEditDraft] = useState<VoiceEditDraft | null>(null)
  const [approvedBy, setApprovedBy] = useState('')
  const [allowWithoutPreview, setAllowWithoutPreview] = useState(true)

  const [recipes, setRecipes] = useState<VoiceRecipe[]>([])
  const [previews, setPreviews] = useState<VoicePreview[]>([])
  const [recipeProvider, setRecipeProvider] = useState('')
  const [recipeModel, setRecipeModel] = useState('')
  const [recipeName, setRecipeName] = useState('')
  const [recipeDescription, setRecipeDescription] = useState('')
  const [previewText, setPreviewText] = useState(
    'CineForge provider-safe voice preview. Planning only.',
  )

  const [actionBusy, setActionBusy] = useState(false)
  const [resourcesLoading, setResourcesLoading] = useState(false)
  const [pageError, setPageError] = useState<string | null>(null)
  const [pageNote, setPageNote] = useState<string | null>(null)
  const projectId = data?.story.project_id ?? ''
  const disabled = busy || actionBusy
  const selectedVoiceLocked = selectedVoice?.approval_state === 'approved'
  const consentRequired = modeRequiresConsent(mode)

  const modeHelp = useMemo(() => {
    switch (mode) {
      case 'placeholder':
        return 'Planning stand-in. No provider call and no audio generation.'
      case 'manual':
        return 'Manually configured planning profile without a provider voice reference.'
      case 'existing_provider_voice':
        return 'References an existing provider voice by provider and provider-owned identifier.'
      case 'qwen_voice_design':
        return 'Stores a Qwen voice-design description. Saving does not synthesize audio.'
      case 'qwen_custom_voice':
        return 'Selects a Qwen preset speaker identifier. Reference-audio cloning is forbidden.'
      case 'elevenlabs_voice_design':
        return 'Stores an ElevenLabs voice-design description. Provider availability is checked server-side.'
      case 'parler_local_voice_design':
        return 'Stores a local Parler design description. The backend may report: “Parler-TTS is not installed or approved.”'
      case 'user_provided_consented':
        return 'Uploads a managed audio source only after consent is confirmed. The source is referenced by asset ID; cloning is not performed.'
    }
  }, [mode])

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

  const refreshSourceAssets = useCallback(async () => {
    if (!projectId) return
    try {
      const result = await api.listVoiceSourceAssets(projectId)
      setSourceAssets(result?.items ?? [])
    } catch (error) {
      setPageError(errorText(error, 'Could not load managed voice source assets.'))
    }
  }, [projectId])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadVoiceResources(effectiveSelectedVoiceId), 0)
    return () => window.clearTimeout(timer)
  }, [effectiveSelectedVoiceId, loadVoiceResources])

  useEffect(() => {
    const timer = window.setTimeout(() => void refreshSourceAssets(), 0)
    return () => window.clearTimeout(timer)
  }, [refreshSourceAssets])

  if (!data) return null
  const loadedStoryId = data.story.id

  const shotCoverage = shots.filter((shot) => Boolean(shot.narration_voice_profile_id)).length
  const unresolvedShots = shots.length - shotCoverage
  const consentHolds = voices.filter((voice) => voice.consent_required && !voice.consent_confirmed).length
  const selectedNarrations = selectedVoice
    ? shots.filter((shot) => shot.narration_voice_profile_id === selectedVoice.id).length
    : 0
  const effectiveEditDraft: VoiceEditDraft =
    editDraft && editDraft.voiceId === selectedVoice?.id
      ? editDraft
      : {
          voiceId: selectedVoice?.id ?? '',
          name: selectedVoice?.name ?? '',
          language: selectedVoice?.language ?? '',
          notes: selectedVoice?.usage_notes ?? '',
          sourceDescription: selectedVoice?.source_description ?? '',
        }
  const effectiveRecipeProvider = recipeProvider || selectedVoice?.provider || ''

  function selectVoice(voice: Voice) {
    setSelectedVoiceId(voice.id)
    setEditDraft(null)
    setRecipeProvider(voice.provider ?? '')
    setDrawerTab('profile')
  }

  function onCardKeyDown(event: KeyboardEvent<HTMLElement>, voice: Voice) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      selectVoice(voice)
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setPageError(null)
    setPageNote(null)
    if (!name.trim()) return
    if (consentRequired && !consentConfirmed) {
      setMessage('Confirm consent before saving a user-provided voice source.')
      return
    }
    if (mode === 'existing_provider_voice' && (!provider.trim() || !providerVoiceReference.trim())) {
      setMessage('Provider and provider voice reference are required for an existing provider voice.')
      return
    }
    if (mode === 'qwen_custom_voice' && !customVoiceSpeaker.trim()) {
      setMessage('Choose a preset Qwen speaker identifier. Reference-audio cloning is not accepted.')
      return
    }
    if (modeRequiresDesign(mode) && !notes.trim()) {
      setMessage('A voice design description is required for this setup mode.')
      return
    }
    if (mode === 'user_provided_consented' && !sourceAssetId && !notes.trim()) {
      setMessage('Upload or select a managed voice source, or record a source description.')
      return
    }

    const saved = await addVoice({
      name: name.trim(),
      setup_mode: mode,
      character_id: characterId || null,
      consent_required: consentRequired,
      consent_confirmed: consentRequired ? consentConfirmed : false,
      consent_notes: consentRequired ? 'Confirmed in CineForge Storyboard Studio.' : undefined,
      language: language.trim() || undefined,
      usage_notes: notes.trim() || undefined,
      provider: mode === 'existing_provider_voice' ? provider.trim() : undefined,
      provider_voice_reference:
        mode === 'existing_provider_voice' ? providerVoiceReference.trim() : undefined,
      design_description: modeRequiresDesign(mode) ? notes.trim() : undefined,
      custom_voice_speaker: mode === 'qwen_custom_voice' ? customVoiceSpeaker.trim() : undefined,
      source_asset_id: mode === 'user_provided_consented' && sourceAssetId ? sourceAssetId : null,
      source_description: mode === 'user_provided_consented' ? notes.trim() || undefined : undefined,
    })
    if (!saved) return
    setName('')
    setNotes('')
    setProvider('')
    setProviderVoiceReference('')
    setCustomVoiceSpeaker('')
    setCharacterId('')
    setConsentConfirmed(false)
    setSourceAssetId('')
    setSourceFile(null)
    setMode('placeholder')
    setDrawerTab('profile')
  }

  async function uploadSource() {
    if (!sourceFile || !consentConfirmed) return
    setActionBusy(true)
    setPageError(null)
    setPageNote(null)
    try {
      const result = await api.uploadVoiceSourceAsset(projectId, sourceFile, true)
      if (!result) throw new Error('Managed voice-source upload is unavailable on this backend.')
      setSourceAssetId(result.asset.id)
      setNotes((value) => value || `Consented managed source: ${result.asset.original_filename ?? sourceFile.name}`)
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

  async function saveProfile() {
    if (!selectedVoice || selectedVoiceLocked || !effectiveEditDraft.name.trim()) return
    setActionBusy(true)
    setPageError(null)
    setPageNote(null)
    try {
      const updated = await api.updateVoice(selectedVoice.id, {
        name: effectiveEditDraft.name.trim(),
        language: effectiveEditDraft.language.trim() || null,
        usage_notes: effectiveEditDraft.notes.trim() || null,
        source_description: effectiveEditDraft.sourceDescription.trim() || null,
      })
      if (!updated) throw new Error('Voice profile editing is unavailable on this backend.')
      await reload(loadedStoryId)
      setPageNote('Voice profile changes were saved to the backend.')
      setMessage('Voice profile changes saved. No audio was generated.')
    } catch (error) {
      const text = errorText(error, 'Could not update the voice profile.')
      setPageError(text)
      setMessage(text)
    } finally {
      setActionBusy(false)
    }
  }

  async function approveProfile() {
    if (!selectedVoice || !approvedBy.trim() || selectedVoiceLocked) return
    setActionBusy(true)
    setPageError(null)
    setPageNote(null)
    try {
      const result = await api.approveVoice(selectedVoice.id, approvedBy.trim(), allowWithoutPreview)
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

  async function createRecipe(event: FormEvent) {
    event.preventDefault()
    if (!selectedVoice || selectedVoiceLocked || !effectiveRecipeProvider.trim()) return
    setActionBusy(true)
    setPageError(null)
    try {
      const recipe = await api.createVoiceRecipe(selectedVoice.id, {
        provider: effectiveRecipeProvider.trim(),
        model: recipeModel.trim() || null,
        recipe_name: recipeName.trim() || null,
        description: recipeDescription.trim() || null,
      })
      if (!recipe) throw new Error('Voice recipe creation is unavailable on this backend.')
      setRecipeModel('')
      setRecipeName('')
      setRecipeDescription('')
      await loadVoiceResources(selectedVoice.id)
      await reload(loadedStoryId)
      setPageNote('Voice recipe metadata saved. No provider was invoked.')
    } catch (error) {
      setPageError(errorText(error, 'Could not save the voice recipe.'))
    } finally {
      setActionBusy(false)
    }
  }

  async function requestPreview() {
    if (!selectedVoice || selectedVoiceLocked || !previewText.trim()) return
    setActionBusy(true)
    setPageError(null)
    setPageNote(null)
    try {
      const result = await api.requestVoicePreview(selectedVoice.id, previewText.trim())
      if (!result) throw new Error('Voice preview API is unavailable on this backend.')
      const detail = result.message || result.error_message || `Preview job ${result.job_id} is ${result.status}.`
      setPageNote(detail)
      setMessage(detail)
    } catch (error) {
      const text = errorText(error, 'Voice preview is unavailable.')
      setPageError(text)
      setMessage(`${text} No audio was generated.`)
    } finally {
      setActionBusy(false)
    }
  }

  async function togglePreview(preview: VoicePreview) {
    if (selectedVoiceLocked) return
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

  async function archiveSelectedVoice() {
    if (!selectedVoice || selectedVoiceLocked) return
    if (!window.confirm(`Archive voice profile “${selectedVoice.name}”?`)) return
    setActionBusy(true)
    setPageError(null)
    setPageNote(null)
    try {
      const result = await api.deleteVoice(selectedVoice.id, 'Archived from Voice coverage.')
      if (result === null) throw new Error('Voice profile archive API is unavailable on this backend.')
      await reload(loadedStoryId)
      setSelectedVoiceId('')
      setPageNote(`Voice profile “${selectedVoice.name}” archived.`)
      setMessage(`Voice profile “${selectedVoice.name}” archived.`)
    } catch (error) {
      const text = errorText(error, 'Could not archive the voice profile.')
      setPageError(text)
      setMessage(text)
    } finally {
      setActionBusy(false)
    }
  }

  return (
    <div className="stack-form" style={{ maxWidth: '100%' }}>
      <PageTitle
        eyebrow="VOICE ASSIGNMENT"
        title="Voices"
        description="Plan narration and character delivery without cloning or generating final audio."
        aside={
          <div className="page-actions">
            <Button
              icon="lock"
              onClick={() =>
                setMessage(
                  'User-provided voices require a managed source, explicit consent confirmation, and usage notes. Voice cloning and final audio generation are not exposed in Storyboard Phase 1.',
                )
              }
            >
              Consent policy
            </Button>
            <Button
              variant="primary"
              icon="plus"
              onClick={() => {
                setDrawerTab('create')
                setPageNote(null)
              }}
            >
              Add voice profile
            </Button>
          </div>
        }
      />

      <div className="summary-strip" aria-label="Voice coverage summary">
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
      </div>
      <p className="form-hint" style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: -4 }}>
        <Icon name="warning" size={14} />
        Final voice generation happens only after storyboard approval. Waveforms on this page are decorative placeholders, not audio.
      </p>

      {pageError ? <ErrorState title="Voice workflow error" detail={pageError} /> : null}
      {pageNote ? (
        <p className="notice info" role="status">
          {pageNote}
        </p>
      ) : null}

      <div className="voice-layout">
        <div className="stack-form" style={{ maxWidth: '100%' }}>
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
                const selected = effectiveSelectedVoiceId === voice.id && drawerTab !== 'create'
                return (
                  <article
                    key={voice.id}
                    role="button"
                    tabIndex={0}
                    className={selected ? 'selected' : undefined}
                    aria-pressed={selected}
                    onClick={() => selectVoice(voice)}
                    onKeyDown={(event) => onCardKeyDown(event, voice)}
                  >
                    <header
                      style={{
                        display: 'flex',
                        gap: 10,
                        alignItems: 'flex-start',
                        justifyContent: 'space-between',
                      }}
                    >
                      <span
                        style={{
                          display: 'inline-grid',
                          placeItems: 'center',
                          width: 34,
                          height: 34,
                          borderRadius: 10,
                          background: '#1f2a28',
                          color: 'var(--mint, #58dda1)',
                          flexShrink: 0,
                        }}
                        aria-hidden="true"
                      >
                        <Icon name="mic" size={16} />
                      </span>
                      <span style={{ flex: 1, minWidth: 0 }}>
                        <small style={{ display: 'block', color: 'var(--muted)' }}>
                          {voiceModeLabel(voice)}
                        </small>
                        <b style={{ display: 'block' }}>{voice.name}</b>
                      </span>
                      <StatusPill status={approvalPillLabel(voice.approval_state)} />
                    </header>

                    <DecorativeWaveform />

                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {voice.language ? (
                        <span className="truth-pill">{voice.language}</span>
                      ) : null}
                      {voice.tone ? <span className="truth-pill">{voice.tone}</span> : null}
                      {voice.accent ? <span className="truth-pill">{voice.accent}</span> : null}
                      {!voice.language && !voice.tone && !voice.accent ? (
                        <span className="truth-pill">{voice.source_type || voiceModeLabel(voice)}</span>
                      ) : null}
                    </div>

                    <dl
                      style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
                        gap: 8,
                        margin: 0,
                      }}
                    >
                      <div>
                        <dt style={{ color: 'var(--muted)', fontSize: '0.72rem' }}>Provider</dt>
                        <dd style={{ margin: 0 }}>{voice.provider?.trim() || 'Unassigned'}</dd>
                      </div>
                      <div>
                        <dt style={{ color: 'var(--muted)', fontSize: '0.72rem' }}>Assigned</dt>
                        <dd style={{ margin: 0 }}>{assignedCharacter?.name ?? 'Unassigned'}</dd>
                      </div>
                      <div>
                        <dt style={{ color: 'var(--muted)', fontSize: '0.72rem' }}>Narration</dt>
                        <dd style={{ margin: 0 }}>{linkedShots} shots</dd>
                      </div>
                    </dl>

                    <p className="form-hint" style={{ margin: 0 }}>
                      {providerNote(voice)}
                    </p>

                    <footer
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        gap: 8,
                        alignItems: 'center',
                        flexWrap: 'wrap',
                      }}
                    >
                      {voice.consent_confirmed ? (
                        <span style={{ color: 'var(--mint, #58dda1)', display: 'inline-flex', gap: 6, alignItems: 'center' }}>
                          <Icon name="check" size={13} />
                          Source clear
                        </span>
                      ) : voice.consent_required ? (
                        <span style={{ color: '#e0b35a', display: 'inline-flex', gap: 6, alignItems: 'center' }}>
                          <Icon name="warning" size={13} />
                          Consent required
                        </span>
                      ) : (
                        <span style={{ color: 'var(--muted)', display: 'inline-flex', gap: 6, alignItems: 'center' }}>
                          <Icon name="check" size={13} />
                          No consent required
                        </span>
                      )}
                      <small style={{ color: 'var(--muted)' }}>Decorative waveform only</small>
                    </footer>
                  </article>
                )
              })}
            </div>
          )}
        </div>

        <aside className="entity-drawer" aria-label="Voice profile drawer">
          <header>
            <div>
              <span className="eyebrow">VOICE PROFILE</span>
              <h2 style={{ marginBottom: 0 }}>
                {drawerTab === 'create'
                  ? 'Add voice profile'
                  : selectedVoice?.name ?? 'No profile selected'}
              </h2>
            </div>
            {drawerTab !== 'create' && selectedVoice ? (
              <StatusPill status={approvalPillLabel(selectedVoice.approval_state)} />
            ) : null}
          </header>

          <div className="segmented" role="tablist" aria-label="Voice drawer sections">
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
              disabled={!selectedVoice}
            >
              Recipes
            </button>
            <button
              type="button"
              className={drawerTab === 'create' ? 'active' : undefined}
              role="tab"
              aria-selected={drawerTab === 'create'}
              onClick={() => setDrawerTab('create')}
            >
              Add
            </button>
          </div>

          {drawerTab === 'create' ? (
            <form className="stack-form" style={{ maxWidth: '100%' }} onSubmit={(event) => void onSubmit(event)}>
              <p className="form-hint">Select one of the eight modes. Saving writes planning metadata only.</p>
              <fieldset style={{ border: 0, margin: 0, padding: 0 }}>
                <legend className="eyebrow">Source mode (8)</legend>
                <div className="mode-grid" role="group" aria-label="Voice source modes">
                  {VOICE_SETUP_MODES.map((item) => (
                    <button
                      key={item}
                      type="button"
                      className={`mode-option ${mode === item ? 'selected' : ''}`}
                      aria-pressed={mode === item}
                      onClick={() => {
                        setMode(item)
                        if (!modeRequiresConsent(item)) setConsentConfirmed(false)
                      }}
                      disabled={disabled}
                    >
                      {VOICE_SETUP_MODE_LABELS[item]}
                      <small>{item}</small>
                    </button>
                  ))}
                </div>
                <p className="form-hint">{modeHelp}</p>
              </fieldset>
              <label>
                Profile name
                <input
                  required
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  disabled={disabled}
                  autoComplete="off"
                />
              </label>
              <label>
                Character assignment
                <select
                  value={characterId}
                  onChange={(event) => setCharacterId(event.target.value)}
                  disabled={disabled}
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
                  value={language}
                  onChange={(event) => setLanguage(event.target.value)}
                  disabled={disabled}
                />
              </label>
              {mode === 'existing_provider_voice' ? (
                <div className="split-2">
                  <label>
                    Provider
                    <input
                      required
                      value={provider}
                      onChange={(event) => setProvider(event.target.value)}
                      disabled={disabled}
                    />
                  </label>
                  <label>
                    Provider voice reference
                    <input
                      required
                      value={providerVoiceReference}
                      onChange={(event) => setProviderVoiceReference(event.target.value)}
                      disabled={disabled}
                    />
                  </label>
                </div>
              ) : null}
              {mode === 'qwen_custom_voice' ? (
                <label>
                  Preset Qwen speaker identifier
                  <input
                    required
                    value={customVoiceSpeaker}
                    onChange={(event) => setCustomVoiceSpeaker(event.target.value)}
                    disabled={disabled}
                    placeholder="Preset speaker only — no reference audio"
                  />
                </label>
              ) : null}
              {mode === 'user_provided_consented' ? (
                <div className="notice warning stack-form" style={{ maxWidth: '100%' }}>
                  <strong>Managed consented source</strong>
                  <label style={{ gridTemplateColumns: 'auto 1fr', alignItems: 'center' }}>
                    <input
                      type="checkbox"
                      checked={consentConfirmed}
                      onChange={(event) => setConsentConfirmed(event.target.checked)}
                      disabled={disabled}
                      style={{ width: 20, height: 20, minHeight: 20 }}
                    />
                    <span>I confirm rights/consent for this user-provided voice sample.</span>
                  </label>
                  <label>
                    Audio source (.wav, .mp3, .ogg, or .flac; up to 50 MB)
                    <input
                      type="file"
                      accept="audio/wav,audio/x-wav,audio/mpeg,audio/ogg,audio/flac,.wav,.mp3,.ogg,.flac"
                      disabled={disabled}
                      onChange={(event) => setSourceFile(event.target.files?.[0] ?? null)}
                    />
                  </label>
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={disabled || !sourceFile || !consentConfirmed}
                    onClick={() => void uploadSource()}
                  >
                    Upload consented managed source
                  </button>
                  <label>
                    Managed source asset
                    <select
                      value={sourceAssetId}
                      onChange={(event) => setSourceAssetId(event.target.value)}
                      disabled={disabled}
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
                {modeRequiresDesign(mode)
                  ? 'Voice design description'
                  : mode === 'user_provided_consented'
                    ? 'Managed source description'
                    : 'Usage notes'}
                <textarea
                  required={modeRequiresDesign(mode)}
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                  disabled={disabled}
                />
              </label>
              <Button
                type="submit"
                variant="primary"
                disabled={disabled || !name.trim() || (consentRequired && !consentConfirmed)}
              >
                Save voice profile
              </Button>
              <p className="notice info">
                Voice cloning and final audio generation are not exposed in Storyboard Phase 1.
              </p>
            </form>
          ) : null}

          {drawerTab === 'profile' ? (
            !selectedVoice ? (
              <EmptyState
                title="No profile selected"
                detail="Create or select a voice profile to manage it."
              />
            ) : (
              <div className="stack-form" style={{ maxWidth: '100%' }}>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'auto 1fr',
                    gap: 12,
                    alignItems: 'center',
                    marginBottom: 4,
                  }}
                >
                  <span
                    style={{
                      display: 'inline-grid',
                      placeItems: 'center',
                      width: 48,
                      height: 48,
                      borderRadius: 12,
                      background: '#1f2a28',
                      color: 'var(--mint, #58dda1)',
                    }}
                    aria-hidden="true"
                  >
                    <Icon name="mic" size={24} />
                  </span>
                  <DecorativeWaveform label="Decorative waveform for selected voice" />
                </div>

                <ul className="kv-list">
                  <li>
                    <span>Mode</span>
                    <strong>{voiceModeLabel(selectedVoice)}</strong>
                  </li>
                  <li>
                    <span>Status</span>
                    <strong>{selectedVoice.approval_state}</strong>
                  </li>
                  <li>
                    <span>Shot assignments</span>
                    <strong>{selectedNarrations}</strong>
                  </li>
                  <li>
                    <span>Provider notes</span>
                    <strong>{providerNote(selectedVoice)}</strong>
                  </li>
                  <li>
                    <span>Selected preview asset</span>
                    <strong className="mono">
                      {selectedVoice.selected_preview_asset_id ?? 'None'}
                    </strong>
                  </li>
                </ul>

                <label>
                  Name
                  <input
                    value={effectiveEditDraft.name}
                    onChange={(event) =>
                      setEditDraft({ ...effectiveEditDraft, name: event.target.value })
                    }
                    disabled={disabled || selectedVoiceLocked}
                  />
                </label>
                <label>
                  Language
                  <input
                    value={effectiveEditDraft.language}
                    onChange={(event) =>
                      setEditDraft({ ...effectiveEditDraft, language: event.target.value })
                    }
                    disabled={disabled || selectedVoiceLocked}
                  />
                </label>
                <label>
                  Usage notes
                  <textarea
                    value={effectiveEditDraft.notes}
                    onChange={(event) =>
                      setEditDraft({ ...effectiveEditDraft, notes: event.target.value })
                    }
                    disabled={disabled || selectedVoiceLocked}
                  />
                </label>
                <label>
                  Source description
                  <textarea
                    value={effectiveEditDraft.sourceDescription}
                    onChange={(event) =>
                      setEditDraft({
                        ...effectiveEditDraft,
                        sourceDescription: event.target.value,
                      })
                    }
                    disabled={disabled || selectedVoiceLocked}
                  />
                </label>

                {selectedVoiceLocked ? (
                  <p className="notice info">
                    Approved profiles are immutable in Phase 1. Create a new profile to change identity
                    or routing fields.
                  </p>
                ) : (
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={disabled || !effectiveEditDraft.name.trim()}
                    onClick={() => void saveProfile()}
                  >
                    Save profile edits
                  </button>
                )}

                <button
                  type="button"
                  className="ghost-button"
                  disabled={disabled || selectedVoiceLocked}
                  title={
                    selectedVoiceLocked
                      ? 'Approved profiles cannot be archived while locked into production identity.'
                      : undefined
                  }
                  onClick={() => void archiveSelectedVoice()}
                >
                  Archive voice profile
                </button>

                <label>
                  Approval audit name
                  <input
                    value={approvedBy}
                    onChange={(event) => setApprovedBy(event.target.value)}
                    disabled={disabled || selectedVoiceLocked}
                    placeholder="Your name or production role"
                  />
                </label>
                <label style={{ gridTemplateColumns: 'auto 1fr', alignItems: 'center' }}>
                  <input
                    type="checkbox"
                    checked={allowWithoutPreview}
                    onChange={(event) => setAllowWithoutPreview(event.target.checked)}
                    disabled={disabled || selectedVoiceLocked}
                    style={{ width: 20, height: 20, minHeight: 20 }}
                  />
                  <span>Allow approval without a preview when this setup mode permits it</span>
                </label>
                <button
                  type="button"
                  className="primary-button"
                  disabled={disabled || selectedVoiceLocked || !approvedBy.trim()}
                  onClick={() => void approveProfile()}
                >
                  {selectedVoiceLocked ? 'Profile approved' : 'Approve voice profile'}
                </button>
              </div>
            )
          ) : null}

          {drawerTab === 'recipes' ? (
            !selectedVoice ? (
              <EmptyState
                title="No profile selected"
                detail="Select a profile to inspect recipes and previews."
              />
            ) : resourcesLoading ? (
              <LoadingState title="Loading recipes and previews…" />
            ) : (
              <div className="stack-form" style={{ maxWidth: '100%' }}>
                <form
                  className="stack-form"
                  style={{ maxWidth: '100%' }}
                  onSubmit={(event) => void createRecipe(event)}
                >
                  <h3>Create recipe</h3>
                  <p className="form-hint">
                    Recipe creation stores metadata only. Preview generation is an explicit request and
                    currently returns the backend&apos;s truthful unavailable response when no durable
                    worker is configured.
                  </p>
                  <div className="split-2">
                    <label>
                      Provider
                      <input
                        required
                        value={effectiveRecipeProvider}
                        onChange={(event) => setRecipeProvider(event.target.value)}
                        disabled={disabled || selectedVoiceLocked}
                      />
                    </label>
                    <label>
                      Model (optional)
                      <input
                        value={recipeModel}
                        onChange={(event) => setRecipeModel(event.target.value)}
                        disabled={disabled || selectedVoiceLocked}
                      />
                    </label>
                  </div>
                  <label>
                    Recipe name
                    <input
                      value={recipeName}
                      onChange={(event) => setRecipeName(event.target.value)}
                      disabled={disabled || selectedVoiceLocked}
                    />
                  </label>
                  <label>
                    Description
                    <textarea
                      value={recipeDescription}
                      onChange={(event) => setRecipeDescription(event.target.value)}
                      disabled={disabled || selectedVoiceLocked}
                    />
                  </label>
                  <button
                    type="submit"
                    className="secondary-button"
                    disabled={
                      disabled || selectedVoiceLocked || !effectiveRecipeProvider.trim()
                    }
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
                    disabled={disabled || selectedVoiceLocked}
                    maxLength={2000}
                  />
                </label>
                <button
                  type="button"
                  className="secondary-button"
                  disabled={disabled || selectedVoiceLocked || !previewText.trim()}
                  onClick={() => void requestPreview()}
                >
                  Request provider-safe preview
                </button>
                <p className="form-hint">
                  The public backend currently responds 503 until a durable isolated preview worker is
                  configured. This action never falls back to in-process generation and never clones a
                  voice.
                </p>

                <h3>Persisted preview records</h3>
                {previews.length ? (
                  <ul className="kv-list">
                    {previews.map((preview) => (
                      <li key={preview.id}>
                        <span>
                          {preview.provider ?? 'Unknown provider'} ·{' '}
                          {preview.preview_text ?? 'No preview text'} · asset{' '}
                          {preview.planning_media_asset_id ?? 'missing'}
                        </span>
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={
                            disabled ||
                            selectedVoiceLocked ||
                            preview.rejected ||
                            !preview.planning_media_asset_id
                          }
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
                    ))}
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
