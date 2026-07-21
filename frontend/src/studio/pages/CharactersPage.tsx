import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  api,
  type CharacterReferenceLink,
  type PlanningMediaAsset,
} from '../../api/client'
import { useStudio } from '../StudioState'
import { selectCharacterHeroReference } from '../characterReferences'
import { ManagedAssetImage } from '../components/ManagedAssetImage'
import { characterPortraitUrl } from '../mediaUrls'
import { EmptyState, ErrorState, LoadingState, UnavailableState } from '../components/StateBlocks'
import { initials } from '../utils'

const REFERENCE_ROLES = ['primary', 'alternate', 'expression', 'costume', 'detail'] as const

/** Gold Sites status filter chips (All + ApprovalState surface labels). */
const STATUS_FILTERS = ['All', 'Draft', 'Review', 'Approved', 'Blocked'] as const
type StatusFilter = (typeof STATUS_FILTERS)[number]

function selectDisplayReference(
  links: CharacterReferenceLink[],
): CharacterReferenceLink | null {
  return selectCharacterHeroReference(
    links.filter(
      (reference) =>
        reference.asset?.archived_at == null &&
        reference.asset?.mime_type?.startsWith('image/'),
    ),
  )
}

function errorText(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback
}

/** Map backend approval_state → Gold status-pill data-status token. */
function statusPillToken(approvalState: string | null | undefined): string {
  const raw = (approvalState ?? 'draft').toLowerCase().replace(/\s+/g, '_')
  if (raw === 'in_review' || raw === 'review') return 'review'
  return raw
}

function statusPillLabel(approvalState: string | null | undefined): string {
  const token = statusPillToken(approvalState)
  if (token === 'review') return 'Review'
  if (token === 'approved') return 'Approved'
  if (token === 'blocked') return 'Blocked'
  return 'Draft'
}

function matchesStatusFilter(approvalState: string | null | undefined, filter: StatusFilter): boolean {
  if (filter === 'All') return true
  return statusPillLabel(approvalState) === filter
}

function hasApprovedHeroReference(links: CharacterReferenceLink[]): boolean {
  return links.some(
    (reference) =>
      reference.approved &&
      (reference.reference_role === 'primary' || reference.reference_role === 'hero') &&
      reference.asset?.archived_at == null,
  )
}

