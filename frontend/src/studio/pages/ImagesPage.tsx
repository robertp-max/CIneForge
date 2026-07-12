import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { api, planningAssetContentUrl, type PlanningMediaAsset } from '../../api/client'
import { PageTitle, StatusPill } from '../../components/ui'
import { useStudio } from '../StudioState'
import { EmptyState, ErrorState, LoadingState, UnavailableState } from '../components/StateBlocks'

const GENERATION_DISABLED_REASON =
  'Image generation is disabled in Phase 1 planning; no render or ComfyUI submission endpoint is exposed.'

type RequirementFilter = 'all' | 'required' | 'missing' | 'assigned'

type ShotLike = {
  starting_image_required: boolean
  starting_image_asset_id: string | null
}

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

function tileStatus(shot: ShotLike, asset: PlanningMediaAsset | null | undefined): string {
  if (asset?.approval_state) return asset.approval_state
  if (shot.starting_image_required && !shot.starting_image_asset_id) return 'missing'
  if (shot.starting_image_asset_id) return 'draft'
  return shot.starting_image_required ? 'required' : 'draft'
}

function statusLabel(status: string): string {
  switch (status) {
    case 'in_review':
      return 'Review'
    case 'missing':
      return 'Missing'
    case 'required':
      return 'Required'
    case 'approved':
      return 'Approved'
    case 'blocked':
      return 'Blocked'
    case 'draft':
      return 'Draft'
    default:
      return status.replace(/_/g, ' ')
  }
}

