/**
 * Structural port of CineForge-Storyboard-Studio-v2 SettingsPage (pagesOps.tsx)
 * adapted to production project storyboard-settings + runtime status APIs.
 */
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  api,
  type ProjectStoryboardSettings,
  type ProjectStoryboardSettingsUpdate,
  type RuntimeStatus,
} from '../../api/client'
import { Button, Icon, Modal, PageTitle, Section, StatusPill } from '../../components/ui'
import { useStudio } from '../StudioState'
import { ErrorState, LoadingState, UnavailableState } from '../components/StateBlocks'

const DEFAULT_DRAFT: ProjectStoryboardSettingsUpdate = {
  shot_duration_min_sec: 6,
  shot_duration_max_sec: 12,
  continuity_policy_json: {
    require_starting_image_when_flagged: true,
    allow_cross_scene_continuity: true,
  },
  prompting_policy_json: {
    require_visual_description: false,
    require_story_purpose: false,
  },
  voice_policy_json: {
    allow_placeholder_for_approval: true,
    allow_manual_for_approval: true,
    require_consent_when_required: true,
    block_unresolved_provider_voices: false,
  },
  approval_policy_json: {
    require_exact_duration: true,
    require_at_least_one_chapter: true,
    require_at_least_one_scene: true,
    require_at_least_one_shot: true,
    require_narration_or_exception: true,
    block_on_shot_blocked: true,
  },
  speaking_rate: 1,
  aspect_ratio: '16:9',
  preview_width: 1280,
  preview_height: 720,
  final_width: 1920,
  final_height: 1080,
  fps: 24,
  captions_enabled: true,
  audio_enabled: true,
  prefer_hosted_providers: false,
  prefer_local_providers: true,
  allow_model_download: false,
  allow_rendering: false,
  require_voice_consent: true,
  require_production_plan_approval: true,
}

const PREVIEW_RESOLUTIONS = [
  { label: '1280 × 720', width: 1280, height: 720 },
  { label: '1920 × 1080', width: 1920, height: 1080 },
] as const

const FINAL_RESOLUTIONS = [
  { label: '1920 × 1080', width: 1920, height: 1080 },
  { label: '3840 × 2160', width: 3840, height: 2160 },
] as const

function editableSettings(settings: ProjectStoryboardSettings): ProjectStoryboardSettingsUpdate {
  return {
    shot_duration_min_sec: settings.shot_duration_min_sec,
    shot_duration_max_sec: settings.shot_duration_max_sec,
    continuity_policy_json: settings.continuity_policy_json,
    prompting_policy_json: settings.prompting_policy_json,
    voice_policy_json: settings.voice_policy_json,
    approval_policy_json: settings.approval_policy_json,
    speaking_rate: settings.speaking_rate,
    aspect_ratio: settings.aspect_ratio,
    preview_width: settings.preview_width,
    preview_height: settings.preview_height,
    final_width: settings.final_width,
    final_height: settings.final_height,
    fps: settings.fps,
    captions_enabled: settings.captions_enabled,
    audio_enabled: settings.audio_enabled,
    prefer_hosted_providers: settings.prefer_hosted_providers,
    prefer_local_providers: settings.prefer_local_providers,
    allow_model_download: settings.allow_model_download,
    allow_rendering: settings.allow_rendering,
    require_voice_consent: settings.require_voice_consent,
    require_production_plan_approval: settings.require_production_plan_approval,
  }
}

function policyFlag(policy: Record<string, unknown>, key: string): boolean {
  return Boolean(policy[key])
}

function resolutionValue(width: number, height: number): string {
  return `${width}x${height}`
}

function parseResolution(value: string): { width: number; height: number } | null {
  const match = /^(\d+)x(\d+)$/.exec(value)
  if (!match) return null
  return { width: Number(match[1]), height: Number(match[2]) }
}

function Toggle({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean
  onChange?: (value: boolean) => void
  label: string
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      className={`toggle${checked ? ' on' : ''}`}
      disabled={disabled}
      onClick={() => {
        if (!disabled && onChange) onChange(!checked)
      }}
    >
      <i />
      <span>{label}</span>
    </button>
  )
}

