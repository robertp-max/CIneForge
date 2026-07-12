import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  api,
  type PlanningTaskType,
  type ProjectStoryboardSettings,
  type ProviderExecutionMode,
  type ProviderProfile,
  type RuntimeCatalog,
  type TaskProviderAssignment,
} from '../../api/client'
import { formatDate } from '../../components/formatDate'
import { useStudio } from '../StudioState'
import { EmptyState, ErrorState, LoadingState, UnavailableState } from '../components/StateBlocks'

const TASK_PROFILE_MAP: ReadonlyArray<{
  task: PlanningTaskType
  logicalProfile: 'Sol' | 'Terra' | 'Luna'
  description: string
}> = [
  { task: 'story_structure', logicalProfile: 'Sol', description: 'Long-form story structure' },
  { task: 'character_bible', logicalProfile: 'Terra', description: 'Structured identity detail' },
  { task: 'chapter_outline', logicalProfile: 'Terra', description: 'Chapter-level narrative plan' },
  { task: 'scene_breakdown', logicalProfile: 'Terra', description: 'Narrative continuity and beats' },
  { task: 'shot_list', logicalProfile: 'Luna', description: 'Fast bulk shot planning' },
  { task: 'narration_plan', logicalProfile: 'Terra', description: 'Narration fit and voice planning' },
  { task: 'prompt_package', logicalProfile: 'Luna', description: 'Workflow-specific prompt drafting' },
  { task: 'continuity_plan', logicalProfile: 'Terra', description: 'Cross-shot continuity review' },
  { task: 'model_recommendation', logicalProfile: 'Terra', description: 'Evidence-based model matching' },
  { task: 'production_proposal', logicalProfile: 'Sol', description: 'Final reviewed proposal synthesis' },
]

type RouteDraft = {
  providerProfileId: string
  enabled: boolean
  rationale: string
}

function evidenceClass(status: string): string {
  if (status === 'available' || status === 'verified' || status === 'ready') return 'verified'
  if (status === 'unavailable' || status === 'blocked' || status === 'failed') return 'blocked'
  return 'unknown'
}

function errorText(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback
}

function capabilityLabels(profile: ProviderProfile): string {
  const declared =
    profile.capabilities_json.declared_capabilities ?? profile.capabilities_json.capabilities
  return Array.isArray(declared) && declared.length
    ? declared.map(String).join(', ')
    : 'No declared capabilities'
}

