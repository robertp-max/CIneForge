import { useEffect, useState, type FormEvent } from 'react'
import {
  api,
  type Character,
  type RuntimeCatalog,
  type Shot,
  type ShotCharacterLink,
  type ShotNarrationPayload,
  type ShotPromptPackagePayload,
  type ShotUpdatePayload,
  type Voice,
} from '../../api/client'
import { useStudio } from '../StudioState'
import { shotCodeFromLabel, startingFrameUrl } from '../mediaUrls'
import { formatDuration } from '../utils'
import { EmptyState } from '../components/StateBlocks'

type InspectorTab = 'details' | 'prompts' | 'cast' | 'technical'

function errorText(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback
}

function ShotInspector({
  shot,
  busy,
  onSave,
  onSaveNarration,
  onSavePromptPackage,
  characters,
  voices,
  runtimeCatalog,
  onRefresh,
  onMessage,
}: {
  shot: Shot
  busy: boolean
  onSave: (shotId: string, payload: ShotUpdatePayload) => Promise<void>
  onSaveNarration: (shotId: string, payload: ShotNarrationPayload) => Promise<void>
  onSavePromptPackage: (shotId: string, payload: ShotPromptPackagePayload) => Promise<void>
  characters: Character[]
  voices: Voice[]
  runtimeCatalog: RuntimeCatalog | null
  onRefresh: () => Promise<void>
  onMessage: (message: string) => void
}) {
  const [tab, setTab] = useState<InspectorTab>('details')
  const [draft, setDraft] = useState(shot)
  const [characterLinks, setCharacterLinks] = useState<ShotCharacterLink[]>(shot.characters ?? [])
  const [recommendationKind, setRecommendationKind] = useState<'generation' | 'workflow'>('generation')
  const [recommendationTargetId, setRecommendationTargetId] = useState('')
  const [recommendationRationale, setRecommendationRationale] = useState('')
  const [actionBusy, setActionBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const disabled = busy || actionBusy

  const save = () => {
    void onSave(draft.id, {
      order_index: draft.order_index,
      title: draft.title,
      duration_sec: draft.duration_sec,
      duration_override_reason: draft.duration_override_reason,
      story_purpose: draft.story_purpose,
      visual_description: draft.visual_description,
      location: draft.location,
      camera_direction: draft.camera_direction,
      motion_direction: draft.motion_direction,
      continuity_source_type: draft.continuity_source_type,
      continuity_source_shot_id: draft.continuity_source_shot_id,
      starting_image_required: draft.starting_image_required,
      starting_image_asset_id: draft.starting_image_asset_id,
    })
  }

  const saveNarration = () => {
    const narrationText = draft.narration?.trim() || null
    const exceptionReason = draft.narration_exception_reason?.trim() || null
    if (!narrationText && !exceptionReason) return
    void onSaveNarration(draft.id, {
      voice_profile_id: draft.narration_voice_profile_id ?? null,
      narration_text: narrationText,
      start_offset_sec: draft.narration_start_offset_sec ?? 0,
      expected_duration_sec: draft.narration_expected_duration_sec ?? null,
      narration_exception_reason: exceptionReason,
      // Editing narration returns it to draft for explicit review.
      approval_state: 'draft',
    })
  }

  const savePromptPackage = () => {
    void onSavePromptPackage(draft.id, {
      image_prompt: draft.prompt_positive?.trim() || null,
      video_prompt: draft.prompt_video?.trim() || null,
      negative_prompt: draft.prompt_negative?.trim() || null,
      continuity_instructions: draft.prompt_continuity_instructions?.trim() || null,
      style_lock_prompt: draft.prompt_style_lock?.trim() || null,
      provider_profile_id: draft.prompt_provider_profile_id ?? null,
      provider_model_id: draft.prompt_provider_model_id?.trim() || null,
      proposal_id: draft.prompt_proposal_id ?? null,
      approval_state: 'draft',
    })
  }

  async function saveLifecycle() {
    setActionBusy(true)
    setActionError(null)
    try {
      await api.patchShot(draft.id, {
        approval_state: draft.approval_state as 'draft' | 'in_review' | 'approved' | 'blocked',
        production_status: draft.production_status,
        blocked_reason:
          draft.production_status === 'blocked' ? draft.blocked_reason?.trim() || null : null,
        camera_direction: draft.camera_direction?.trim() || null,
        motion_direction: draft.motion_direction?.trim() || null,
      })
      await onRefresh()
      onMessage('Shot lifecycle, blocker, and production fields saved to the backend.')
    } catch (error) {
      setActionError(errorText(error, 'Could not save shot lifecycle fields.'))
    } finally {
      setActionBusy(false)
    }
  }

  async function saveCharacterLinks() {
    setActionBusy(true)
    setActionError(null)
    try {
      await api.replaceShotCharacters(
        draft.id,
        characterLinks.map((link, order_index) => ({ ...link, order_index })),
      )
      await onRefresh()
      onMessage('Ordered shot character assignments saved to the backend.')
    } catch (error) {
      setActionError(errorText(error, 'Could not save shot character assignments.'))
    } finally {
      setActionBusy(false)
    }
  }

  async function createRecommendation(event: FormEvent) {
    event.preventDefault()
    if (!recommendationTargetId) return
    setActionBusy(true)
    setActionError(null)
    try {
      const selectedVariant = runtimeCatalog?.model_variants.find(
        (item) => item.id === recommendationTargetId,
      )
      const selectedWorkflow = runtimeCatalog?.workflow_templates.find(
        (item) => item.id === recommendationTargetId,
      )
      await api.createShotRecommendation(draft.id, {
        recommendation_type: recommendationKind,
        generation_model_variant_id:
          recommendationKind === 'generation' ? recommendationTargetId : null,
        workflow_template_id:
          recommendationKind === 'workflow' ? recommendationTargetId : null,
        rationale: recommendationRationale.trim() || null,
        availability_status:
          selectedVariant?.path_status ?? selectedWorkflow?.registration_status ?? 'unknown',
        benchmark_status:
          selectedVariant?.benchmark_status ?? selectedWorkflow?.benchmark_status ?? 'unknown',
        risk_status: 'unknown',
        approval_state: 'draft',
      })
      setRecommendationTargetId('')
      setRecommendationRationale('')
      await onRefresh()
      onMessage('Model/workflow recommendation saved as planning metadata.')
    } catch (error) {
      setActionError(errorText(error, 'Could not create the recommendation.'))
    } finally {
      setActionBusy(false)
    }
  }

  async function updateRecommendation(
    recommendationId: string,
    payload: { acknowledge?: boolean; approval_state?: 'draft' | 'in_review' | 'approved' | 'blocked' },
  ) {
    setActionBusy(true)
    setActionError(null)
    try {
      await api.updateShotRecommendation(recommendationId, payload)
      await onRefresh()
      onMessage(payload.acknowledge ? 'Recommendation acknowledged.' : 'Recommendation review state updated.')
    } catch (error) {
      setActionError(errorText(error, 'Could not update the recommendation.'))
    } finally {
      setActionBusy(false)
    }
  }

  async function deleteRecommendation(recommendationId: string) {
    if (!window.confirm('Delete this persisted recommendation?')) return
    setActionBusy(true)
    setActionError(null)
    try {
      await api.deleteShotRecommendation(recommendationId)
      await onRefresh()
      onMessage('Recommendation deleted from the planning record.')
    } catch (error) {
      setActionError(errorText(error, 'Could not delete the recommendation.'))
    } finally {
      setActionBusy(false)
    }
  }

  return (
    <>
      <p className="eyebrow mono">{draft.id}</p>

      <div className="inspector-tabs" role="tablist" aria-label="Inspector sections">
        {(
          [
            ['details', 'Details'],
            ['prompts', 'Prompts'],
            ['cast', 'Cast & routing'],
            ['technical', 'Technical'],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'details' ? (
        <div role="tabpanel">
          <label>
            Title
            <input
              value={draft.title}
              onChange={(event) => setDraft({ ...draft, title: event.target.value })}
              disabled={busy}
            />
          </label>
          <label>
            Duration (sec)
            <input
              type="number"
              min={0.1}
              step={0.1}
              value={draft.duration_sec}
              onChange={(event) => setDraft({ ...draft, duration_sec: Number(event.target.value) })}
              disabled={busy}
            />
          </label>
          <label>
            Override reason
            <input
              value={draft.duration_override_reason ?? ''}
              onChange={(event) => setDraft({ ...draft, duration_override_reason: event.target.value || null })}
              disabled={busy}
            />
          </label>
          <label>
            Story purpose
            <textarea
              value={draft.story_purpose ?? ''}
              onChange={(event) => setDraft({ ...draft, story_purpose: event.target.value || null })}
              disabled={busy}
            />
          </label>
          <label>
            Visual description
            <textarea
              value={draft.visual_description ?? ''}
              onChange={(event) => setDraft({ ...draft, visual_description: event.target.value || null })}
              disabled={busy}
            />
          </label>
          <label>
            Location
            <input
              value={draft.location ?? ''}
              onChange={(event) => setDraft({ ...draft, location: event.target.value || null })}
              disabled={busy}
            />
          </label>
          <label>
            Narration
            <textarea
              value={draft.narration ?? ''}
              onChange={(event) => setDraft({ ...draft, narration: event.target.value || null })}
              disabled={busy}
            />
          </label>
          <label>
            Narration exception reason
            <textarea
              value={draft.narration_exception_reason ?? ''}
              onChange={(event) => setDraft({ ...draft, narration_exception_reason: event.target.value || null })}
              disabled={busy}
            />
          </label>
          <label>
            Narration voice profile
            <select
              value={draft.narration_voice_profile_id ?? ''}
              onChange={(event) => setDraft({ ...draft, narration_voice_profile_id: event.target.value || null })}
              disabled={busy}
            >
              <option value="">No voice assigned</option>
              {voices.map((voice) => (
                <option key={voice.id} value={voice.id}>{voice.name} · {voice.approval_state}</option>
              ))}
            </select>
          </label>
          <div className="split-2">
            <label>
              Start offset (sec)
              <input
                type="number"
                min={0}
                step={0.1}
                value={draft.narration_start_offset_sec ?? 0}
                onChange={(event) => setDraft({ ...draft, narration_start_offset_sec: Number(event.target.value) })}
                disabled={busy}
              />
            </label>
            <label>
              Expected duration (sec)
              <input
                type="number"
                min={0.1}
                step={0.1}
                value={draft.narration_expected_duration_sec ?? ''}
                onChange={(event) => setDraft({
                  ...draft,
                  narration_expected_duration_sec: event.target.value ? Number(event.target.value) : null,
                })}
                disabled={busy}
              />
            </label>
          </div>
          <p className="form-hint">
            Narration saves through its canonical resource and requires text or an exception reason.
          </p>
        </div>
      ) : null}

      {tab === 'prompts' ? (
        <div role="tabpanel">
          <p className="form-hint">
            Saving creates a new canonical prompt-package version; it never invokes a model or starts generation.
          </p>
          <label>
            Image prompt
            <textarea
              value={draft.prompt_positive ?? ''}
              onChange={(event) => setDraft({ ...draft, prompt_positive: event.target.value || null })}
              disabled={busy}
            />
          </label>
          <label>
            Video prompt
            <textarea
              value={draft.prompt_video ?? ''}
              onChange={(event) => setDraft({ ...draft, prompt_video: event.target.value || null })}
              disabled={busy}
            />
          </label>
          <label>
            Negative prompt
            <textarea
              value={draft.prompt_negative ?? ''}
              onChange={(event) => setDraft({ ...draft, prompt_negative: event.target.value || null })}
              disabled={busy}
            />
          </label>
          <label>
            Continuity instructions
            <textarea
              value={draft.prompt_continuity_instructions ?? ''}
              onChange={(event) => setDraft({ ...draft, prompt_continuity_instructions: event.target.value || null })}
              disabled={busy}
            />
          </label>
          <label>
            Style lock prompt
            <textarea
              value={draft.prompt_style_lock ?? ''}
              onChange={(event) => setDraft({ ...draft, prompt_style_lock: event.target.value || null })}
              disabled={busy}
            />
          </label>
        </div>
      ) : null}

      {tab === 'cast' ? (
        <div role="tabpanel" className="stack-form" style={{ maxWidth: '100%' }}>
          <div>
            <h3>Character assignments</h3>
            <p className="form-hint">
              Checked characters and their roles are persisted as ordered shot-character links.
            </p>
          </div>
          {characters.length ? characters.map((character) => {
            const link = characterLinks.find((item) => item.character_id === character.id)
            return (
              <div key={character.id} className="notice info">
                <label style={{ gridTemplateColumns: 'auto 1fr', alignItems: 'center' }}>
                  <input
                    type="checkbox"
                    checked={Boolean(link)}
                    disabled={disabled}
                    style={{ width: 20, height: 20, minHeight: 20 }}
                    onChange={(event) => {
                      if (event.target.checked) {
                        setCharacterLinks((current) => [
                          ...current,
                          {
                            character_id: character.id,
                            order_index: current.length,
                            role_in_shot: character.role,
                            continuity_notes: null,
                          },
                        ])
                      } else {
                        setCharacterLinks((current) =>
                          current
                            .filter((item) => item.character_id !== character.id)
                            .map((item, order_index) => ({ ...item, order_index })),
                        )
                      }
                    }}
                  />
                  <span>{character.name}</span>
                </label>
                {link ? (
                  <label>
                    Role in shot
                    <input
                      value={link.role_in_shot ?? ''}
                      disabled={disabled}
                      onChange={(event) => setCharacterLinks((current) =>
                        current.map((item) => item.character_id === character.id
                          ? { ...item, role_in_shot: event.target.value || null }
                          : item),
                      )}
                    />
                  </label>
                ) : null}
              </div>
            )
          }) : <p className="form-hint">No characters exist in this story.</p>}
          <button type="button" className="secondary-button" disabled={disabled} onClick={() => void saveCharacterLinks()}>
            Save character assignments
          </button>

          <div>
            <h3>Model / workflow recommendations</h3>
            <p className="form-hint">
              Recommendations are planning metadata only. Saving or acknowledging one never submits a render.
            </p>
          </div>
          {draft.recommendations?.length ? (
            <div className="stack-form" style={{ maxWidth: '100%' }}>
              {draft.recommendations.map((recommendation) => (
                <article className="notice info" key={recommendation.id}>
                  <strong>{recommendation.recommendation_type} · {recommendation.approval_state}</strong>
                  <p>{recommendation.rationale || 'No rationale recorded.'}</p>
                  <small>
                    Availability {recommendation.availability_status} · benchmark {recommendation.benchmark_status}
                    {recommendation.acknowledged_at ? ` · acknowledged ${recommendation.acknowledged_at}` : ''}
                  </small>
                  <div className="inline-actions" style={{ marginTop: 8 }}>
                    <button
                      type="button"
                      className="ghost-button"
                      disabled={disabled || Boolean(recommendation.acknowledged_at)}
                      onClick={() => void updateRecommendation(recommendation.id, { acknowledge: true })}
                    >
                      {recommendation.acknowledged_at ? 'Acknowledged' : 'Acknowledge'}
                    </button>
                    <button
                      type="button"
                      className="ghost-button"
                      disabled={disabled || recommendation.approval_state === 'in_review'}
                      onClick={() => void updateRecommendation(recommendation.id, { approval_state: 'in_review' })}
                    >
                      Mark in review
                    </button>
                    <button
                      type="button"
                      className="ghost-button"
                      disabled={disabled}
                      onClick={() => void deleteRecommendation(recommendation.id)}
                    >
                      Delete
                    </button>
                  </div>
                </article>
              ))}
            </div>
          ) : <p className="form-hint">No recommendation is persisted for this shot.</p>}
          <form className="stack-form" style={{ maxWidth: '100%' }} onSubmit={(event) => void createRecommendation(event)}>
            <label>
              Recommendation target type
              <select
                value={recommendationKind}
                disabled={disabled}
                onChange={(event) => {
                  setRecommendationKind(event.target.value as 'generation' | 'workflow')
                  setRecommendationTargetId('')
                }}
              >
                <option value="generation">Generation model variant</option>
                <option value="workflow">Workflow template</option>
              </select>
            </label>
            <label>
              Catalog target
              <select value={recommendationTargetId} onChange={(event) => setRecommendationTargetId(event.target.value)} disabled={disabled}>
                <option value="">Select a factual catalog record</option>
                {recommendationKind === 'generation'
                  ? runtimeCatalog?.model_variants.map((variant) => (
                      <option key={variant.id} value={variant.id}>{variant.variant_name} · {variant.path_status} · {variant.benchmark_status}</option>
                    ))
                  : runtimeCatalog?.workflow_templates.map((workflow) => (
                      <option key={workflow.id} value={workflow.id}>{workflow.name} {workflow.version} · {workflow.registration_status}</option>
                    ))}
              </select>
            </label>
            <label>
              Rationale
              <textarea value={recommendationRationale} onChange={(event) => setRecommendationRationale(event.target.value)} disabled={disabled} />
            </label>
            <button type="submit" className="secondary-button" disabled={disabled || !recommendationTargetId}>
              Save recommendation
            </button>
            {!runtimeCatalog ? <p className="notice warning">Runtime catalog is unavailable; new recommendations cannot be created, but existing records remain reviewable.</p> : null}
          </form>
        </div>
      ) : null}

      {tab === 'technical' ? (
        <div role="tabpanel">
          <label>
            Continuity source type
            <select
              value={draft.continuity_source_type}
              onChange={(event) => setDraft({
                ...draft,
                continuity_source_type: event.target.value,
                continuity_source_shot_id: event.target.value === 'none' ? null : draft.continuity_source_shot_id,
              })}
              disabled={busy}
            >
              <option value="none">None</option>
              <option value="previous_shot">Previous shot</option>
              <option value="shot_ref">Specific shot reference</option>
              <option value="starting_image">Starting image</option>
            </select>
          </label>
          <label>
            Continuity source shot ID
            <input
              value={draft.continuity_source_shot_id ?? ''}
              onChange={(event) => setDraft({ ...draft, continuity_source_shot_id: event.target.value || null })}
              disabled={busy || draft.continuity_source_type === 'none'}
              className="mono"
            />
          </label>
          <label style={{ gridTemplateColumns: 'auto 1fr', alignItems: 'center' }}>
            <input
              type="checkbox"
              checked={draft.starting_image_required}
              onChange={(event) => setDraft({ ...draft, starting_image_required: event.target.checked })}
              disabled={busy}
              style={{ width: 20, height: 20, minHeight: 20 }}
            />
            <span>Starting image required</span>
          </label>
          <label>
            Starting image asset ID
            <input
              value={draft.starting_image_asset_id ?? ''}
              onChange={(event) => setDraft({ ...draft, starting_image_asset_id: event.target.value || null })}
              disabled={busy}
              className="mono"
            />
          </label>
          <label>
            Camera direction
            <textarea
              value={draft.camera_direction ?? ''}
              onChange={(event) => setDraft({ ...draft, camera_direction: event.target.value || null })}
              disabled={disabled}
            />
          </label>
          <label>
            Motion direction
            <textarea
              value={draft.motion_direction ?? ''}
              onChange={(event) => setDraft({ ...draft, motion_direction: event.target.value || null })}
              disabled={disabled}
            />
          </label>
          <label>
            Shot approval state
            <select
              value={draft.approval_state}
              onChange={(event) => setDraft({ ...draft, approval_state: event.target.value })}
              disabled={disabled}
            >
              <option value="draft">Draft</option>
              <option value="in_review">In review</option>
              <option value="approved">Approved</option>
              <option value="blocked">Blocked</option>
            </select>
          </label>
          <label>
            Production status
            <input
              list={`production-status-${draft.id}`}
              value={draft.production_status}
              onChange={(event) => setDraft({ ...draft, production_status: event.target.value })}
              disabled={disabled}
            />
            <datalist id={`production-status-${draft.id}`}>
              <option value="planned" />
              <option value="ready" />
              <option value="blocked" />
              <option value="complete" />
            </datalist>
          </label>
          <label>
            Blocked reason
            <textarea
              value={draft.blocked_reason ?? ''}
              onChange={(event) => setDraft({ ...draft, blocked_reason: event.target.value || null })}
              disabled={disabled || draft.production_status !== 'blocked'}
              required={draft.production_status === 'blocked'}
              placeholder="Required when production status is blocked"
            />
          </label>
          <p className="form-hint">
            The backend requires a blocker reason when production status is blocked and clears the reason for other statuses.
          </p>
        </div>
      ) : null}

      {actionError ? <p className="notice error" role="alert">{actionError}</p> : null}

      <div className="inline-actions" style={{ marginTop: 14 }}>
        {tab === 'details' ? (
          <>
            <button type="button" className="primary-button touch-target" disabled={busy} onClick={save}>
              Save shot details
            </button>
            <button
              type="button"
              className="secondary-button touch-target"
              disabled={busy || (!draft.narration?.trim() && !draft.narration_exception_reason?.trim())}
              onClick={saveNarration}
            >
              Save narration
            </button>
          </>
        ) : null}
        {tab === 'prompts' ? (
          <button type="button" className="primary-button touch-target" disabled={busy} onClick={savePromptPackage}>
            Save new prompt version
          </button>
        ) : null}
        {tab === 'technical' ? (
          <button
            type="button"
            className="primary-button touch-target"
            disabled={disabled || !draft.production_status.trim() || (draft.production_status === 'blocked' && !draft.blocked_reason?.trim())}
            onClick={() => void saveLifecycle()}
          >
            Save technical and lifecycle fields
          </button>
        ) : null}
      </div>
    </>
  )
}

type ShotFilter = 'all' | 'draft' | 'review' | 'approved' | 'blocked'

function matchesShotFilter(shot: { approval_state: string; production_status: string }, filter: ShotFilter) {
  if (filter === 'all') return true
  const state = (shot.approval_state || '').toLowerCase()
  if (filter === 'blocked') return shot.production_status === 'blocked' || state === 'blocked'
  if (filter === 'approved') return state === 'approved'
  if (filter === 'review') return state === 'in_review' || state === 'review' || state === 'needs_review'
  if (filter === 'draft') return state === 'draft' || state === '' || state === 'pending'
  return true
}

function shortTitle(title: string, max = 28) {
  const t = title.trim()
  return t.length > max ? `${t.slice(0, max - 1)}…` : t
}

export function StoryboardPage() {
  const {
    data,
    selectedShot,
    setSelectedShot,
    addHierarchy,
    saveShot,
    saveNarration,
    savePromptPackage,
    busy,
    reload,
    setMessage,
  } = useStudio()
  const [runtimeCatalog, setRuntimeCatalog] = useState<RuntimeCatalog | null>(null)
  const [filter, setFilter] = useState<ShotFilter>('all')
  const [collapsedChapterIds, setCollapsedChapterIds] = useState<string[]>([])
  const [inspectorOpen, setInspectorOpen] = useState(true)

  useEffect(() => {
    let active = true
    void api.runtimeCatalog().then((catalog) => {
      if (active) setRuntimeCatalog(catalog)
    }).catch(() => {
      if (active) setRuntimeCatalog(null)
    })
    return () => {
      active = false
    }
  }, [])

  if (!data) return null

  const mediaScope = {
    projectId: data.story.project_id,
    storyTitle: data.story.title,
  }

  // Global scene ordinal for S##X codes (matches ProductionPhasePreview / static pack).
  const sceneNumberById = new Map<string, number>()
  let sceneOrdinal = 0
  for (const chapter of data.chapters) {
    for (const scene of chapter.scenes) {
      sceneOrdinal += 1
      sceneNumberById.set(scene.id, sceneOrdinal)
    }
  }

  const allShots = data.chapters.flatMap((chapter) => chapter.scenes.flatMap((scene) => scene.shots))
  const totalShots = allShots.length
  const approvedShots = allShots.filter((shot) => shot.approval_state === 'approved').length
  const progressPct = totalShots > 0 ? Math.round((approvedShots / totalShots) * 100) : 0
  const filterCounts: Record<ShotFilter, number> = {
    all: totalShots,
    draft: allShots.filter((s) => matchesShotFilter(s, 'draft')).length,
    review: allShots.filter((s) => matchesShotFilter(s, 'review')).length,
    approved: approvedShots,
    blocked: allShots.filter((s) => matchesShotFilter(s, 'blocked')).length,
  }
  const targetLabel = formatDuration(data.story.target_duration_sec)

  return (
    <div className={`page storyboard-page${inspectorOpen ? '' : ' inspector-closed'}`}>
      <div className="page-title">
        <div>
          <span className="eyebrow">STORYBOARD WORKSPACE</span>
          <h1>Production storyboard</h1>
          <p>
            Review all {totalShots} planned shots across the {targetLabel} target.
          </p>
        </div>
        <div className="page-actions">
          <div className="readiness-block">
            <span>
              <b>{progressPct}%</b> storyboard readiness
            </span>
            <div className="progress" role="progressbar" aria-valuenow={progressPct} aria-valuemin={0} aria-valuemax={100}>
              <i style={{ width: `${progressPct}%` }} />
            </div>
            <small>
              {approvedShots} of {totalShots} shots approved
            </small>
          </div>
        </div>
      </div>

      <div className={`storyboard-layout${inspectorOpen ? '' : ' inspector-closed'}`}>
        <div className="storyboard-main">
          <div className="toolbar">
            <div className="segmented" role="group" aria-label="Shot filter">
              {(
                [
                  ['all', 'All'],
                  ['draft', 'Draft'],
                  ['review', 'Review'],
                  ['approved', 'Approved'],
                  ['blocked', 'Blocked'],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  className={filter === id ? 'active' : ''}
                  onClick={() => setFilter(id)}
                >
                  {label}
                  <em>{filterCounts[id]}</em>
                </button>
              ))}
            </div>
            <div>
              <button
                type="button"
                className="btn secondary touch-target"
                disabled={busy}
                onClick={() => void addHierarchy('chapter')}
              >
                + Chapter
              </button>
              <button
                type="button"
                className="btn secondary touch-target"
                disabled={busy}
                onClick={() => void addHierarchy('scene')}
              >
                + Scene
              </button>
              <button
                type="button"
                className="btn secondary touch-target"
                disabled={busy}
                onClick={() => void addHierarchy('shot')}
              >
                + Shot
              </button>
            </div>
          </div>

          {!data.chapters.length ? (
            <EmptyState
              title="No chapters yet"
              detail="Add a chapter to begin the ordered production hierarchy."
              action={
                <button
                  type="button"
                  className="btn primary"
                  disabled={busy}
                  onClick={() => void addHierarchy('chapter')}
                >
                  Add chapter
                </button>
              }
            />
          ) : (
            data.chapters.map((chapter, index) => {
              const open = !collapsedChapterIds.includes(chapter.id)
              const chapterShots = chapter.scenes.flatMap((s) => s.shots)
              const visibleShotCount = chapterShots.filter((s) => matchesShotFilter(s, filter)).length
              return (
                <section className="chapter-group" key={chapter.id}>
                  <button
                    type="button"
                    className="chapter-bar"
                    aria-expanded={open}
                    onClick={() =>
                      setCollapsedChapterIds((ids) =>
                        open ? [...ids, chapter.id] : ids.filter((id) => id !== chapter.id),
                      )
                    }
                  >
                    <span className="hierarchy-chevron" aria-hidden="true">
                      {open ? '▾' : '▸'}
                    </span>
                    <span>
                      <small>CH{String(index + 1).padStart(2, '0')}</small>
                      <b>{shortTitle(chapter.title, 48)}</b>
                    </span>
                    <span>
                      <b>{formatDuration(chapter.duration_sec)}</b>
                      <small>
                        {chapter.scenes.length} scene{chapter.scenes.length === 1 ? '' : 's'} ·{' '}
                        {visibleShotCount}/{chapterShots.length} shots
                      </small>
                    </span>
                    <span className="status-pill" data-status={chapterShots.every((s) => s.approval_state === 'approved') ? 'approved' : 'draft'}>
                      {chapterShots.every((s) => s.approval_state === 'approved') ? 'Approved' : 'In progress'}
                    </span>
                  </button>
                  {open
                    ? chapter.scenes.map((scene, sceneIndex) => {
                        const filteredShots = scene.shots.filter((s) => matchesShotFilter(s, filter))
                        if (filter !== 'all' && !filteredShots.length) return null
                        return (
                          <div className="scene-block" key={scene.id} aria-label={`Scene ${scene.title}`}>
                            <div className="scene-row scene-name">
                              <span>
                                SC{String(sceneIndex + 1).padStart(2, '0')} · {shortTitle(scene.title, 40)}
                              </span>
                              <small>
                                {formatDuration(scene.duration_sec)} · {filteredShots.length} shot
                                {filteredShots.length === 1 ? '' : 's'}
                              </small>
                            </div>
                            <div className="shot-strip" role="list">
                              {(filter === 'all' ? scene.shots : filteredShots).map((shot, shotIndex) => {
                                const sceneNumber = sceneNumberById.get(scene.id) ?? sceneIndex + 1
                                const letter =
                                  shot.order_index < 26
                                    ? String.fromCharCode(65 + shot.order_index)
                                    : String(shot.order_index + 1)
                                const syntheticCode = `S${String(sceneNumber).padStart(2, '0')}${letter}`
                                const shotCode =
                                  shotCodeFromLabel(shot.title) ||
                                  shotCodeFromLabel(shot.display_label) ||
                                  syntheticCode
                                const frameUrl = startingFrameUrl({
                                  title: shot.title,
                                  code: shotCode,
                                  assetId: shot.starting_image_asset_id,
                                  ...mediaScope,
                                })
                                const frameLabel = shotCode
                                return (
                                  <button
                                    key={shot.id}
                                    type="button"
                                    role="listitem"
                                    className={`shot-card ${selectedShot?.id === shot.id ? 'selected' : ''}`}
                                    aria-pressed={selectedShot?.id === shot.id}
                                    onClick={() => {
                                      setSelectedShot(shot)
                                      setInspectorOpen(true)
                                    }}
                                  >
                                    <div
                                      className={`frame-art frame-${shotIndex % 8}${frameUrl ? ' has-image' : ''}`}
                                    >
                                      {frameUrl ? (
                                        <img
                                          src={frameUrl}
                                          alt={`${frameLabel} starting frame`}
                                          loading="lazy"
                                          decoding="async"
                                          onError={(event) => {
                                            const img = event.currentTarget
                                            img.style.display = 'none'
                                            img.parentElement?.classList.remove('has-image')
                                          }}
                                        />
                                      ) : null}
                                      <span>{frameLabel}</span>
                                    </div>
                                    <div>
                                      <span>
                                        <code>{frameLabel}</code>
                                        <b>{shot.duration_sec}s</b>
                                      </span>
                                      <strong>{shortTitle(shot.title, 26)}</strong>
                                      <small>
                                        <span className="status-pill" data-status={shot.approval_state || 'draft'}>
                                          {shot.approval_state || 'draft'}
                                        </span>
                                        {shot.production_status === 'blocked' ? ' · blocked' : ''}
                                      </small>
                                    </div>
                                  </button>
                                )
                              })}
                              {!scene.shots.length ? (
                                <p className="form-hint" style={{ margin: 0 }}>
                                  No shots in this scene.
                                </p>
                              ) : null}
                            </div>
                          </div>
                        )
                      })
                    : null}
                  {open && !chapter.scenes.length ? (
                    <div className="scene-block">
                      <p className="form-hint">No scenes in this chapter yet.</p>
                    </div>
                  ) : null}
                </section>
              )
            })
          )}
        </div>

        {inspectorOpen ? (
          <aside className="inspector" aria-label="Shot inspector">
            <header className="inspector-header">
              <div>
                <span className="eyebrow">SHOT {selectedShot?.display_label || selectedShot?.title || '—'}</span>
                <h2>{selectedShot ? shortTitle(selectedShot.title, 36) : 'Shot inspector'}</h2>
                {selectedShot ? (
                  <span className="status-pill" data-status={selectedShot.approval_state || 'draft'}>
                    {selectedShot.approval_state || 'draft'}
                  </span>
                ) : null}
              </div>
              <button
                type="button"
                className="icon-button"
                aria-label="Close shot inspector"
                onClick={() => setInspectorOpen(false)}
              >
                ×
              </button>
            </header>
            {selectedShot ? (
              <ShotInspector
                key={`${selectedShot.id}-${data.revision}`}
                shot={selectedShot}
                busy={busy}
                onSave={saveShot}
                onSaveNarration={saveNarration}
                onSavePromptPackage={savePromptPackage}
                characters={data.characters}
                voices={data.voices}
                runtimeCatalog={runtimeCatalog}
                onRefresh={() => reload(data.story.id)}
                onMessage={setMessage}
              />
            ) : (
              <p className="form-hint">
                Select a shot to inspect persisted details, prompts, and technical planning information.
              </p>
            )}
          </aside>
        ) : (
          <button
            type="button"
            className="open-inspector btn secondary"
            onClick={() => setInspectorOpen(true)}
          >
            Open inspector
          </button>
        )}
      </div>
    </div>
  )
}