export function ImagesPage() {
  const { data, readiness, busy, saveShot, setMessage } = useStudio()
  const [items, setItems] = useState<PlanningMediaAsset[] | null>(null)
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

  const requirementCounts = useMemo(() => {
    let required = 0
    let missing = 0
    let assigned = 0
    for (const { shot } of shotRows) {
      if (shot.starting_image_required) required += 1
      if (shot.starting_image_required && !shot.starting_image_asset_id) missing += 1
      if (shot.starting_image_asset_id) assigned += 1
    }
    return {
      all: shotRows.length,
      required,
      missing,
      assigned,
    }
  }, [shotRows])

  const load = useCallback(async () => {
    if (!data) return
    setLoading(true)
    setError(null)
    try {
      const result = await api.listStartingImageAssets(data.story.project_id)
      if (result == null) {
        setAvailable(false)
        setItems(null)
      } else {
        setAvailable(true)
        setItems(result.items)
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
  const selectedPreviewAsset =
    selectedAssetId && assetsById.get(selectedAssetId)
      ? assetsById.get(selectedAssetId) ?? null
      : selectedAssignedAsset
  const selectedStatus = selectedShot
    ? tileStatus(selectedShot, selectedAssignedAsset)
    : 'draft'
  const selectedReadiness = selectedShot
    ? (readiness?.reasons.filter((reason) => reason.entity_id === selectedShot.id) ?? [])
    : []
  const selectedCharacters =
    selectedShot?.characters
      ?.map((link) => data.characters.find((character) => character.id === link.character_id)?.name)
      .filter(Boolean) ?? []

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

  const actionsBusy = approvalSaving || saving || busy

  return (
    <div>
      <PageTitle
        eyebrow="STARTING-IMAGE PLAN"
        title="Starting images"
        description="Plan and approve the visual anchor for every generation-ready shot."
        aside={
          <div className="page-actions">
            <button
              type="button"
              className="ghost-button touch-target"
              onClick={() => void load()}
              disabled={loading || busy}
            >
              Refresh assets
            </button>
            <button
              type="button"
              className="btn primary touch-target"
              disabled
              title={GENERATION_DISABLED_REASON}
            >
              Generate candidate
            </button>
          </div>
        }
      />

      <div className="image-layout">
        <div>
          <div className="segmented" role="tablist" aria-label="Filter shots by starting-image requirement">
            {(
              [
                ['all', 'All'],
                ['required', 'Required'],
                ['missing', 'Missing'],
                ['assigned', 'Assigned'],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={requirementFilter === id}
                className={requirementFilter === id ? 'active' : ''}
                onClick={() => setRequirementFilter(id)}
              >
                {label} <em>{requirementCounts[id]}</em>
              </button>
            ))}
          </div>

          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 10,
              alignItems: 'flex-end',
              marginBottom: 14,
            }}
          >
            <div
              className="segmented"
              role="tablist"
              aria-label="Filter by assigned asset approval"
              style={{ marginBottom: 0 }}
            >
              {(
                [
                  ['all', 'All'],
                  ['draft', 'Draft'],
                  ['in_review', 'Review'],
                  ['approved', 'Approved'],
                  ['blocked', 'Blocked'],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={approvalFilter === id}
                  className={approvalFilter === id ? 'active' : ''}
                  onClick={() => setApprovalFilter(id)}
                >
                  {label}
                </button>
              ))}
            </div>
            <label style={{ margin: 0, minWidth: 180, flex: '1 1 180px' }}>
              Search
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Shot, scene, or chapter"
              />
            </label>
          </div>

          {loading ? <LoadingState title="Loading managed starting images…" /> : null}
          {error ? <ErrorState detail={error} onRetry={() => void load()} /> : null}
          {!available && !loading ? (
            <UnavailableState
              title="Managed assets API unavailable"
              detail="No local path, candidate, or generated-image claim is substituted."
            />
          ) : null}

          {!filteredRows.length && !loading ? (
            <EmptyState
              title="No shots match these filters"
              detail="Change a filter or add shots to the storyboard."
            />
          ) : null}

          {filteredRows.length ? (
            <div className="image-grid" role="list" aria-label="Starting-image shot tiles">
              {filteredRows.map(({ chapter, scene, shot }) => {
                const asset = shot.starting_image_asset_id
                  ? assetsById.get(shot.starting_image_asset_id) ?? null
                  : null
                const status = tileStatus(shot, asset)
                const selected = selectedShot?.id === shot.id
                const hasImage = Boolean(asset?.mime_type?.startsWith('image/'))
                return (
                  <button
                    key={shot.id}
                    type="button"
                    role="listitem"
                    className={selected ? 'image-tile selected' : 'image-tile'}
                    onClick={() => setSelectedShotId(shot.id)}
                    aria-pressed={selected}
                    style={{ width: '100%', padding: 0 }}
                  >
                    <div className="thumb" style={{ position: 'relative', overflow: 'hidden' }}>
                      {hasImage && asset ? (
                        <img
                          src={planningAssetContentUrl(asset.id)}
                          alt=""
                          loading="lazy"
                          style={{
                            position: 'absolute',
                            inset: 0,
                            width: '100%',
                            height: '100%',
                            objectFit: 'cover',
                          }}
                        />
                      ) : (
                        <span
                          style={{
                            position: 'relative',
                            zIndex: 1,
                            padding: '4px 8px',
                            borderRadius: 6,
                            background: 'rgba(0,0,0,.55)',
                            fontSize: '0.7rem',
                            letterSpacing: '0.04em',
                            textTransform: 'uppercase',
                          }}
                        >
                          {shot.starting_image_required && !shot.starting_image_asset_id
                            ? 'Image required'
                            : shot.starting_image_asset_id
                              ? 'Assigned asset'
                              : 'No candidate'}
                        </span>
                      )}
                    </div>
                    <div className="body">
                      <small>
                        {chapter.title} · {scene.title} · {shot.duration_sec}s
                      </small>
                      <b>{shot.title}</b>
                      <StatusPill status={statusLabel(status)} />
                    </div>
                  </button>
                )
              })}
            </div>
          ) : null}
        </div>

        <aside
          className="image-review"
          aria-label="Image review"
          style={{ maxHeight: 'calc(100dvh - 140px)', overflow: 'auto' }}
        >
          {selectedShot && selectedRow ? (
            <>
              <header style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'flex-start', marginBottom: 12 }}>
                <div>
                  <span className="eyebrow">IMAGE REVIEW</span>
                  <h2 style={{ margin: '4px 0 0' }}>{selectedShot.title}</h2>
                  <p style={{ margin: '4px 0 0', color: 'var(--muted)' }}>
                    {selectedRow.chapter.title} · {selectedRow.scene.title} · {selectedShot.duration_sec}s
                  </p>
                </div>
                <StatusPill status={statusLabel(selectedStatus)} />
              </header>

              <div className="review-canvas">
                {selectedPreviewAsset?.mime_type?.startsWith('image/') ? (
                  <img
                    src={planningAssetContentUrl(selectedPreviewAsset.id)}
                    alt={`Starting image for ${selectedShot.title}`}
                  />
                ) : (
                  <div style={{ textAlign: 'center', color: 'var(--muted)', padding: 16 }}>
                    <b style={{ display: 'block', color: 'var(--text)', marginBottom: 6 }}>
                      {selectedShot.starting_image_required ? 'No candidates yet' : 'Optional starting image'}
                    </b>
                    <small>CURRENT SELECTED IMAGE</small>
                  </div>
                )}
              </div>

              <ul className="kv-list">
                <li>
                  <span>Requirement</span>
                  <strong>{selectedShot.starting_image_required ? 'Required' : 'Optional'}</strong>
                </li>
                <li>
                  <span>Current asset</span>
                  <strong>
                    {selectedAssignedAsset?.original_filename ??
                      selectedShot.starting_image_asset_id ??
                      'None'}
                  </strong>
                </li>
                <li>
                  <span>Asset approval</span>
                  <strong>{selectedAssignedAsset?.approval_state ?? 'Not assigned'}</strong>
                </li>
                <li>
                  <span>Continuity source</span>
                  <strong>{selectedShot.continuity_source_type || 'none'}</strong>
                </li>
                <li>
                  <span>Source shot</span>
                  <strong>{selectedShot.continuity_source_shot_id ?? 'None'}</strong>
                </li>
                <li>
                  <span>Location</span>
                  <strong>{selectedShot.location || 'None recorded'}</strong>
                </li>
                <li>
                  <span>Characters</span>
                  <strong>{selectedCharacters.length ? selectedCharacters.join(', ') : 'None linked'}</strong>
                </li>
              </ul>

              <div className="stack-form" style={{ marginTop: 12 }}>
                <label>
                  Candidate asset
                  <select
                    value={selectedAssetId}
                    onChange={(event) =>
                      setAssetDraft({ shotId: selectedShot.id, assetId: event.target.value })
                    }
                    disabled={actionsBusy || !available}
                  >
                    <option value="">No starting image</option>
                    {items?.map((asset) => (
                      <option key={asset.id} value={asset.id}>
                        {asset.original_filename ?? asset.id} · {asset.approval_state}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  className="primary-button touch-target"
                  onClick={() => void onAssign()}
                  disabled={
                    actionsBusy || selectedAssetId === (selectedShot.starting_image_asset_id ?? '')
                  }
                >
                  {saving ? 'Saving…' : selectedAssetId ? 'Assign candidate' : 'Clear assignment'}
                </button>
                {selectedAssignedAsset && selectedAssignedAsset.approval_state !== 'approved' ? (
                  <button
                    type="button"
                    className="secondary-button touch-target"
                    onClick={() => void onApprove()}
                    disabled={actionsBusy}
                  >
                    {approvalSaving ? 'Approving…' : 'Approve candidate'}
                  </button>
                ) : null}

                <h3>Image prompt</h3>
                <p>{selectedShot.prompt_positive || 'No image prompt recorded.'}</p>
                {selectedShot.prompt_video ? (
                  <p>
                    <strong>Video:</strong> {selectedShot.prompt_video}
                  </p>
                ) : null}
                <h3>Negative prompt</h3>
                <p>{selectedShot.prompt_negative || 'None recorded.'}</p>
                <h3>Style lock</h3>
                <p>{selectedShot.prompt_style_lock || 'None recorded.'}</p>
                <h3>Continuity instructions</h3>
                <p>{selectedShot.prompt_continuity_instructions || 'None recorded.'}</p>

                <h3>Model / workflow recommendations</h3>
                {selectedShot.recommendations?.length ? (
                  <ul className="kv-list">
                    {selectedShot.recommendations.map((recommendation) => (
                      <li key={recommendation.id}>
                        <span>
                          {recommendation.recommendation_type} ·{' '}
                          {recommendation.rationale ?? 'No rationale'}
                        </span>
                        <strong>
                          {recommendation.availability_status} / {recommendation.benchmark_status}
                        </strong>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="form-hint">No model or workflow recommendation is persisted for this shot.</p>
                )}

                <h3>Readiness</h3>
                {selectedReadiness.length ? (
                  selectedReadiness.map((reason) => (
                    <p className="notice warning" key={`${reason.code}-${reason.entity_id}`}>
                      {reason.message}
                    </p>
                  ))
                ) : (
                  <p className="notice success">No shot-specific blocking reason is currently reported.</p>
                )}

                <form className="stack-form" onSubmit={(event) => void onUpload(event)}>
                  <h3>Upload existing candidate</h3>
                  <p className="form-hint">
                    Creates a server-managed starting-image asset from explicit user bytes. Upload never
                    starts generation.
                  </p>
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
                  <button
                    type="submit"
                    className="secondary-button touch-target"
                    disabled={saving || busy || !file}
                  >
                    {saving ? 'Uploading…' : 'Upload managed candidate'}
                  </button>
                </form>

                {items?.length ? (
                  <div>
                    <h3>Candidate inventory</h3>
                    <ul className="kv-list">
                      {items.map((asset) => (
                        <li key={asset.id}>
                          <span>
                            {asset.original_filename ?? asset.id} · {formatBytes(asset.size_bytes)}
                          </span>
                          <strong>{asset.approval_state}</strong>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                <button
                  type="button"
                  className="primary-button touch-target"
                  disabled
                  title={GENERATION_DISABLED_REASON}
                >
                  Generate candidate — disabled
                </button>
                <p className="form-hint">{GENERATION_DISABLED_REASON}</p>
              </div>
            </>
          ) : (
            <EmptyState
              title="No shot selected"
              detail="Add shots to the storyboard to plan starting images."
            />
          )}
        </aside>
      </div>
    </div>
  )
}
