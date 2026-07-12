/**
 * Structural port of prototype StoryboardPage (pagesCore.tsx) adapted to
 * production studio context + shot save / narration / prompt APIs.
 */
import { useEffect, useMemo, useState, type FormEvent } from 'react'
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
import { Button, Icon, PageTitle, Progress, Section, StatusPill } from '../../components/ui'
import { useStudio } from '../StudioState'
import { formatDuration } from '../utils'
import { EmptyState } from '../components/StateBlocks'
import { toProtoProject, type ProtoStatus } from '../proto/adapter'

type InspectorTab = 'details' | 'prompts' | 'technical' | 'cast'
type StatusFilter = 'All' | 'Draft' | 'Review' | 'Approved' | 'Blocked'

function errorText(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback
}

function approvalToProto(state: string): ProtoStatus {
  const v = (state ?? 'draft').toLowerCase()
  if (v === 'approved') return 'Approved'
  if (v === 'blocked') return 'Blocked'
  if (v === 'in_review' || v === 'review') return 'Review'
  return 'Draft'
}

function protoToApproval(status: ProtoStatus): 'draft' | 'in_review' | 'approved' | 'blocked' {
  if (status === 'Approved') return 'approved'
  if (status === 'Blocked') return 'blocked'
  if (status === 'Review') return 'in_review'
  return 'draft'
}

function chapterLabel(index: number): string {
  return `CH${String(index + 1).padStart(2, '0')}`
}

function sceneLabel(index: number): string {
  return `SC${String(index + 1).padStart(2, '0')}`
}

