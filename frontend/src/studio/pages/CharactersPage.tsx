/**
 * Exact structural port of prototype CharactersPage (pagesAssets.tsx / pagesAssets.source.tsx)
 * adapted to production studio context + character CRUD / reference APIs.
 *
 * DOM hierarchy matches the ZIP prototype:
 * page-title (CHARACTER BIBLE + Needs review / Create character) →
 * character-layout → stack (segmented filter + character-grid cards) |
 * entity-drawer (portrait, reference-strip, Identity / Linked shots / Continuity tabs,
 * identity form fields, voice assignment).
 *
 * Production create/update/archive + managed reference upload/link/unlink + voice assign
 * stay wired via api client only (no mock / project store).
 */
import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  api,
  planningAssetContentUrl,
  type Character,
  type CharacterReferenceLink,
  type PlanningMediaAsset,
  type StoryboardAggregate,
  type Voice,
} from '../../api/client'
import { Button, Empty, Icon, PageTitle, StatusPill } from '../proto/ui'
import { useStudio } from '../StudioState'
import { EmptyState, ErrorState, LoadingState, UnavailableState } from '../components/StateBlocks'
import { initials } from '../utils'

const REFERENCE_ROLES = ['primary', 'alternate', 'expression', 'costume', 'detail'] as const

const GENERATION_DISABLED_REASON =
  'Image generation is disabled in Phase 1 planning; this page only stores and links user-provided managed assets.'

const APPROVE_EXISTING_LINK_REASON =
  'The backend exposes approval only while creating a reference link; unlink and relink it as an approved hero reference.'

type ApprovalFilter = 'All' | 'Draft' | 'Review' | 'Approved' | 'Blocked'
type DrawerTab = 'identity' | 'linked' | 'continuity'

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

/** Map backend approval_state → display label for StatusPill / filters. */
function approvalLabel(state: string): Exclude<ApprovalFilter, 'All'> {
  const normalized = state.toLowerCase()
  if (normalized === 'in_review' || normalized === 'review') return 'Review'
  if (normalized === 'approved') return 'Approved'
  if (normalized === 'blocked') return 'Blocked'
  return 'Draft'
}

function matchesApprovalFilter(state: string, filter: ApprovalFilter): boolean {
  if (filter === 'All') return true
  return approvalLabel(state) === filter
}

function characterShotLinks(characterId: string, chapters: StoryboardAggregate['chapters']) {
  const scenes = chapters.flatMap((chapter) =>
    chapter.scenes.filter((scene) =>
      scene.shots.some((shot) => shot.characters?.some((link) => link.character_id === characterId)),
    ),
  )
  const shots = scenes.flatMap((scene) =>
    scene.shots.filter((shot) =>
      shot.characters?.some((link) => link.character_id === characterId),
    ),
  )
  return { scenes, shots }
}

function characterVoiceName(character: Character, voices: Voice[]): string {
  if (character.assigned_voice_profile_id) {
    const canonical = voices.find((voice) => voice.id === character.assigned_voice_profile_id)
    if (canonical) return canonical.name
  }
  const associated = voices.find((voice) => voice.character_id === character.id)
  return associated?.name ?? 'Voice missing'
}

/** Display-only outfit chips (no outfits API field) — short wardrobe phrases. */
function outfitTokens(character: Character): string[] {
  const wardrobe = character.wardrobe?.trim()
  if (!wardrobe) return []
  return wardrobe
    .split(/[,;|]/)
    .map((part) => part.trim())
    .filter((part) => part.length > 0 && part.length <= 36)
    .slice(0, 4)
}

function Portrait({
  name,
  role,
  large = false,
}: {
  name: string
  role?: string | null
  large?: boolean
}) {
  const roleLabel = (role ?? 'Character').split('·')[0]?.trim() || 'Character'
  return (
    <div className={`portrait${large ? ' large' : ''}`} aria-hidden="true">
      <span>{initials(name)}</span>
      <i>{roleLabel}</i>
    </div>
  )
}

