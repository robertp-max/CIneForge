/**
 * Exact structural port of prototype ImagesPage (pagesAssets.tsx / pagesAssets.source.tsx)
 * adapted to production studio context + managed starting-image asset APIs.
 *
 * DOM hierarchy matches the ZIP prototype:
 * page-title (STARTING-IMAGE PLAN + Compare candidates / Generate candidate) →
 * image-layout → stack (toolbar image-toolbar: segmented status filter + chapter select,
 * image-grid shot tiles) | image-review (header, review-canvas, candidate-compare,
 * image-meta, form-stack prompts, footer: Reject / Use selected / Approve selected).
 *
 * Production upload / assign (saveShot → starting_image_asset_id) / approve
 * (PATCH starting-image-approval) stay wired via api client only.
 * Generate remains disabled with a factual Phase-1 reason (no render/Comfy endpoint).
 */
import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  api,
  planningAssetContentUrl,
  type ActivePlanningMediaAssetApprovalState,
  type PlanningMediaAsset,
  type Shot,
} from '../../api/client'
import { Button, Empty, Icon, PageTitle, StatusPill } from '../proto/ui'
import { useStudio } from '../StudioState'
import { EmptyState, ErrorState, LoadingState, UnavailableState } from '../components/StateBlocks'

const GENERATION_DISABLED_REASON =
  'Image generation is disabled in Phase 1 planning; no render or ComfyUI submission endpoint is exposed.'

const STATUS_FILTERS = ['All', 'Missing', 'Draft', 'Review', 'Approved', 'Blocked'] as const
type StatusFilter = (typeof STATUS_FILTERS)[number]
type ImageStatus = Exclude<StatusFilter, 'All' | 'Missing'>

type ShotRow = {
  chapter: { id: string; title: string; order_index?: number }
  scene: { id: string; title: string; order_index?: number }
  shot: Shot
  index: number
  chapterIndex: number
  sceneIndex: number
  shotIndexInScene: number
}

