import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { api, type PlanningMediaAsset } from '../../api/client'
import { useStudio } from '../StudioState'
import { ManagedAssetImage } from '../components/ManagedAssetImage'
import { EmptyState, ErrorState, LoadingState, UnavailableState } from '../components/StateBlocks'

const GENERATION_DISABLED_REASON =
  'Image generation is disabled in Phase 1 planning; no render or ComfyUI submission endpoint is exposed.'

type RequirementFilter = 'all' | 'required' | 'missing' | 'assigned'

function formatBytes(value: number | null): string {
  if (value == null) return 'Unknown size'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

function errorText(error: unknown): string {
  return error instanceof Error && error.message
    ? error.message
    : 'Failed to load managed starting-image assets.'
}

export function ImagesPage() {
  const { data, readiness, busy, saveShot, setMessage } = useStudio()
  const [items, setItems] = useState<PlanningMediaAsset[] | null>(null)
  const [artDirectionItems, setArtDirectionItems] = useState<PlanningMediaAsset[]>([])
  const [available, setAvailable] = useState(true)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [fileInputKey, setFileInputKey] = useState(0)
  const [saving, setSaving] = useState(false)
  const [approvalSaving, setApprovalSaving] = useState(false)
  const [selectedShotId, setSelectedShotId] = useState('')
  const [assetDraft, setAssetDraft] = useState<{ shotId: string; assetId: string } | null>(null)
  const [requirementFilter, setRequirementFilter] = useState<RequirementFilter>('all')
  const [approvalFilter, setApprovalFilter] = useState('all')
  const [search, setSearch] = useState('')

  const shotRows = useMemo(
    () =>
      data?.chapters.flatMap((chapter) =>
        chapter.scenes.flatMap((scene) =>
          scene.shots.map((shot) => ({ chapter, scene, shot })),
        ),
      ) ?? [],
    [data],
  )
  const selectedRow =
    shotRows.find((row) => row.shot.id === selectedShotId) ?? shotRows[0] ?? null

  const load = useCallback(async () => {
    if (!data) return
    setLoading(true)
    setError(null)
    try {
      const [startingImageResult, artDirectionResult] = await Promise.all([
        api.listStartingImageAssets(data.story.project_id),
        api.listArtDirectionReferenceAssets(data.story.project_id),
      ])
      if (startingImageResult == null || artDirectionResult == null) {
        setAvailable(false)
        setItems(null)
        setArtDirectionItems([])
      } else {
        setAvailable(true)
        setItems(startingImageResult.items)
        setArtDirectionItems(artDirectionResult.items)
      }
    } catch (err) {
      setError(errorText(err))
    } finally {
      setLoading(false)
    }
  }, [data])

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0)
    return () => window.clearTimeout(timer)
  }, [load])

  if (!data) return null

  const assetsById = new Map(items?.map((asset) => [asset.id, asset]) ?? [])
  const sceneRows = data.chapters.flatMap((chapter) =>
    chapter.scenes.map((scene) => ({ chapter, scene })),
  )
  const sceneById = new Map(sceneRows.map((row) => [row.scene.id, row]))
  const artDirectionRows = artDirectionItems
    .map((asset) => {
      const client = asset.metadata_json.client as Record<string, unknown> | undefined
      const sceneId = typeof client?.scene_id === 'string' ? client.scene_id : null
      const sceneNumber = typeof client?.scene_number === 'number' ? client.scene_number : null
      const sceneRow =
        (sceneId ? sceneById.get(sceneId) : null) ??
        (sceneNumber ? sceneRows[sceneNumber - 1] : null) ??
        null
      return { asset, sceneRow, sceneNumber }
    })
    .sort(
      (left, right) =>
        (left.sceneNumber ?? Number.MAX_SAFE_INTEGER) -
        (right.sceneNumber ?? Number.MAX_SAFE_INTEGER),
    )
  const filteredRows = shotRows.filter(({ shot, scene, chapter }) => {
    const matchesRequirement =
      requirementFilter === 'all' ||
      (requirementFilter === 'required' && shot.starting_image_required) ||
      (requirementFilter === 'missing' && shot.starting_image_required && !shot.starting_image_asset_id) ||
      (requirementFilter === 'assigned' && Boolean(shot.starting_image_asset_id))
    const assignedAsset = shot.starting_image_asset_id
      ? assetsById.get(shot.starting_image_asset_id)
      : null
    const matchesApproval =
      approvalFilter === 'all' || assignedAsset?.approval_state === approvalFilter
    const normalizedSearch = search.trim().toLowerCase()
    const matchesSearch =
      !normalizedSearch ||
      `${chapter.title} ${scene.title} ${shot.title}`.toLowerCase().includes(normalizedSearch)
    return matchesRequirement && matchesApproval && matchesSearch
  })
  const selectedShot = selectedRow?.shot ?? null
  const selectedAssetId =
    selectedShot && assetDraft?.shotId === selectedShot.id
      ? assetDraft.assetId
      : (selectedShot?.starting_image_asset_id ?? '')
  const selectedAssignedAsset = selectedShot?.starting_image_asset_id
    ? assetsById.get(selectedShot.starting_image_asset_id) ?? null
    : null
  const selectedReadiness = selectedShot
    ? (readiness?.reasons.filter((reason) => reason.entity_id === selectedShot.id) ?? [])
    : []

  const onUpload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!file) return
    setSaving(true)
    setError(null)
    try {
      const result = await api.uploadStartingImageAsset(data.story.project_id, file)
      if (!result) {
        setAvailable(false)
        setMessage('Managed asset API is unavailable on this backend. No file was stored.')
        return
      }
      setFile(null)
      setFileInputKey((value) => value + 1)
      if (selectedShot) setAssetDraft({ shotId: selectedShot.id, assetId: result.asset.id })
      setMessage(
        result.duplicate_of_existing
          ? `Reused existing managed asset ${result.asset.id}; no duplicate file was created.`
          : `Uploaded managed starting-image asset ${result.asset.id}. No image generation was started.`,
      )
      await load()
    } catch (err) {
      const text = errorText(err)
      setError(text)
      setMessage(text)
    } finally {
      setSaving(false)
    }
  }

  const onAssign = async () => {
    if (!selectedShot) return
    setSaving(true)
    try {
      await saveShot(selectedShot.id, {
        order_index: selectedShot.order_index,
        title: selectedShot.title,
        duration_sec: selectedShot.duration_sec,
        duration_override_reason: selectedShot.duration_override_reason,
        story_purpose: selectedShot.story_purpose,
        visual_description: selectedShot.visual_description,
        location: selectedShot.location,
        continuity_source_type: selectedShot.continuity_source_type,
        continuity_source_shot_id: selectedShot.continuity_source_shot_id,
        starting_image_required: selectedShot.starting_image_required,
        starting_image_asset_id: selectedAssetId || null,
      })
      setAssetDraft(null)
    } finally {
      setSaving(false)
    }
  }

  const onApprove = async () => {
    if (!selectedShot || !selectedAssignedAsset) return
    if (selectedAssignedAsset.kind !== 'starting_image') {
      const text = 'Only a managed starting-image asset can be approved from this page.'
      setError(text)
      setMessage(text)
      return
    }
    if (selectedAssignedAsset.approval_state === 'archived') {
      const text = 'Archived starting-image assets cannot be approved. Refresh and select an active candidate.'
      setError(text)
      setMessage(text)
      return
    }

    setApprovalSaving(true)
    setError(null)
    try {
      const approved = await api.updateStartingImageApproval(selectedAssignedAsset.id, {
        approval_state: 'approved',
        expected_approval_state: selectedAssignedAsset.approval_state,
        reason: `Explicit approval from Starting Images for shot ${selectedShot.id}.`,
      })
      setMessage(`Approved managed starting-image candidate ${approved.original_filename ?? approved.id}. No generation was started.`)
      await load()
    } catch (err) {
      const text = errorText(err)
      setError(text)
      setMessage(text)
    } finally {
      setApprovalSaving(false)
    }
  }

  return (
    <div className="split-2">
      <section className="panel">
        <div className="panel-title">
          <div>
            <h2>Starting-image plan</h2>
            <p>Every shot shows its persisted requirement, assignment, prompt, continuity, recommendation, and readiness state.</p>
          </div>
          <button type="button" className="ghost-button touch-target" onClick={() => void load()} disabled={loading || busy}>Refresh assets</button>
        </div>

        <section className="art-direction-references" aria-labelledby="art-direction-heading">
          <div className="panel-title">
            <div>
              <h3 id="art-direction-heading">Scene art-direction references</h3>
              <p>Planning-only multi-panel boards. These are never shot starting images.</p>
            </div>
            <span className="status-pill">{artDirectionRows.length} references</span>
          </div>
          {artDirectionRows.length ? (
            <div className="card-grid art-direction-grid">
              {artDirectionRows.map(({ asset, sceneRow, sceneNumber }) => (
                <article key={asset.id}>
                  <ManagedAssetImage
                    assetId={asset.mime_type?.startsWith('image/') ? asset.id : null}
                    alt={`Art-direction storyboard reference for ${sceneRow?.scene.title ?? `scene ${sceneNumber ?? 'unknown'}`}`}
                    fit="contain"
                    className="art-direction-image"
                    fallback={<span>Art-direction reference record unavailable</span>}
                    errorLabel="Reference bytes unavailable"
                    loading="eager"
                  />
                  <b>{sceneRow?.scene.title ?? `Scene ${sceneNumber ?? 'unmapped'}`}</b>
                  <small>{sceneRow?.chapter.title ?? 'Scene mapping unavailable'}</small>
                  <p>Planning reference · not an approved frame zero</p>
                </article>
              ))}
            </div>
          ) : !loading ? (
            <EmptyState
              title="No scene art-direction references"
              detail="No planning-only storyboard boards are linked to this project."
            />
          ) : null}
        </section>

        <div className="filters-row">
          <label>
            Requirement
            <select value={requirementFilter} onChange={(event) => setRequirementFilter(event.target.value as RequirementFilter)}>
              <option value="all">All shots</option>
              <option value="required">Image required</option>
              <option value="missing">Required and missing</option>
              <option value="assigned">Asset assigned</option>
            </select>
          </label>
          <label>
            Assigned asset approval
            <select value={approvalFilter} onChange={(event) => setApprovalFilter(event.target.value)}>
              <option value="all">Any state</option>
              <option value="draft">Draft</option>
              <option value="in_review">In review</option>
              <option value="approved">Approved</option>
              <option value="blocked">Blocked</option>
            </select>
          </label>
          <label>Search<input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Shot, scene, or chapter" /></label>
        </div>

        {loading ? <LoadingState title="Loading managed starting images…" /> : null}
        {error ? <ErrorState detail={error} onRetry={() => void load()} /> : null}
        {!available && !loading ? <UnavailableState title="Managed assets API unavailable" detail="No local path, candidate, or generated-image claim is substituted." /> : null}

        {!filteredRows.length && !loading ? <EmptyState title="No shots match these filters" detail="Change a filter or add shots to the storyboard." /> : null}
        {filteredRows.length ? (
          <div className="card-grid">
            {filteredRows.map(({ chapter, scene, shot }) => {
              const asset = shot.starting_image_asset_id
                ? assetsById.get(shot.starting_image_asset_id) ?? null
                : null
              const promptReady = Boolean(shot.prompt_positive || shot.prompt_video)
              const reasons = readiness?.reasons.filter((reason) => reason.entity_id === shot.id) ?? []
              return (
                <article key={shot.id}>
                  <ManagedAssetImage
                    assetId={asset?.mime_type?.startsWith('image/') ? asset.id : null}
                    alt={`Starting image for ${shot.title}`}
                    fit="contain"
                    className="shot-starting-image"
                    fallback={
                      <span>
                        {shot.starting_image_asset_id
                          ? 'Assigned image record unavailable'
                          : 'No starting image assigned'}
                      </span>
                    }
                    errorLabel="The assigned managed image could not be loaded."
                  />
                  <b>{shot.title}</b>
                  <small>{chapter.title} · {scene.title}</small>
                  <ul className="kv-list">
                    <li><span>Requirement</span><strong>{shot.starting_image_required ? 'Required' : 'Optional'}</strong></li>
                    <li><span>Candidate</span><strong>{asset?.original_filename ?? (shot.starting_image_asset_id ? 'Assigned asset not in active list' : 'Missing')}</strong></li>
                    <li><span>Asset approval</span><strong>{asset?.approval_state ?? 'Not assigned'}</strong></li>
                    <li><span>Prompt</span><strong>{promptReady ? shot.prompt_approval_state ?? 'draft' : 'Missing'}</strong></li>
                    <li><span>Continuity</span><strong>{shot.continuity_source_type || 'none'}</strong></li>
                    <li><span>Recommendations</span><strong>{shot.recommendations?.length ?? 0}</strong></li>
                    <li><span>Readiness</span><strong>{reasons.length ? `${reasons.length} issue(s)` : 'No shot-specific blocker'}</strong></li>
                  </ul>
                  <button type="button" className={selectedShot?.id === shot.id ? 'primary-button touch-target' : 'secondary-button touch-target'} onClick={() => setSelectedShotId(shot.id)}>{selectedShot?.id === shot.id ? 'Selected' : 'Review shot'}</button>
                </article>
              )
            })}
          </div>
        ) : null}
      </section>

      <div className="stack-form">
        {selectedShot ? (
          <section className="panel stack-form">
            <div className="panel-title"><div><h2>{selectedShot.title}</h2><p>{selectedRow?.chapter.title} · {selectedRow?.scene.title} · {selectedShot.duration_sec}s</p></div></div>
            <ManagedAssetImage
              assetId={
                selectedAssignedAsset?.mime_type?.startsWith('image/')
                  ? selectedAssignedAsset.id
                  : null
              }
              alt={`Selected starting image for ${selectedShot.title}`}
              fit="contain"
              className="selected-shot-review-image"
              fallback={
                <span>
                  {selectedShot.starting_image_asset_id
                    ? 'Assigned image record unavailable'
                    : 'No starting image assigned'}
                </span>
              }
              errorLabel="The selected managed image could not be loaded."
            />
            <ul className="kv-list">
              <li><span>Starting image</span><strong>{selectedShot.starting_image_required ? 'Required' : 'Optional'}</strong></li>
              <li><span>Current asset</span><strong>{selectedAssignedAsset?.original_filename ?? selectedShot.starting_image_asset_id ?? 'None'}</strong></li>
              <li><span>Current approval</span><strong>{selectedAssignedAsset?.approval_state ?? 'Not assigned'}</strong></li>
              <li><span>Continuity source</span><strong>{selectedShot.continuity_source_type || 'none'}</strong></li>
              <li><span>Source shot</span><strong>{selectedShot.continuity_source_shot_id ?? 'None'}</strong></li>
            </ul>
            <label>
              Candidate asset
              <select value={selectedAssetId} onChange={(event) => setAssetDraft({ shotId: selectedShot.id, assetId: event.target.value })} disabled={approvalSaving || saving || busy || !available}>
                <option value="">No starting image</option>
                {items?.map((asset) => <option key={asset.id} value={asset.id}>{asset.original_filename ?? asset.id} · {asset.approval_state}</option>)}
              </select>
            </label>
            <button type="button" className="primary-button touch-target" onClick={() => void onAssign()} disabled={approvalSaving || saving || busy || selectedAssetId === (selectedShot.starting_image_asset_id ?? '')}>{saving ? 'Saving…' : selectedAssetId ? 'Assign candidate' : 'Clear assignment'}</button>
            {selectedAssignedAsset && selectedAssignedAsset.approval_state !== 'approved' ? (
              <button type="button" className="secondary-button touch-target" onClick={() => void onApprove()} disabled={approvalSaving || saving || busy}>{approvalSaving ? 'Approving…' : 'Approve candidate'}</button>
            ) : null}

            <h3>Prompt package</h3>
            <p>{selectedShot.prompt_positive || 'No image prompt recorded.'}</p>
            {selectedShot.prompt_video ? <p><strong>Video:</strong> {selectedShot.prompt_video}</p> : null}
            {selectedShot.prompt_negative ? <p><strong>Negative:</strong> {selectedShot.prompt_negative}</p> : null}
            <p><strong>Continuity instructions:</strong> {selectedShot.prompt_continuity_instructions || 'None recorded.'}</p>
            <p><strong>Style lock:</strong> {selectedShot.prompt_style_lock || 'None recorded.'}</p>

            <h3>Model / workflow recommendations</h3>
            {selectedShot.recommendations?.length ? (
              <ul className="kv-list">
                {selectedShot.recommendations.map((recommendation) => (
                  <li key={recommendation.id}>
                    <span>{recommendation.recommendation_type} · {recommendation.rationale ?? 'No rationale'}</span>
                    <strong>{recommendation.availability_status} / {recommendation.benchmark_status}</strong>
                  </li>
                ))}
              </ul>
            ) : <p className="form-hint">No model or workflow recommendation is persisted for this shot.</p>}

            <h3>Readiness</h3>
            {selectedReadiness.length ? selectedReadiness.map((reason) => <p className="notice warning" key={`${reason.code}-${reason.entity_id}`}>{reason.message}</p>) : <p className="notice success">No shot-specific blocking reason is currently reported.</p>}

            <button type="button" className="primary-button touch-target" disabled title={GENERATION_DISABLED_REASON}>Generate candidate — disabled</button>
            <p className="form-hint">{GENERATION_DISABLED_REASON}</p>
          </section>
        ) : null}

        <form className="panel stack-form" onSubmit={(event) => void onUpload(event)}>
          <div className="panel-title"><div><h2>Upload existing candidate</h2><p>Creates a server-managed starting-image asset from explicit user bytes.</p></div></div>
          <label>Starting-image file<input key={fileInputKey} type="file" accept="image/*" required onChange={(event) => setFile(event.target.files?.[0] ?? null)} disabled={saving || busy} /></label>
          {file ? <p className="form-hint">{file.name} · {formatBytes(file.size)}</p> : null}
          <button type="submit" className="secondary-button touch-target" disabled={saving || busy || !file}>{saving ? 'Uploading…' : 'Upload managed candidate'}</button>
          <p className="form-hint">Upload never starts generation, rendering, installation, or queue submission.</p>
        </form>

        {items?.length ? (
          <section className="panel">
            <h2>Candidate inventory</h2>
            <div className="card-grid candidate-comparison-grid">
              {items.map((asset) => (
                <article key={asset.id}>
                  <ManagedAssetImage
                    assetId={asset.mime_type?.startsWith('image/') ? asset.id : null}
                    alt={`Starting-image candidate ${asset.original_filename ?? asset.id}`}
                    fit="contain"
                    className="candidate-comparison-image"
                    fallback={<span>Candidate image unavailable</span>}
                    errorLabel="The candidate content request failed."
                  />
                  <b>{asset.original_filename ?? asset.id}</b>
                  <small>{formatBytes(asset.size_bytes)} · {asset.approval_state}</small>
                </article>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </div>
  )
}