function ShotInspector({
  shot,
  busy,
  edit,
  onSave,
  onSaveNarration,
  onSavePromptPackage,
  characters,
  voices,
  runtimeCatalog,
  onRefresh,
  onMessage,
  onApprove,
  onRequestChanges,
}: {
  shot: Shot
  busy: boolean
  edit: boolean
  onSave: (shotId: string, payload: ShotUpdatePayload) => Promise<void>
  onSaveNarration: (shotId: string, payload: ShotNarrationPayload) => Promise<void>
  onSavePromptPackage: (shotId: string, payload: ShotPromptPackagePayload) => Promise<void>
  characters: Character[]
  voices: Voice[]
  runtimeCatalog: RuntimeCatalog | null
  onRefresh: () => Promise<void>
  onMessage: (message: string) => void
  onApprove: () => void
  onRequestChanges: () => void
}) {
  const [tab, setTab] = useState<InspectorTab>('details')
  const [draft, setDraft] = useState(shot)
  const [characterLinks, setCharacterLinks] = useState<ShotCharacterLink[]>(shot.characters ?? [])
  const [recommendationKind, setRecommendationKind] = useState<'generation' | 'workflow'>('generation')
  const [recommendationTargetId, setRecommendationTargetId] = useState('')
  const [recommendationRationale, setRecommendationRationale] = useState('')
  const [actionBusy, setActionBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const disabled = busy || actionBusy || !edit

  useEffect(() => {
    setDraft(shot)
    setCharacterLinks(shot.characters ?? [])
    setTab('details')
    setActionError(null)
  }, [shot])

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
        workflow_template_id: recommendationKind === 'workflow' ? recommendationTargetId : null,
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

  const continuityValid = Boolean(
    draft.continuity_source_type && draft.continuity_source_type !== 'none',
  )
  const status = approvalToProto(draft.approval_state)

  return (
    <>
      <header>
        <div>
          <span className="eyebrow">SHOT {draft.display_label || 'A'}</span>
          <h2>{draft.id}</h2>
        </div>
        <StatusPill status={status} />
      </header>

      <div className="tabs" role="tablist" aria-label="Inspector sections">
        {(
          [
            ['details', 'Shot details'],
            ['prompts', 'Prompts'],
            ['technical', 'Technical'],
            ['cast', 'Cast & routing'],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            className={tab === id ? 'active' : ''}
            aria-selected={tab === id}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'details' ? (
        <div className="form-stack" role="tabpanel">
          <label>
            Story purpose
            <textarea
              disabled={disabled}
              value={draft.story_purpose ?? ''}
              onChange={(e) => setDraft({ ...draft, story_purpose: e.target.value || null })}
            />
          </label>
          <label>
            Visual description
            <textarea
              className="tall"
              disabled={disabled}
              value={draft.visual_description ?? ''}
              onChange={(e) => setDraft({ ...draft, visual_description: e.target.value || null })}
            />
          </label>
          <div className="form-grid">
            <label>
              Duration
              <input
                type="number"
                min={0.1}
                step={0.1}
                disabled={disabled}
                value={draft.duration_sec}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    duration_sec: Number(e.target.value),
                    approval_state:
                      draft.approval_state === 'approved' ? 'in_review' : draft.approval_state,
                  })
                }
              />
            </label>
            <label>
              Approval
              <select
                disabled={disabled}
                value={status}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    approval_state: protoToApproval(e.target.value as ProtoStatus),
                  })
                }
              >
                {(['Draft', 'Review', 'Approved', 'Blocked'] as const).map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label>
            Characters present
            <div className="token-field">
              {(draft.characters ?? []).length
                ? (draft.characters ?? []).map((link) => {
                    const c = characters.find((x) => x.id === link.character_id)
                    return <span key={link.character_id}>{c?.name ?? link.character_id}</span>
                  })
                : <span>None assigned</span>}
            </div>
          </label>
          <label>
            Location
            <input
              disabled={disabled}
              value={draft.location ?? ''}
              onChange={(e) => setDraft({ ...draft, location: e.target.value || null })}
            />
          </label>
          <label>
            Narration
            <textarea
              disabled={disabled}
              value={draft.narration ?? ''}
              onChange={(e) => setDraft({ ...draft, narration: e.target.value || null })}
            />
          </label>
          <label>
            Narration exception reason
            <textarea
              disabled={disabled}
              value={draft.narration_exception_reason ?? ''}
              onChange={(e) =>
                setDraft({ ...draft, narration_exception_reason: e.target.value || null })
              }
            />
          </label>
          <label>
            Voice profile
            <select
              disabled={disabled}
              value={draft.narration_voice_profile_id ?? ''}
              onChange={(e) =>
                setDraft({ ...draft, narration_voice_profile_id: e.target.value || null })
              }
            >
              <option value="">Unassigned / exception needed</option>
              {voices.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Continuity source
            <input
              disabled={disabled}
              value={
                draft.continuity_source_type === 'none'
                  ? ''
                  : draft.continuity_source_shot_id || draft.continuity_source_type
              }
              onChange={(e) =>
                setDraft({
                  ...draft,
                  continuity_source_type: e.target.value ? 'shot_ref' : 'none',
                  continuity_source_shot_id: e.target.value || null,
                })
              }
              className="mono"
              placeholder="Shot id or leave empty"
            />
          </label>
          <div className={`validation ${continuityValid ? 'pass' : 'fail'}`}>
            <Icon name={continuityValid ? 'check' : 'warning'} />
            <span>
              <b>{continuityValid ? 'Continuity link valid' : 'Continuity repair required'}</b>
              <small>
                {continuityValid
                  ? `Source: ${draft.continuity_source_type}`
                  : 'Set a continuity source type other than none.'}
              </small>
            </span>
          </div>
          <div className="inline-actions" style={{ marginTop: 8 }}>
            <Button variant="primary" disabled={busy || actionBusy} onClick={save}>
              Save shot details
            </Button>
            <Button
              disabled={
                busy ||
                actionBusy ||
                (!draft.narration?.trim() && !draft.narration_exception_reason?.trim())
              }
              onClick={saveNarration}
            >
              Save narration
            </Button>
          </div>
        </div>
      ) : null}

      {tab === 'prompts' ? (
        <div className="form-stack" role="tabpanel">
          <p className="form-hint">
            Saving creates a new canonical prompt-package version; it never invokes a model or starts
            generation.
          </p>
          <label>
            Starting-image prompt
            <textarea
              className="prompt tall"
              disabled={disabled}
              value={draft.prompt_positive ?? ''}
              onChange={(e) => setDraft({ ...draft, prompt_positive: e.target.value || null })}
            />
          </label>
          <label>
            Video prompt
            <textarea
              className="prompt tall"
              disabled={disabled}
              value={draft.prompt_video ?? ''}
              onChange={(e) => setDraft({ ...draft, prompt_video: e.target.value || null })}
            />
          </label>
          <label>
            Negative prompt
            <textarea
              className="prompt"
              disabled={disabled}
              value={draft.prompt_negative ?? ''}
              onChange={(e) => setDraft({ ...draft, prompt_negative: e.target.value || null })}
            />
          </label>
          <label>
            Continuity instructions
            <textarea
              className="prompt"
              disabled={disabled}
              value={draft.prompt_continuity_instructions ?? ''}
              onChange={(e) =>
                setDraft({ ...draft, prompt_continuity_instructions: e.target.value || null })
              }
            />
          </label>
          <label>
            Style-lock prompt
            <textarea
              className="prompt"
              disabled={disabled}
              value={draft.prompt_style_lock ?? ''}
              onChange={(e) => setDraft({ ...draft, prompt_style_lock: e.target.value || null })}
            />
          </label>
          <Button variant="primary" disabled={busy || actionBusy} onClick={savePromptPackage}>
            Save new prompt version
          </Button>
        </div>
      ) : null}

      {tab === 'technical' ? (
        <div className="form-stack" role="tabpanel">
          <label>
            Continuity source type
            <select
              disabled={disabled}
              value={draft.continuity_source_type}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  continuity_source_type: e.target.value,
                  continuity_source_shot_id:
                    e.target.value === 'none' ? null : draft.continuity_source_shot_id,
                })
              }
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
              className="mono"
              disabled={disabled || draft.continuity_source_type === 'none'}
              value={draft.continuity_source_shot_id ?? ''}
              onChange={(e) =>
                setDraft({ ...draft, continuity_source_shot_id: e.target.value || null })
              }
            />
          </label>
          <label style={{ gridTemplateColumns: 'auto 1fr', alignItems: 'center' }}>
            <input
              type="checkbox"
              checked={draft.starting_image_required}
              disabled={disabled}
              style={{ width: 20, height: 20, minHeight: 20 }}
              onChange={(e) => setDraft({ ...draft, starting_image_required: e.target.checked })}
            />
            <span>Starting image required</span>
          </label>
          <label>
            Starting image asset ID
            <input
              className="mono"
              disabled={disabled}
              value={draft.starting_image_asset_id ?? ''}
              onChange={(e) =>
                setDraft({ ...draft, starting_image_asset_id: e.target.value || null })
              }
            />
          </label>
          <label>
            Camera direction
            <textarea
              disabled={disabled}
              value={draft.camera_direction ?? ''}
              onChange={(e) => setDraft({ ...draft, camera_direction: e.target.value || null })}
            />
          </label>
          <label>
            Motion direction
            <textarea
              disabled={disabled}
              value={draft.motion_direction ?? ''}
              onChange={(e) => setDraft({ ...draft, motion_direction: e.target.value || null })}
            />
          </label>
          <label>
            Production status
            <input
              list={`production-status-${draft.id}`}
              disabled={disabled}
              value={draft.production_status}
              onChange={(e) => setDraft({ ...draft, production_status: e.target.value })}
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
              disabled={disabled || draft.production_status !== 'blocked'}
              value={draft.blocked_reason ?? ''}
              onChange={(e) => setDraft({ ...draft, blocked_reason: e.target.value || null })}
              placeholder="Required when production status is blocked"
            />
          </label>
          <div className="spec-grid">
            <div>
              <span>Resolution</span>
              <b>1280×720</b>
            </div>
            <div>
              <span>Frame rate</span>
              <b>24 fps</b>
            </div>
            <div>
              <span>Frames</span>
              <b>{Math.round(draft.duration_sec * 24)}</b>
            </div>
            <div>
              <span>Seed policy</span>
              <b>Fixed</b>
            </div>
          </div>
          <Button
            variant="primary"
            disabled={
              busy ||
              actionBusy ||
              !draft.production_status.trim() ||
              (draft.production_status === 'blocked' && !draft.blocked_reason?.trim())
            }
            onClick={() => void saveLifecycle()}
          >
            Save technical and lifecycle fields
          </Button>
        </div>
      ) : null}

      {tab === 'cast' ? (
        <div className="form-stack" role="tabpanel">
          <div>
            <h3>Character assignments</h3>
            <p className="form-hint">
              Checked characters and their roles are persisted as ordered shot-character links.
            </p>
          </div>
          {characters.length ? (
            characters.map((character) => {
              const link = characterLinks.find((item) => item.character_id === character.id)
              return (
                <div key={character.id} className="notice info">
                  <label style={{ gridTemplateColumns: 'auto 1fr', alignItems: 'center' }}>
                    <input
                      type="checkbox"
                      checked={Boolean(link)}
                      disabled={busy || actionBusy}
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
                        disabled={busy || actionBusy}
                        onChange={(event) =>
                          setCharacterLinks((current) =>
                            current.map((item) =>
                              item.character_id === character.id
                                ? { ...item, role_in_shot: event.target.value || null }
                                : item,
                            ),
                          )
                        }
                      />
                    </label>
                  ) : null}
                </div>
              )
            })
          ) : (
            <p className="form-hint">No characters exist in this story.</p>
          )}
          <Button disabled={busy || actionBusy} onClick={() => void saveCharacterLinks()}>
            Save character assignments
          </Button>

          <div>
            <h3>Model / workflow recommendations</h3>
            <p className="form-hint">
              Recommendations are planning metadata only. Saving or acknowledging one never submits a
              render.
            </p>
          </div>
          {draft.recommendations?.length ? (
            draft.recommendations.map((recommendation) => (
              <article className="notice info" key={recommendation.id}>
                <strong>
                  {recommendation.recommendation_type} · {recommendation.approval_state}
                </strong>
                <p>{recommendation.rationale || 'No rationale recorded.'}</p>
                <small>
                  Availability {recommendation.availability_status} · benchmark{' '}
                  {recommendation.benchmark_status}
                  {recommendation.acknowledged_at
                    ? ` · acknowledged ${recommendation.acknowledged_at}`
                    : ''}
                </small>
                <div className="inline-actions" style={{ marginTop: 8 }}>
                  <Button
                    variant="quiet"
                    disabled={busy || actionBusy || Boolean(recommendation.acknowledged_at)}
                    onClick={() => void updateRecommendation(recommendation.id, { acknowledge: true })}
                  >
                    {recommendation.acknowledged_at ? 'Acknowledged' : 'Acknowledge'}
                  </Button>
                  <Button
                    variant="quiet"
                    disabled={busy || actionBusy || recommendation.approval_state === 'in_review'}
                    onClick={() =>
                      void updateRecommendation(recommendation.id, { approval_state: 'in_review' })
                    }
                  >
                    Mark in review
                  </Button>
                  <Button
                    variant="quiet"
                    disabled={busy || actionBusy}
                    onClick={() => void deleteRecommendation(recommendation.id)}
                  >
                    Delete
                  </Button>
                </div>
              </article>
            ))
          ) : (
            <p className="form-hint">No recommendation is persisted for this shot.</p>
          )}
          <form className="form-stack" onSubmit={(event) => void createRecommendation(event)}>
            <label>
              Recommendation target type
              <select
                value={recommendationKind}
                disabled={busy || actionBusy}
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
              <select
                value={recommendationTargetId}
                onChange={(event) => setRecommendationTargetId(event.target.value)}
                disabled={busy || actionBusy}
              >
                <option value="">Select a factual catalog record</option>
                {recommendationKind === 'generation'
                  ? runtimeCatalog?.model_variants.map((variant) => (
                      <option key={variant.id} value={variant.id}>
                        {variant.variant_name} · {variant.path_status} · {variant.benchmark_status}
                      </option>
                    ))
                  : runtimeCatalog?.workflow_templates.map((workflow) => (
                      <option key={workflow.id} value={workflow.id}>
                        {workflow.name} {workflow.version} · {workflow.registration_status}
                      </option>
                    ))}
              </select>
            </label>
            <label>
              Rationale
              <textarea
                value={recommendationRationale}
                onChange={(event) => setRecommendationRationale(event.target.value)}
                disabled={busy || actionBusy}
              />
            </label>
            <Button
              type="submit"
              disabled={busy || actionBusy || !recommendationTargetId}
            >
              Save recommendation
            </Button>
            {!runtimeCatalog ? (
              <p className="notice warning">
                Runtime catalog is unavailable; new recommendations cannot be created, but existing
                records remain reviewable.
              </p>
            ) : null}
          </form>
        </div>
      ) : null}

      {actionError ? (
        <p className="notice error" role="alert">
          {actionError}
        </p>
      ) : null}

      <footer>
        <Button variant="danger" onClick={onRequestChanges} disabled={busy || actionBusy}>
          Request changes
        </Button>
        <Button variant="primary" icon="check" onClick={onApprove} disabled={busy || actionBusy}>
          Approve shot
        </Button>
      </footer>
    </>
  )
}