export function CharactersPage() {
  const { data, readiness, reload, setMessage, busy } = useStudio()
  const [selectedId, setSelectedId] = useState('')
  const [filter, setFilter] = useState<ApprovalFilter>('All')
  const [edit, setEdit] = useState(false)
  const [drawerTab, setDrawerTab] = useState<DrawerTab>('identity')
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [newRole, setNewRole] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [assets, setAssets] = useState<PlanningMediaAsset[]>([])
  const [references, setReferences] = useState<CharacterReferenceLink[]>([])
  const [referenceApiAvailable, setReferenceApiAvailable] = useState(true)
  const [selectedAssetId, setSelectedAssetId] = useState('')
  const [referenceRole, setReferenceRole] = useState<(typeof REFERENCE_ROLES)[number]>('primary')
  const [approveHero, setApproveHero] = useState(false)
  const [referenceFile, setReferenceFile] = useState<File | null>(null)
  const [fileInputKey, setFileInputKey] = useState(0)
  const [selectedVoiceId, setSelectedVoiceId] = useState('')
  const [loadingReferences, setLoadingReferences] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const actionsBusy = busy || saving
  const busyReason = busy
    ? 'A studio save or reload is already in progress.'
    : saving
      ? 'A character action is already in progress.'
      : null
  const editReason = !edit
    ? 'Turn on edit (pencil) to change identity fields and save via PATCH /storyboard/characters/{id}.'
    : null
  const fieldsDisabledReason = firstReason(busyReason, editReason)

  const characters = useMemo(() => data?.characters ?? [], [data?.characters])

  const filterCounts = useMemo(() => {
    const counts: Record<ApprovalFilter, number> = {
      All: characters.length,
      Draft: 0,
      Review: 0,
      Approved: 0,
      Blocked: 0,
    }
    for (const character of characters) {
      counts[approvalLabel(character.approval_state)] += 1
    }
    return counts
  }, [characters])

  const filteredCharacters = useMemo(
    () => characters.filter((character) => matchesApprovalFilter(character.approval_state, filter)),
    [characters, filter],
  )

  const selectedCharacter =
    characters.find((character) => character.id === selectedId) ??
    filteredCharacters[0] ??
    characters[0] ??
    null

  const loadReferences = useCallback(async () => {
    if (!data || !selectedCharacter) {
      setAssets([])
      setReferences([])
      return
    }
    setLoadingReferences(true)
    setError(null)
    try {
      const [assetResult, linkResult] = await Promise.all([
        api.listCharacterReferenceAssets(data.story.project_id),
        api.listCharacterReferences(selectedCharacter.id),
      ])
      if (assetResult == null || linkResult == null) {
        setReferenceApiAvailable(false)
        setAssets([])
        setReferences([])
        return
      }
      setReferenceApiAvailable(true)
      setAssets(assetResult.items)
      setReferences(linkResult)
      setSelectedAssetId((current) =>
        assetResult.items.some((asset) => asset.id === current)
          ? current
          : (assetResult.items[0]?.id ?? ''),
      )
    } catch (err) {
      setError(errorText(err, 'Could not load managed character references.'))
    } finally {
      setLoadingReferences(false)
    }
  }, [data, selectedCharacter])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadReferences(), 0)
    return () => window.clearTimeout(timer)
  }, [loadReferences])

  if (!data) return null

  const linkedScenes = selectedCharacter
    ? characterShotLinks(selectedCharacter.id, data.chapters).scenes
    : []
  const linkedShots = selectedCharacter
    ? characterShotLinks(selectedCharacter.id, data.chapters).shots
    : []
  const characterReadiness = selectedCharacter
    ? (readiness?.reasons.filter((reason) => reason.entity_id === selectedCharacter.id) ?? [])
    : []
  const associatedVoices = selectedCharacter
    ? data.voices.filter((voice) => voice.character_id === selectedCharacter.id)
    : []
  const canonicalVoice = selectedCharacter?.assigned_voice_profile_id
    ? data.voices.find((voice) => voice.id === selectedCharacter.assigned_voice_profile_id)
    : null
  const selectedVoice = data.voices.find((voice) => voice.id === selectedVoiceId)
  const heroReference = references.find(
    (reference) =>
      (reference.reference_role === 'primary' || reference.reference_role === 'hero') &&
      reference.approved,
  )
  /** Reference strip prefers live links; falls back to aggregate summaries before load. */
  const displayReferences: Array<{
    id: string
    asset_id: string
    reference_role: string
    approved: boolean
    label?: string | null
  }> =
    references.length > 0
      ? references.map((reference) => ({
          id: reference.id,
          asset_id: reference.asset_id,
          reference_role: reference.reference_role,
          approved: reference.approved,
          label: reference.asset?.original_filename ?? null,
        }))
      : (selectedCharacter?.reference_assets ?? []).map((ref) => ({
          id: ref.id,
          asset_id: ref.asset_id,
          reference_role: ref.reference_role,
          approved: ref.approved,
          label: null,
        }))
  const selectedOutfits = selectedCharacter ? outfitTokens(selectedCharacter) : []

  // Factual archive blockers mirror backend archive_character conflict checks.
  const archiveConflictParts: string[] = []
  if (selectedCharacter?.approval_state === 'approved') {
    archiveConflictParts.push('character is approved')
  }
  if (linkedShots.length) {
    archiveConflictParts.push(
      `linked to ${linkedShots.length} active shot${linkedShots.length === 1 ? '' : 's'}`,
    )
  }
  if (associatedVoices.length) {
    archiveConflictParts.push(
      `referenced by ${associatedVoices.length} active voice profile${associatedVoices.length === 1 ? '' : 's'}`,
    )
  }
  if (references.length) {
    archiveConflictParts.push(
      `owns ${references.length} character reference link${references.length === 1 ? '' : 's'}`,
    )
  }
  const archiveReason = firstReason(
    busyReason,
    archiveConflictParts.length > 0 &&
      `Cannot archive: ${archiveConflictParts.join('; ')}. Unlink shots/voices/references or use a non-approved character.`,
  )
  const createNameReason = firstReason(
    busyReason,
    !newName.trim() &&
      'Enter a character name before creating via POST /storyboard/stories/{id}/characters.',
  )
  const saveReason = firstReason(busyReason, editReason)
  const uploadReason = firstReason(
    busyReason,
    !referenceApiAvailable && 'Character-reference upload API is unavailable.',
    !referenceFile && 'Choose an image file before uploading a managed reference asset.',
  )
  const linkReason = firstReason(
    busyReason,
    !referenceApiAvailable && 'Character-reference link API is unavailable.',
    !selectedAssetId && 'Select a managed asset before creating a character reference link.',
  )
  const assignVoiceReason = firstReason(
    busyReason,
    !selectedVoice &&
      'Choose a mutable voice profile before assigning character_id via PATCH /voices/profiles/{id}.',
    selectedVoice?.approval_state === 'approved' &&
      'Approved voice profiles are immutable and cannot be reassigned.',
  )

  const onAddCharacter = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!newName.trim() || actionsBusy) return
    setSaving(true)
    setError(null)
    try {
      const created = await api.createCharacter(data.story.id, {
        name: newName.trim(),
        role: newRole.trim() || undefined,
        physical_description: newDescription.trim() || undefined,
      })
      await reload()
      setSelectedId(created.id)
      setEdit(true)
      setDrawerTab('identity')
      setNewName('')
      setNewRole('')
      setNewDescription('')
      setShowCreate(false)
      setMessage(`Character “${created.name}” saved. No image generation was started.`)
    } catch (err) {
      const text = errorText(err, 'Could not create the character.')
      setError(text)
      setMessage(text)
    } finally {
      setSaving(false)
    }
  }

  const onQuickCreate = () => {
    if (showCreate) {
      setShowCreate(false)
      return
    }
    // Production needs a name; open the compact create form (proto creates a draft instantly).
    setShowCreate(true)
    setNewName('New character')
    setNewRole('Unassigned role')
    setNewDescription('')
  }

  const onSaveCharacter = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!selectedCharacter || actionsBusy || !edit) return
    const form = new FormData(event.currentTarget)
    const nextName =
      String(form.get('name') ?? selectedCharacter.name).trim() || selectedCharacter.name
    if (!nextName) return
    setSaving(true)
    setError(null)
    try {
      const result = await api.updateCharacter(selectedCharacter.id, {
        name: nextName,
        role:
          String(form.get('role') ?? selectedCharacter.role ?? '').trim() ||
          selectedCharacter.role ||
          null,
        age_range: String(form.get('age_range') ?? '').trim() || null,
        physical_description: String(form.get('physical_description') ?? '').trim() || null,
        personality: String(form.get('personality') ?? '').trim() || null,
        speaking_style: String(form.get('speaking_style') ?? '').trim() || null,
        wardrobe: String(form.get('wardrobe') ?? '').trim() || null,
        consistency_prompt: String(form.get('consistency_prompt') ?? '').trim() || null,
        negative_identity_prompt: String(form.get('negative_identity_prompt') ?? '').trim() || null,
        identity_method: String(form.get('identity_method') ?? '').trim() || null,
      })
      if (result == null) {
        setMessage('Character edit API is unavailable; no changes were persisted.')
        return
      }
      await reload()
      setEdit(false)
      setMessage(`Character “${result.name}” updated on the server.`)
    } catch (err) {
      const text = errorText(err, 'Could not update the character.')
      setError(text)
      setMessage(text)
    } finally {
      setSaving(false)
    }
  }

  const onArchiveCharacter = async () => {
    if (!selectedCharacter || archiveReason) return
    if (!window.confirm(`Archive character “${selectedCharacter.name}”?`)) return
    setSaving(true)
    setError(null)
    try {
      const result = await api.deleteCharacter(
        selectedCharacter.id,
        'Archived from Character bible.',
      )
      if (result === null) {
        setMessage('Character archive API is unavailable; no changes were persisted.')
        return
      }
      await reload()
      setSelectedId('')
      setEdit(false)
      setMessage(`Character “${selectedCharacter.name}” archived on the server.`)
    } catch (err) {
      const text = errorText(err, 'Could not archive the character.')
      setError(text)
      setMessage(text)
    } finally {
      setSaving(false)
    }
  }

  const onUploadReference = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!referenceFile || actionsBusy || !referenceApiAvailable) return
    setSaving(true)
    setError(null)
    try {
      const result = await api.uploadCharacterReferenceAsset(data.story.project_id, referenceFile)
      if (result == null) {
        setReferenceApiAvailable(false)
        setMessage('Managed character-reference upload API is unavailable; no file was stored.')
        return
      }
      setSelectedAssetId(result.asset.id)
      setReferenceFile(null)
      setFileInputKey((value) => value + 1)
      await loadReferences()
      setMessage(
        result.duplicate_of_existing
          ? `Reused managed reference asset ${result.asset.id}; no duplicate file was stored.`
          : `Uploaded managed reference asset ${result.asset.id}. No image generation was started.`,
      )
    } catch (err) {
      const text = errorText(err, 'Could not upload the character reference.')
      setError(text)
      setMessage(text)
    } finally {
      setSaving(false)
    }
  }

  const onLinkReference = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!selectedCharacter || !selectedAssetId || actionsBusy || !referenceApiAvailable) return
    const willApproveHero = approveHero
    setSaving(true)
    setError(null)
    try {
      const result = await api.linkCharacterReference(selectedCharacter.id, {
        asset_id: selectedAssetId,
        reference_role: willApproveHero ? 'primary' : referenceRole,
        approved: willApproveHero,
        order_index: references.length,
      })
      if (result == null) {
        setReferenceApiAvailable(false)
        setMessage('Character-reference link API is unavailable; no link was created.')
        return
      }
      setApproveHero(false)
      await Promise.all([loadReferences(), reload()])
      setMessage(
        willApproveHero
          ? `Approved ${result.asset?.original_filename ?? result.asset_id} as the character’s primary hero reference.`
          : `Linked ${result.asset?.original_filename ?? result.asset_id} as ${result.reference_role}.`,
      )
    } catch (err) {
      const text = errorText(err, 'Could not link the character reference.')
      setError(text)
      setMessage(text)
    } finally {
      setSaving(false)
    }
  }

  const onUnlinkReference = async (reference: CharacterReferenceLink) => {
    if (actionsBusy || !referenceApiAvailable) return
    setSaving(true)
    setError(null)
    try {
      const result = await api.unlinkCharacterReference(reference.id)
      if (result === null) {
        setReferenceApiAvailable(false)
        setMessage('Character-reference unlink API is unavailable; the link was not changed.')
        return
      }
      await Promise.all([loadReferences(), reload()])
      setMessage(`Unlinked reference ${reference.asset?.original_filename ?? reference.asset_id}.`)
    } catch (err) {
      const text = errorText(err, 'Could not unlink the character reference.')
      setError(text)
      setMessage(text)
    } finally {
      setSaving(false)
    }
  }

  const onAssignVoice = async () => {
    if (!selectedCharacter || !selectedVoice || assignVoiceReason) return
    setSaving(true)
    setError(null)
    try {
      const result = await api.updateVoice(selectedVoice.id, { character_id: selectedCharacter.id })
      if (result == null) {
        setMessage('Voice profile assignment API is unavailable; no assignment was changed.')
        return
      }
      await reload()
      setSelectedVoiceId('')
      setMessage(`Associated voice profile “${result.name}” with ${selectedCharacter.name}.`)
    } catch (err) {
      const text = errorText(err, 'Could not assign the voice profile.')
      setError(text)
      setMessage(text)
    } finally {
      setSaving(false)
    }
  }

  const onUnassignVoice = async (voiceId: string) => {
    const voice = data.voices.find((item) => item.id === voiceId)
    if (actionsBusy || voice?.approval_state === 'approved') return
    setSaving(true)
    setError(null)
    try {
      const result = await api.updateVoice(voiceId, { character_id: null })
      if (result == null) {
        setMessage('Voice profile assignment API is unavailable; no assignment was changed.')
        return
      }
      await reload()
      setMessage(`Removed voice profile “${result.name}” from this character.`)
    } catch (err) {
      const text = errorText(err, 'Could not remove the voice profile assignment.')
      setError(text)
      setMessage(text)
    } finally {
      setSaving(false)
    }
  }

  const selectCharacter = (id: string) => {
    setSelectedId(id)
    setSelectedVoiceId('')
    setEdit(false)
    setDrawerTab('identity')
    setError(null)
  }

  return (
    <div className="page">
      <PageTitle
        eyebrow="CHARACTER BIBLE"
        title="Characters"
        description="Lock identity, wardrobe, references, and voice assignments before image generation."
        aside={
          <div className="page-actions">
            <Button
              type="button"
              icon="filter"
              onClick={() => setFilter(filter === 'All' ? 'Review' : 'All')}
              disabled={actionsBusy}
              title={busyReason ?? undefined}
            >
              {filter === 'All' ? 'Needs review' : 'Show all'}
            </Button>
            <Button
              type="button"
              variant="primary"
              icon="plus"
              onClick={onQuickCreate}
              disabled={actionsBusy}
              title={busyReason ?? undefined}
            >
              Create character
            </Button>
          </div>
        }
      />

      <div className="character-layout">
        <div className="stack">
          <div className="segmented" role="tablist" aria-label="Filter characters by approval state">
            {(['All', 'Draft', 'Review', 'Approved', 'Blocked'] as const).map((label) => (
              <button
                key={label}
                type="button"
                role="tab"
                aria-selected={filter === label}
                className={filter === label ? 'active' : ''}
                onClick={() => setFilter(label)}
              >
                {label}
                <span>{filterCounts[label]}</span>
              </button>
            ))}
          </div>

          {showCreate ? (
            <form className="panel stack-form" onSubmit={(event) => void onAddCharacter(event)}>
              <h3>Create character</h3>
              <p className="form-hint">
                Persists via POST /storyboard/stories/{'{story_id}'}/characters. No image is
                generated.
              </p>
              <label>
                Name
                <input
                  required
                  value={newName}
                  onChange={(event) => setNewName(event.target.value)}
                  disabled={actionsBusy}
                  title={busyReason ?? undefined}
                />
              </label>
              <label>
                Role
                <input
                  value={newRole}
                  onChange={(event) => setNewRole(event.target.value)}
                  disabled={actionsBusy}
                  title={busyReason ?? undefined}
                />
              </label>
              <label>
                Description
                <textarea
                  value={newDescription}
                  onChange={(event) => setNewDescription(event.target.value)}
                  disabled={actionsBusy}
                  title={busyReason ?? undefined}
                />
              </label>
              <div className="inline-actions">
                <Button
                  type="submit"
                  variant="primary"
                  disabled={Boolean(createNameReason)}
                  title={createNameReason}
                >
                  {saving ? 'Creating…' : 'Add character'}
                </Button>
                <Button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  disabled={actionsBusy}
                  title={busyReason ?? undefined}
                >
                  Cancel
                </Button>
              </div>
            </form>
          ) : null}

          {!characters.length ? (
            <EmptyState
              title="No characters yet"
              detail="Add a character to begin the production bible."
              action={
                <Button
                  type="button"
                  variant="primary"
                  icon="plus"
                  onClick={onQuickCreate}
                  disabled={actionsBusy}
                  title={busyReason ?? undefined}
                >
                  Create character
                </Button>
              }
            />
          ) : !filteredCharacters.length ? (
            <Empty
              title="No characters match"
              detail="Try another readiness filter."
              action={
                <Button type="button" onClick={() => setFilter('All')}>
                  Clear filter
                </Button>
              }
            />
          ) : (
            <div className="character-grid">
              {filteredCharacters.map((character) => {
                const links = characterShotLinks(character.id, data.chapters)
                const voiceName = characterVoiceName(character, data.voices)
                const refCount =
                  character.reference_assets?.length ??
                  (character.id === selectedCharacter?.id ? references.length : 0)
                const heroReady =
                  character.reference_assets?.some(
                    (ref) =>
                      (ref.reference_role === 'primary' || ref.reference_role === 'hero') &&
                      ref.approved,
                  ) || (character.id === selectedCharacter?.id && Boolean(heroReference))
                const status = approvalLabel(character.approval_state)
                const isSelected = character.id === selectedCharacter?.id

                return (
                  <button
                    key={character.id}
                    type="button"
                    className={isSelected ? 'selected' : ''}
                    aria-pressed={isSelected}
                    onClick={() => selectCharacter(character.id)}
                  >
                    <Portrait name={character.name} role={character.role} />
                    <div className="character-card-copy">
                      <div>
                        <span className="eyebrow">{character.role ?? 'Role not specified'}</span>
                        <StatusPill status={status} />
                      </div>
                      <h3>{character.name}</h3>
                      <p>
                        {character.physical_description || 'Physical description not recorded.'}
                      </p>
                      <dl>
                        <div>
                          <dt>Scenes</dt>
                          <dd>{links.scenes.length}</dd>
                        </div>
                        <div>
                          <dt>Shots</dt>
                          <dd>{links.shots.length}</dd>
                        </div>
                        <div>
                          <dt>References</dt>
                          <dd>{refCount}</dd>
                        </div>
                      </dl>
                      <footer>
                        <span>
                          <Icon name="mic" size={13} />
                          {voiceName}
                        </span>
                        {!heroReady ? (
                          <em>
                            <Icon name="warning" size={12} />
                            Hero image needed
                          </em>
                        ) : null}
                      </footer>
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        {selectedCharacter ? (
          <aside className="entity-drawer" aria-label="Selected character drawer">
            <header>
              <div>
                <span className="eyebrow">SELECTED CHARACTER</span>
                <h2>{selectedCharacter.name}</h2>
              </div>
              <StatusPill status={approvalLabel(selectedCharacter.approval_state)} />
              <button
                type="button"
                className="icon-button"
                onClick={() => setEdit((value) => !value)}
                aria-label={edit ? 'Exit edit mode' : 'Edit character'}
                disabled={actionsBusy}
                title={busyReason ?? (edit ? 'Exit edit mode' : 'Enable identity field edits')}
              >
                <Icon name={edit ? 'check' : 'edit'} />
              </button>
            </header>

            <Portrait name={selectedCharacter.name} role={selectedCharacter.role} large />

            <div className="reference-strip">
              <button
                type="button"
                onClick={() => {
                  setDrawerTab('continuity')
                  setMessage('Use managed reference upload below to add a real reference asset.')
                }}
                disabled={actionsBusy}
                title={
                  busyReason ??
                  'Open Continuity tab to upload or link a managed reference asset (no generation).'
                }
              >
                <Icon name="plus" />
                <span>Add reference</span>
              </button>
              {displayReferences.slice(0, 4).map((reference, index) => (
                <button
                  key={reference.id}
                  type="button"
                  className={`ref ref-${index}`}
                  onClick={() =>
                    setMessage(
                      `Reference ${reference.label ?? reference.asset_id} · ${reference.reference_role}`,
                    )
                  }
                >
                  <span>
                    {index === 0 &&
                    (reference.approved ||
                      reference.reference_role === 'primary' ||
                      reference.reference_role === 'hero')
                      ? 'HERO'
                      : `REF ${index + 1}`}
                  </span>
                </button>
              ))}
            </div>

            <div className="tabs small-tabs" role="tablist" aria-label="Character drawer sections">
              <button
                type="button"
                className={drawerTab === 'identity' ? 'active' : ''}
                role="tab"
                aria-selected={drawerTab === 'identity'}
                onClick={() => setDrawerTab('identity')}
              >
                Identity
              </button>
              <button
                type="button"
                className={drawerTab === 'linked' ? 'active' : ''}
                role="tab"
                aria-selected={drawerTab === 'linked'}
                onClick={() => setDrawerTab('linked')}
              >
                Linked shots
              </button>
              <button
                type="button"
                className={drawerTab === 'continuity' ? 'active' : ''}
                role="tab"
                aria-selected={drawerTab === 'continuity'}
                onClick={() => setDrawerTab('continuity')}
              >
                Continuity
              </button>
            </div>

            {error ? <ErrorState detail={error} /> : null}

            {drawerTab === 'identity' ? (
              <form
                key={selectedCharacter.id}
                className="form-stack compact"
                onSubmit={(event) => void onSaveCharacter(event)}
              >
                {edit ? (
                  <>
                    <label>
                      Name
                      <input
                        name="name"
                        required
                        defaultValue={selectedCharacter.name}
                        disabled={actionsBusy}
                        title={busyReason ?? undefined}
                      />
                    </label>
                    <label>
                      Role
                      <input
                        name="role"
                        defaultValue={selectedCharacter.role ?? ''}
                        disabled={actionsBusy}
                        title={busyReason ?? undefined}
                      />
                    </label>
                  </>
                ) : null}

                <label>
                  Physical description
                  <textarea
                    name="physical_description"
                    defaultValue={selectedCharacter.physical_description ?? ''}
                    disabled={Boolean(fieldsDisabledReason)}
                    title={fieldsDisabledReason}
                  />
                </label>
                <div className="form-grid">
                  <label>
                    Age range
                    <input
                      name="age_range"
                      defaultValue={selectedCharacter.age_range ?? ''}
                      disabled={Boolean(fieldsDisabledReason)}
                      title={fieldsDisabledReason}
                    />
                  </label>
                  <label>
                    Approval
                    <select
                      value={approvalLabel(selectedCharacter.approval_state)}
                      disabled
                      title="Approval state is managed by server readiness and proposal apply — not editable on this page."
                    >
                      {(['Draft', 'Review', 'Approved', 'Blocked'] as const).map((status) => (
                        <option key={status}>{status}</option>
                      ))}
                    </select>
                  </label>
                </div>
                <label>
                  Personality
                  <input
                    name="personality"
                    defaultValue={selectedCharacter.personality ?? ''}
                    disabled={Boolean(fieldsDisabledReason)}
                    title={fieldsDisabledReason}
                  />
                </label>
                <label>
                  Speaking style
                  <input
                    name="speaking_style"
                    defaultValue={selectedCharacter.speaking_style ?? ''}
                    disabled={Boolean(fieldsDisabledReason)}
                    title={fieldsDisabledReason}
                  />
                </label>
                <label>
                  Wardrobe
                  <textarea
                    name="wardrobe"
                    defaultValue={selectedCharacter.wardrobe ?? ''}
                    disabled={Boolean(fieldsDisabledReason)}
                    title={fieldsDisabledReason}
                  />
                </label>
                <label>
                  Approved outfits
                  <div className="token-field">
                    {selectedOutfits.length ? (
                      selectedOutfits.map((outfit) => <span key={outfit}>{outfit}</span>)
                    ) : (
                      <span>None recorded</span>
                    )}
                  </div>
                </label>
                <label>
                  Visual consistency prompt
                  <textarea
                    name="consistency_prompt"
                    defaultValue={selectedCharacter.consistency_prompt ?? ''}
                    disabled={Boolean(fieldsDisabledReason)}
                    title={fieldsDisabledReason}
                  />
                </label>
                <label>
                  Negative identity prompt
                  <textarea
                    name="negative_identity_prompt"
                    defaultValue={selectedCharacter.negative_identity_prompt ?? ''}
                    disabled={Boolean(fieldsDisabledReason)}
                    title={fieldsDisabledReason}
                  />
                </label>
                <label>
                  Identity method
                  <input
                    name="identity_method"
                    defaultValue={selectedCharacter.identity_method ?? ''}
                    disabled={Boolean(fieldsDisabledReason)}
                    title={fieldsDisabledReason}
                  />
                </label>
                <label>
                  Voice assignment
                  <select
                    value={
                      selectedVoiceId ||
                      selectedCharacter.assigned_voice_profile_id ||
                      associatedVoices[0]?.id ||
                      ''
                    }
                    onChange={(event) => setSelectedVoiceId(event.target.value)}
                    disabled={Boolean(fieldsDisabledReason)}
                    title={fieldsDisabledReason}
                  >
                    <option value="">Unassigned</option>
                    {data.voices.map((voice) => (
                      <option key={voice.id} value={voice.id}>
                        {voice.name} · {voice.approval_state}
                      </option>
                    ))}
                  </select>
                </label>
                {edit ? (
                  <div className="inline-actions">
                    <Button
                      type="button"
                      onClick={() => void onAssignVoice()}
                      disabled={Boolean(assignVoiceReason)}
                      title={assignVoiceReason}
                    >
                      Assign voice
                    </Button>
                    <Button
                      type="submit"
                      variant="primary"
                      disabled={Boolean(saveReason)}
                      title={saveReason}
                    >
                      {saving ? 'Saving…' : 'Save character bible'}
                    </Button>
                    <Button
                      type="button"
                      disabled={Boolean(archiveReason)}
                      title={archiveReason}
                      onClick={() => void onArchiveCharacter()}
                    >
                      Archive character
                    </Button>
                  </div>
                ) : null}
              </form>
            ) : null}

            {drawerTab === 'linked' ? (
              <div className="form-stack compact">
                <ul className="kv-list">
                  <li>
                    <span>Scenes</span>
                    <strong>{linkedScenes.length}</strong>
                  </li>
                  <li>
                    <span>Shots</span>
                    <strong>{linkedShots.length}</strong>
                  </li>
                  <li>
                    <span>Approved hero</span>
                    <strong>{heroReference ? 'Ready' : 'Missing'}</strong>
                  </li>
                  <li>
                    <span>Canonical voice</span>
                    <strong>
                      {canonicalVoice?.name ??
                        associatedVoices[0]?.name ??
                        'Not assigned by an applied proposal'}
                    </strong>
                  </li>
                </ul>
                {linkedScenes.length ? (
                  <p className="form-hint">
                    Scenes: {linkedScenes.map((scene) => scene.title).join(', ')}
                  </p>
                ) : (
                  <p className="form-hint">No scenes currently link this character.</p>
                )}
                {linkedShots.length ? (
                  <p className="form-hint">
                    Shots: {linkedShots.map((shot) => shot.title).join(', ')}
                  </p>
                ) : (
                  <p className="form-hint">No shots currently link this character.</p>
                )}
                <h3>Voice assignment</h3>
                <p className="form-hint">
                  Associates a mutable voice profile via PATCH /voices/profiles/{'{id}'} with
                  character_id. Canonical assigned_voice_profile_id is set only by applied
                  proposals.
                </p>
                {associatedVoices.length ? (
                  <ul className="kv-list">
                    {associatedVoices.map((voice) => {
                      const unassignReason = firstReason(
                        busyReason,
                        voice.approval_state === 'approved' &&
                          'Approved voice profiles are immutable; create a replacement profile to change this association.',
                      )
                      return (
                        <li key={voice.id}>
                          <span>
                            {voice.name} · {voice.setup_mode}
                          </span>
                          <button
                            type="button"
                            className="ghost-button touch-target"
                            onClick={() => void onUnassignVoice(voice.id)}
                            disabled={Boolean(unassignReason)}
                            title={unassignReason}
                          >
                            {voice.approval_state === 'approved'
                              ? 'Approved assignment'
                              : 'Unassign'}
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                ) : (
                  <p className="form-hint">
                    No voice profile is associated through the voice-profile API.
                  </p>
                )}
                <label>
                  Voice profile
                  <select
                    value={selectedVoiceId}
                    onChange={(event) => setSelectedVoiceId(event.target.value)}
                    disabled={actionsBusy}
                    title={busyReason ?? undefined}
                  >
                    <option value="">Choose a mutable profile</option>
                    {data.voices.map((voice) => (
                      <option key={voice.id} value={voice.id}>
                        {voice.name} · {voice.approval_state}
                      </option>
                    ))}
                  </select>
                </label>
                <Button
                  type="button"
                  onClick={() => void onAssignVoice()}
                  disabled={Boolean(assignVoiceReason)}
                  title={assignVoiceReason}
                >
                  Assign voice profile
                </Button>
              </div>
            ) : null}

            {drawerTab === 'continuity' ? (
              <div className="form-stack compact">
                <h3>Readiness</h3>
                {characterReadiness.length ? (
                  characterReadiness.map((reason) => (
                    <p className="notice warning" key={`${reason.code}-${reason.entity_id}`}>
                      {reason.message}
                    </p>
                  ))
                ) : (
                  <p className="notice success">
                    No character-specific blocking reason is currently reported.
                  </p>
                )}

                <div className="panel-title" style={{ marginBottom: 8 }}>
                  <div>
                    <h3>Managed reference assets</h3>
                    <p className="form-hint">
                      Upload, link, list, unlink, and approve a hero reference when the link is
                      created. No mock store substitution.
                    </p>
                  </div>
                  <button
                    type="button"
                    className="ghost-button touch-target"
                    onClick={() => void loadReferences()}
                    disabled={loadingReferences || actionsBusy}
                    title={
                      firstReason(
                        loadingReferences && 'Reference list is already loading.',
                        busyReason,
                      ) ?? undefined
                    }
                  >
                    Refresh
                  </button>
                </div>
                {loadingReferences ? <LoadingState title="Loading character references…" /> : null}
                {!referenceApiAvailable && !loadingReferences ? (
                  <UnavailableState
                    title="Character-reference API unavailable"
                    detail="No file or link operation was substituted with a mock store."
                  />
                ) : null}
                {references.length ? (
                  <div className="card-grid">
                    {references.map((reference) => {
                      const unlinkReason = firstReason(
                        busyReason,
                        !referenceApiAvailable &&
                          'Character-reference unlink API is unavailable; the link was not changed.',
                      )
                      return (
                        <article key={reference.id}>
                          {reference.asset?.mime_type?.startsWith('image/') ? (
                            <img
                              src={planningAssetContentUrl(reference.asset_id)}
                              alt={`${selectedCharacter.name} ${reference.reference_role} reference`}
                              width="200"
                              height="140"
                              loading="lazy"
                            />
                          ) : null}
                          <b>{reference.asset?.original_filename ?? reference.asset_id}</b>
                          <small>
                            {reference.reference_role} ·{' '}
                            {reference.approved ? 'approved' : 'not approved'}
                          </small>
                          <p>
                            {reference.asset?.approval_state ?? 'Asset record unavailable'} ·{' '}
                            {reference.asset?.mime_type ?? 'Unknown type'}
                          </p>
                          <button
                            type="button"
                            className="secondary-button touch-target"
                            onClick={() => void onUnlinkReference(reference)}
                            disabled={Boolean(unlinkReason)}
                            title={unlinkReason}
                          >
                            Unlink
                          </button>
                          {!reference.approved ? (
                            <button
                              type="button"
                              className="ghost-button touch-target"
                              disabled
                              title={APPROVE_EXISTING_LINK_REASON}
                            >
                              Approve existing link — unavailable
                            </button>
                          ) : null}
                        </article>
                      )
                    })}
                  </div>
                ) : !loadingReferences && referenceApiAvailable ? (
                  <EmptyState
                    title="No linked references"
                    detail="Upload or select a managed asset, then create a character link."
                  />
                ) : null}

                <form
                  className="form-stack compact"
                  onSubmit={(event) => void onUploadReference(event)}
                >
                  <label>
                    Reference image
                    <input
                      key={fileInputKey}
                      type="file"
                      accept="image/*"
                      onChange={(event) => setReferenceFile(event.target.files?.[0] ?? null)}
                      disabled={actionsBusy || !referenceApiAvailable}
                      title={
                        firstReason(
                          busyReason,
                          !referenceApiAvailable && 'Character-reference upload API is unavailable.',
                        ) ?? undefined
                      }
                    />
                  </label>
                  <Button type="submit" disabled={Boolean(uploadReason)} title={uploadReason}>
                    {saving ? 'Working…' : 'Upload managed reference'}
                  </Button>
                </form>

                <form
                  className="form-stack compact"
                  onSubmit={(event) => void onLinkReference(event)}
                >
                  <label>
                    Managed asset
                    <select
                      value={selectedAssetId}
                      onChange={(event) => setSelectedAssetId(event.target.value)}
                      disabled={actionsBusy || !assets.length || !referenceApiAvailable}
                      title={
                        firstReason(
                          busyReason,
                          !referenceApiAvailable && 'Character-reference link API is unavailable.',
                          !assets.length &&
                            'Upload a managed reference asset before linking it to this character.',
                        ) ?? undefined
                      }
                    >
                      {!assets.length ? (
                        <option value="">No managed reference assets</option>
                      ) : null}
                      {assets.map((asset) => (
                        <option key={asset.id} value={asset.id}>
                          {asset.original_filename ?? asset.id} · {asset.approval_state}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Reference role
                    <select
                      value={referenceRole}
                      onChange={(event) =>
                        setReferenceRole(event.target.value as (typeof REFERENCE_ROLES)[number])
                      }
                      disabled={actionsBusy || approveHero}
                      title={
                        firstReason(
                          busyReason,
                          approveHero &&
                            'Role is forced to primary while “Approve as primary hero reference” is checked.',
                        ) ?? undefined
                      }
                    >
                      {REFERENCE_ROLES.map((item) => (
                        <option key={item} value={item}>
                          {item}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="checkbox-row">
                    <input
                      type="checkbox"
                      checked={approveHero}
                      onChange={(event) => setApproveHero(event.target.checked)}
                      disabled={actionsBusy || !referenceApiAvailable}
                      title={
                        firstReason(
                          busyReason,
                          !referenceApiAvailable && 'Character-reference link API is unavailable.',
                        ) ?? undefined
                      }
                    />
                    Approve as primary hero reference
                  </label>
                  <Button
                    type="submit"
                    variant="primary"
                    disabled={Boolean(linkReason)}
                    title={linkReason}
                  >
                    Link reference
                  </Button>
                </form>
                <Button type="button" disabled title={GENERATION_DISABLED_REASON}>
                  Generate reference image — disabled
                </Button>
                <p className="form-hint">{GENERATION_DISABLED_REASON}</p>
              </div>
            ) : null}
          </aside>
        ) : null}
      </div>
    </div>
  )
}