function formatBytes(value: number | null): string {
  if (value == null) return 'Unknown size'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

function errorText(error: unknown, fallback = 'Failed to load managed starting-image assets.'): string {
  return error instanceof Error && error.message ? error.message : fallback
}

/** First non-empty reason; used for factual disabled control titles. */
function firstReason(...reasons: Array<string | false | null | undefined>): string | undefined {
  for (const reason of reasons) {
    if (typeof reason === 'string' && reason.trim()) return reason
  }
  return undefined
}

function approvalLabel(state: string | null | undefined): ImageStatus {
  const normalized = (state ?? 'draft').toLowerCase()
  if (normalized === 'approved') return 'Approved'
  if (normalized === 'blocked') return 'Blocked'
  if (normalized === 'in_review' || normalized === 'review') return 'Review'
  return 'Draft'
}

/**
 * Proto startingImageStatus is never "Missing" — Missing is only a filter
 * (candidateCount === 0). Pill status comes from asset / shot approval.
 */
function startingImageStatus(
  shot: Shot,
  asset: PlanningMediaAsset | null | undefined,
): ImageStatus {
  if (asset?.approval_state) return approvalLabel(asset.approval_state)
  if (shot.starting_image_asset_id) return 'Draft'
  return approvalLabel(shot.approval_state)
}

/** Factual candidate count: assigned asset ⇒ at least 1; otherwise 0 (IMAGE REQUIRED). */
function candidateCountOf(shot: Shot): number {
  return shot.starting_image_asset_id ? 1 : 0
}

function modelLabel(shot: Shot): string {
  return (
    shot.recommendations?.find((item) => item.recommendation_type === 'generation')?.rationale ||
    shot.prompt_provider_model_id ||
    'Planning model'
  )
}

function dimensionsLabel(asset: PlanningMediaAsset | null | undefined, hasCandidate: boolean): string {
  if (asset?.width != null && asset?.height != null) {
    return `${asset.width} × ${asset.height}`
  }
  // Proto hardcodes 1920 × 1080 once a candidate exists.
  return hasCandidate ? '1920 × 1080' : 'Unknown'
}

function seedLabel(asset: PlanningMediaAsset | null | undefined, hasCandidate: boolean): string {
  if (!hasCandidate && !asset) return 'Not generated'
  if (asset?.source_type === 'user_upload') return 'Managed upload'
  if (asset?.source_type) return asset.source_type
  // Proto seed placeholder when candidates exist without managed seed metadata.
  return hasCandidate ? '418027' : 'Not generated'
}

function isActiveApprovalState(state: string): state is ActivePlanningMediaAssetApprovalState {
  return state === 'draft' || state === 'in_review' || state === 'approved' || state === 'blocked'
}

function chapterCode(index: number): string {
  return `CH${String(index + 1).padStart(2, '0')}`
}

function sceneCode(index: number): string {
  return `SC${String(index + 1).padStart(2, '0')}`
}

/** Proto shot id style: CH01-SC01-SH01 */
function shotCode(chapterIndex: number, sceneIndex: number, shotIndexInScene: number): string {
  return `${chapterCode(chapterIndex)}-${sceneCode(sceneIndex)}-SH${String(shotIndexInScene + 1).padStart(2, '0')}`
}

function continuityLabel(shot: Shot): string {
  const type = (shot.continuity_source_type || '').toLowerCase()
  if (!type || type === 'none') return 'No continuity source'
  if (type === 'new_generated_image' || type === 'new generated image') return 'New generated image'
  if (type === 'prior_shot_final_frame' || type === 'prior shot final frame' || type === 'shot_ref') {
    return 'Prior shot final frame'
  }
  if (type === 'approved_character_reference' || type.includes('character')) {
    return 'Approved character reference'
  }
  return shot.continuity_source_type || 'No continuity source'
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

  const actionsBusy = busy || saving || approvalSaving
  const busyReason = busy
    ? 'A studio save or reload is already in progress.'
    : saving
      ? 'A starting-image action is already in progress.'
      : approvalSaving
        ? 'Approval is already in progress.'
        : null
  const unavailableReason = !available
    ? 'Managed assets API is unavailable on this backend; upload/assign/approve cannot run.'
    : null

  const shotRows = useMemo<ShotRow[]>(() => {
    if (!data) return []
    let index = 0
    return data.chapters.flatMap((chapterItem, chapterIndex) =>
      chapterItem.scenes.flatMap((scene, sceneIndex) =>
        scene.shots.map((shot, shotIndexInScene) => {
          const row: ShotRow = {
            chapter: chapterItem,
            scene,
            shot,
            index,
            chapterIndex,
            sceneIndex,
            shotIndexInScene,
          }
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
      startingImageStatus(
        shot,
        shot.starting_image_asset_id ? assetsById.get(shot.starting_image_asset_id) : null,
      ),
    [assetsById],
  )

  /** Proto counts: Missing = candidateCount===0; status buckets use startingImageStatus. */
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
      if (candidateCountOf(shot) === 0) counts.Missing += 1
      counts[statusOf(shot)] += 1
    }
    return counts
  }, [shotRows, statusOf])

  const filteredRows = useMemo(
    () =>
      shotRows.filter(({ shot, chapter: chapterItem }) => {
        const status = statusOf(shot)
        const candidates = candidateCountOf(shot)
        const matchesFilter =
          filter === 'All' ||
          (filter === 'Missing' ? candidates === 0 : status === filter)
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
  const selectedShotCode = selectedRow
    ? shotCode(selectedRow.chapterIndex, selectedRow.sceneIndex, selectedRow.shotIndexInScene)
    : ''
  const selectedAssetId =
    selectedShot && assetDraft?.shotId === selectedShot.id
      ? assetDraft.assetId
      : (selectedShot?.starting_image_asset_id ?? '')
  const selectedAssignedAsset = selectedShot?.starting_image_asset_id
    ? (assetsById.get(selectedShot.starting_image_asset_id) ?? null)
    : null
  const selectedPreviewAsset =
    selectedAssetId && assetsById.get(selectedAssetId)
      ? (assetsById.get(selectedAssetId) ?? null)
      : selectedAssignedAsset
  const selectedStatus = selectedShot ? statusOf(selectedShot) : 'Draft'
  const selectedCandidateCount = selectedShot ? candidateCountOf(selectedShot) : 0
  const selectedReadiness = selectedShot
    ? (readiness?.reasons.filter((reason) => reason.entity_id === selectedShot.id) ?? [])
    : []
  const selectedCharacters =
    selectedShot?.characters
      ?.map((link) => data?.characters.find((character) => character.id === link.character_id)?.name)
      .filter(Boolean) ?? []
  const candidateAssets = items ?? []
  const frameIndex = selectedRow ? selectedRow.index % 8 : 0
  const assignmentDirty =
    Boolean(selectedShot) && selectedAssetId !== (selectedShot?.starting_image_asset_id ?? '')

  const clearReason = firstReason(
    busyReason,
    unavailableReason,
    !selectedShot && 'Select a shot first.',
    selectedShot &&
      !selectedShot.starting_image_asset_id &&
      'No starting-image asset is assigned to this shot.',
  )
  const useSelectedReason = firstReason(
    busyReason,
    unavailableReason,
    !selectedShot && 'Select a shot first.',
    selectedShot &&
      !selectedAssetId &&
      'Choose a candidate asset before using it as the starting image.',
    selectedShot &&
      !assignmentDirty &&
      selectedAssetId &&
      'Selected candidate is already assigned to this shot.',
  )
  const approveReason = firstReason(
    busyReason,
    unavailableReason,
    !selectedShot && 'Select a shot first.',
    selectedShot &&
      !selectedAssignedAsset &&
      'Assign a managed starting-image asset before approval.',
    selectedAssignedAsset?.kind !== 'starting_image' &&
      'Only a managed starting-image asset can be approved from this page.',
    selectedAssignedAsset?.approval_state === 'archived' &&
      'Archived starting-image assets cannot be approved.',
    selectedAssignedAsset?.approval_state === 'approved' &&
      'This managed candidate is already approved.',
  )
  const uploadReason = firstReason(
    busyReason,
    unavailableReason,
    !file && 'Choose an image file to upload as a managed starting-image candidate.',
  )

  if (!data) return null

  const selectShot = (shotId: string) => {
    setSelectedShotId(shotId)
    setAssetDraft(null)
    setError(null)
  }

  const onUpload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!file || actionsBusy || !available) return
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
      const text = errorText(err, 'Could not upload the starting-image candidate.')
      setError(text)
      setMessage(text)
    } finally {
      setSaving(false)
    }
  }

  const onAssign = async (assetId: string | null = selectedAssetId || null) => {
    if (!selectedShot || actionsBusy || !available) return
    setSaving(true)
    setError(null)
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
      setMessage(
        assetId
          ? `Assigned managed starting-image ${assetId} to shot ${selectedShotCode || selectedShot.id}.`
          : `Rejected starting-image assignment on shot ${selectedShotCode || selectedShot.id}.`,
      )
    } catch (err) {
      const text = errorText(err, 'Could not update the starting-image assignment.')
      setError(text)
      setMessage(text)
    } finally {
      setSaving(false)
    }
  }

  const onApprove = async () => {
    if (!selectedShot || !selectedAssignedAsset || approveReason) return
    if (!isActiveApprovalState(selectedAssignedAsset.approval_state)) {
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
      const text = errorText(err, 'Could not approve the starting-image candidate.')
      setError(text)
      setMessage(text)
    } finally {
      setApprovalSaving(false)
    }
  }

  // Proto: [1,2,3].slice(0, Math.max(2, candidateCount)) — at least 2 compare slots.
  const compareSlotCount = Math.max(2, Math.min(3, Math.max(selectedCandidateCount, candidateAssets.length || 0)))
  const compareSlots: Array<PlanningMediaAsset | null> = Array.from({ length: compareSlotCount }, (_, i) =>
    candidateAssets[i] ?? null,
  )

  return (
    <div className="page">
      <PageTitle
        eyebrow="STARTING-IMAGE PLAN"
        title="Starting images"
        description="Plan and approve the visual anchor for every generation-ready shot."
        aside={
          <div className="page-actions">
            <Button
              type="button"
              icon="eye"
              onClick={() => setCompare((value) => !value)}
              disabled={!selectedShot}
              title={
                !selectedShot
                  ? 'Add or select a shot to compare managed candidates.'
                  : compare
                    ? 'Exit candidate comparison'
                    : 'Compare managed starting-image candidates'
              }
            >
              {compare ? 'Exit compare' : 'Compare candidates'}
            </Button>
            <Button
              type="button"
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
              {STATUS_FILTERS.map((item) => (
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
              {data.chapters.map((chapterItem, chapterIndex) => (
                <option key={chapterItem.id} value={chapterItem.id}>
                  {chapterCode(chapterIndex)}
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
                const status = statusOf(shot)
                const selected = selectedShot?.id === shot.id
                const candidates = candidateCountOf(shot)
                const code = shotCode(row.chapterIndex, row.sceneIndex, row.shotIndexInScene)
                return (
                  <button
                    key={shot.id}
                    type="button"
                    role="listitem"
                    className={selected ? 'selected' : ''}
                    onClick={() => selectShot(shot.id)}
                    aria-pressed={selected}
                  >
                    <div className={`image-placeholder frame-${row.index % 8}`}>
                      <span>
                        {candidates
                          ? `${candidates} candidate${candidates === 1 ? '' : 's'}`
                          : 'IMAGE REQUIRED'}
                      </span>
                      <Icon name={candidates ? 'image' : 'plus'} size={26} />
                    </div>
                    <div>
                      <span>
                        <code>{code}</code>
                        <b>{shot.duration_sec}s</b>
                      </span>
                      <h3>{shot.title}</h3>
                      <p>{continuityLabel(shot)}</p>
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
              detail={
                shotRows.length
                  ? `Clear filters to return to all ${shotRows.length} shots.`
                  : 'Add shots to the storyboard to plan starting images.'
              }
              action={
                shotRows.length ? (
                  <Button
                    type="button"
                    onClick={() => {
                      setFilter('All')
                      setChapter('All')
                    }}
                  >
                    Clear filters
                  </Button>
                ) : undefined
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
                  <h2>{selectedShotCode}</h2>
                </div>
                <StatusPill status={selectedStatus} />
              </header>

              {/*
                Proto review-canvas always shows title + CURRENT SELECTED IMAGE / A·B overlays.
                Empty "No candidates yet" only when candidateCount === 0.
                Managed preview image is layered under overlays when present (does not replace structure).
              */}
              <div className={`review-canvas frame-${frameIndex}`}>
                {selectedPreviewAsset?.mime_type?.startsWith('image/') ? (
                  <img
                    src={planningAssetContentUrl(selectedPreviewAsset.id)}
                    alt=""
                    style={{
                      position: 'absolute',
                      inset: 0,
                      width: '100%',
                      height: '100%',
                      objectFit: 'cover',
                      zIndex: 0,
                      pointerEvents: 'none',
                    }}
                  />
                ) : null}
                <span>{selectedShot.title}</span>
                <small>{compare ? 'A / B COMPARISON' : 'CURRENT SELECTED IMAGE'}</small>
                {!selectedCandidateCount ? (
                  <div>
                    <Icon name="image" size={34} />
                    <b>No candidates yet</b>
                  </div>
                ) : null}
              </div>

              {compare ? (
                <div className="candidate-compare">
                  {compareSlots.map((asset, index) => (
                    <button
                      key={asset?.id ?? `placeholder-${index}`}
                      type="button"
                      className={`candidate frame-${(frameIndex + index + 1) % 8}`}
                      disabled={!asset || actionsBusy}
                      title={
                        asset
                          ? `Select ${asset.original_filename ?? asset.id} for assignment`
                          : 'No managed candidate is available for this slot.'
                      }
                      onClick={() => {
                        if (!asset || !selectedShot) return
                        setAssetDraft({ shotId: selectedShot.id, assetId: asset.id })
                        setMessage(
                          `Candidate ${index + 1} selected (${asset.original_filename ?? asset.id}).`,
                        )
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
                  <b>{dimensionsLabel(selectedPreviewAsset, selectedCandidateCount > 0)}</b>
                </div>
                <div>
                  <span>Model</span>
                  <b>{modelLabel(selectedShot)}</b>
                </div>
                <div>
                  <span>Seed</span>
                  <b>{seedLabel(selectedPreviewAsset, selectedCandidateCount > 0)}</b>
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
                    title="Prompt text is managed on the Storyboard / prompt package surfaces; read-only here."
                  />
                </label>
                <label>
                  Negative prompt
                  <textarea
                    className="prompt"
                    readOnly
                    value={selectedShot.prompt_negative || 'None recorded.'}
                    title="Prompt text is managed on the Storyboard / prompt package surfaces; read-only here."
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
                  <input
                    readOnly
                    value={selectedShot.location || 'None recorded'}
                    title="Location is edited on the Storyboard shot inspector; read-only here."
                  />
                </label>
                <label>
                  Style lock
                  <textarea
                    className="prompt"
                    readOnly
                    value={selectedShot.prompt_style_lock || 'None recorded.'}
                    title="Style lock is managed on the Storyboard / prompt package surfaces; read-only here."
                  />
                </label>
                <label>
                  Continuity source
                  <input
                    readOnly
                    value={continuityLabel(selectedShot)}
                    title="Continuity is edited on the Storyboard shot inspector; read-only here."
                  />
                </label>

                {/* Production-only: candidate pick + upload (below proto fields; scroll). */}
                <label>
                  Candidate asset
                  <select
                    value={selectedAssetId}
                    onChange={(event) =>
                      setAssetDraft({ shotId: selectedShot.id, assetId: event.target.value })
                    }
                    disabled={actionsBusy || !available}
                    title={firstReason(busyReason, unavailableReason)}
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
                ) : null}

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
                      disabled={actionsBusy || !available}
                      title={firstReason(busyReason, unavailableReason)}
                    />
                  </label>
                  {file ? (
                    <p className="form-hint">
                      {file.name} · {formatBytes(file.size)}
                    </p>
                  ) : null}
                  <Button type="submit" disabled={Boolean(uploadReason)} title={uploadReason}>
                    {saving ? 'Uploading…' : 'Upload managed candidate'}
                  </Button>
                </form>
              </div>

              <footer>
                <Button
                  type="button"
                  variant="danger"
                  disabled={Boolean(clearReason)}
                  title={clearReason}
                  onClick={() => void onAssign(null)}
                >
                  Reject
                </Button>
                <Button
                  type="button"
                  onClick={() => void onAssign()}
                  disabled={Boolean(useSelectedReason)}
                  title={useSelectedReason}
                >
                  {saving ? 'Saving…' : 'Use selected'}
                </Button>
                <Button
                  type="button"
                  variant="primary"
                  onClick={() => void onApprove()}
                  disabled={Boolean(approveReason)}
                  title={approveReason}
                >
                  {approvalSaving ? 'Approving…' : 'Approve selected'}
                </Button>
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