export function StoryboardPage() {
  const {
    data,
    readiness,
    selectedShot,
    setSelectedShot,
    addHierarchy,
    saveShot,
    saveNarration,
    savePromptPackage,
    busy,
    reload,
    setMessage,
    navigate,
  } = useStudio()

  const view = useMemo(() => (data ? toProtoProject(data, readiness) : null), [data, readiness])

  const productionShots = useMemo(
    () => data?.chapters.flatMap((c) => c.scenes.flatMap((s) => s.shots)) ?? [],
    [data],
  )

  const [filter, setFilter] = useState<StatusFilter>('All')
  const [expanded, setExpanded] = useState<string[]>([])
  const [edit, setEdit] = useState(false)
  const [inspector, setInspector] = useState(true)
  const [runtimeCatalog, setRuntimeCatalog] = useState<RuntimeCatalog | null>(null)

  useEffect(() => {
    let active = true
    void api
      .runtimeCatalog()
      .then((catalog) => {
        if (active) setRuntimeCatalog(catalog)
      })
      .catch(() => {
        if (active) setRuntimeCatalog(null)
      })
    return () => {
      active = false
    }
  }, [])

  // Seed expanded chapters once per story load; keep user collapse/expand choices.
  const chapterIdsKey = data?.chapters.map((c) => c.id).join('|') ?? ''
  useEffect(() => {
    if (!chapterIdsKey) return
    setExpanded((current) => {
      const ids = chapterIdsKey.split('|').filter(Boolean)
      if (!current.length) return ids
      const known = new Set(ids)
      const kept = current.filter((id) => known.has(id))
      const added = ids.filter((id) => !current.includes(id))
      return [...kept, ...added]
    })
  }, [chapterIdsKey])

  // Keep selected shot synced with aggregate; default to first shot.
  useEffect(() => {
    if (!productionShots.length) {
      setSelectedShot(null)
      return
    }
    setSelectedShot((current) => {
      if (current) {
        const refreshed = productionShots.find((s) => s.id === current.id)
        if (refreshed) return refreshed
      }
      return productionShots[0]
    })
  }, [productionShots, setSelectedShot])

  if (!data || !view) return null

  const { project, readinessPct } = view
  const shotTotal = project.shots.length
  const approvedCount = project.shots.filter((s) => s.status === 'Approved').length

  const statusFilter = filter as StatusFilter
  const showAllShots = statusFilter === 'All'
  const filterCounts: Record<StatusFilter, number> = {
    All: shotTotal,
    Draft: project.shots.filter((s) => s.status === 'Draft').length,
    Review: project.shots.filter((s) => s.status === 'Review').length,
    Approved: approvedCount,
    Blocked: project.shots.filter((s) => s.status === 'Blocked').length,
  }

  const visibleProto = showAllShots
    ? project.shots
    : project.shots.filter((s) => s.status === statusFilter)
  const visibleIds = new Set(visibleProto.map((s) => s.id))

  const selected =
    (selectedShot && productionShots.find((s) => s.id === selectedShot.id)) ||
    productionShots[0] ||
    null

  const selectedProto = selected
    ? project.shots.find((s) => s.id === selected.id) ?? null
    : null

  const selectedSceneId = selectedProto?.sceneId
  const selectedChapter = selectedSceneId
    ? data.chapters.find((c) => c.scenes.some((sc) => sc.id === selectedSceneId))
    : null
  const selectedScene = selectedChapter?.scenes.find((sc) => sc.id === selectedSceneId) ?? null
  const sceneShots = selectedScene?.shots ?? []
  const sceneDurationSec = sceneShots.reduce((n, s) => n + s.duration_sec, 0)

  const selectShot = (shot: Shot) => {
    setSelectedShot(shot)
    setInspector(true)
  }

  const approveSelected = async () => {
    if (!selected) return
    const blockers: string[] = []
    if (!selected.narration_voice_profile_id) blockers.push('voice assignment')
    if (!selected.continuity_source_type || selected.continuity_source_type === 'none') {
      blockers.push('valid continuity')
    }
    if (selected.starting_image_required && !selected.starting_image_asset_id) {
      blockers.push('approved starting image')
    }
    if (blockers.length) {
      setMessage(`Cannot approve: needs ${blockers.join(', ')}`)
      return
    }
    try {
      await api.patchShot(selected.id, { approval_state: 'approved' })
      await reload(data.story.id)
      setMessage(`${selected.display_label || selected.id} approved`)
    } catch (error) {
      setMessage(errorText(error, 'Could not approve shot.'))
    }
  }

  const requestChanges = async () => {
    if (!selected) return
    try {
      await api.patchShot(selected.id, { approval_state: 'in_review' })
      await reload(data.story.id)
      setMessage(`${selected.display_label || selected.id} returned to review`)
    } catch (error) {
      setMessage(errorText(error, 'Could not return shot to review.'))
    }
  }

  const globalShotIndex = (shotId: string) =>
    productionShots.findIndex((s) => s.id === shotId)

  return (
    <div className="page storyboard-page proto-page">
      <PageTitle
        eyebrow="STORYBOARD WORKSPACE"
        title="Production storyboard"
        description={`Review all ${shotTotal || 0} generation-ready shots across the complete ${formatDuration(data.story.target_duration_sec)} plan.`}
        aside={
          <div className="readiness-block">
            <span>
              <b>{readinessPct}%</b> storyboard readiness
            </span>
            <Progress value={readinessPct} />
            <small>
              {approvedCount} of {shotTotal} shots approved
            </small>
          </div>
        }
      />

      <div className="toolbar">
        <div className="segmented" role="tablist" aria-label="Filter shots by approval state">
          {(['All', 'Draft', 'Review', 'Approved', 'Blocked'] as const).map((s) => (
            <button
              key={s}
              type="button"
              className={filter === s ? 'active' : ''}
              onClick={() => setFilter(s)}
            >
              {s}
              <span>{filterCounts[s]}</span>
            </button>
          ))}
        </div>
        <div>
          <Button
            variant="quiet"
            icon="filter"
            onClick={() => setMessage(`Showing ${filter.toLowerCase()} shots`)}
          >
            Filter
          </Button>
          <Button icon={edit ? 'check' : 'edit'} onClick={() => setEdit(!edit)}>
            {edit ? 'Finish editing' : 'Edit storyboard'}
          </Button>
          <Button variant="quiet" icon="plus" disabled={busy} onClick={() => void addHierarchy('shot')}>
            + Shot
          </Button>
        </div>
      </div>

      <div className={`storyboard-layout ${inspector ? '' : 'inspector-closed'}`}>
        <div className="storyboard-main">
          {!data.chapters.length ? (
            <EmptyState
              title="No chapters yet"
              detail="Add a chapter to begin the ordered production hierarchy."
              action={
                <Button
                  variant="primary"
                  disabled={busy}
                  onClick={() => void addHierarchy('chapter')}
                >
                  Add chapter
                </Button>
              }
            />
          ) : (
            data.chapters.map((chapter, chapterIndex) => {
              const chLabel = chapterLabel(chapterIndex)
              const open = expanded.includes(chapter.id)
              const chapterShots = chapter.scenes.flatMap((sc) => sc.shots)
              const shown = chapterShots.some((s) => visibleIds.has(s.id)) || showAllShots
              if (!shown && !showAllShots) return null
              const chapterApproved = chapterShots.length
                ? chapterShots.every((s) => s.approval_state === 'approved')
                : false
              return (
                <section className="chapter-group" key={chapter.id} hidden={!shown && !showAllShots}>
                  <button
                    type="button"
                    className="chapter-bar"
                    onClick={() =>
                      setExpanded(
                        open ? expanded.filter((id) => id !== chapter.id) : [...expanded, chapter.id],
                      )
                    }
                    aria-expanded={open}
                  >
                    <Icon name="chevron" size={16} />
                    <span>
                      <b>
                        {chLabel} · {chapter.title}
                      </b>
                      <small>{chapter.summary || 'No chapter summary'}</small>
                    </span>
                    <span className="chapter-stats">
                      <b>{formatDuration(chapter.duration_sec)}</b>
                      <small>
                        {chapter.scenes.length} scenes · {chapterShots.length} shots
                      </small>
                    </span>
                    <StatusPill status={chapterApproved ? 'Approved' : 'Review'} />
                  </button>
                  {open
                    ? chapter.scenes.map((scene, sceneIndex) => {
                        const shots = scene.shots.filter((s) => visibleIds.has(s.id))
                        if (!showAllShots && !shots.length) return null
                        const scLabel = sceneLabel(sceneIndex)
                        return (
                          <div className="scene-block" key={scene.id}>
                            <div className="scene-row">
                              <span>
                                <small>
                                  {chLabel} / {scLabel}
                                </small>
                                <b>{scene.title}</b>
                                <p>{scene.summary || 'No scene summary'}</p>
                              </span>
                              <span>
                                <Icon name="clock" size={14} />
                                <b>{scene.duration_sec} sec</b>
                                <small>
                                  {scene.shots.length} shot{scene.shots.length === 1 ? '' : 's'}
                                </small>
                              </span>
                            </div>
                            <div className="shot-strip" role="list">
                              {(showAllShots ? scene.shots : shots).map((shot, i) => {
                                const gIndex = globalShotIndex(shot.id)
                                const status = approvalToProto(shot.approval_state)
                                return (
                                  <button
                                    key={shot.id}
                                    type="button"
                                    role="listitem"
                                    className={`shot-card ${shot.id === selected?.id ? 'selected' : ''}`}
                                    onClick={() => selectShot(shot)}
                                  >
                                    <div
                                      className={`frame-art frame-${Math.max(0, gIndex) % 8}`}
                                    >
                                      <span>
                                        {shot.display_label ||
                                          String.fromCharCode(65 + (shot.order_index % 26))}
                                      </span>
                                      <i>
                                        <Icon name="play" size={11} />
                                      </i>
                                    </div>
                                    <div>
                                      <span>
                                        <code>{`SH${String(i + 1).padStart(2, '0')}`}</code>
                                        <b>{shot.duration_sec}s</b>
                                      </span>
                                      <strong>{shot.title}</strong>
                                      <StatusPill status={status} />
                                    </div>
                                  </button>
                                )
                              })}
                              {!showAllShots && !shots.length ? (
                                <p className="form-hint" style={{ margin: 0 }}>
                                  No shots match this filter in this scene.
                                </p>
                              ) : null}
                              {showAllShots && !scene.shots.length ? (
                                <p className="form-hint" style={{ margin: 0 }}>
                                  No shots in this scene yet.
                                </p>
                              ) : null}
                            </div>
                          </div>
                        )
                      })
                    : null}
                </section>
              )
            })
          )}

          {selectedScene ? (
            <Section
              title="Sequence timeline"
              subtitle={`${sceneLabel(selectedChapter?.scenes.findIndex((s) => s.id === selectedScene.id) ?? 0)} · ${formatDuration(sceneDurationSec)}`}
              className="timeline-panel"
            >
              <div className="timeline-track">
                {sceneShots.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    style={{ flex: Math.max(s.duration_sec, 1) }}
                    className={s.id === selected?.id ? 'selected' : ''}
                    onClick={() => selectShot(s)}
                  >
                    <b>{s.display_label || 'A'}</b>
                    <small>{s.duration_sec}s</small>
                  </button>
                ))}
              </div>
              <div className="narration-track">
                <Icon name="mic" />
                <div>
                  {sceneShots.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      style={{ flex: Math.max(s.duration_sec, 1) }}
                      onClick={() => selectShot(s)}
                    >
                      {(s.narration || 'No narration').slice(0, 30)}
                      {s.narration && s.narration.length > 30 ? '…' : ''}
                    </button>
                  ))}
                </div>
              </div>
            </Section>
          ) : null}

          {selected ? (
            <div className="lower-grid">
              <Section
                title="Character readiness"
                subtitle="References must be locked before approval."
                action={
                  <button
                    type="button"
                    className="text-action"
                    onClick={() => navigate('characters')}
                  >
                    Open bible
                  </button>
                }
              >
                <div className="mini-entity-list">
                  {(selected.characters ?? []).length ? (
                    (selected.characters ?? []).map((link) => {
                      const c = data.characters.find((x) => x.id === link.character_id)
                      if (!c) return null
                      const linked = productionShots.filter((s) =>
                        s.characters?.some((l) => l.character_id === c.id),
                      ).length
                      return (
                        <button
                          key={c.id}
                          type="button"
                          onClick={() => navigate('characters')}
                        >
                          <span className="avatar">{c.name.slice(0, 2).toUpperCase()}</span>
                          <span>
                            <b>{c.name}</b>
                            <small>{linked} linked shots</small>
                          </span>
                          <StatusPill status={approvalToProto(c.approval_state)} />
                        </button>
                      )
                    })
                  ) : (
                    <p className="form-hint">No characters linked to this shot.</p>
                  )}
                </div>
              </Section>
              <Section
                title="Generation plan"
                subtitle="Recommendations validated against this machine."
              >
                <div className="model-summary">
                  <div>
                    <span>
                      {selected.recommendations?.find((r) => r.recommendation_type === 'generation')
                        ?.rationale || 'No image model recommendation'}
                    </span>
                    <StatusPill status="Review" />
                  </div>
                  <div>
                    <span>
                      {selected.recommendations?.find((r) => r.recommendation_type === 'workflow')
                        ?.rationale || 'No video model recommendation'}
                    </span>
                    <StatusPill status="Review" />
                  </div>
                  <div>
                    <span>Planning workflow</span>
                    <StatusPill status="Validated" />
                  </div>
                </div>
                <button
                  type="button"
                  className="full-row-action"
                  onClick={() => navigate('routing')}
                >
                  Review model routing <Icon name="arrow" />
                </button>
              </Section>
            </div>
          ) : null}
        </div>

        {inspector && selected ? (
          <aside className="inspector" aria-label="Shot inspector">
            <button
              type="button"
              className="icon-button"
              style={{ position: 'absolute', right: 12, top: 12 }}
              onClick={() => setInspector(false)}
              aria-label="Close inspector"
            >
              <Icon name="close" />
            </button>
            <ShotInspector
              key={`${selected.id}-${data.revision}`}
              shot={selected}
              busy={busy}
              edit={edit}
              onSave={saveShot}
              onSaveNarration={saveNarration}
              onSavePromptPackage={savePromptPackage}
              characters={data.characters}
              voices={data.voices}
              runtimeCatalog={runtimeCatalog}
              onRefresh={() => reload(data.story.id)}
              onMessage={setMessage}
              onApprove={() => void approveSelected()}
              onRequestChanges={() => void requestChanges()}
            />
          </aside>
        ) : (
          <button type="button" className="open-inspector" onClick={() => setInspector(true)}>
            <Icon name="settings" /> Shot details
          </button>
        )}
      </div>
    </div>
  )
}
