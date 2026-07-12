/**
 * Exact structural port of prototype StoryboardPage (pagesCore.tsx)
 * adapted to production studio context + saveShot / saveNarration / savePromptPackage.
 *
 * DOM hierarchy matches the ZIP prototype:
 * page-title → toolbar/segmented → chapter bars → shot strip/frame-art →
 * sequence timeline + narration track → character readiness / generation plan →
 * inspector tabs: Shot details | Prompts | Technical.
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
import { Button, Icon, PageTitle, Progress, Section, StatusPill } from '../proto/ui'
import { useStudio } from '../StudioState'
import { formatDuration } from '../utils'
import { EmptyState } from '../components/StateBlocks'
import { toProtoProject, type ProtoShot, type ProtoStatus } from '../proto/adapter'

type InspectorTab = 'details' | 'prompts' | 'technical'
type StatusFilter = 'All' | 'Draft' | 'Review' | 'Approved' | 'Blocked'

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

/** Fields inspected for per-shot approval gates (planning only; no render). */
type ShotApprovalGateFields = Pick<
  Shot,
  | 'narration_voice_profile_id'
  | 'continuity_source_type'
  | 'starting_image_required'
  | 'starting_image_asset_id'
>

/** Blockers for per-shot approval from a field snapshot (production or same-save draft). */
function shotApprovalBlockers(fields: ShotApprovalGateFields): string[] {
  const blockers: string[] = []
  if (!fields.narration_voice_profile_id) blockers.push('voice assignment')
  if (!fields.continuity_source_type || fields.continuity_source_type === 'none') {
    blockers.push('valid continuity')
  }
  if (fields.starting_image_required && !fields.starting_image_asset_id) {
    blockers.push('approved starting image')
  }
  return blockers
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

function shotCode(
  chapterIndex: number,
  sceneIndex: number,
  shotIndexInScene: number,
): string {
  return `${chapterLabel(chapterIndex)}-${sceneLabel(sceneIndex)}-SH${String(shotIndexInScene + 1).padStart(2, '0')}`
}

function shotLetter(label: string | undefined, orderIndex: number): string {
  if (label && label.length <= 2) return label
  return orderIndex < 26 ? String.fromCharCode(65 + orderIndex) : String(orderIndex + 1)
}

function characterInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return '??'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0] ?? ''}${parts[1][0] ?? ''}`.toUpperCase()
}

function characterReadinessStatus(character: Character): ProtoStatus {
  const refs = character.reference_assets ?? []
  const heroOk = refs.some(
    (r) => r.approved && (r.reference_role === 'hero' || r.reference_role === 'primary'),
  )
  if (heroOk || character.approval_state === 'approved') return 'Approved'
  if (!refs.length) return 'Blocked'
  return approvalToProto(character.approval_state)
}

function ShotInspector({
  shot,
  shotCodeLabel,
  protoShot,
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
  onClose,
  onOpenWorkflows,
}: {
  shot: Shot
  shotCodeLabel: string
  protoShot: ProtoShot | null
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
  onClose: () => void
  onOpenWorkflows: () => void
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

  const busyReason = busy
    ? 'A studio save or reload is already in progress.'
    : actionBusy
      ? 'This inspector action is already in progress.'
      : null
  const editReason = !edit
    ? 'Turn on Edit storyboard to change inspector fields and save via production APIs.'
    : null
  const fieldsDisabledReason = firstReason(busyReason, editReason)
  const hasNarrationOrException = Boolean(
    draft.narration?.trim() || draft.narration_exception_reason?.trim(),
  )
  const narrationSaveReason = firstReason(
    busyReason,
    editReason,
    !hasNarrationOrException &&
      'Enter narration text or a narration exception reason before saving narration.',
  )
  const lifecycleSaveReason = firstReason(
    busyReason,
    editReason,
    !draft.production_status.trim() && 'Production status is required before saving lifecycle fields.',
    draft.production_status === 'blocked' &&
      !draft.blocked_reason?.trim() &&
      'Blocked reason is required when production status is blocked.',
  )
  const recommendationSaveReason = firstReason(
    busyReason,
    editReason,
    !runtimeCatalog &&
      'Runtime catalog is unavailable; new recommendations cannot be created from catalog targets.',
    !recommendationTargetId && 'Select a factual runtime-catalog target before saving a recommendation.',
  )
  // Approve uses the production aggregate shot (prop), not unsaved draft fields.
  const approveBlockers = shotApprovalBlockers(shot)
  const approveReason = firstReason(
    busyReason,
    approveBlockers.length > 0 && `Cannot approve: needs ${approveBlockers.join(', ')}.`,
  )

  // Draft state is reset by remounting ShotInspector with key=shot.id+revision at the call site.

  const save = () => {
    if (disabled) return
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
    if (disabled || !hasNarrationOrException) return
    const narrationText = draft.narration?.trim() || null
    const exceptionReason = draft.narration_exception_reason?.trim() || null
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
    if (disabled) return
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
    if (disabled || lifecycleSaveReason) return
    // Same approval gates as Approve shot — no lifecycle bypass.
    // Continuity / starting-image use the draft values being patched in this call.
    // Voice is not part of this patch, so it must already exist on the production shot.
    if (draft.approval_state === 'approved') {
      const blockers = shotApprovalBlockers({
        narration_voice_profile_id: shot.narration_voice_profile_id,
        continuity_source_type: draft.continuity_source_type,
        starting_image_required: draft.starting_image_required,
        starting_image_asset_id: draft.starting_image_asset_id,
      })
      if (blockers.length) {
        const reason = `Cannot approve via lifecycle save: needs ${blockers.join(', ')}.`
        setActionError(reason)
        onMessage(reason)
        return
      }
    }
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
        continuity_source_type: draft.continuity_source_type,
        continuity_source_shot_id:
          draft.continuity_source_type === 'none'
            ? null
            : draft.continuity_source_shot_id?.trim() || null,
        starting_image_required: draft.starting_image_required,
        starting_image_asset_id: draft.starting_image_asset_id?.trim() || null,
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
    if (disabled) return
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
    if (disabled || !recommendationTargetId || !runtimeCatalog) return
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
    if (busy || actionBusy) return
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
    if (busy || actionBusy) return
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
  const imageModel =
    protoShot?.imageModel ||
    draft.recommendations?.find((r) => r.recommendation_type === 'generation')?.rationale ||
    'Unknown'
  const videoModel =
    protoShot?.videoModel ||
    draft.recommendations?.find((r) => r.recommendation_type === 'workflow')?.rationale ||
    'Unknown'
  const workflow = protoShot?.workflow || 'Planning workflow'
  const resolution = protoShot?.resolution || '1280×720'
  const fps = protoShot?.fps || 24
  const seedPolicy = protoShot?.seedPolicy || 'Fixed'
  const risk = protoShot?.risk || (draft.approval_state === 'blocked' ? 'Blocked' : 'Ready')

  return (
    <>
      <header>
        <div>
          <span className="eyebrow">SHOT {shotLetter(draft.display_label, draft.order_index)}</span>
          <h2>{shotCodeLabel}</h2>
        </div>
        <StatusPill status={status} />
        <button type="button" className="icon-button" onClick={onClose} aria-label="Close inspector">
          <Icon name="close" />
        </button>
      </header>

      {!edit ? (
        <p className="form-hint" role="status">
          Inspector is read-only. Click <b>Edit storyboard</b> to enable field edits and production API
          saves.
        </p>
      ) : null}

      <div className="tabs" role="tablist" aria-label="Inspector sections">
        {(
          [
            ['details', 'Shot details'],
            ['prompts', 'Prompts'],
            ['technical', 'Technical'],
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
              title={fieldsDisabledReason}
              value={draft.story_purpose ?? ''}
              onChange={(e) => setDraft({ ...draft, story_purpose: e.target.value || null })}
            />
          </label>
          <label>
            Visual description
            <textarea
              className="tall"
              disabled={disabled}
              title={fieldsDisabledReason}
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
                title={fieldsDisabledReason}
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
                title={fieldsDisabledReason}
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
              {(draft.characters ?? []).length ? (
                (draft.characters ?? []).map((link) => {
                  const c = characters.find((x) => x.id === link.character_id)
                  return <span key={link.character_id}>{c?.name ?? link.character_id}</span>
                })
              ) : (
                <span>None assigned</span>
              )}
            </div>
          </label>
          <label>
            Location
            <input
              disabled={disabled}
              title={fieldsDisabledReason}
              value={draft.location ?? ''}
              onChange={(e) => setDraft({ ...draft, location: e.target.value || null })}
            />
          </label>
          <label>
            Narration
            <textarea
              disabled={disabled}
              title={fieldsDisabledReason}
              value={draft.narration ?? ''}
              onChange={(e) => setDraft({ ...draft, narration: e.target.value || null })}
            />
          </label>
          <label>
            Narration exception reason
            <textarea
              disabled={disabled}
              title={fieldsDisabledReason}
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
              title={fieldsDisabledReason}
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
              title={fieldsDisabledReason}
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
                  ? 'Identity, wardrobe, lighting, eyeline, and screen direction.'
                  : 'Set a continuity source type other than none.'}
              </small>
            </span>
          </div>
          <div className="inline-actions" style={{ marginTop: 8 }}>
            <Button
              type="button"
              variant="primary"
              disabled={disabled}
              title={fieldsDisabledReason}
              onClick={save}
            >
              Save shot details
            </Button>
            <Button
              type="button"
              disabled={Boolean(narrationSaveReason)}
              title={narrationSaveReason}
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
            Saving creates a new canonical prompt-package version via the production API; it never
            invokes a model or starts generation.
          </p>
          <label>
            Starting-image prompt
            <textarea
              className="prompt tall"
              disabled={disabled}
              title={fieldsDisabledReason}
              value={draft.prompt_positive ?? ''}
              onChange={(e) => setDraft({ ...draft, prompt_positive: e.target.value || null })}
            />
          </label>
          <label>
            Video prompt
            <textarea
              className="prompt tall"
              disabled={disabled}
              title={fieldsDisabledReason}
              value={draft.prompt_video ?? ''}
              onChange={(e) => setDraft({ ...draft, prompt_video: e.target.value || null })}
            />
          </label>
          <label>
            Negative prompt
            <textarea
              className="prompt"
              disabled={disabled}
              title={fieldsDisabledReason}
              value={draft.prompt_negative ?? ''}
              onChange={(e) => setDraft({ ...draft, prompt_negative: e.target.value || null })}
            />
          </label>
          <label>
            Continuity instructions
            <textarea
              className="prompt"
              disabled={disabled}
              title={fieldsDisabledReason}
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
              title={fieldsDisabledReason}
              value={draft.prompt_style_lock ?? ''}
              onChange={(e) => setDraft({ ...draft, prompt_style_lock: e.target.value || null })}
            />
          </label>
          <Button
            type="button"
            variant="primary"
            disabled={disabled}
            title={fieldsDisabledReason}
            onClick={savePromptPackage}
          >
            Save new prompt version
          </Button>
        </div>
      ) : null}

      {tab === 'technical' ? (
        <div className="form-stack" role="tabpanel">
          <label>
            Recommended image model
            <input
              disabled
              value={imageModel}
              readOnly
              title="Planning display from persisted recommendations; edit recommendations below."
            />
          </label>
          <label>
            Recommended video model
            <input
              disabled
              value={videoModel}
              readOnly
              title="Planning display from persisted recommendations; edit recommendations below."
            />
          </label>
          <label>
            Workflow
            <input
              disabled
              value={workflow}
              readOnly
              title="Planning display only; open Workflows for template registration status."
            />
          </label>
          <div className="spec-grid">
            <div>
              <span>Resolution</span>
              <b>{resolution}</b>
            </div>
            <div>
              <span>Frame rate</span>
              <b>{fps} fps</b>
            </div>
            <div>
              <span>Frames</span>
              <b>{Math.round(draft.duration_sec * fps)}</b>
            </div>
            <div>
              <span>Seed policy</span>
              <b>{seedPolicy}</b>
            </div>
          </div>
          <div className={`validation ${risk === 'Ready' ? 'pass' : 'fail'}`}>
            <Icon name={risk === 'Ready' ? 'check' : 'warning'} />
            <span>
              <b>{risk === 'Ready' ? 'Workflow ready' : `${risk} risk`}</b>
              <small>
                {String(videoModel).toLowerCase().includes('missing')
                  ? 'Recommended checkpoint is not installed.'
                  : 'Manifest and object-info checks complete.'}
              </small>
            </span>
          </div>
          <Button type="button" onClick={onOpenWorkflows}>
            Open workflow details
          </Button>

          <label>
            Continuity source type
            <select
              disabled={disabled}
              title={fieldsDisabledReason}
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
              title={firstReason(
                fieldsDisabledReason,
                draft.continuity_source_type === 'none' &&
                  'Continuity source type is none; pick previous shot, shot ref, or starting image first.',
              )}
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
              title={fieldsDisabledReason}
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
              title={fieldsDisabledReason}
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
              title={fieldsDisabledReason}
              value={draft.camera_direction ?? ''}
              onChange={(e) => setDraft({ ...draft, camera_direction: e.target.value || null })}
            />
          </label>
          <label>
            Motion direction
            <textarea
              disabled={disabled}
              title={fieldsDisabledReason}
              value={draft.motion_direction ?? ''}
              onChange={(e) => setDraft({ ...draft, motion_direction: e.target.value || null })}
            />
          </label>
          <label>
            Production status
            <input
              list={`production-status-${draft.id}`}
              disabled={disabled}
              title={fieldsDisabledReason}
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
              title={firstReason(
                fieldsDisabledReason,
                draft.production_status !== 'blocked' &&
                  'Blocked reason is only editable when production status is blocked.',
              )}
              value={draft.blocked_reason ?? ''}
              onChange={(e) => setDraft({ ...draft, blocked_reason: e.target.value || null })}
              placeholder="Required when production status is blocked"
            />
          </label>
          <Button
            type="button"
            variant="primary"
            disabled={Boolean(lifecycleSaveReason)}
            title={lifecycleSaveReason}
            onClick={() => void saveLifecycle()}
          >
            Save technical and lifecycle fields
          </Button>

          <div>
            <h3>Character assignments</h3>
            <p className="form-hint">
              Checked characters and their roles are persisted as ordered shot-character links via the
              production replace-characters API.
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
                      disabled={disabled}
                      title={fieldsDisabledReason}
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
                        title={fieldsDisabledReason}
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
          <Button
            type="button"
            disabled={disabled}
            title={fieldsDisabledReason}
            onClick={() => void saveCharacterLinks()}
          >
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
                    type="button"
                    variant="quiet"
                    disabled={Boolean(busyReason) || Boolean(recommendation.acknowledged_at)}
                    title={firstReason(
                      busyReason,
                      recommendation.acknowledged_at &&
                        'This recommendation is already acknowledged on the server.',
                    )}
                    onClick={() => void updateRecommendation(recommendation.id, { acknowledge: true })}
                  >
                    {recommendation.acknowledged_at ? 'Acknowledged' : 'Acknowledge'}
                  </Button>
                  <Button
                    type="button"
                    variant="quiet"
                    disabled={Boolean(busyReason) || recommendation.approval_state === 'in_review'}
                    title={firstReason(
                      busyReason,
                      recommendation.approval_state === 'in_review' &&
                        'Recommendation is already marked in_review on the server.',
                    )}
                    onClick={() =>
                      void updateRecommendation(recommendation.id, { approval_state: 'in_review' })
                    }
                  >
                    Mark in review
                  </Button>
                  <Button
                    type="button"
                    variant="quiet"
                    disabled={Boolean(busyReason)}
                    title={busyReason ?? undefined}
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
                disabled={disabled}
                title={fieldsDisabledReason}
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
                disabled={disabled || !runtimeCatalog}
                title={firstReason(
                  fieldsDisabledReason,
                  !runtimeCatalog &&
                    'Runtime catalog is unavailable; catalog targets cannot be selected.',
                )}
              >
                <option value="">Select a factual catalog record</option>
                {recommendationKind === 'generation'
                  ? runtimeCatalog?.model_variants.map((variant) => (
                      <option key={variant.id} value={variant.id}>
                        {variant.variant_name} · {variant.path_status} · {variant.benchmark_status}
                      </option>
                    ))
                  : runtimeCatalog?.workflow_templates.map((wf) => (
                      <option key={wf.id} value={wf.id}>
                        {wf.name} {wf.version} · {wf.registration_status}
                      </option>
                    ))}
              </select>
            </label>
            <label>
              Rationale
              <textarea
                value={recommendationRationale}
                onChange={(event) => setRecommendationRationale(event.target.value)}
                disabled={disabled}
                title={fieldsDisabledReason}
              />
            </label>
            <Button
              type="submit"
              disabled={Boolean(recommendationSaveReason)}
              title={recommendationSaveReason}
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
        <Button
          type="button"
          variant="danger"
          onClick={onRequestChanges}
          disabled={Boolean(busyReason)}
          title={
            busyReason ??
            'Returns this shot to in_review via the production patch-shot API (does not render).'
          }
        >
          Request changes
        </Button>
        <Button
          type="button"
          variant="primary"
          icon="check"
          onClick={onApprove}
          disabled={Boolean(approveReason)}
          title={
            approveReason ??
            'Approves this shot via the production patch-shot API (planning only; no render).'
          }
        >
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

  // Prototype opens only the first chapter (CH01). Seed once when hierarchy first appears.
  const chapterIdsKey = data?.chapters.map((c) => c.id).join('|') ?? ''
  useEffect(() => {
    if (!chapterIdsKey) return
    const ids = chapterIdsKey.split('|').filter(Boolean)
    if (!ids.length) return
    setExpanded((current) => {
      if (!current.length) return ids.slice(0, 1)
      const known = new Set(ids)
      const kept = current.filter((id) => known.has(id))
      return kept.length ? kept : ids.slice(0, 1)
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

  // Resolve hierarchy indices for CH/SC/SH display codes.
  let selectedChapterIndex = 0
  let selectedSceneIndex = 0
  let selectedShotIndexInScene = 0
  let selectedScene = data.chapters[0]?.scenes[0] ?? null

  if (selected) {
    outer: for (let ci = 0; ci < data.chapters.length; ci++) {
      const chapter = data.chapters[ci]
      for (let si = 0; si < chapter.scenes.length; si++) {
        const scene = chapter.scenes[si]
        const idx = scene.shots.findIndex((s) => s.id === selected.id)
        if (idx >= 0) {
          selectedChapterIndex = ci
          selectedSceneIndex = si
          selectedShotIndexInScene = idx
          selectedScene = scene
          break outer
        }
      }
    }
  }

  const sceneShots = selectedScene?.shots ?? []
  const sceneDurationSec = sceneShots.reduce((n, s) => n + s.duration_sec, 0)
  const selectedCode = selected
    ? shotCode(selectedChapterIndex, selectedSceneIndex, selectedShotIndexInScene)
    : ''

  const selectShot = (shot: Shot) => {
    setSelectedShot(shot)
    setInspector(true)
  }

  const approveSelected = async () => {
    if (!selected) return
    const blockers = shotApprovalBlockers(selected)
    if (blockers.length) {
      setMessage(`Cannot approve: needs ${blockers.join(', ')}`)
      return
    }
    try {
      await api.patchShot(selected.id, { approval_state: 'approved' })
      await reload(data.story.id)
      setMessage(`${selected.display_label || selected.id} approved via production API`)
    } catch (error) {
      setMessage(errorText(error, 'Could not approve shot.'))
    }
  }

  const requestChanges = async () => {
    if (!selected) return
    try {
      await api.patchShot(selected.id, { approval_state: 'in_review' })
      await reload(data.story.id)
      setMessage(`${selected.display_label || selected.id} returned to review via production API`)
    } catch (error) {
      setMessage(errorText(error, 'Could not return shot to review.'))
    }
  }

  const globalShotIndex = (shotId: string) => productionShots.findIndex((s) => s.id === shotId)

  // Generation-plan rows from selected shot recommendations + runtime catalog (planning only).
  const selectedRecs = selected?.recommendations ?? []
  const generationRec =
    selectedRecs.find((r) => r.recommendation_type === 'generation') ?? null
  const workflowRec =
    selectedRecs.find((r) => r.recommendation_type === 'workflow') ?? null
  const catalogVariant = generationRec?.generation_model_variant_id
    ? runtimeCatalog?.model_variants.find((v) => v.id === generationRec.generation_model_variant_id)
    : undefined
  const catalogWorkflow = workflowRec?.workflow_template_id
    ? runtimeCatalog?.workflow_templates.find((w) => w.id === workflowRec.workflow_template_id)
    : undefined
  const catalogModel = catalogVariant
    ? runtimeCatalog?.models.find((m) => m.id === catalogVariant.model_id)
    : undefined
  const protoImage =
    selectedProto?.imageModel && selectedProto.imageModel !== 'Unknown'
      ? selectedProto.imageModel
      : null
  const protoVideo =
    selectedProto?.videoModel &&
    selectedProto.videoModel !== 'Unknown' &&
    /video|ltx|wan|i2v|cog|missing/i.test(selectedProto.videoModel)
      ? selectedProto.videoModel
      : null
  const genImage =
    catalogVariant?.variant_name ||
    generationRec?.rationale ||
    protoImage ||
    'No image model recommendation'
  const genVideo =
    protoVideo ||
    catalogModel?.family ||
    catalogModel?.name ||
    selectedRecs.find((r) => r.rationale && /video|ltx|wan|i2v|cog/i.test(r.rationale || ''))
      ?.rationale ||
    'No video model recommendation'
  const genWorkflow = catalogWorkflow
    ? `${catalogWorkflow.name}${catalogWorkflow.version ? ` ${catalogWorkflow.version}` : ''}`
    : workflowRec?.rationale || selectedProto?.workflow || 'Planning workflow'
  const videoMissing =
    String(genVideo).toLowerCase().includes('missing') ||
    catalogVariant?.path_status === 'missing' ||
    generationRec?.availability_status === 'missing'
  // Planning-only per-shot estimate (matches Overview planning constants; never a real GPU job).
  const PLANNING_MIN_PER_SHOT = 1.52 + 14.37 + 1.22
  const estimateLabel = selected
    ? `~${Math.max(1, Math.round(PLANNING_MIN_PER_SHOT))}m`
    : '—'

  return (
    <div className="page storyboard-page">
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
              role="tab"
              aria-selected={filter === s}
              className={filter === s ? 'active' : ''}
              onClick={() => setFilter(s)}
              title={`Show ${s === 'All' ? 'all' : s.toLowerCase()} shots (${filterCounts[s]})`}
            >
              {s}
              <span>{filterCounts[s]}</span>
            </button>
          ))}
        </div>
        <div>
          <Button
            type="button"
            variant="quiet"
            icon="filter"
            onClick={() =>
              setMessage(
                `Filter active: ${filter} (${filterCounts[filter]} of ${shotTotal} production shots).`,
              )
            }
          >
            Filter
          </Button>
          <Button
            type="button"
            icon={edit ? 'check' : 'edit'}
            onClick={() => setEdit(!edit)}
            title={
              edit
                ? 'Leave edit mode; inspector fields return to read-only.'
                : 'Enable inspector field edits and production API saves.'
            }
          >
            {edit ? 'Finish editing' : 'Edit storyboard'}
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
                  type="button"
                  variant="primary"
                  disabled={busy}
                  title={
                    busy
                      ? 'A studio save or reload is already in progress.'
                      : 'Create the first chapter via the production hierarchy API.'
                  }
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
              const shown = chapterShots.some((s) => visibleIds.has(s.id))
              if (!shown && !showAllShots) return null
              if (!shown && showAllShots && !chapterShots.length && filter !== 'All') return null
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
                        if (!shots.length) return null
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
                              {shots.map((shot, i) => {
                                const gIndex = globalShotIndex(shot.id)
                                const status = approvalToProto(shot.approval_state)
                                const letter = shotLetter(shot.display_label, shot.order_index)
                                // SH index among filtered strip matches prototype scene-local index.
                                const sceneLocalIndex = scene.shots.findIndex((s) => s.id === shot.id)
                                return (
                                  <button
                                    key={shot.id}
                                    type="button"
                                    role="listitem"
                                    className={`shot-card ${shot.id === selected?.id ? 'selected' : ''}`}
                                    onClick={() => selectShot(shot)}
                                  >
                                    <div className={`frame-art frame-${Math.max(0, gIndex) % 8}`}>
                                      <span>{letter}</span>
                                      <i>
                                        <Icon name="play" size={11} />
                                      </i>
                                    </div>
                                    <div>
                                      <span>
                                        <code>{`SH${String((sceneLocalIndex >= 0 ? sceneLocalIndex : i) + 1).padStart(2, '0')}`}</code>
                                        <b>{shot.duration_sec}s</b>
                                      </span>
                                      <strong>{shot.title}</strong>
                                      <StatusPill status={status} />
                                    </div>
                                  </button>
                                )
                              })}
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
              subtitle={`${sceneLabel(selectedSceneIndex)} · ${formatDuration(sceneDurationSec)}`}
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
                    <b>{shotLetter(s.display_label, s.order_index)}</b>
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
                      {s.narration ? '…' : ''}
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
                      const readyStatus = characterReadinessStatus(c)
                      const rolePart = (link.role_in_shot || c.role || 'Character').split('·')[0].trim()
                      const refs = c.reference_assets ?? []
                      const hasApprovedHero = refs.some(
                        (r) =>
                          r.approved &&
                          (r.reference_role === 'hero' || r.reference_role === 'primary'),
                      )
                      const pillLabel =
                        readyStatus === 'Approved' || hasApprovedHero
                          ? 'Approved'
                          : !refs.length || !hasApprovedHero
                            ? 'Needs image'
                            : readyStatus
                      return (
                        <button
                          key={c.id}
                          type="button"
                          onClick={() => navigate('characters')}
                        >
                          <span className="avatar">{characterInitials(c.name)}</span>
                          <span>
                            <b>{c.name}</b>
                            <small>
                              {rolePart} · {linked} shot{linked === 1 ? '' : 's'}
                            </small>
                          </span>
                          <StatusPill status={pillLabel} />
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
                    <span>{genImage}</span>
                    <StatusPill
                      status={
                        generationRec?.availability_status === 'missing' ||
                        catalogVariant?.path_status === 'missing'
                          ? 'Missing'
                          : 'Installed'
                      }
                    />
                  </div>
                  <div>
                    <span>{genVideo}</span>
                    <StatusPill status={videoMissing ? 'Missing' : 'Installed'} />
                  </div>
                  <div>
                    <span>{genWorkflow}</span>
                    <StatusPill
                      status={
                        catalogWorkflow?.registration_status === 'missing' ||
                        workflowRec?.availability_status === 'missing'
                          ? 'Missing'
                          : 'Validated'
                      }
                    />
                  </div>
                  <div title="Planning estimate only — rendering is disabled in Phase A.">
                    <span>Estimated render workload</span>
                    <b>{estimateLabel}</b>
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
            <ShotInspector
              key={`${selected.id}-${data.revision}`}
              shot={selected}
              shotCodeLabel={selectedCode}
              protoShot={selectedProto}
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
              onClose={() => setInspector(false)}
              onOpenWorkflows={() => navigate('workflows')}
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
