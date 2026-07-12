import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  api,
  type ProjectStoryboardSettings,
  type ProjectStoryboardSettingsUpdate,
} from '../../api/client'
import { Button, PageTitle, Section } from '../../components/ui'
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

type ToggleRowProps = {
  label: string
  checked: boolean
  disabled?: boolean
  locked?: boolean
  onChange?: (checked: boolean) => void
}

function ToggleRow({ label, checked, disabled, locked, onChange }: ToggleRowProps) {
  return (
    <label className="toggle-row">
      <span>
        {label}
        {locked ? <small style={{ display: 'block', color: 'var(--muted)' }}>Locked off in Phase A planning</small> : null}
      </span>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled || locked}
        aria-disabled={locked || disabled ? true : undefined}
        onChange={
          locked || !onChange
            ? undefined
            : (event) => onChange(event.target.checked)
        }
        style={{ width: 20, height: 20, minHeight: 20 }}
      />
    </label>
  )
}

export function SettingsPage() {
  const { data, busy, setMessage, backendStatus } = useStudio()
  const [settings, setSettings] = useState<ProjectStoryboardSettings | null>(null)
  const [available, setAvailable] = useState(true)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [draft, setDraft] = useState<ProjectStoryboardSettingsUpdate>(DEFAULT_DRAFT)

  const load = useCallback(async () => {
    if (!data) return
    setLoading(true)
    setError(null)
    try {
      const result = await api.getSettings(data.story.project_id)
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

  const onSave = async (event: FormEvent) => {
    event.preventDefault()
    if (!available) return
    setSaving(true)
    setError(null)
    try {
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

  if (loading) {
    return <LoadingState title="Loading project settings…" detail="Fetching project-scoped policy configuration." />
  }

  if (!available) {
    return (
      <>
        <UnavailableState
          title="Settings API unavailable"
          detail="This backend does not currently expose the project storyboard-settings GET/PUT contract. No local fallback is presented as persisted policy."
        />
        <div className="panel" style={{ marginTop: 14 }}>
          <h2>Read-only story context</h2>
          <ul className="kv-list">
            <li><span>Project</span><strong className="mono">{data.story.project_id}</strong></li>
            <li><span>Story</span><strong>{data.story.title}</strong></li>
            <li><span>Target duration</span><strong>{data.story.target_duration_sec}s</strong></li>
            <li><span>Backend</span><strong>{backendStatus}</strong></li>
          </ul>
        </div>
      </>
    )
  }

  const savingDisabled = saving || busy

  const setPolicyFlag = (
    bucket: 'continuity_policy_json' | 'prompting_policy_json' | 'voice_policy_json' | 'approval_policy_json',
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

  return (
    <form className="page settings-page" onSubmit={(event) => void onSave(event)}>
      <PageTitle
        eyebrow="PROJECT CONFIGURATION"
        title="Project settings"
        description="Control planning rules, output defaults, provider preferences, and safety gates for this project."
        aside={
          <div className="page-actions">
            <Button
              icon="spark"
              onClick={() => void load()}
              disabled={savingDisabled}
            >
              Refresh
            </Button>
            <Button
              type="submit"
              variant="primary"
              icon="check"
              disabled={savingDisabled}
            >
              {saving ? 'Saving…' : 'Save settings'}
            </Button>
          </div>
        }
      />

      <div className="panel-title" style={{ marginBottom: 12 }}>
        <div>
          <p className="form-hint" style={{ margin: 0 }}>
            Project <span className="mono">{data.story.project_id}</span>
            {' · '}settings version {settings?.settings_version ?? 'new'}
            {' · '}<span className="truth-pill">Server-backed · revision-aware PUT</span>
          </p>
        </div>
      </div>

      {error ? <ErrorState detail={error} onRetry={() => void load()} /> : null}

      <div className="settings-grid">
        <Section title="Storyboard" subtitle="Duration, approval, continuity, and prompting policies.">
          <div className="stack-form" style={{ maxWidth: '100%' }}>
            <div className="split-2">
              <label>
                Minimum shot (sec)
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
                Maximum shot (sec)
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
            <label>
              Speaking rate
              <input
                type="number"
                min={0.1}
                step={0.05}
                value={draft.speaking_rate}
                onChange={(event) => setDraft({ ...draft, speaking_rate: Number(event.target.value) })}
                disabled={savingDisabled}
              />
            </label>
            <ToggleRow
              label="Require exact reconciled story duration"
              checked={policyFlag(draft.approval_policy_json, 'require_exact_duration')}
              disabled={savingDisabled}
              onChange={(checked) => setPolicyFlag('approval_policy_json', 'require_exact_duration', checked)}
            />
            <ToggleRow
              label="Require at least one chapter"
              checked={policyFlag(draft.approval_policy_json, 'require_at_least_one_chapter')}
              disabled={savingDisabled}
              onChange={(checked) => setPolicyFlag('approval_policy_json', 'require_at_least_one_chapter', checked)}
            />
            <ToggleRow
              label="Require at least one scene"
              checked={policyFlag(draft.approval_policy_json, 'require_at_least_one_scene')}
              disabled={savingDisabled}
              onChange={(checked) => setPolicyFlag('approval_policy_json', 'require_at_least_one_scene', checked)}
            />
            <ToggleRow
              label="Require at least one shot"
              checked={policyFlag(draft.approval_policy_json, 'require_at_least_one_shot')}
              disabled={savingDisabled}
              onChange={(checked) => setPolicyFlag('approval_policy_json', 'require_at_least_one_shot', checked)}
            />
            <ToggleRow
              label="Require narration or exception"
              checked={policyFlag(draft.approval_policy_json, 'require_narration_or_exception')}
              disabled={savingDisabled}
              onChange={(checked) => setPolicyFlag('approval_policy_json', 'require_narration_or_exception', checked)}
            />
            <ToggleRow
              label="Block approval when any shot is blocked"
              checked={policyFlag(draft.approval_policy_json, 'block_on_shot_blocked')}
              disabled={savingDisabled}
              onChange={(checked) => setPolicyFlag('approval_policy_json', 'block_on_shot_blocked', checked)}
            />
            <ToggleRow
              label="Require starting image when a shot is flagged"
              checked={policyFlag(draft.continuity_policy_json, 'require_starting_image_when_flagged')}
              disabled={savingDisabled}
              onChange={(checked) =>
                setPolicyFlag('continuity_policy_json', 'require_starting_image_when_flagged', checked)
              }
            />
            <ToggleRow
              label="Allow cross-scene continuity"
              checked={policyFlag(draft.continuity_policy_json, 'allow_cross_scene_continuity')}
              disabled={savingDisabled}
              onChange={(checked) =>
                setPolicyFlag('continuity_policy_json', 'allow_cross_scene_continuity', checked)
              }
            />
            <ToggleRow
              label="Require visual description on shots"
              checked={policyFlag(draft.prompting_policy_json, 'require_visual_description')}
              disabled={savingDisabled}
              onChange={(checked) =>
                setPolicyFlag('prompting_policy_json', 'require_visual_description', checked)
              }
            />
            <ToggleRow
              label="Require story purpose on shots"
              checked={policyFlag(draft.prompting_policy_json, 'require_story_purpose')}
              disabled={savingDisabled}
              onChange={(checked) =>
                setPolicyFlag('prompting_policy_json', 'require_story_purpose', checked)
              }
            />
            <ToggleRow
              label="Allow placeholder voices for approval"
              checked={policyFlag(draft.voice_policy_json, 'allow_placeholder_for_approval')}
              disabled={savingDisabled}
              onChange={(checked) =>
                setPolicyFlag('voice_policy_json', 'allow_placeholder_for_approval', checked)
              }
            />
            <ToggleRow
              label="Allow manual voices for approval"
              checked={policyFlag(draft.voice_policy_json, 'allow_manual_for_approval')}
              disabled={savingDisabled}
              onChange={(checked) =>
                setPolicyFlag('voice_policy_json', 'allow_manual_for_approval', checked)
              }
            />
            <ToggleRow
              label="Require consent when voice policy marks it required"
              checked={policyFlag(draft.voice_policy_json, 'require_consent_when_required')}
              disabled={savingDisabled}
              onChange={(checked) =>
                setPolicyFlag('voice_policy_json', 'require_consent_when_required', checked)
              }
            />
            <ToggleRow
              label="Block unresolved provider voices"
              checked={policyFlag(draft.voice_policy_json, 'block_unresolved_provider_voices')}
              disabled={savingDisabled}
              onChange={(checked) =>
                setPolicyFlag('voice_policy_json', 'block_unresolved_provider_voices', checked)
              }
            />
          </div>
        </Section>

        <Section title="Output" subtitle="Preview and final production targets.">
          <div className="stack-form" style={{ maxWidth: '100%' }}>
            <div className="split-2">
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
                Frames per second
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
              Final target resolution
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
            <div className="split-2">
              <label>
                Preview width
                <input
                  type="number"
                  min={1}
                  step={1}
                  value={draft.preview_width}
                  onChange={(event) =>
                    setDraft({ ...draft, preview_width: Number(event.target.value) })
                  }
                  disabled={savingDisabled}
                />
              </label>
              <label>
                Preview height
                <input
                  type="number"
                  min={1}
                  step={1}
                  value={draft.preview_height}
                  onChange={(event) =>
                    setDraft({ ...draft, preview_height: Number(event.target.value) })
                  }
                  disabled={savingDisabled}
                />
              </label>
            </div>
            <div className="split-2">
              <label>
                Final width
                <input
                  type="number"
                  min={1}
                  step={1}
                  value={draft.final_width}
                  onChange={(event) =>
                    setDraft({ ...draft, final_width: Number(event.target.value) })
                  }
                  disabled={savingDisabled}
                />
              </label>
              <label>
                Final height
                <input
                  type="number"
                  min={1}
                  step={1}
                  value={draft.final_height}
                  onChange={(event) =>
                    setDraft({ ...draft, final_height: Number(event.target.value) })
                  }
                  disabled={savingDisabled}
                />
              </label>
            </div>
            <ToggleRow
              label="Captions enabled"
              checked={draft.captions_enabled}
              disabled={savingDisabled}
              onChange={(checked) => setDraft({ ...draft, captions_enabled: checked })}
            />
            <ToggleRow
              label="Audio enabled"
              checked={draft.audio_enabled}
              disabled={savingDisabled}
              onChange={(checked) => setDraft({ ...draft, audio_enabled: checked })}
            />
          </div>
        </Section>

        <Section title="Providers" subtitle="Planning preferences only—no credentials are stored here.">
          <div className="stack-form" style={{ maxWidth: '100%' }}>
            <ToggleRow
              label="Prefer local providers"
              checked={draft.prefer_local_providers}
              disabled={savingDisabled}
              onChange={(checked) => setDraft({ ...draft, prefer_local_providers: checked })}
            />
            <ToggleRow
              label="Prefer hosted providers"
              checked={draft.prefer_hosted_providers}
              disabled={savingDisabled}
              onChange={(checked) => setDraft({ ...draft, prefer_hosted_providers: checked })}
            />
            <p className="form-hint">
              These flags influence planning routing preference metadata only. They do not store API
              keys, open provider sessions, or start planning runs.
            </p>
          </div>
        </Section>

        <Section title="Safety" subtitle="Explicit approval gates for consequential actions.">
          <div className="stack-form" style={{ maxWidth: '100%' }}>
            <ToggleRow
              label="Require voice consent"
              checked={draft.require_voice_consent}
              disabled={savingDisabled}
              onChange={(checked) => setDraft({ ...draft, require_voice_consent: checked })}
            />
            <ToggleRow
              label="Require production-plan approval"
              checked={draft.require_production_plan_approval}
              disabled={savingDisabled}
              onChange={(checked) =>
                setDraft({ ...draft, require_production_plan_approval: checked })
              }
            />
            <ToggleRow
              label="Allow model download"
              checked={false}
              locked
              disabled={savingDisabled}
            />
            <ToggleRow
              label="Allow rendering"
              checked={false}
              locked
              disabled={savingDisabled}
            />
            <p className="form-hint">
              Rendering and model downloads remain forced off on every save in Phase A, regardless of
              server or draft values.
            </p>
          </div>
        </Section>
      </div>

      <div className="inline-actions" style={{ marginTop: 16 }}>
        <Button type="submit" variant="primary" icon="check" disabled={savingDisabled}>
          {saving ? 'Saving…' : 'Save settings'}
        </Button>
        <span className="truth-pill">Server-backed · revision-aware PUT</span>
      </div>

      <p className="form-hint">
        Saving settings does not install models, submit workflows, queue renders, or generate media.
      </p>
    </form>
  )
}
