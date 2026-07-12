import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { api, planningAssetContentUrl, type PlanningMediaAsset, type Shot } from '../../api/client'
import { Button, Empty, Icon, PageTitle, StatusPill } from '../../components/ui'
import { useStudio } from '../StudioState'
import { EmptyState, ErrorState, LoadingState, UnavailableState } from '../components/StateBlocks'

const GENERATION_DISABLED_REASON =
  'Image generation is disabled in Phase 1 planning; no render or ComfyUI submission endpoint is exposed.'

type StatusFilter = 'All' | 'Missing' | 'Draft' | 'Review' | 'Approved' | 'Blocked'

type ShotRow = {
  chapter: { id: string; title: string }
  scene: { id: string; title: string }
  shot: Shot
  index: number
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

function approvalLabel(state: string | null | undefined): StatusFilter {
  const normalized = (state ?? 'draft').toLowerCase()
  if (normalized === 'approved') return 'Approved'
  if (normalized === 'blocked') return 'Blocked'
  if (normalized === 'in_review' || normalized === 'review') return 'Review'
  return 'Draft'
}

function shotImageStatus(
  shot: Shot,
  asset: PlanningMediaAsset | null | undefined,
): StatusFilter {
  if (shot.starting_image_required && !shot.starting_image_asset_id) return 'Missing'
  if (asset?.approval_state) return approvalLabel(asset.approval_state)
  if (shot.starting_image_asset_id) return 'Draft'
  return shot.starting_image_required ? 'Missing' : 'Draft'
}

function modelLabel(shot: Shot): string {
  return (
    shot.recommendations?.find((item) => item.recommendation_type === 'generation')?.rationale ||
    shot.prompt_provider_model_id ||
    'Planning model'
  )
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
  const [filter, setFilter] = useState<StatusFilter>('All')
  const [chapter, setChapter] = useState('All')
  const [compare, setCompare] = useState(false)

  const shotRows = useMemo<ShotRow[]>(() => {
    if (!data) return []
    let index = 0
    return data.chapters.flatMap((chapterItem) =>
      chapterItem.scenes.flatMap((scene) =>
        scene.shots.map((shot) => {
          const row = { chapter: chapterItem, scene, shot, index }
          index += 1
          return row
        }),
      ),
    )
  }, [data])

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

  const assetsById = useMemo(
    () => new Map(items?.map((asset) => [asset.id, asset]) ?? []),
    [items],
  )

  const statusOf = useCallback(
    (shot: Shot) =>
      shotImageStatus(
        shot,
        shot.starting_image_asset_id ? assetsById.get(shot.starting_image_asset_id) : null,
      ),
    [assetsById],
  )

  const filterCounts = useMemo(() => {
    const counts: Record<StatusFilter, number> = {
      All: shotRows.length,
      Missing: 0,
      Draft: 0,
      Review: 0,
      Approved: 0,
      Blocked: 0,
    }
    for (const { shot } of shotRows) {
      counts[statusOf(shot)] += 1
    }
    return counts
  }, [shotRows, statusOf])

  const filteredRows = useMemo(
    () =>
      shotRows.filter(({ shot, chapter: chapterItem }) => {
        const status = statusOf(shot)
        const matchesFilter = filter === 'All' || status === filter
        const matchesChapter = chapter === 'All' || chapterItem.id === chapter
        return matchesFilter && matchesChapter
      }),
    [shotRows, statusOf, filter, chapter],
  )

  const selectedRow =
    filteredRows.find((row) => row.shot.id === selectedShotId) ??
    shotRows.find((row) => row.shot.id === selectedShotId) ??
    filteredRows[0] ??
    shotRows[0] ??
    null

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
  const selectedStatus = selectedShot ? statusOf(selectedShot) : 'Draft'
  const selectedReadiness = selectedShot
    ? (readiness?.reasons.filter((reason) => reason.entity_id === selectedShot.id) ?? [])
    : []
  const selectedCharacters =
    selectedShot?.characters
      ?.map((link) => data?.characters.find((character) => character.id === link.character_id)?.name)
      .filter(Boolean) ?? []
  const candidateAssets = items ?? []
  const frameIndex = selectedRow ? selectedRow.index % 8 : 0

  if (!data) return null

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

  const onAssign = async (assetId: string | null = selectedAssetId || null) => {
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
        starting_image_asset_id: assetId,
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
      const text =
        'Archived starting-image assets cannot be approved. Refresh and select an active candidate.'
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
      setMessage(
        `Approved managed starting-image candidate ${approved.original_filename ?? approved.id}. No generation was started.`,
      )
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
    <div className="page">
      <PageTitle
        eyebrow="STARTING-IMAGE PLAN"
        title="Starting images"
        description="Plan and approve the visual anchor for every generation-ready shot."
        aside={
          <div className="page-actions">
            <Button icon="eye" onClick={() => setCompare((value) => !value)} disabled={!selectedShot}>
              {compare ? 'Exit compare' : 'Compare candidates'}
            </Button>
            <Button
              variant="primary"
              icon="wand"
              disabled
              title={GENERATION_DISABLED_REASON}
            >
              Generate candidate
            </Button>
          </div>
        }
      />

      <div className="image-layout">
        <div className="stack">
          <div className="toolbar image-toolbar">
            <div className="segmented" role="tablist" aria-label="Filter shots by starting-image status">
              {(['All', 'Missing', 'Draft', 'Review', 'Approved', 'Blocked'] as const).map((item) => (
                <button
                  key={item}
                  type="button"
                  role="tab"
                  aria-selected={filter === item}
                  className={filter === item ? 'active' : ''}
                  onClick={() => setFilter(item)}
                >
                  {item}
                  <span>{filterCounts[item]}</span>
                </button>
              ))}
            </div>
            <select
              aria-label="Filter by chapter"
              value={chapter}
              onChange={(event) => setChapter(event.target.value)}
            >
              <option value="All">All</option>
              {data.chapters.map((chapterItem) => (
                <option key={chapterItem.id} value={chapterItem.id}>
                  {chapterItem.title || chapterItem.id}
                </option>
              ))}
            </select>
          </div>

          {loading ? <LoadingState title="Loading managed starting images…" /> : null}
          {error ? <ErrorState detail={error} onRetry={() => void load()} /> : null}
          {!available && !loading ? (
            <UnavailableState
              title="Managed assets API unavailable"
              detail="No local path, candidate, or generated-image claim is substituted."
            />
          ) : null}

          {filteredRows.length ? (
            <div className="image-grid" role="list" aria-label="Starting-image shot tiles">
              {filteredRows.map((row) => {
                const { shot } = row
                const asset = shot.starting_image_asset_id
                  ? assetsById.get(shot.starting_image_asset_id) ?? null
                  : null
                const status = statusOf(shot)
                const selected = selectedShot?.id === shot.id
                const hasImage = Boolean(asset?.mime_type?.startsWith('image/'))
                const candidateCount = shot.starting_image_asset_id ? 1 : 0
                return (
                  <button
                    key={shot.id}
                    type="button"
                    role="listitem"
                    className={selected ? 'selected' : ''}
                    onClick={() => setSelectedShotId(shot.id)}
                    aria-pressed={selected}
                  >
                    <div className={`image-placeholder frame-${row.index % 8}`}>
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
                            zIndex: 1,
                          }}
                        />
                      ) : null}
                      <span>
                        {candidateCount
                          ? `${candidateCount} candidate${candidateCount === 1 ? '' : 's'}`
                          : 'IMAGE REQUIRED'}
                      </span>
                      <Icon name={candidateCount ? 'image' : 'plus'} size={26} />
                    </div>
                    <div>
                      <span>
                        <code>{shot.display_label || shot.id.slice(0, 8)}</code>
                        <b>{shot.duration_sec}s</b>
                      </span>
                      <h3>{shot.title}</h3>
                      <p>{shot.continuity_source_type || 'No continuity source'}</p>
                      <footer>
                        <StatusPill status={status} />
                        <small>{modelLabel(shot)}</small>
                      </footer>
                    </div>
                  </button>
                )
              })}
            </div>
          ) : !loading ? (
            <Empty
              title="No images match"
              detail="Clear filters to return to all shots."
              action={
                <Button
                  onClick={() => {
                    setFilter('All')
                    setChapter('All')
                  }}
                >
                  Clear filters
                </Button>
              }
            />
          ) : null}
        </div>

        <aside className="image-review" aria-label="Image review">
          {selectedShot && selectedRow ? (
            <>
              <header>
                <div>
                  <span className="eyebrow">IMAGE REVIEW</span>
                  <h2>{selectedShot.display_label || selectedShot.id.slice(0, 8)}</h2>
                </div>
                <StatusPill status={selectedStatus} />
              </header>

              <div className={`review-canvas frame-${frameIndex}`}>
                {selectedPreviewAsset?.mime_type?.startsWith('image/') ? (
                  <img
                    src={planningAssetContentUrl(selectedPreviewAsset.id)}
                    alt={`Starting image for ${selectedShot.title}`}
                  />
                ) : (
                  <>
                    <span>{selectedShot.title}</span>
                    <small>{compare ? 'A / B COMPARISON' : 'CURRENT SELECTED IMAGE'}</small>
                    <div>
                      <Icon name="image" size={34} />
                      <b>
                        {selectedShot.starting_image_required
                          ? 'No candidates yet'
                          : 'Optional starting image'}
                      </b>
                    </div>
                  </>
                )}
              </div>

              {compare ? (
                <div className="candidate-compare">
                  {(
                    candidateAssets.length
                      ? candidateAssets.slice(0, 3)
                      : ([null, null] as Array<PlanningMediaAsset | null>)
                  ).map((asset, index) => (
                    <button
                      key={asset?.id ?? `placeholder-${index}`}
                      type="button"
                      className={`candidate frame-${(frameIndex + index + 1) % 8}`}
                      onClick={() => {
                        if (asset) {
                          setAssetDraft({ shotId: selectedShot.id, assetId: asset.id })
                          setMessage(
                            `Candidate ${asset.original_filename ?? asset.id} selected for assignment.`,
                          )
                        } else {
                          setMessage('No managed candidate is available for this slot.')
                        }
                      }}
                    >
                      <span>{index + 1}</span>
                    </button>
                  ))}
                </div>
              ) : null}

              <div className="image-meta">
                <div>
                  <span>Dimensions</span>
                  <b>1920 × 1080</b>
                </div>
                <div>
                  <span>Model</span>
                  <b>{modelLabel(selectedShot)}</b>
                </div>
                <div>
                  <span>Seed</span>
                  <b>{selectedShot.starting_image_asset_id ? 'Managed asset' : 'Not generated'}</b>
                </div>
                <div>
                  <span>Workflow</span>
                  <b>Cinematic Starting Image</b>
                </div>
              </div>

              <div className="form-stack compact">
                <label>
                  Image prompt
                  <textarea
                    className="prompt tall"
                    readOnly
                    value={selectedShot.prompt_positive || 'No image prompt recorded.'}
                  />
                </label>
                <label>
                  Negative prompt
                  <textarea
                    className="prompt"
                    readOnly
                    value={selectedShot.prompt_negative || 'None recorded.'}
                  />
                </label>
                <label>
                  Characters
                  <div className="token-field">
                    {selectedCharacters.length ? (
                      selectedCharacters.map((name) => <span key={String(name)}>{name}</span>)
                    ) : (
                      <span>None linked</span>
                    )}
                  </div>
                </label>
                <label>
                  Location
                  <input readOnly value={selectedShot.location || 'None recorded'} />
                </label>
                <label>
                  Style lock
                  <textarea
                    className="prompt"
                    readOnly
                    value={selectedShot.prompt_style_lock || 'None recorded.'}
                  />
                </label>
                <label>
                  Continuity source
                  <input
                    readOnly
                    value={
                      selectedShot.continuity_source_shot_id
                        ? `${selectedShot.continuity_source_type} · ${selectedShot.continuity_source_shot_id}`
                        : selectedShot.continuity_source_type || 'none'
                    }
                  />
                </label>

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

                {selectedReadiness.length ? (
                  selectedReadiness.map((reason) => (
                    <p className="notice warning" key={`${reason.code}-${reason.entity_id}`}>
                      {reason.message}
                    </p>
                  ))
                ) : (
                  <p className="notice success">
                    No shot-specific blocking reason is currently reported.
                  </p>
                )}

                <form className="form-stack compact" onSubmit={(event) => void onUpload(event)}>
                  <h3>Upload existing candidate</h3>
                  <p className="form-hint">
                    Creates a server-managed starting-image asset from explicit user bytes. Upload
                    never starts generation.
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
                  <Button type="submit" disabled={saving || busy || !file}>
                    {saving ? 'Uploading…' : 'Upload managed candidate'}
                  </Button>
                </form>
              </div>

              <footer>
                <Button
                  variant="danger"
                  disabled={actionsBusy || !selectedShot.starting_image_asset_id}
                  onClick={() => void onAssign(null)}
                >
                  Clear assignment
                </Button>
                <Button
                  onClick={() => void onAssign()}
                  disabled={
                    actionsBusy || selectedAssetId === (selectedShot.starting_image_asset_id ?? '')
                  }
                >
                  {saving ? 'Saving…' : selectedAssetId ? 'Assign candidate' : 'Clear assignment'}
                </Button>
                {selectedAssignedAsset && selectedAssignedAsset.approval_state !== 'approved' ? (
                  <Button
                    variant="primary"
                    onClick={() => void onApprove()}
                    disabled={actionsBusy}
                  >
                    {approvalSaving ? 'Approving…' : 'Approve candidate'}
                  </Button>
                ) : (
                  <Button variant="primary" disabled title={GENERATION_DISABLED_REASON}>
                    Generate candidate — disabled
                  </Button>
                )}
              </footer>
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