export function RoutingPage() {
  const { data, busy, reload, setMessage } = useStudio()
  const [catalog, setCatalog] = useState<RuntimeCatalog | null>(null)
  const [profiles, setProfiles] = useState<ProviderProfile[]>([])
  const [assignments, setAssignments] = useState<TaskProviderAssignment[]>([])
  const [settings, setSettings] = useState<ProjectStoryboardSettings | null>(null)
  const [catalogAvailable, setCatalogAvailable] = useState(true)
  const [settingsAvailable, setSettingsAvailable] = useState(true)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedProfileId, setSelectedProfileId] = useState('')
  const [preferLocal, setPreferLocal] = useState(true)
  const [preferHosted, setPreferHosted] = useState(false)
  const [routeDrafts, setRouteDrafts] = useState<Record<string, RouteDraft>>({})

  const selectedProfile =
    profiles.find((profile) => profile.id === selectedProfileId) ?? null

  const load = useCallback(async () => {
    if (!data) return
    setLoading(true)
    setError(null)
    try {
      const [catalogResult, profileResult, assignmentResult, settingsResult] = await Promise.all([
        api.runtimeCatalog(),
        api.listProviderProfiles(),
        api.listTaskProviderAssignments(data.story.id),
        api.getSettings(data.story.project_id),
      ])
      setCatalogAvailable(catalogResult != null)
      setCatalog(catalogResult)
      setProfiles(profileResult)
      setAssignments(assignmentResult)
      setRouteDrafts({})
      setSettingsAvailable(settingsResult != null)
      setSettings(settingsResult)
      if (settingsResult) {
        setPreferLocal(settingsResult.prefer_local_providers)
        setPreferHosted(settingsResult.prefer_hosted_providers)
      }
    } catch (err) {
      setError(errorText(err, 'Failed to load routing configuration.'))
    } finally {
      setLoading(false)
    }
  }, [data])

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0)
    return () => window.clearTimeout(timer)
  }, [load])

  const modelsById = useMemo(
    () => new Map(catalog?.models.map((model) => [model.id, model]) ?? []),
    [catalog],
  )

  if (!data) return null

  const resetProfileForm = () => {
    setSelectedProfileId('')
  }

  const declaredCapabilities = (value: string) =>
    value
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)

  const onSaveProfile = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const providerIdentifier = String(form.get('provider_identifier') ?? '').trim()
    const displayName = String(form.get('display_name') ?? '').trim()
    if (!providerIdentifier || !displayName) return
    setSaving(true)
    setError(null)
    try {
      const payload = {
        display_name: displayName,
        provider_model_id: String(form.get('provider_model_id') ?? '').trim() || null,
        execution_mode: String(form.get('execution_mode') ?? 'disabled') as ProviderExecutionMode,
        privacy_classification: String(form.get('privacy_classification') ?? '').trim() || 'unknown',
        capabilities_json: {
          ...(selectedProfile?.capabilities_json ?? {}),
          declared_capabilities: declaredCapabilities(String(form.get('capabilities') ?? '')),
        },
        capability_source: 'user_declared',
      }
      if (selectedProfileId) {
        await api.updateProviderProfile(selectedProfileId, payload)
        setMessage(`Provider profile “${displayName}” updated. Availability was not inferred or changed.`)
      } else {
        await api.createProviderProfile({
          provider_identifier: providerIdentifier,
          ...payload,
          availability_status: 'unknown',
        })
        setMessage(`Provider profile “${displayName}” created with availability Unknown.`)
      }
      await load()
    } catch (err) {
      const text = errorText(err, 'Could not save the provider profile.')
      setError(text)
      setMessage(text)
    } finally {
      setSaving(false)
    }
  }

  const onDeleteProfile = async () => {
    if (!selectedProfile) return
    if (!window.confirm(`Delete provider profile “${selectedProfile.display_name}”?`)) return
    setSaving(true)
    setError(null)
    try {
      await api.deleteProviderProfile(selectedProfile.id)
      resetProfileForm()
      await load()
      setMessage(`Deleted provider profile “${selectedProfile.display_name}”.`)
    } catch (err) {
      const text = errorText(err, 'Could not delete the provider profile.')
      setError(text)
      setMessage(text)
    } finally {
      setSaving(false)
    }
  }

  const updateRouteDraft = (task: PlanningTaskType, patch: Partial<RouteDraft>) => {
    setRouteDrafts((current) => ({
      ...current,
      [task]: {
        providerProfileId:
          current[task]?.providerProfileId ??
          assignments.find((assignment) => assignment.task_type === task)?.provider_profile_id ??
          '',
        enabled:
          current[task]?.enabled ??
          assignments.find((assignment) => assignment.task_type === task)?.enabled ??
          true,
        rationale:
          current[task]?.rationale ??
          assignments.find((assignment) => assignment.task_type === task)?.rationale ??
          '',
        ...patch,
      },
    }))
  }

  const onSaveAssignment = async (task: PlanningTaskType) => {
    const draft = routeDrafts[task]
    if (!draft?.providerProfileId) return
    const existing = assignments.find((assignment) => assignment.task_type === task)
    setSaving(true)
    setError(null)
    try {
      if (existing) {
        await api.updateTaskProviderAssignment(existing.id, {
          provider_profile_id: draft.providerProfileId,
          assignment_mode: 'manual',
          rationale: draft.rationale.trim() || null,
          enabled: draft.enabled,
        })
      } else {
        await api.createTaskProviderAssignment(data.story.id, {
          task_type: task,
          provider_profile_id: draft.providerProfileId,
          assignment_mode: 'manual',
          rationale: draft.rationale.trim() || null,
          enabled: draft.enabled,
          priority: 0,
        })
      }
      await Promise.all([load(), reload()])
      setMessage(`Saved the ${task} provider assignment. Its logical profile remains the displayed default unless a run explicitly overrides it.`)
    } catch (err) {
      const text = errorText(err, 'Could not save the task-provider assignment.')
      setError(text)
      setMessage(text)
    } finally {
      setSaving(false)
    }
  }

  const onDeleteAssignment = async (assignment: TaskProviderAssignment) => {
    setSaving(true)
    setError(null)
    try {
      await api.deleteTaskProviderAssignment(assignment.id)
      await Promise.all([load(), reload()])
      setMessage(`Removed the ${assignment.task_type} provider assignment.`)
    } catch (err) {
      const text = errorText(err, 'Could not delete the task-provider assignment.')
      setError(text)
      setMessage(text)
    } finally {
      setSaving(false)
    }
  }

  const onSavePreferences = async () => {
    if (!settings) return
    if (!preferLocal && !preferHosted) {
      setError('At least one provider privacy preference must remain enabled.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const result = await api.updateSettings(data.story.project_id, {
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
        prefer_hosted_providers: preferHosted,
        prefer_local_providers: preferLocal,
        allow_model_download: settings.allow_model_download,
        allow_rendering: settings.allow_rendering,
        require_voice_consent: settings.require_voice_consent,
        require_production_plan_approval: settings.require_production_plan_approval,
        expected_settings_version: settings.id ? settings.settings_version : undefined,
      })
      if (result == null) {
        setSettingsAvailable(false)
        setMessage('Project routing-preference API is unavailable; no preference was changed.')
        return
      }
      setSettings(result)
      setMessage('Provider privacy preferences saved without probing or contacting a provider.')
    } catch (err) {
      const text = errorText(err, 'Could not save provider privacy preferences.')
      setError(text)
      setMessage(text)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="stack-form">
      <section className="panel">
        <div className="panel-title">
          <div><h2>Model routing</h2><p>Manage planning provider records and per-story task assignments without storing secrets or claiming a connection.</p></div>
          <button type="button" className="ghost-button touch-target" onClick={() => void load()} disabled={loading || busy || saving}>Refresh</button>
        </div>
        {loading ? <LoadingState title="Loading routing records…" /> : null}
        {error ? <ErrorState detail={error} onRetry={() => void load()} /> : null}
      </section>

      <div className="split-2">
        <section className="panel">
          <div className="panel-title"><div><h2>Provider profiles</h2><p>Configuration records only; credentials and secret values are never requested.</p></div><button type="button" className="secondary-button touch-target" onClick={resetProfileForm} disabled={saving}>New profile</button></div>
          {!profiles.length && !loading ? <EmptyState title="No provider profiles" detail="Create a disabled or manually controlled provider record. Availability begins Unknown." /> : null}
          {profiles.length ? (
            <div className="card-grid">
              {profiles.map((profile) => (
                <article key={profile.id}>
                  <b>{profile.display_name}</b>
                  <small>{profile.provider_identifier} · {profile.provider_model_id ?? 'No model selected'}</small>
                  <ul className="kv-list">
                    <li><span>Execution</span><strong>{profile.execution_mode}</strong></li>
                    <li><span>Privacy</span><strong>{profile.privacy_classification ?? 'unknown'}</strong></li>
                    <li><span>Availability</span><strong><span className={`truth-pill ${evidenceClass(profile.availability_status)}`}>{profile.availability_status}</span></strong></li>
                    <li><span>Capabilities</span><strong>{capabilityLabels(profile)}</strong></li>
                    <li><span>Capability source</span><strong>{profile.capability_source ?? 'Unknown'}</strong></li>
                    <li><span>Capability check</span><strong>{profile.capabilities_checked_at ? formatDate(profile.capabilities_checked_at) : 'Never checked'}</strong></li>
                    <li><span>Health check</span><strong>{profile.health_checked_at ? formatDate(profile.health_checked_at) : 'Never checked'}</strong></li>
                  </ul>
                  <button type="button" className={selectedProfile?.id === profile.id ? 'primary-button touch-target' : 'secondary-button touch-target'} onClick={() => setSelectedProfileId(profile.id)}>{selectedProfile?.id === profile.id ? 'Selected' : 'Edit profile'}</button>
                </article>
              ))}
            </div>
          ) : null}
        </section>

        <form key={selectedProfile?.id ?? 'new'} className="panel stack-form" onSubmit={(event) => void onSaveProfile(event)}>
          <div className="panel-title"><div><h2>{selectedProfileId ? 'Edit provider profile' : 'Create provider profile'}</h2><p>Availability remains factual backend evidence and is not editable here.</p></div></div>
          <label>Provider identifier<input name="provider_identifier" required defaultValue={selectedProfile?.provider_identifier ?? ''} disabled={saving} readOnly={Boolean(selectedProfileId)} placeholder="openai, xai, local_cli…" /></label>
          <label>Display name<input name="display_name" required defaultValue={selectedProfile?.display_name ?? ''} disabled={saving} /></label>
          <label>Provider model ID<input name="provider_model_id" defaultValue={selectedProfile?.provider_model_id ?? ''} disabled={saving} placeholder="Optional configuration value" /></label>
          <label>Execution mode<select name="execution_mode" defaultValue={selectedProfile?.execution_mode ?? 'disabled'} disabled={saving}><option value="disabled">Disabled</option><option value="manual">Manual</option><option value="assisted">Assisted</option><option value="automatic">Automatic</option></select></label>
          <label>Privacy classification<select name="privacy_classification" defaultValue={selectedProfile?.privacy_classification ?? 'local'} disabled={saving}><option value="local">Local</option><option value="hosted">Hosted</option><option value="restricted">Restricted</option><option value="unknown">Unknown</option></select></label>
          <label>Declared capabilities<input name="capabilities" defaultValue={selectedProfile ? capabilityLabels(selectedProfile).replace('No declared capabilities', '') : 'planning'} disabled={saving} placeholder="Comma-separated, e.g. planning" /></label>
          <button type="submit" className="primary-button touch-target" disabled={saving}>{saving ? 'Saving…' : 'Save provider profile'}</button>
          {selectedProfile ? <button type="button" className="danger-button touch-target" onClick={() => void onDeleteProfile()} disabled={saving}>Delete profile</button> : null}
          <button type="button" className="secondary-button touch-target" disabled title="No provider validation or health-probe endpoint is exposed in Phase 1; availability and check timestamps remain factual database evidence.">Validate connection — unavailable</button>
          <p className="form-hint">No provider validation or health-probe endpoint is exposed in Phase 1; availability and check timestamps remain factual database evidence.</p>
        </form>
      </div>

      <section className="panel">
        <div className="panel-title"><div><h2>Task-routing matrix</h2><p>Persist a provider profile per task. Sol, Terra, and Luna are deterministic logical defaults; run-specific overrides are configured when starting an orchestration run.</p></div></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Task</th><th>Logical default</th><th>Provider profile</th><th>Enabled</th><th>Rationale</th><th>Action</th></tr></thead>
            <tbody>
              {TASK_PROFILE_MAP.map((row) => {
                const assignment = assignments.find((item) => item.task_type === row.task)
                const draft = routeDrafts[row.task] ?? {
                  providerProfileId: assignment?.provider_profile_id ?? '',
                  enabled: assignment?.enabled ?? true,
                  rationale: assignment?.rationale ?? '',
                }
                return (
                  <tr key={row.task}>
                    <td><strong>{row.task}</strong><div className="form-hint">{row.description}</div></td>
                    <td><span className="truth-pill verified">{row.logicalProfile}</span></td>
                    <td><select value={draft.providerProfileId} onChange={(event) => updateRouteDraft(row.task, { providerProfileId: event.target.value })} disabled={saving || !profiles.length}><option value="">Unassigned</option>{profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.display_name} · {profile.availability_status}</option>)}</select></td>
                    <td><input type="checkbox" checked={draft.enabled} onChange={(event) => updateRouteDraft(row.task, { enabled: event.target.checked })} disabled={saving} aria-label={`Enable ${row.task} provider assignment`} /></td>
                    <td><input value={draft.rationale} onChange={(event) => updateRouteDraft(row.task, { rationale: event.target.value })} disabled={saving} placeholder="Optional review note" /></td>
                    <td>
                      <button type="button" className="secondary-button touch-target" onClick={() => void onSaveAssignment(row.task)} disabled={saving || !draft.providerProfileId}>Save</button>
                      {assignment ? <button type="button" className="ghost-button touch-target" onClick={() => void onDeleteAssignment(assignment)} disabled={saving}>Remove</button> : null}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>

      <div className="split-2">
        <section className="panel stack-form">
          <div className="panel-title"><div><h2>Privacy preference</h2><p>Project-scoped routing policy used by new orchestration runs.</p></div></div>
          {!settingsAvailable && !loading ? <UnavailableState title="Project settings unavailable" detail="No privacy preference was inferred or changed." /> : null}
          {settings ? (
            <>
              <label className="checkbox-row"><input type="checkbox" checked={preferLocal} onChange={(event) => setPreferLocal(event.target.checked)} disabled={saving} />Prefer local providers</label>
              <label className="checkbox-row"><input type="checkbox" checked={preferHosted} onChange={(event) => setPreferHosted(event.target.checked)} disabled={saving} />Permit hosted providers</label>
              <button type="button" className="primary-button touch-target" onClick={() => void onSavePreferences()} disabled={saving || (!preferLocal && !preferHosted)}>Save privacy preference</button>
              {!preferLocal && !preferHosted ? <p className="notice warning">At least one provider class must be permitted for routing.</p> : null}
              <p className="form-hint">Saving policy does not contact providers, validate credentials, or start a planning run.</p>
            </>
          ) : null}
        </section>

        <section className="panel">
          <div className="panel-title"><div><h2>Factual runtime catalog</h2><p>Database evidence only; no hardware or provider probes run from this page.</p></div></div>
          {!catalogAvailable && !loading ? <UnavailableState title="Runtime catalog unavailable" detail="No model, install, benchmark, or connection claim is inferred." /> : null}
          {catalog ? <p className="notice info">{catalog.summary.evidence_note}</p> : null}
          {!loading && catalog && !catalog.model_variants.length ? <EmptyState title="No model variants registered" detail="The runtime catalog contains no model-variant records." /> : null}
          {catalog?.model_variants.length ? (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Model / variant</th><th>24 GB</th><th>Path</th><th>Checksum</th><th>Benchmark</th><th>Native voice</th></tr></thead>
                <tbody>
                  {catalog.model_variants.map((variant) => {
                    const model = modelsById.get(variant.model_id)
                    return (
                      <tr key={variant.id}>
                        <td><strong>{model ? `${model.family} · ${model.name}` : 'Unknown model'}</strong><div className="form-hint">{variant.variant_name}</div></td>
                        <td>{variant.compatible_24gb_status || 'unknown'}</td>
                        <td><span className={`truth-pill ${evidenceClass(variant.path_status)}`}>{variant.path_status}</span></td>
                        <td><span className={`truth-pill ${evidenceClass(variant.checksum_status)}`}>{variant.checksum_status}</span></td>
                        <td><span className={`truth-pill ${evidenceClass(variant.benchmark_status)}`}>{variant.benchmark_status}</span> {variant.benchmark_run_count ? `${variant.benchmark_run_count} run(s)` : ''}</td>
                        <td>{variant.native_voice_capability || 'unknown'}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
      </div>
    </div>
  )
}