export function SettingsPage() {
  const { data, busy, setMessage, backendStatus, updateStoryFields } = useStudio()
  const [settings, setSettings] = useState<ProjectStoryboardSettings | null>(null)
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null)
  const [available, setAvailable] = useState(true)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testingRuntime, setTestingRuntime] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [draft, setDraft] = useState<ProjectStoryboardSettingsUpdate>(DEFAULT_DRAFT)
  const [storyTitle, setStoryTitle] = useState('')
  const [storySynopsis, setStorySynopsis] = useState('')
  const [targetRuntime, setTargetRuntime] = useState('')
  const [confirmReset, setConfirmReset] = useState(false)

  const load = useCallback(async () => {
    if (!data) return
    setLoading(true)
    setError(null)
    setStoryTitle(data.story.title)
    setStorySynopsis(data.story.synopsis || '')
    setTargetRuntime(String(data.story.target_duration_sec ?? ''))
    try {
      const [result, rt] = await Promise.all([
        api.getSettings(data.story.project_id),
        api.runtimeStatus().catch(() => null),
      ])
      setRuntime(rt)
      if (result == null) {
        setAvailable(false)
        setSettings(null)
        setDraft(DEFAULT_DRAFT)
      } else {
        setAvailable(true)
        setSettings(result)
        setDraft(editableSettings(result))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load settings.')
    } finally {
      setLoading(false)
    }
  }, [data])

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0)
    return () => window.clearTimeout(timer)
  }, [load])

  if (!data) return null

  const onSave = async (event?: FormEvent) => {
    event?.preventDefault()
    if (!available) return
    setSaving(true)
    setError(null)
    try {
      const parsedRuntime = Number(targetRuntime)
      const nextTitle = storyTitle.trim() || data.story.title
      const nextSynopsis = storySynopsis.trim() || null
      const storyChanged =
        nextTitle !== data.story.title ||
        nextSynopsis !== (data.story.synopsis || null) ||
        (Number.isFinite(parsedRuntime) &&
          parsedRuntime > 0 &&
          Math.round(parsedRuntime) !== data.story.target_duration_sec)
      if (storyChanged) {
        await updateStoryFields({
          title: nextTitle,
          synopsis: nextSynopsis,
          ...(Number.isFinite(parsedRuntime) && parsedRuntime > 0
            ? { target_duration_sec: Math.round(parsedRuntime) }
            : {}),
        })
      }

      const updated = await api.updateSettings(data.story.project_id, {
        ...draft,
        expected_settings_version: settings?.id ? settings.settings_version : undefined,
        // Phase A remains plan-only even if stale server data says otherwise.
        allow_model_download: false,
        allow_rendering: false,
      })
      if (!updated) {
        setAvailable(false)
        setMessage('Project storyboard settings API is unavailable on this backend.')
        return
      }
      setSettings(updated)
      setDraft(editableSettings(updated))
      setMessage('Project storyboard settings saved. Rendering and model downloads remain disabled.')
    } catch (err) {
      const text = err instanceof Error ? err.message : 'Could not save settings.'
      setError(text)
      setMessage(text)
    } finally {
      setSaving(false)
    }
  }

  const testRuntime = async () => {
    setTestingRuntime(true)
    try {
      const rt = await api.runtimeStatus()
      setRuntime(rt)
      setMessage(
        `Runtime status: ComfyUI ${String(rt.comfyui.status ?? 'unknown')} · env ${rt.environment} · phase ${rt.current_phase}. No execution was started.`,
      )
    } catch (err) {
      const text = err instanceof Error ? err.message : 'Runtime status request failed.'
      setMessage(text)
    } finally {
      setTestingRuntime(false)
    }
  }

  if (loading) {
    return (
      <LoadingState
        title="Loading project settings…"
        detail="Fetching project-scoped policy configuration."
      />
    )
  }

  if (!available) {
    return (
      <div className="page settings-page">
        <UnavailableState
          title="Settings API unavailable"
          detail="This backend does not currently expose the project storyboard-settings GET/PUT contract. No local fallback is presented as persisted policy."
        />
        <div className="panel" style={{ marginTop: 14 }}>
          <h2>Read-only story context</h2>
          <ul className="kv-list">
            <li>
              <span>Project</span>
              <strong className="mono">{data.story.project_id}</strong>
            </li>
            <li>
              <span>Story</span>
              <strong>{data.story.title}</strong>
            </li>
            <li>
              <span>Target duration</span>
              <strong>{data.story.target_duration_sec}s</strong>
            </li>
            <li>
              <span>Backend</span>
              <strong>{backendStatus}</strong>
            </li>
          </ul>
        </div>
      </div>
    )
  }

  const savingDisabled = saving || busy

  const setPolicyFlag = (
    bucket:
      | 'continuity_policy_json'
      | 'prompting_policy_json'
      | 'voice_policy_json'
      | 'approval_policy_json',
    key: string,
    value: boolean,
  ) => {
    setDraft({
      ...draft,
      [bucket]: {
        ...draft[bucket],
        [key]: value,
      },
    })
  }

  const previewResolution = resolutionValue(draft.preview_width, draft.preview_height)
  const finalResolution = resolutionValue(draft.final_width, draft.final_height)
  const previewKnown = PREVIEW_RESOLUTIONS.some(
    (item) => item.width === draft.preview_width && item.height === draft.preview_height,
  )
  const finalKnown = FINAL_RESOLUTIONS.some(
    (item) => item.width === draft.final_width && item.height === draft.final_height,
  )

  const comfyStatus = String(runtime?.comfyui.status ?? 'unknown')
  const comfyReady = /ready|ok|available|connected/i.test(comfyStatus)

  return (
    <form className="page settings-page" onSubmit={(event) => void onSave(event)}>
      <PageTitle
        eyebrow="PROJECT CONFIGURATION"
        title="Project settings"
        description="Control planning rules, output defaults, provider permissions, runtime metadata, and safety gates."
        aside={
          <div className="page-actions">
            <Button
              variant="danger"
              icon="trash"
              onClick={() => setConfirmReset(true)}
              disabled={savingDisabled}
            >
              Reset prototype
            </Button>
            <Button type="submit" variant="primary" icon="check" disabled={savingDisabled}>
              {saving ? 'Saving…' : 'Apply settings'}
            </Button>
          </div>
        }
      />

      <p className="form-hint" style={{ marginTop: -4, marginBottom: 12 }}>
        Project <span className="mono">{data.story.project_id}</span>
        {' · '}settings version {settings?.settings_version ?? 'new'}
        {' · '}
        <span className="truth-pill">Server-backed · revision-aware PUT</span>
      </p>

      {error ? <ErrorState detail={error} onRetry={() => void load()} /> : null}

      <div className="settings-grid">
        <Section title="Project" subtitle="Identity, ownership, and version behavior.">
          <div className="form-stack compact">
            <label>
              Project name
              <input
                value={storyTitle}
                onChange={(event) => setStoryTitle(event.target.value)}
                disabled={savingDisabled}
              />
            </label>
            <label>
              Description
              <textarea
                value={storySynopsis}
                onChange={(event) => setStorySynopsis(event.target.value)}
                disabled={savingDisabled}
              />
            </label>
            <div className="form-grid">
              <label>
                Target runtime
                <input
                  type="number"
                  value={targetRuntime}
                  onChange={(event) => setTargetRuntime(event.target.value)}
                  disabled={savingDisabled}
                />
              </label>
              <label>
                Owner
                <input
                  value={data.story.project_id}
                  disabled
                  title="Project ownership is bound to the project id; no separate owner field is exposed."
                />
              </label>
            </div>
            <label>
              Phase
              <input value={runtime?.current_phase ?? 'Phase A planning'} disabled />
            </label>
            <Toggle
              checked={true}
              disabled
              label="Autosave local prototype state (not available — server is source of truth)"
            />
            <Toggle
              checked={policyFlag(draft.approval_policy_json, 'require_exact_duration')}
              disabled={savingDisabled}
              onChange={(value) =>
                setPolicyFlag('approval_policy_json', 'require_exact_duration', value)
              }
              label="Create a draft version on approval (maps to require exact duration gate)"
            />
          </div>
        </Section>

        <Section title="Storyboard" subtitle="Duration, approval, and continuity policies.">
          <div className="form-stack compact">
            <div className="form-grid">
              <label>
                Minimum shot
                <input
                  type="number"
                  min={0.1}
                  step={0.1}
                  value={draft.shot_duration_min_sec}
                  onChange={(event) =>
                    setDraft({ ...draft, shot_duration_min_sec: Number(event.target.value) })
                  }
                  disabled={savingDisabled}
                />
              </label>
              <label>
                Maximum shot
                <input
                  type="number"
                  min={0.1}
                  step={0.1}
                  value={draft.shot_duration_max_sec}
                  onChange={(event) =>
                    setDraft({ ...draft, shot_duration_max_sec: Number(event.target.value) })
                  }
                  disabled={savingDisabled}
                />
              </label>
            </div>
            <Toggle
              checked={policyFlag(draft.approval_policy_json, 'require_narration_or_exception')}
              disabled={savingDisabled}
              onChange={(value) =>
                setPolicyFlag('approval_policy_json', 'require_narration_or_exception', value)
              }
              label="Allow duration override / narration exception policy"
            />
            <Toggle
              checked={policyFlag(draft.approval_policy_json, 'block_on_shot_blocked')}
              disabled={savingDisabled}
              onChange={(value) =>
                setPolicyFlag('approval_policy_json', 'block_on_shot_blocked', value)
              }
              label="Require override reason when shots are blocked"
            />
            <label>
              Approval policy
              <select
                value={
                  policyFlag(draft.approval_policy_json, 'require_at_least_one_shot')
                    ? 'shots'
                    : 'scenes'
                }
                onChange={(event) => {
                  const shots = event.target.value === 'shots'
                  setDraft({
                    ...draft,
                    approval_policy_json: {
                      ...draft.approval_policy_json,
                      require_at_least_one_shot: shots,
                      require_at_least_one_scene: true,
                      require_at_least_one_chapter: true,
                    },
                  })
                }}
                disabled={savingDisabled}
              >
                <option value="shots">Producer approves every shot</option>
                <option value="scenes">Producer approves scenes</option>
              </select>
            </label>
            <label>
              Continuity policy
              <select
                value={
                  policyFlag(draft.continuity_policy_json, 'require_starting_image_when_flagged')
                    ? 'explicit'
                    : 'anchor'
                }
                onChange={(event) =>
                  setPolicyFlag(
                    'continuity_policy_json',
                    'require_starting_image_when_flagged',
                    event.target.value === 'explicit',
                  )
                }
                disabled={savingDisabled}
              >
                <option value="explicit">Explicit source required</option>
                <option value="anchor">Scene anchor allowed</option>
              </select>
            </label>
            <Toggle
              checked={policyFlag(draft.prompting_policy_json, 'require_visual_description')}
              disabled={savingDisabled}
              onChange={(value) =>
                setPolicyFlag('prompting_policy_json', 'require_visual_description', value)
              }
              label="Show narration-fit / visual description warnings"
            />
          </div>
        </Section>

        <Section title="Output" subtitle="Preview and final production targets.">
          <div className="form-stack compact">
            <div className="form-grid">
              <label>
                Aspect ratio
                <select
                  value={draft.aspect_ratio}
                  onChange={(event) => setDraft({ ...draft, aspect_ratio: event.target.value })}
                  disabled={savingDisabled}
                >
                  <option value="16:9">16:9</option>
                  <option value="9:16">9:16</option>
                  <option value="1:1">1:1</option>
                  <option value="2.39:1">2.39:1</option>
                </select>
              </label>
              <label>
                FPS
                <select
                  value={String(draft.fps)}
                  onChange={(event) => setDraft({ ...draft, fps: Number(event.target.value) })}
                  disabled={savingDisabled}
                >
                  <option value="24">24 fps</option>
                  <option value="25">25 fps</option>
                  <option value="30">30 fps</option>
                  <option value="60">60 fps</option>
                  {!['24', '25', '30', '60'].includes(String(draft.fps)) ? (
                    <option value={String(draft.fps)}>{draft.fps} fps (current)</option>
                  ) : null}
                </select>
              </label>
            </div>
            <label>
              Preview resolution
              <select
                value={previewKnown ? previewResolution : 'custom'}
                onChange={(event) => {
                  if (event.target.value === 'custom') return
                  const parsed = parseResolution(event.target.value)
                  if (!parsed) return
                  setDraft({
                    ...draft,
                    preview_width: parsed.width,
                    preview_height: parsed.height,
                  })
                }}
                disabled={savingDisabled}
              >
                {PREVIEW_RESOLUTIONS.map((item) => (
                  <option key={item.label} value={resolutionValue(item.width, item.height)}>
                    {item.label}
                  </option>
                ))}
                {!previewKnown ? (
                  <option value="custom">
                    {draft.preview_width} × {draft.preview_height} (current)
                  </option>
                ) : null}
              </select>
            </label>
            <label>
              Final target
              <select
                value={finalKnown ? finalResolution : 'custom'}
                onChange={(event) => {
                  if (event.target.value === 'custom') return
                  const parsed = parseResolution(event.target.value)
                  if (!parsed) return
                  setDraft({
                    ...draft,
                    final_width: parsed.width,
                    final_height: parsed.height,
                  })
                }}
                disabled={savingDisabled}
              >
                {FINAL_RESOLUTIONS.map((item) => (
                  <option key={item.label} value={resolutionValue(item.width, item.height)}>
                    {item.label}
                  </option>
                ))}
                {!finalKnown ? (
                  <option value="custom">
                    {draft.final_width} × {draft.final_height} (current)
                  </option>
                ) : null}
              </select>
            </label>
            <Toggle
              checked={draft.captions_enabled}
              disabled={savingDisabled}
              onChange={(value) => setDraft({ ...draft, captions_enabled: value })}
              label="Captions required"
            />
            <Toggle
              checked={draft.audio_enabled}
              disabled={savingDisabled}
              onChange={(value) => setDraft({ ...draft, audio_enabled: value })}
              label="Audio plan required"
            />
          </div>
        </Section>

        <Section title="Providers" subtitle="Planning preferences only—no keys are stored.">
          <div className="form-stack compact">
            <label>
              Default provider
              <select
                value={
                  draft.prefer_local_providers && !draft.prefer_hosted_providers
                    ? 'local'
                    : draft.prefer_hosted_providers && !draft.prefer_local_providers
                      ? 'hosted'
                      : 'hybrid'
                }
                onChange={(event) => {
                  const value = event.target.value
                  if (value === 'local') {
                    setDraft({
                      ...draft,
                      prefer_local_providers: true,
                      prefer_hosted_providers: false,
                    })
                  } else if (value === 'hosted') {
                    setDraft({
                      ...draft,
                      prefer_local_providers: false,
                      prefer_hosted_providers: true,
                    })
                  } else {
                    setDraft({
                      ...draft,
                      prefer_local_providers: true,
                      prefer_hosted_providers: true,
                    })
                  }
                }}
                disabled={savingDisabled}
              >
                <option value="hybrid">Hybrid routing</option>
                <option value="hosted">Hosted preferred</option>
                <option value="local">Local only</option>
              </select>
            </label>
            <Toggle
              checked={draft.prefer_local_providers && !draft.prefer_hosted_providers}
              disabled={savingDisabled}
              onChange={(value) =>
                setDraft({
                  ...draft,
                  prefer_local_providers: true,
                  prefer_hosted_providers: value ? false : draft.prefer_hosted_providers,
                })
              }
              label="Local-only mode"
            />
            <Toggle
              checked={policyFlag(draft.voice_policy_json, 'block_unresolved_provider_voices')}
              disabled={savingDisabled}
              onChange={(value) =>
                setPolicyFlag('voice_policy_json', 'block_unresolved_provider_voices', value)
              }
              label="Sensitive-content / unresolved-provider restrictions"
            />
            <Toggle
              checked={draft.prefer_hosted_providers}
              disabled={savingDisabled}
              onChange={(value) => setDraft({ ...draft, prefer_hosted_providers: value })}
              label="Hosted-provider permission"
            />
            <Button
              icon="cpu"
              onClick={() =>
                setMessage(
                  'Provider configuration: This page stores routing preference labels only. API credentials and external provider calls are intentionally unavailable from Settings.',
                )
              }
            >
              Review provider boundary
            </Button>
          </div>
        </Section>

        <Section title="Runtime" subtitle="ComfyUI inventory and device readiness metadata.">
          <div className="runtime-card">
            <div>
              <i />
              <span>
                <b>ComfyUI {comfyStatus}</b>
                <small>
                  {runtime
                    ? `${runtime.environment} · no execution from this page`
                    : 'Runtime status not loaded'}
                </small>
              </span>
              <StatusPill status={comfyReady ? 'Ready' : humanizeRuntime(comfyStatus)} />
            </div>
            <dl>
              <div>
                <dt>URL</dt>
                <dd>From runtime config (not editable here)</dd>
              </div>
              <div>
                <dt>Queue worker</dt>
                <dd>{runtime?.queue.worker_enabled ? 'Enabled' : 'Disabled'}</dd>
              </div>
              <div>
                <dt>Submission</dt>
                <dd>{runtime?.queue.submission_enabled ? 'Enabled' : 'Disabled'}</dd>
              </div>
              <div>
                <dt>object_info</dt>
                <dd>
                  {runtime?.object_info?.available
                    ? `Available${
                        runtime.object_info.class_count != null
                          ? ` · ${runtime.object_info.class_count} classes`
                          : ''
                      }`
                    : 'Unavailable'}
                </dd>
              </div>
              <div>
                <dt>FFmpeg</dt>
                <dd>{String(runtime?.ffmpeg.status ?? 'unknown')}</dd>
              </div>
              <div>
                <dt>Backend</dt>
                <dd>{backendStatus}</dd>
              </div>
            </dl>
            <Button onClick={() => void testRuntime()} disabled={testingRuntime || savingDisabled} icon="play">
              {testingRuntime ? 'Testing…' : 'Test connection'}
            </Button>
          </div>
        </Section>

        <Section title="Safety" subtitle="Explicit approval gates for consequential actions.">
          <div className="form-stack compact">
            <Toggle
              checked={false}
              disabled
              label="Approval before model download (locked off — allow_model_download forced false)"
            />
            <Toggle
              checked={false}
              disabled
              label="Approval before render (locked off — allow_rendering forced false)"
            />
            <Toggle
              checked={draft.require_voice_consent}
              disabled={savingDisabled}
              onChange={(value) => setDraft({ ...draft, require_voice_consent: value })}
              label="Consent for user-provided voice"
            />
            <Toggle
              checked={draft.require_production_plan_approval}
              disabled={savingDisabled}
              onChange={(value) =>
                setDraft({ ...draft, require_production_plan_approval: value })
              }
              label="Final production-plan approval"
            />
            <Toggle
              checked={policyFlag(draft.voice_policy_json, 'require_consent_when_required')}
              disabled={savingDisabled}
              onChange={(value) =>
                setPolicyFlag('voice_policy_json', 'require_consent_when_required', value)
              }
              label="Destructive-action / consent confirmation"
            />
            <div className="safety-note">
              <Icon name="lock" />
              <p>
                Rendering, model downloads, voice cloning, and external execution remain unavailable
                in Phase A planning regardless of these preferences. Saves force{' '}
                <code>allow_model_download=false</code> and <code>allow_rendering=false</code>.
              </p>
            </div>
          </div>
        </Section>
      </div>

      {confirmReset ? (
        <Modal title="Reset local prototype?" onClose={() => setConfirmReset(false)}>
          <div className="confirm-reset">
            <Icon name="warning" size={28} />
            <p>
              Production has no “reset to canonical sample” API. Reload the story from the server or
              load the demo plan from the bootstrap surface instead. No local mock project is
              overwritten from this dialog.
            </p>
            <div className="modal-actions">
              <Button onClick={() => setConfirmReset(false)}>Cancel</Button>
              <Button
                variant="danger"
                disabled
                title="No reset-to-canonical-sample API is exposed in production."
              >
                Reset prototype
              </Button>
            </div>
          </div>
        </Modal>
      ) : null}
    </form>
  )
}

function humanizeRuntime(status: string): string {
  if (!status) return 'Unknown'
  return status.replace(/_/g, ' ')
}
