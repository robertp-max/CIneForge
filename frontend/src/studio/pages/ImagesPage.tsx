import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { api, type PlanningMediaAsset } from '../../api/client'
import { useStudio } from '../StudioState'
import { startingFrameUrl, staticStoryboardUrl } from '../mediaUrls'
import { EmptyState, ErrorState, LoadingState, UnavailableState } from '../components/StateBlocks'

function MediaThumb({
  url,
  label,
  frameClass = '',
  tall = false,
}: {
  url: string | null
  label: string
  frameClass?: string
  tall?: boolean
}) {
  return (
    <div
      className={`image-placeholder ${frameClass}${url ? ' has-image' : ''}${tall ? ' review-canvas' : ''}`.trim()}
      style={
        tall
          ? { position: 'relative', minHeight: 280, aspectRatio: '16 / 9', overflow: 'hidden' }
          : { position: 'relative', height: 98, overflow: 'hidden' }
      }
    >
      {url ? (
        <img
          src={url}
          alt={label}
          loading="lazy"
          decoding="async"
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', display: 'block', zIndex: 1 }}
        />
      ) : null}
      <span style={{ position: 'absolute', zIndex: 2, left: 7, top: 7, fontSize: 10, background: 'rgba(0,0,0,.6)', padding: '3px 4px' }}>
        {label}
      </span>
    </div>
  )
}

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
  const { data, busy, saveShot, setMessage } = useStudio()
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
        setItems(startingImageResult.items.filter((asset) => asset.kind === 'starting_image'))
        setArtDirectionItems(
          artDirectionResult.items.filter((asset) => asset.kind === 'art_direction_reference'),
        )
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

  const selectedThumbUrl = selectedShot
    ? startingFrameUrl({
        title: selectedShot.title,
        filename: selectedAssignedAsset?.original_filename,
        assetId: selectedShot.starting_image_asset_id,
      })
    : null

  return (
    <div className="page">
      <div className="page-title">
        <div>
          <span className="eyebrow">STARTING-IMAGE PLAN</span>
          <h1>Starting images</h1>
          <p>Plan and approve the visual anchor for every generation-ready shot.</p>
        </div>
        <div className="page-actions">
          <button type="button" className="btn secondary" onClick={() => void load()} disabled={loading || busy}>
            Refresh assets
          </button>
        </div>
      </div>

      {artDirectionRows.length ? (
        <section className="panel" aria-labelledby="art-direction-heading" style={{ marginBottom: 12 }}>
          <div className="panel-title">
            <div>
              <h3 id="art-direction-heading">Scene art-direction references</h3>
              <p>Planning-only multi-panel boards. These are never shot starting images.</p>
            </div>
            <span className="status-pill">{artDirectionRows.length} references</span>
          </div>
          <div className="image-grid">
            {artDirectionRows.map(({ asset, sceneRow, sceneNumber }, index) => {
              const url =
                (typeof sceneNumber === 'number' ? staticStoryboardUrl(sceneNumber) : null) ||
                startingFrameUrl({
                  filename: asset.original_filename,
                  assetId: asset.mime_type && !asset.mime_type.startsWith('image/') ? null : asset.id,
                })
              return (
                <button type="button" key={asset.id} className="selected" style={{ cursor: 'default' }}>
                  <MediaThumb
                    url={url}
                    label={sceneRow?.scene.title ?? `Scene ${sceneNumber ?? index + 1}`}
                    frameClass={`frame-${index % 8}`}
                  />
                  <div>
                    <span>
                      <code>{sceneRow?.scene.title ?? `Scene ${sceneNumber ?? 'unmapped'}`}</code>
                    </span>
                    <h3>{sceneRow?.chapter.title ?? 'Scene mapping unavailable'}</h3>
                    <p>Planning reference · not an approved frame zero</p>
                  </div>
                </button>
              )
            })}
          </div>
        </section>
      ) : null}

      <div className="image-layout">
        <div className="stack">
          <div className="toolbar image-toolbar">
            <div className="segmented">
              {(
                [
                  ['all', 'All'],
                  ['missing', 'Missing'],
                  ['required', 'Required'],
                  ['assigned', 'Assigned'],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  className={requirementFilter === id ? 'active' : ''}
                  onClick={() => setRequirementFilter(id)}
                >
                  {label}
                  <span>
                    {id === 'all'
                      ? shotRows.length
                      : id === 'missing'
                        ? shotRows.filter((row) => row.shot.starting_image_required && !row.shot.starting_image_asset_id).length
                        : id === 'required'
                          ? shotRows.filter((row) => row.shot.starting_image_required).length
                          : shotRows.filter((row) => Boolean(row.shot.starting_image_asset_id)).length}
                  </span>
                </button>
              ))}
            </div>
            <select aria-label="Approval filter" value={approvalFilter} onChange={(event) => setApprovalFilter(event.target.value)}>
              <option value="all">Any approval</option>
              <option value="draft">Draft</option>
              <option value="in_review">In review</option>
              <option value="approved">Approved</option>
              <option value="blocked">Blocked</option>
            </select>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search shot, scene, chapter"
              aria-label="Search shots"
            />
          </div>

          {loading ? <LoadingState title="Loading managed starting images…" /> : null}
          {error ? <ErrorState detail={error} onRetry={() => void load()} /> : null}
          {!available && !loading ? (
            <UnavailableState
              title="Managed assets API unavailable"
              detail="Static published media still renders when shot codes match the Gold pack."
            />
          ) : null}
          {!filteredRows.length && !loading ? (
            <EmptyState title="No shots match these filters" detail="Change a filter or add shots to the storyboard." />
          ) : null}

          {filteredRows.length ? (
            <div className="image-grid">
              {filteredRows.map(({ chapter, scene, shot }, index) => {
                const asset = shot.starting_image_asset_id
                  ? assetsById.get(shot.starting_image_asset_id) ?? null
                  : null
                const url = startingFrameUrl({
                  title: shot.title,
                  filename: asset?.original_filename,
                  assetId: shot.starting_image_asset_id,
                })
                return (
                  <button
                    key={shot.id}
                    type="button"
                    className={selectedShot?.id === shot.id ? 'selected' : ''}
                    onClick={() => setSelectedShotId(shot.id)}
                  >
                    <MediaThumb
                      url={url}
                      label={asset ? `${asset.approval_state}` : shot.starting_image_required ? 'IMAGE REQUIRED' : 'OPTIONAL'}
                      frameClass={`frame-${index % 8}`}
                    />
                    <div>
                      <span>
                        <code>{shot.title.split(' - ')[0] || shot.title}</code>
                        <b>{shot.duration_sec}s</b>
                      </span>
                      <h3>{shot.title}</h3>
                      <p>
                        {chapter.title} · {scene.title}
                      </p>
                      <footer>
                        <span className="status-pill">{asset?.approval_state ?? (shot.starting_image_asset_id ? 'mapped' : 'missing')}</span>
                        <small>{shot.continuity_source_type || 'none'}</small>
                      </footer>
                    </div>
                  </button>
                )
              })}
            </div>
          ) : null}
        </div>

        <aside className="image-review">
          {selectedShot ? (
            <>
              <header>
                <div>
                  <span className="eyebrow">IMAGE REVIEW</span>
                  <h2>{selectedShot.title.split(' - ')[0] || selectedShot.title}</h2>
                </div>
                <span className="status-pill">{selectedAssignedAsset?.approval_state ?? 'draft'}</span>
              </header>
              <MediaThumb
                url={selectedThumbUrl}
                label={selectedShot.title}
                frameClass={`frame-${Math.max(0, shotRows.findIndex((row) => row.shot.id === selectedShot.id)) % 8}`}
                tall
              />
              <div className="image-meta">
                <div>
                  <span>Requirement</span>
                  <b>{selectedShot.starting_image_required ? 'Required' : 'Optional'}</b>
                </div>
                <div>
                  <span>Current asset</span>
                  <b>{selectedAssignedAsset?.original_filename ?? selectedShot.starting_image_asset_id ?? 'None'}</b>
                </div>
                <div>
                  <span>Continuity</span>
                  <b>{selectedShot.continuity_source_type || 'none'}</b>
                </div>
                <div>
                  <span>Source state</span>
                  <b>{selectedThumbUrl ? 'Attached · draft' : 'Not generated'}</b>
                </div>
              </div>
              <div className="form-stack compact">
                <label>
                  Candidate asset
                  <select
                    value={selectedAssetId}
                    onChange={(event) => setAssetDraft({ shotId: selectedShot.id, assetId: event.target.value })}
                    disabled={approvalSaving || saving || busy || !available}
                  >
                    <option value="">No starting image</option>
                    {items?.map((asset) => (
                      <option key={asset.id} value={asset.id}>
                        {asset.original_filename ?? asset.id} · {asset.approval_state}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="page-actions">
                  <button
                    type="button"
                    className="btn primary"
                    onClick={() => void onAssign()}
                    disabled={
                      approvalSaving ||
                      saving ||
                      busy ||
                      selectedAssetId === (selectedShot.starting_image_asset_id ?? '')
                    }
                  >
                    {saving ? 'Saving…' : selectedAssetId ? 'Assign candidate' : 'Clear assignment'}
                  </button>
                  {selectedAssignedAsset && selectedAssignedAsset.approval_state !== 'approved' ? (
                    <button
                      type="button"
                      className="btn secondary"
                      onClick={() => void onApprove()}
                      disabled={approvalSaving || saving || busy}
                    >
                      {approvalSaving ? 'Approving…' : 'Approve candidate'}
                    </button>
                  ) : null}
                </div>
                <label>
                  Image prompt
                  <textarea className="prompt tall" readOnly value={selectedShot.prompt_positive || 'No image prompt recorded.'} />
                </label>
                {selectedShot.prompt_negative ? (
                  <label>
                    Negative prompt
                    <textarea className="prompt" readOnly value={selectedShot.prompt_negative} />
                  </label>
                ) : null}
                <p className="form-hint">{GENERATION_DISABLED_REASON}</p>
                <button type="button" className="btn primary" disabled title={GENERATION_DISABLED_REASON}>
                  Generate candidate — disabled
                </button>
              </div>
            </>
          ) : (
            <EmptyState title="Select a shot" detail="Choose a starting-image card to review the managed candidate." />
          )}

          <form className="form-stack compact" onSubmit={(event) => void onUpload(event)} style={{ marginTop: 16 }}>
            <h3>Upload existing candidate</h3>
            <label>
              Starting-image file
              <input
                key={fileInputKey}
                type="file"
                accept="image/*"
                required
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                disabled={saving || busy}
              />
            </label>
            {file ? (
              <p className="form-hint">
                {file.name} · {formatBytes(file.size)}
              </p>
            ) : null}
            <button type="submit" className="btn secondary" disabled={saving || busy || !file}>
              {saving ? 'Uploading…' : 'Upload managed candidate'}
            </button>
          </form>

          {items?.length ? (
            <section style={{ marginTop: 16 }}>
              <h3>Candidate inventory</h3>
              <div className="image-grid" style={{ gridTemplateColumns: 'repeat(2, minmax(0, 1fr))' }}>
                {items.map((asset, index) => {
                  const url = startingFrameUrl({
                    filename: asset.original_filename,
                    assetId: asset.mime_type && !asset.mime_type.startsWith('image/') ? null : asset.id,
                  })
                  return (
                    <button type="button" key={asset.id} style={{ cursor: 'default' }}>
                      <MediaThumb
                        url={url}
                        label={asset.approval_state}
                        frameClass={`frame-${index % 8}`}
                      />
                      <div>
                        <h3>{asset.original_filename ?? asset.id}</h3>
                        <p>
                          {formatBytes(asset.size_bytes)} · {asset.approval_state}
                        </p>
                      </div>
                    </button>
                  )
                })}
              </div>
            </section>
          ) : null}
        </aside>
      </div>
    </div>
  )
}