export function CharactersPage() {
  const { data, readiness, reload, setMessage, addCharacter, busy } = useStudio()
  const [selectedId, setSelectedId] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('All')
  const [newName, setNewName] = useState('')
  const [newRole, setNewRole] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [assets, setAssets] = useState<PlanningMediaAsset[]>([])
  const [referencesByCharacter, setReferencesByCharacter] = useState<
    Record<string, CharacterReferenceLink[]>
  >({})
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

  const selectedCharacter =
    data?.characters.find((character) => character.id === selectedId) ?? data?.characters[0] ?? null
  const references = selectedCharacter
    ? (referencesByCharacter[selectedCharacter.id] ?? [])
    : []

  const loadReferences = useCallback(async () => {
    if (!data) {
      setAssets([])
      setReferencesByCharacter({})
      return
    }
    setLoadingReferences(true)
    setError(null)
    try {
      const [assetResult, ...linkResults] = await Promise.all([
        api.listCharacterReferenceAssets(data.story.project_id),
        ...data.characters.map((character) => api.listCharacterReferences(character.id)),
      ])
      if (assetResult == null || linkResults.some((result) => result == null)) {
        setReferenceApiAvailable(false)
        setAssets([])
        setReferencesByCharacter({})
        return
      }
      setReferenceApiAvailable(true)
      setAssets(assetResult.items)
      setReferencesByCharacter(
        Object.fromEntries(
          data.characters.map((character, index) => [character.id, linkResults[index] ?? []]),
        ),
      )
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
  }, [data])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadReferences(), 0)
    return () => window.clearTimeout(timer)
  }, [loadReferences])

  const characters = useMemo(() => data?.characters ?? [], [data?.characters])
  const filteredCharacters = useMemo(
    () => characters.filter((character) => matchesStatusFilter(character.approval_state, statusFilter)),
    [characters, statusFilter],
  )
  const filterCounts = useMemo(() => {
    const counts: Record<StatusFilter, number> = {
      All: characters.length,
      Draft: 0,
      Review: 0,
      Approved: 0,
      Blocked: 0,
    }
    for (const character of characters) {
      const label = statusPillLabel(character.approval_state) as Exclude<StatusFilter, 'All'>
      if (label in counts) counts[label] += 1
    }
    return counts
  }, [characters])

  if (!data) return null

  const linkedScenes = selectedCharacter
    ? data.chapters.flatMap((chapter) =>
        chapter.scenes.filter((scene) =>
          scene.shots.some((shot) =>
            shot.characters?.some((link) => link.character_id === selectedCharacter.id),
          ),
        ),
      )
    : []
  const linkedShots = selectedCharacter
    ? linkedScenes.flatMap((scene) =>
        scene.shots.filter((shot) =>
          shot.characters?.some((link) => link.character_id === selectedCharacter.id),
        ),
      )
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
  const heroReference = selectDisplayReference(references)
  const approvedHeroReference =
    heroReference?.approved &&
    (heroReference.reference_role === 'primary' || heroReference.reference_role === 'hero')
      ? heroReference
      : null
  const selectedDisplayReference = selectDisplayReference(references)

  const onAddCharacter = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!newName.trim()) return
    await addCharacter({
      name: newName.trim(),
      role: newRole.trim() || undefined,
      physical_description: newDescription.trim() || undefined,
    })
    setNewName('')
    setNewRole('')
    setNewDescription('')
  }

  const onSaveCharacter = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!selectedCharacter) return
    const form = new FormData(event.currentTarget)
    const nextName = String(form.get('name') ?? '').trim()
    if (!nextName) return
    setSaving(true)
    setError(null)
    try {
      const result = await api.updateCharacter(selectedCharacter.id, {
        name: nextName,
        role: String(form.get('role') ?? '').trim() || null,
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
    if (!selectedCharacter) return
    if (!window.confirm(`Archive character “${selectedCharacter.name}”?`)) return
    setSaving(true)
    setError(null)
    try {
      const result = await api.deleteCharacter(
        selectedCharacter.id,
        'Archived from character profile.',
      )
      if (result === null) {
        setMessage('Character archive API is unavailable; no changes were persisted.')
        return
      }
      await reload()
      setSelectedId('')
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
    if (!referenceFile) return
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
    if (!selectedCharacter || !selectedAssetId) return
    setSaving(true)
    setError(null)
    try {
      const result = await api.linkCharacterReference(selectedCharacter.id, {
        asset_id: selectedAssetId,
        reference_role: approveHero ? 'primary' : referenceRole,
        approved: approveHero,
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
        approveHero
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
    if (!selectedCharacter || !selectedVoice) return
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

  return (
    <div className="character-layout">
      <div className="stack">
        <div className="segmented" role="tablist" aria-label="Filter characters by approval state">
          {STATUS_FILTERS.map((filter) => (
            <button
              key={filter}
              type="button"
              role="tab"
              aria-selected={statusFilter === filter}
              className={statusFilter === filter ? 'active' : undefined}
              onClick={() => setStatusFilter(filter)}
            >
              {filter}
              <span>{filterCounts[filter]}</span>
            </button>
          ))}
        </div>

        {!data.characters.length ? (
          <EmptyState title="No characters yet" detail="Add a character to begin building a character profile." />
        ) : !filteredCharacters.length ? (
          <EmptyState
            title="No characters match"
            detail="Try another readiness filter."
            action={
              <button type="button" className="secondary-button touch-target" onClick={() => setStatusFilter('All')}>
                Clear filter
              </button>
            }
          />
        ) : (
          <div className="character-grid">
            {filteredCharacters.map((character) => {
              const characterRefs = referencesByCharacter[character.id] ?? []
              const displayReference = selectDisplayReference(characterRefs)
              const portraitUrl = characterPortraitUrl({
                name: character.name,
                assetId: displayReference?.asset_id,
                projectId: data.story.project_id,
                storyTitle: data.story.title,
              })
              const isSelected = character.id === selectedCharacter?.id
              const linkedShotList = data.chapters.flatMap((chapter) =>
                chapter.scenes.flatMap((scene) =>
                  scene.shots.filter((shot) =>
                    shot.characters?.some((link) => link.character_id === character.id),
                  ),
                ),
              )
              const linkedSceneCount = new Set(
                data.chapters.flatMap((chapter) =>
                  chapter.scenes
                    .filter((scene) =>
                      scene.shots.some((shot) =>
                        shot.characters?.some((link) => link.character_id === character.id),
                      ),
                    )
                    .map((scene) => scene.id),
                ),
              ).size
              const referenceCount = characterRefs.length
              const roleLabel = character.role?.trim() || 'Role not specified'
              const cardVoice =
                (character.assigned_voice_profile_id
                  ? data.voices.find((voice) => voice.id === character.assigned_voice_profile_id)
                  : null) ?? data.voices.find((voice) => voice.character_id === character.id)
              const heroReady = hasApprovedHeroReference(characterRefs)
              const pillToken = statusPillToken(character.approval_state)
              return (
                <button
                  type="button"
                  key={character.id}
                  className={isSelected ? 'selected' : undefined}
                  aria-pressed={isSelected}
                  aria-label={
                    isSelected
                      ? `Open character: ${character.name} (selected)`
                      : `Open character: ${character.name}`
                  }
                  onClick={() => {
                    setSelectedId(character.id)
                    setSelectedVoiceId('')
                  }}
                >
                  <div className={`portrait${portraitUrl ? ' has-image' : ''}`}>
                    {portraitUrl ? (
                      <img
                        src={portraitUrl}
                        alt=""
                        loading="lazy"
                        decoding="async"
                      />
                    ) : null}
                    <span>{initials(character.name)}</span>
                    <i>{roleLabel.split('·')[0].trim()}</i>
                  </div>
                  <div className="character-card-copy">
                    <div>
                      <span className="eyebrow">{roleLabel}</span>
                      <span className="status-pill" data-status={pillToken}>
                        {statusPillLabel(character.approval_state)}
                      </span>
                    </div>
                    <h3>{character.name}</h3>
                    <p>{character.physical_description || 'Physical description not recorded.'}</p>
                    <dl>
                      <div>
                        <dt>Scenes</dt>
                        <dd>{linkedSceneCount}</dd>
                      </div>
                      <div>
                        <dt>Shots</dt>
                        <dd>{linkedShotList.length}</dd>
                      </div>
                      <div>
                        <dt>References</dt>
                        <dd>{referenceCount}</dd>
                      </div>
                    </dl>
                    <footer>
                      <span>{cardVoice?.name ?? 'Voice missing'}</span>
                      {!heroReady ? <em>Hero image needed</em> : null}
                    </footer>
                  </div>
                </button>
              )
            })}
          </div>
        )}

        <form className="stack-form form-stack" onSubmit={(event) => void onAddCharacter(event)}>
          <h3>Add character</h3>
          <div className="form-grid">
            <label>
              Name
              <input required value={newName} onChange={(event) => setNewName(event.target.value)} disabled={busy || saving} />
            </label>
            <label>
              Role
              <input value={newRole} onChange={(event) => setNewRole(event.target.value)} disabled={busy || saving} />
            </label>
          </div>
          <label>
            Description
            <textarea value={newDescription} onChange={(event) => setNewDescription(event.target.value)} disabled={busy || saving} />
          </label>
          <button type="submit" className="primary-button touch-target" disabled={busy || saving || !newName.trim()}>
            Add character
          </button>
        </form>
      </div>

      {selectedCharacter ? (
        <aside className="entity-drawer stack-form">
          <header>
            <div>
              <span className="eyebrow">Selected character</span>
              <h2>{selectedCharacter.name}</h2>
            </div>
            <span className="status-pill" data-status={statusPillToken(selectedCharacter.approval_state)}>
              {statusPillLabel(selectedCharacter.approval_state)}
            </span>
          </header>
          {(() => {
            const selectedPortraitUrl = characterPortraitUrl({
              name: selectedCharacter.name,
              assetId: selectedDisplayReference?.asset_id,
              projectId: data.story.project_id,
              storyTitle: data.story.title,
            })
            const roleLabel = selectedCharacter.role?.trim() || 'Role not specified'
            return (
              <div className={`portrait large${selectedPortraitUrl ? ' has-image' : ''}`}>
                {selectedPortraitUrl ? (
                  <img
                    src={selectedPortraitUrl}
                    alt=""
                    loading="lazy"
                    decoding="async"
                  />
                ) : null}
                <span>{initials(selectedCharacter.name)}</span>
                <i>{roleLabel.split('·')[0].trim()}</i>
              </div>
            )
          })()}
          {error ? <ErrorState detail={error} /> : null}
          <form key={selectedCharacter.id} className="stack-form form-stack compact" onSubmit={(event) => void onSaveCharacter(event)}>
            <div className="form-grid">
              <label>
                Name
                <input name="name" required defaultValue={selectedCharacter.name} disabled={busy || saving} />
              </label>
              <label>
                Role
                <input name="role" defaultValue={selectedCharacter.role ?? ''} disabled={busy || saving} />
              </label>
            </div>
            <div className="form-grid">
              <label>
                Age range
                <input name="age_range" defaultValue={selectedCharacter.age_range ?? ''} disabled={busy || saving} />
              </label>
              <label>
                Speaking style
                <input name="speaking_style" defaultValue={selectedCharacter.speaking_style ?? ''} disabled={busy || saving} />
              </label>
            </div>
            <label>
              Physical description
              <textarea name="physical_description" defaultValue={selectedCharacter.physical_description ?? ''} disabled={busy || saving} />
            </label>
            <label>
              Personality
              <textarea name="personality" defaultValue={selectedCharacter.personality ?? ''} disabled={busy || saving} />
            </label>
            <label>
              Wardrobe
              <textarea name="wardrobe" defaultValue={selectedCharacter.wardrobe ?? ''} disabled={busy || saving} />
            </label>
            <label>
              Identity method
              <input name="identity_method" defaultValue={selectedCharacter.identity_method ?? ''} disabled={busy || saving} />
            </label>
            <label>
              Consistency prompt
              <textarea name="consistency_prompt" defaultValue={selectedCharacter.consistency_prompt ?? ''} disabled={busy || saving} />
            </label>
            <label>
              Negative identity prompt
              <textarea name="negative_identity_prompt" defaultValue={selectedCharacter.negative_identity_prompt ?? ''} disabled={busy || saving} />
            </label>
            <div className="inline-actions">
              <button type="submit" className="primary-button touch-target" disabled={busy || saving}>{saving ? 'Saving…' : 'Save character profile'}</button>
              <button
                type="button"
                className="ghost-button touch-target"
                disabled={busy || saving || selectedCharacter.approval_state === 'approved'}
                title={selectedCharacter.approval_state === 'approved' ? 'Approved characters cannot be archived while locked into production identity.' : undefined}
                onClick={() => void onArchiveCharacter()}
              >
                Archive character
              </button>
            </div>
          </form>

          <section>
            <div className="panel-title"><div><h2>Coverage and readiness</h2><p>Live links from the storyboard snapshot.</p></div></div>
            <ul className="kv-list">
              <li><span>Scenes</span><strong>{linkedScenes.length}</strong></li>
              <li><span>Shots</span><strong>{linkedShots.length}</strong></li>
              <li><span>Approved hero</span><strong>{approvedHeroReference ? 'Ready' : 'Missing'}</strong></li>
              <li><span>Canonical voice</span><strong>{canonicalVoice?.name ?? 'Not assigned by an applied proposal'}</strong></li>
            </ul>
            {linkedScenes.length ? <p className="form-hint">Scenes: {linkedScenes.map((scene) => scene.title).join(', ')}</p> : null}
            {linkedShots.length ? <p className="form-hint">Shots: {linkedShots.map((shot) => shot.title).join(', ')}</p> : null}
            {characterReadiness.length ? characterReadiness.map((reason) => <p className="notice warning" key={`${reason.code}-${reason.entity_id}`}>{reason.message}</p>) : <p className="notice success">No character-specific blocking reason is currently reported.</p>}
          </section>

          <section className="stack-form">
            <div className="panel-title"><div><h2>Voice assignment</h2><p>Associates a mutable voice profile through its persisted character_id.</p></div></div>
            {associatedVoices.length ? (
              <ul className="kv-list">
                {associatedVoices.map((voice) => (
                  <li key={voice.id}>
                    <span>{voice.name} · {voice.setup_mode}</span>
                    <button
                      type="button"
                      className="ghost-button touch-target"
                      onClick={() => void onUnassignVoice(voice.id)}
                      disabled={busy || saving || voice.approval_state === 'approved'}
                      title={voice.approval_state === 'approved' ? 'Approved voice profiles are immutable; create a replacement profile to change this association.' : undefined}
                    >
                      {voice.approval_state === 'approved' ? 'Approved assignment' : 'Unassign'}
                    </button>
                  </li>
                ))}
              </ul>
            ) : <p className="form-hint">No voice profile is associated through the voice-profile API.</p>}
            <label>
              Voice profile
              <select value={selectedVoiceId} onChange={(event) => setSelectedVoiceId(event.target.value)} disabled={busy || saving}>
                <option value="">Choose a mutable profile</option>
                {data.voices.map((voice) => <option key={voice.id} value={voice.id}>{voice.name} · {voice.approval_state}</option>)}
              </select>
            </label>
            <button
              type="button"
              className="secondary-button touch-target"
              onClick={() => void onAssignVoice()}
              disabled={busy || saving || !selectedVoice || selectedVoice.approval_state === 'approved'}
              title={selectedVoice?.approval_state === 'approved' ? 'Approved voice profiles are immutable and cannot be reassigned.' : undefined}
            >
              Assign voice profile
            </button>
            <p className="form-hint">Direct mutation of character.assigned_voice_profile_id is not exposed; that canonical field is applied through reviewed proposals.</p>
          </section>

          <section className="stack-form">
            <div className="panel-title">
              <div><h2>Managed reference assets</h2><p>Upload, link, list, unlink, and approve a hero reference when the link is created.</p></div>
              <button type="button" className="ghost-button touch-target" onClick={() => void loadReferences()} disabled={loadingReferences || saving}>Refresh</button>
            </div>
            {loadingReferences ? <LoadingState title="Loading character references…" /> : null}
            {!referenceApiAvailable && !loadingReferences ? <UnavailableState title="Character-reference API unavailable" detail="No file or link operation was substituted." /> : null}
            {references.length ? (
              <div className="card-grid reference-strip">
                {references.map((reference) => (
                  <article key={reference.id}>
                    <ManagedAssetImage
                      assetId={
                        reference.asset?.archived_at == null &&
                        reference.asset?.mime_type?.startsWith('image/')
                          ? reference.asset_id
                          : null
                      }
                      alt={`${selectedCharacter.name} ${reference.reference_role} reference`}
                      fit="contain"
                      className="reference-thumbnail"
                      fallback={<span>Reference image unavailable</span>}
                      errorLabel="The managed reference content request failed."
                    />
                    <b>{reference.asset?.original_filename ?? reference.asset_id}</b>
                    <small>{reference.reference_role} · {reference.approved ? 'approved' : 'not approved'}</small>
                    <p>{reference.asset?.approval_state ?? 'Asset record unavailable'} · {reference.asset?.mime_type ?? 'Unknown type'}</p>
                    <button type="button" className="secondary-button touch-target" onClick={() => void onUnlinkReference(reference)} disabled={saving || busy}>Unlink</button>
                    {!reference.approved ? (
                      <button type="button" className="ghost-button touch-target" disabled title="The backend exposes approval only while creating a reference link; unlink and relink it as an approved hero reference.">Approve existing link — unavailable</button>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : !loadingReferences && referenceApiAvailable ? <EmptyState title="No linked references" detail="Upload or select a managed asset, then create a character link." /> : null}

            <form className="stack-form" onSubmit={(event) => void onUploadReference(event)}>
              <label>Reference image<input key={fileInputKey} type="file" accept="image/*" onChange={(event) => setReferenceFile(event.target.files?.[0] ?? null)} disabled={saving || busy} /></label>
              <button type="submit" className="secondary-button touch-target" disabled={!referenceFile || saving || busy}>{saving ? 'Working…' : 'Upload managed reference'}</button>
            </form>

            <form className="stack-form" onSubmit={(event) => void onLinkReference(event)}>
              <label>
                Managed asset
                <select value={selectedAssetId} onChange={(event) => setSelectedAssetId(event.target.value)} disabled={saving || busy || !assets.length}>
                  {!assets.length ? <option value="">No managed reference assets</option> : null}
                  {assets.map((asset) => <option key={asset.id} value={asset.id}>{asset.original_filename ?? asset.id} · {asset.approval_state}</option>)}
                </select>
              </label>
              <label>Reference role<select value={referenceRole} onChange={(event) => setReferenceRole(event.target.value as (typeof REFERENCE_ROLES)[number])} disabled={saving || busy || approveHero}>{REFERENCE_ROLES.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
              <label className="checkbox-row"><input type="checkbox" checked={approveHero} onChange={(event) => setApproveHero(event.target.checked)} disabled={saving || busy} />Approve as primary hero reference</label>
              <button type="submit" className="primary-button touch-target" disabled={!selectedAssetId || saving || busy}>Link reference</button>
            </form>
            <button type="button" className="secondary-button touch-target" disabled title="Image generation is disabled in Phase 1 planning; this page only stores and links user-provided managed assets.">Generate reference image — disabled</button>
            <p className="form-hint">Image generation is disabled in Phase 1 planning; this page only stores and links user-provided managed assets.</p>
          </section>
        </aside>
      ) : null}
    </div>
  )
}
