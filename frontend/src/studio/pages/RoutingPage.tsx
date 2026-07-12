import { useCallback, useEffect, useMemo, useState, type FormEvent, type KeyboardEvent } from 'react'
import {
  api,
  type OrchestrationRoutingMode,
  type PlanningTaskType,
  type ProjectStoryboardSettings,
  type ProviderCatalogEntry,
  type ProviderExecutionMode,
  type ProviderProfile,
  type RoutingPreflightResponse,
  type RuntimeCatalog,
  type TaskProviderAssignment,
} from '../../api/client'
import { formatDate } from '../../components/formatDate'
import { Button, PageTitle, Section } from '../../components/ui'
import { useStudio } from '../StudioState'
import { EmptyState, ErrorState, LoadingState, UnavailableState } from '../components/StateBlocks'

const TASK_PROFILE_MAP: ReadonlyArray<{
  task: PlanningTaskType
  label: string
  logicalProfile: 'Sol' | 'Terra' | 'Luna'
  description: string
}> = [
  { task: 'story_structure', label: 'Story structure', logicalProfile: 'Sol', description: 'Long-form story structure' },
  { task: 'character_bible', label: 'Character bible', logicalProfile: 'Terra', description: 'Structured identity detail' },
  { task: 'chapter_outline', label: 'Chapter outline', logicalProfile: 'Terra', description: 'Chapter-level narrative plan' },
  { task: 'scene_breakdown', label: 'Scene breakdown', logicalProfile: 'Terra', description: 'Narrative continuity and beats' },
  { task: 'shot_list', label: 'Shot list', logicalProfile: 'Luna', description: 'Fast bulk shot planning' },
  { task: 'narration_plan', label: 'Narration plan', logicalProfile: 'Terra', description: 'Narration fit and voice planning' },
  { task: 'prompt_package', label: 'Prompt package', logicalProfile: 'Luna', description: 'Workflow-specific prompt drafting' },
  { task: 'continuity_plan', label: 'Continuity plan', logicalProfile: 'Terra', description: 'Cross-shot continuity review' },
  { task: 'model_recommendation', label: 'Model recommendation', logicalProfile: 'Terra', description: 'Evidence-based model matching' },
  { task: 'production_proposal', label: 'Production proposal', logicalProfile: 'Sol', description: 'Final reviewed proposal synthesis' },
]

type RouteDraft = {
  providerProfileId: string
  enabled: boolean
  rationale: string
}

type DrawerFocus =
  | { kind: 'task'; task: PlanningTaskType }
  | { kind: 'profile'; profileId: string | null }

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

/** Map backend availability to a StatusPill token. Display remains factual. */
function availabilityPillStatus(status: string): string {
  const normalized = status.trim().toLowerCase().replace(/\s+/g, '_')
  if (normalized === 'available' || normalized === 'verified' || normalized === 'ready') return 'verified'
  if (normalized === 'manual' || normalized === 'assisted' || normalized === 'unknown') return 'manual'
  if (
    normalized === 'unavailable' ||
    normalized === 'blocked' ||
    normalized === 'failed' ||
    normalized === 'error' ||
    normalized === 'missing'
  ) {
    return 'error'
  }
  if (normalized === 'not_configured' || normalized === 'not_implemented' || normalized === 'disabled') {
    return normalized === 'disabled' ? 'disabled' : 'missing'
  }
  if (normalized === 'auto' || normalized === 'default' || normalized === 'suggested') return 'auto'
  return normalized || 'unknown'
}

function humanizeStatus(status: string): string {
  return status.replace(/_/g, ' ')
}

function privacyLabel(value: string | null | undefined): string {
  if (!value || value === 'unknown') return 'Unknown'
  if (value === 'local') return 'Local'
  if (value === 'hosted') return 'Hosted'
  if (value === 'restricted') return 'Restricted'
  return humanizeStatus(value)
}

function modePillStatus(mode: string): string {
  const normalized = mode.trim().toLowerCase()
  if (normalized === 'manual') return 'manual'
  if (normalized === 'automatic' || normalized === 'auto') return 'auto'
  if (normalized === 'disabled') return 'disabled'
  return 'draft'
}

/** Status pill with factual label text and CSS token for coloring. */
function EvidencePill({ status, label }: { status: string; label?: string }) {
  const token = availabilityPillStatus(status)
  return (
    <span className="status-pill" data-status={token}>
      {label ?? humanizeStatus(status)}
    </span>
  )
}

function ModePill({ mode }: { mode: string }) {
  return (
    <span className="status-pill" data-status={modePillStatus(mode)}>
      {humanizeStatus(mode)}
    </span>
  )
}

export function RoutingPage() {
  const { data, busy, reload, setMessage } = useStudio()
  const [catalog, setCatalog] = useState<RuntimeCatalog | null>(null)
  const [profiles, setProfiles] = useState<ProviderProfile[]>([])
  const [assignments, setAssignments] = useState<TaskProviderAssignment[]>([])
  const [providerCatalog, setProviderCatalog] = useState<ProviderCatalogEntry[]>([])
  const [settings, setSettings] = useState<ProjectStoryboardSettings | null>(null)
  const [catalogAvailable, setCatalogAvailable] = useState(true)
  const [settingsAvailable, setSettingsAvailable] = useState(true)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testingConnection, setTestingConnection] = useState(false)
  const [routingTestBusy, setRoutingTestBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [preferLocal, setPreferLocal] = useState(true)
  const [preferHosted, setPreferHosted] = useState(false)
  const [routingMode, setRoutingMode] = useState<OrchestrationRoutingMode>('hybrid')
  const [routeDrafts, setRouteDrafts] = useState<Record<string, RouteDraft>>({})
  const [drawer, setDrawer] = useState<DrawerFocus>({ kind: 'task', task: 'story_structure' })
  const [preflight, setPreflight] = useState<RoutingPreflightResponse | null>(null)
  const [lastConnectionNote, setLastConnectionNote] = useState<string | null>(null)
  const [privacyNoteOpen, setPrivacyNoteOpen] = useState(false)

  const profilesById = useMemo(() => new Map(profiles.map((profile) => [profile.id, profile])), [profiles])
  const catalogByIdentifier = useMemo(
    () => new Map(providerCatalog.map((entry) => [entry.provider_identifier, entry])),
    [providerCatalog],
  )

  const load = useCallback(async () => {
    if (!data) return
    setLoading(true)
    setError(null)
    try {
      const [catalogResult, profileResult, assignmentResult, settingsResult, providersResult] =
        await Promise.all([
          api.runtimeCatalog(),
          api.listProviderProfiles(),
          api.listTaskProviderAssignments(data.story.id),
          api.getSettings(data.story.project_id),
          api.listPlanningProviders().catch(() => null),
        ])
      setCatalogAvailable(catalogResult != null)
      setCatalog(catalogResult)
      setProfiles(profileResult)
      setAssignments(assignmentResult)
      setRouteDrafts({})
      setSettingsAvailable(settingsResult != null)
      setSettings(settingsResult)
      setProviderCatalog(providersResult?.providers ?? [])
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

  const selectedProfileId = drawer.kind === 'profile' ? drawer.profileId : null
  const selectedProfile =
    selectedProfileId != null
      ? profiles.find((profile) => profile.id === selectedProfileId) ?? null
      : null
  const selectedTask =
    drawer.kind === 'task'
      ? drawer.task
      : TASK_PROFILE_MAP[0]?.task ?? 'story_structure'
  const selectedTaskMeta =
    TASK_PROFILE_MAP.find((row) => row.task === selectedTask) ?? TASK_PROFILE_MAP[0]

  const getDraft = (task: PlanningTaskType): RouteDraft => {
    const assignment = assignments.find((item) => item.task_type === task)
    return (
      routeDrafts[task] ?? {
        providerProfileId: assignment?.provider_profile_id ?? '',
        enabled: assignment?.enabled ?? true,
        rationale: assignment?.rationale ?? '',
      }
    )
  }

  const assignedCount = TASK_PROFILE_MAP.filter((row) => {
    const draft = getDraft(row.task)
    return Boolean(draft.providerProfileId)
  }).length
  const availableProfiles = profiles.filter((profile) =>
    ['available', 'verified', 'ready'].includes(profile.availability_status.toLowerCase()),
  ).length
  const unknownProfiles = profiles.filter((profile) => {
    const status = profile.availability_status.toLowerCase()
    return status === 'unknown' || status === 'not_configured' || status === 'not_implemented'
  }).length
  const enabledAssignments = assignments.filter((assignment) => assignment.enabled).length

  const resetProfileForm = () => {
    setDrawer({ kind: 'profile', profileId: null })
    setLastConnectionNote(null)
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
        setMessage(
          `Provider profile “${displayName}” updated. Availability was not inferred or changed.`,
        )
      } else {
        const created = await api.createProviderProfile({
          provider_identifier: providerIdentifier,
          ...payload,
          availability_status: 'unknown',
        })
        setDrawer({ kind: 'profile', profileId: created.id })
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
    const draft = routeDrafts[task] ?? getDraft(task)
    if (!draft.providerProfileId) return
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
      setMessage(
        `Saved the ${task} provider assignment. Its logical profile remains the displayed default unless a run explicitly overrides it.`,
      )
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

  const connectionSupportFor = (profile: ProviderProfile | null) => {
    if (!profile) {
      return {
        supported: false,
        reason: 'Select a saved provider profile before running a connection test.',
      }
    }
    const catalogEntry = catalogByIdentifier.get(profile.provider_identifier)
    if (!catalogEntry) {
      return {
        supported: false,
        reason: `No planning-provider catalog entry for “${profile.provider_identifier}”; connection test is not advertised.`,
      }
    }
    if (!catalogEntry.connection_test_supported) {
      return {
        supported: false,
        reason: `Connection test is not supported for “${profile.provider_identifier}” (backend advertises connection_test_supported=false). Only mock and openai expose a bounded test.`,
      }
    }
    return { supported: true, reason: catalogEntry.detail }
  }

  const onTestConnection = async () => {
    if (!selectedProfile) return
    const support = connectionSupportFor(selectedProfile)
    if (!support.supported) {
      setLastConnectionNote(support.reason)
      setMessage(support.reason)
      return
    }
    setTestingConnection(true)
    setError(null)
    setLastConnectionNote(null)
    try {
      const result = await api.testPlanningProviderConnection(selectedProfile.provider_identifier)
      const latency = result.latency_ms != null ? ` · ${result.latency_ms} ms` : ''
      const note = result.success
        ? `Connection test succeeded for ${result.provider_identifier}: ${result.availability_status}${latency}. ${result.detail}`
        : `Connection test did not succeed for ${result.provider_identifier}: ${result.availability_status}${latency}. ${result.detail}${result.error_code ? ` (${result.error_code})` : ''}`
      setLastConnectionNote(note)
      setMessage(note)
      await load()
    } catch (err) {
      const text = errorText(err, 'Connection test request failed.')
      setLastConnectionNote(text)
      setError(text)
      setMessage(text)
    } finally {
      setTestingConnection(false)
    }
  }

  const onRunRoutingTest = async () => {
    setRoutingTestBusy(true)
    setError(null)
    try {
      const result = await api.validateStoryRouting(data.story.id, {
        routing_mode: routingMode,
        prefer_local_providers: preferLocal,
        prefer_hosted_providers: preferHosted,
      })
      setPreflight(result)
      const gapCount = result.errors.length + result.warnings.length
      setMessage(
        result.valid
          ? `Routing preflight valid (${result.effective_mode}): ${result.routes.length} route(s)${gapCount ? `, ${gapCount} warning(s)` : ''}.`
          : `Routing preflight failed (${result.effective_mode}): ${result.errors.length} error(s), ${result.warnings.length} warning(s).`,
      )
    } catch (err) {
      const text = errorText(err, 'Routing preflight request failed.')
      setError(text)
      setMessage(text)
      setPreflight(null)
    } finally {
      setRoutingTestBusy(false)
    }
  }

  const selectTask = (task: PlanningTaskType) => {
    setDrawer({ kind: 'task', task })
    setLastConnectionNote(null)
  }

  const onTaskKeyDown = (event: KeyboardEvent<HTMLDivElement>, task: PlanningTaskType) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      selectTask(task)
    }
  }

  const selectedDraft = getDraft(selectedTask)
  const selectedAssignment = assignments.find((item) => item.task_type === selectedTask)
  const selectedRouteProfile = selectedDraft.providerProfileId
    ? profilesById.get(selectedDraft.providerProfileId) ?? null
    : null
  const selectedRouteCatalog = selectedRouteProfile
    ? catalogByIdentifier.get(selectedRouteProfile.provider_identifier)
    : null
  const connectionSupport = connectionSupportFor(selectedProfile)
  const disabled = loading || busy || saving || testingConnection || routingTestBusy

  return (
    <div className="page" style={{ display: 'grid', gap: 14 }}>
      <PageTitle
        eyebrow="MODEL ORCHESTRATION"
        title="Model routing"
        description="Manage planning provider records and per-story task assignments without storing secrets. Availability and connection claims stay factual backend evidence."
        aside={
          <div className="page-actions">
            <Button
              variant="secondary"
              icon="lock"
              onClick={() => setPrivacyNoteOpen((open) => !open)}
              title="Privacy boundary"
            >
              Privacy boundary
            </Button>
            <Button
              variant="secondary"
              icon="clock"
              onClick={() => void load()}
              disabled={disabled}
            >
              Refresh
            </Button>
            <Button
              variant="primary"
              icon="play"
              onClick={() => void onRunRoutingTest()}
              disabled={disabled}
              title="Runs POST /stories/{id}/routing/validate (non-mutating preflight)."
            >
              {routingTestBusy ? 'Testing routes…' : 'Run routing test'}
            </Button>
          </div>
        }
      />

      {privacyNoteOpen ? (
        <p className="notice info">
          Credentials and secret values are never requested on this page. Connection tests only run when
          the planning-provider catalog advertises <code>connection_test_supported</code> (mock and openai).
          Availability pills reflect stored or catalog evidence—never an inferred “Connected” claim.
        </p>
      ) : null}

      {loading ? <LoadingState title="Loading routing records…" /> : null}
      {error ? <ErrorState detail={error} onRetry={() => void load()} /> : null}

      <section className="panel" style={{ padding: 14 }}>
        <div
          className="form-grid"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: 12,
            alignItems: 'end',
          }}
        >
          <label>
            Preflight routing mode
            <div className="segmented" style={{ margin: '6px 0 0' }}>
              {(['automatic', 'hybrid', 'manual'] as const).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  className={routingMode === mode ? 'active' : ''}
                  onClick={() => setRoutingMode(mode)}
                  disabled={disabled}
                >
                  {mode}
                </button>
              ))}
            </div>
          </label>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center', alignSelf: 'center' }}>
            <input
              type="checkbox"
              checked={preferLocal}
              onChange={(event) => setPreferLocal(event.target.checked)}
              disabled={disabled || !settings}
            />
            Prefer local providers
          </label>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center', alignSelf: 'center' }}>
            <input
              type="checkbox"
              checked={preferHosted}
              onChange={(event) => setPreferHosted(event.target.checked)}
              disabled={disabled || !settings}
            />
            Permit hosted providers
          </label>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <Button
              variant="primary"
              onClick={() => void onSavePreferences()}
              disabled={disabled || !settings || (!preferLocal && !preferHosted)}
              title={
                settingsAvailable
                  ? 'Persist privacy preferences for this project.'
                  : 'Project settings API unavailable.'
              }
            >
              Save privacy preference
            </Button>
          </div>
        </div>
        {!settingsAvailable && !loading ? (
          <UnavailableState
            title="Project settings unavailable"
            detail="No privacy preference was inferred or changed."
          />
        ) : null}
        {!preferLocal && !preferHosted ? (
          <p className="notice warning">At least one provider class must be permitted for routing.</p>
        ) : null}
        <p className="form-hint">
          Privacy toggles persist via project settings. Preflight mode is used only for routing validation
          and is not stored as a project default.
        </p>
      </section>

      {preflight ? (
        <div className={`notice ${preflight.valid ? 'success' : 'warning'}`}>
          <strong>
            Routing preflight {preflight.valid ? 'valid' : 'failed'} · mode {preflight.effective_mode}
          </strong>
          <div className="form-hint">
            {preflight.routes.length} route(s) · {preflight.errors.length} error(s) ·{' '}
            {preflight.warnings.length} warning(s)
            {preflight.errors[0] ? ` · ${preflight.errors[0].message}` : ''}
            {preflight.warnings[0] && !preflight.errors[0] ? ` · ${preflight.warnings[0].message}` : ''}
          </div>
          <button type="button" className="ghost-button" onClick={() => setPreflight(null)}>
            Dismiss
          </button>
        </div>
      ) : null}

      <div className="summary-strip">
        <div>
          <span>Provider profiles</span>
          <b>{profiles.length}</b>
        </div>
        <div>
          <span>Evidence available</span>
          <b>{availableProfiles}</b>
        </div>
        <div>
          <span>Tasks assigned</span>
          <b>
            {assignedCount}/{TASK_PROFILE_MAP.length}
          </b>
        </div>
        <div>
          <span>Unknown / incomplete</span>
          <b>{unknownProfiles}</b>
        </div>
      </div>

      <section>
        <div className="panel-title" style={{ marginBottom: 10 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '1rem' }}>Provider profiles</h2>
            <p className="form-hint" style={{ margin: '4px 0 0' }}>
              Configuration records only. Status comes from stored availability or catalog evidence—not a
              fake Connected claim.
            </p>
          </div>
          <Button variant="secondary" onClick={resetProfileForm} disabled={disabled}>
            New profile
          </Button>
        </div>
        {!profiles.length && !loading ? (
          <EmptyState
            title="No provider profiles"
            detail="Create a disabled or manually controlled provider record. Availability begins Unknown."
          />
        ) : null}
        {profiles.length ? (
          <div className="card-grid">
            {profiles.map((profile) => {
              const catalogEntry = catalogByIdentifier.get(profile.provider_identifier)
              const status = profile.availability_status || catalogEntry?.availability_status || 'unknown'
              const selected = drawer.kind === 'profile' && drawer.profileId === profile.id
              return (
                <article key={profile.id}>
                  <button
                    type="button"
                    className={selected ? 'primary-button touch-target' : 'secondary-button touch-target'}
                    style={{
                      width: '100%',
                      display: 'grid',
                      gridTemplateColumns: '28px 1fr auto',
                      gap: 10,
                      alignItems: 'center',
                      textAlign: 'left',
                    }}
                    onClick={() => {
                      setDrawer({ kind: 'profile', profileId: profile.id })
                      setLastConnectionNote(null)
                    }}
                  >
                    <span
                      aria-hidden="true"
                      style={{
                        width: 28,
                        height: 28,
                        borderRadius: 8,
                        display: 'grid',
                        placeItems: 'center',
                        background: '#25292d',
                        fontWeight: 800,
                        fontSize: '0.75rem',
                      }}
                    >
                      {profile.display_name.charAt(0).toUpperCase()}
                    </span>
                    <span>
                      <b style={{ display: 'block' }}>{profile.display_name}</b>
                      <small style={{ display: 'block', color: 'var(--muted)' }}>
                        {profile.provider_identifier} · {privacyLabel(profile.privacy_classification)} ·{' '}
                        {profile.provider_model_id ?? 'No model'}
                      </small>
                    </span>
                    <EvidencePill status={status} />
                  </button>
                  <small>
                    {humanizeStatus(status)}
                    {catalogEntry?.connection_test_supported ? ' · connection test supported' : ''}
                  </small>
                </article>
              )
            })}
          </div>
        ) : null}
      </section>

      <div className="routing-layout">
        <Section
          title="Task-routing matrix"
          subtitle="Persist a provider profile per planning task. Sol, Terra, and Luna remain logical defaults."
          className="routing-table-panel"
        >
          <div className="data-table routing-table">
            <div className="table-head">
              <span>Task</span>
              <span>Provider / model</span>
              <span>Mode</span>
              <span>Privacy</span>
              <span>Status</span>
            </div>
            {TASK_PROFILE_MAP.map((row) => {
              const assignment = assignments.find((item) => item.task_type === row.task)
              const draft = getDraft(row.task)
              const profile = draft.providerProfileId
                ? profilesById.get(draft.providerProfileId) ?? null
                : null
              const status = profile?.availability_status ?? 'unassigned'
              const mode = assignment?.assignment_mode ?? (draft.providerProfileId ? 'draft' : 'unassigned')
              const selected = drawer.kind === 'task' && drawer.task === row.task
              return (
                <div
                  key={row.task}
                  role="button"
                  tabIndex={0}
                  className={`data-row${selected ? ' selected' : ''}`}
                  onClick={() => selectTask(row.task)}
                  onKeyDown={(event) => onTaskKeyDown(event, row.task)}
                >
                  <span>
                    <b style={{ display: 'block' }}>{row.label}</b>
                    <small style={{ color: 'var(--muted)' }}>
                      {row.description} · {row.logicalProfile}
                    </small>
                  </span>
                  <span onClick={(event) => event.stopPropagation()} onKeyDown={(event) => event.stopPropagation()}>
                    <select
                      aria-label={`Provider for ${row.label}`}
                      value={draft.providerProfileId}
                      onChange={(event) =>
                        updateRouteDraft(row.task, { providerProfileId: event.target.value })
                      }
                      disabled={disabled || !profiles.length}
                      style={{ width: '100%' }}
                    >
                      <option value="">Unassigned</option>
                      {profiles.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.display_name} · {item.availability_status}
                        </option>
                      ))}
                    </select>
                    <small style={{ display: 'block', color: 'var(--muted)', marginTop: 4 }}>
                      {profile?.provider_model_id ?? 'No model selected'}
                    </small>
                  </span>
                  <span>
                    <ModePill mode={mode} />
                  </span>
                  <span>{privacyLabel(profile?.privacy_classification)}</span>
                  <span>
                    <EvidencePill
                      status={status === 'unassigned' ? 'draft' : status}
                      label={status === 'unassigned' ? 'unassigned' : humanizeStatus(status)}
                    />
                  </span>
                </div>
              )
            })}
          </div>
          <p className="form-hint" style={{ marginTop: 10 }}>
            Speed and usage columns from the prototype are omitted: the backend does not expose estimated
            speed or cost indicators for planning routes.
          </p>
        </Section>

        <aside className="entity-drawer">
          {drawer.kind === 'task' && selectedTaskMeta ? (
            <>
              <header>
                <div>
                  <span className="eyebrow">ROUTE DETAIL</span>
                  <h2 style={{ margin: '4px 0 0' }}>{selectedTaskMeta.label}</h2>
                </div>
                {selectedRouteProfile ? (
                  <EvidencePill status={selectedRouteProfile.availability_status} />
                ) : (
                  <EvidencePill status="draft" label="unassigned" />
                )}
              </header>
              <ul className="kv-list">
                <li>
                  <span>Task type</span>
                  <strong className="mono">{selectedTaskMeta.task}</strong>
                </li>
                <li>
                  <span>Logical profile</span>
                  <strong>{selectedTaskMeta.logicalProfile}</strong>
                </li>
                <li>
                  <span>Provider</span>
                  <strong>{selectedRouteProfile?.display_name ?? 'Unassigned'}</strong>
                </li>
                <li>
                  <span>Model</span>
                  <strong>{selectedRouteProfile?.provider_model_id ?? '—'}</strong>
                </li>
                <li>
                  <span>Control</span>
                  <strong>
                    {selectedAssignment?.assignment_mode ??
                      (selectedDraft.providerProfileId ? 'draft (unsaved)' : 'unassigned')}
                  </strong>
                </li>
                <li>
                  <span>Privacy</span>
                  <strong>{privacyLabel(selectedRouteProfile?.privacy_classification)}</strong>
                </li>
                <li>
                  <span>Availability</span>
                  <strong>
                    {selectedRouteProfile
                      ? humanizeStatus(selectedRouteProfile.availability_status)
                      : 'Unassigned'}
                  </strong>
                </li>
                <li>
                  <span>Catalog fact</span>
                  <strong>
                    {selectedRouteCatalog
                      ? humanizeStatus(selectedRouteCatalog.availability_status)
                      : 'No catalog match'}
                  </strong>
                </li>
                <li>
                  <span>Enabled assignments</span>
                  <strong>{enabledAssignments}</strong>
                </li>
              </ul>

              <label style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 12 }}>
                <input
                  type="checkbox"
                  checked={selectedDraft.enabled}
                  onChange={(event) =>
                    updateRouteDraft(selectedTask, { enabled: event.target.checked })
                  }
                  disabled={disabled}
                />
                Assignment enabled
              </label>
              <label style={{ display: 'grid', gap: 6, marginTop: 10 }}>
                Rationale / review note
                <input
                  value={selectedDraft.rationale}
                  onChange={(event) =>
                    updateRouteDraft(selectedTask, { rationale: event.target.value })
                  }
                  disabled={disabled}
                  placeholder="Optional review note"
                />
              </label>
              <p className="notice info" style={{ marginTop: 12 }}>
                <b>Why this route</b>
                <br />
                {selectedDraft.rationale.trim() || selectedTaskMeta.description}. Logical default:{' '}
                {selectedTaskMeta.logicalProfile}. CineForge validates returned structure before storing it.
              </p>
              <div className="page-actions" style={{ marginTop: 12 }}>
                <Button
                  variant="primary"
                  onClick={() => void onSaveAssignment(selectedTask)}
                  disabled={disabled || !selectedDraft.providerProfileId}
                >
                  Save assignment
                </Button>
                {selectedAssignment ? (
                  <Button
                    variant="danger"
                    onClick={() => void onDeleteAssignment(selectedAssignment)}
                    disabled={disabled}
                  >
                    Remove
                  </Button>
                ) : null}
                {selectedRouteProfile ? (
                  <Button
                    variant="secondary"
                    onClick={() =>
                      setDrawer({ kind: 'profile', profileId: selectedRouteProfile.id })
                    }
                    disabled={disabled}
                  >
                    Open profile
                  </Button>
                ) : null}
              </div>
            </>
          ) : (
            <form
              key={selectedProfile?.id ?? 'new'}
              className="stack-form"
              onSubmit={(event) => void onSaveProfile(event)}
            >
              <header>
                <div>
                  <span className="eyebrow">PROVIDER PROFILE</span>
                  <h2 style={{ margin: '4px 0 0' }}>
                    {selectedProfileId ? selectedProfile?.display_name ?? 'Edit profile' : 'New profile'}
                  </h2>
                </div>
                {selectedProfile ? (
                  <EvidencePill status={selectedProfile.availability_status} />
                ) : (
                  <EvidencePill status="draft" label="new" />
                )}
              </header>
              <p className="form-hint">
                Availability remains factual backend evidence and is not editable here.
              </p>
              <label>
                Provider identifier
                <input
                  name="provider_identifier"
                  required
                  defaultValue={selectedProfile?.provider_identifier ?? ''}
                  disabled={disabled}
                  readOnly={Boolean(selectedProfileId)}
                  placeholder="openai, xai, local_cli…"
                />
              </label>
              <label>
                Display name
                <input
                  name="display_name"
                  required
                  defaultValue={selectedProfile?.display_name ?? ''}
                  disabled={disabled}
                />
              </label>
              <label>
                Provider model ID
                <input
                  name="provider_model_id"
                  defaultValue={selectedProfile?.provider_model_id ?? ''}
                  disabled={disabled}
                  placeholder="Optional configuration value"
                />
              </label>
              <label>
                Execution mode
                <select
                  name="execution_mode"
                  defaultValue={selectedProfile?.execution_mode ?? 'disabled'}
                  disabled={disabled}
                >
                  <option value="disabled">Disabled</option>
                  <option value="manual">Manual</option>
                  <option value="assisted">Assisted</option>
                  <option value="automatic">Automatic</option>
                </select>
              </label>
              <label>
                Privacy classification
                <select
                  name="privacy_classification"
                  defaultValue={selectedProfile?.privacy_classification ?? 'local'}
                  disabled={disabled}
                >
                  <option value="local">Local</option>
                  <option value="hosted">Hosted</option>
                  <option value="restricted">Restricted</option>
                  <option value="unknown">Unknown</option>
                </select>
              </label>
              <label>
                Declared capabilities
                <input
                  name="capabilities"
                  defaultValue={
                    selectedProfile
                      ? capabilityLabels(selectedProfile).replace('No declared capabilities', '')
                      : 'planning'
                  }
                  disabled={disabled}
                  placeholder="Comma-separated, e.g. planning"
                />
              </label>
              {selectedProfile ? (
                <ul className="kv-list">
                  <li>
                    <span>Availability</span>
                    <strong>{humanizeStatus(selectedProfile.availability_status)}</strong>
                  </li>
                  <li>
                    <span>Capability source</span>
                    <strong>{selectedProfile.capability_source ?? 'Unknown'}</strong>
                  </li>
                  <li>
                    <span>Capability check</span>
                    <strong>
                      {selectedProfile.capabilities_checked_at
                        ? formatDate(selectedProfile.capabilities_checked_at)
                        : 'Never checked'}
                    </strong>
                  </li>
                  <li>
                    <span>Health check</span>
                    <strong>
                      {selectedProfile.health_checked_at
                        ? formatDate(selectedProfile.health_checked_at)
                        : 'Never checked'}
                    </strong>
                  </li>
                </ul>
              ) : null}
              <div className="page-actions">
                <Button type="submit" variant="primary" disabled={disabled}>
                  {saving ? 'Saving…' : 'Save provider profile'}
                </Button>
                {selectedProfile ? (
                  <Button
                    variant="danger"
                    onClick={() => void onDeleteProfile()}
                    disabled={disabled}
                  >
                    Delete profile
                  </Button>
                ) : null}
              </div>
              <Button
                variant="secondary"
                icon="play"
                onClick={() => void onTestConnection()}
                disabled={disabled || !selectedProfile || !connectionSupport.supported}
                title={
                  connectionSupport.supported
                    ? 'POST /providers/{id}/connection-test (bounded, explicit).'
                    : connectionSupport.reason
                }
              >
                {testingConnection ? 'Testing…' : 'Test connection'}
              </Button>
              {!connectionSupport.supported ? (
                <p className="form-hint">{connectionSupport.reason}</p>
              ) : (
                <p className="form-hint">
                  Bounded non-destructive connection test for providers that advertise support.
                </p>
              )}
              {lastConnectionNote ? <p className="notice info">{lastConnectionNote}</p> : null}
              <Button
                variant="quiet"
                onClick={() => setDrawer({ kind: 'task', task: selectedTask })}
                disabled={disabled}
              >
                Back to route detail
              </Button>
            </form>
          )}
        </aside>
      </div>

      <Section
        title="Factual runtime catalog"
        subtitle="Database evidence only; no hardware or provider probes run from this panel."
        action={
          <span className="form-hint" style={{ margin: 0 }}>
            {catalog?.model_variants.length ?? 0} variant(s)
          </span>
        }
      >
        {!catalogAvailable && !loading ? (
          <UnavailableState
            title="Runtime catalog unavailable"
            detail="No model, install, benchmark, or connection claim is inferred."
          />
        ) : null}
        {catalog ? <p className="notice info">{catalog.summary.evidence_note}</p> : null}
        {!loading && catalog && !catalog.model_variants.length ? (
          <EmptyState
            title="No model variants registered"
            detail="The runtime catalog contains no model-variant records."
          />
        ) : null}
        {catalog?.model_variants.length ? (
          <div className="data-table">
            <div
              className="table-head"
              style={{ gridTemplateColumns: '1.6fr .7fr .7fr .7fr .9fr .8fr' }}
            >
              <span>Model / variant</span>
              <span>24 GB</span>
              <span>Path</span>
              <span>Checksum</span>
              <span>Benchmark</span>
              <span>Native voice</span>
            </div>
            {catalog.model_variants.map((variant) => {
              const model = modelsById.get(variant.model_id)
              return (
                <div
                  key={variant.id}
                  className="data-row"
                  style={{ gridTemplateColumns: '1.6fr .7fr .7fr .7fr .9fr .8fr' }}
                >
                  <span>
                    <b style={{ display: 'block' }}>
                      {model ? `${model.family} · ${model.name}` : 'Unknown model'}
                    </b>
                    <small style={{ color: 'var(--muted)' }}>{variant.variant_name}</small>
                  </span>
                  <span>{variant.compatible_24gb_status || 'unknown'}</span>
                  <span>
                    <EvidencePill status={variant.path_status} />
                  </span>
                  <span>
                    <EvidencePill status={variant.checksum_status} />
                  </span>
                  <span>
                    <EvidencePill status={variant.benchmark_status} />
                    {variant.benchmark_run_count ? ` ${variant.benchmark_run_count} run(s)` : ''}
                  </span>
                  <span>{variant.native_voice_capability || 'unknown'}</span>
                </div>
              )
            })}
          </div>
        ) : null}
      </Section>

      {providerCatalog.length ? (
        <Section
          title="Planning provider catalog"
          subtitle="In-process registry facts from GET /providers. Used for connection-test capability only."
        >
          <div className="data-table">
            <div
              className="table-head"
              style={{ gridTemplateColumns: '1.2fr .9fr .9fr .9fr 1fr' }}
            >
              <span>Provider</span>
              <span>Availability</span>
              <span>Privacy</span>
              <span>Connection test</span>
              <span>Detail</span>
            </div>
            {providerCatalog.map((entry) => (
              <div
                key={entry.provider_identifier}
                className="data-row"
                style={{ gridTemplateColumns: '1.2fr .9fr .9fr .9fr 1fr' }}
              >
                <span>
                  <b style={{ display: 'block' }}>{entry.display_name}</b>
                  <small style={{ color: 'var(--muted)' }}>{entry.provider_identifier}</small>
                </span>
                <span>
                  <EvidencePill status={entry.availability_status} />
                </span>
                <span>{privacyLabel(entry.privacy_classification)}</span>
                <span>
                  {entry.connection_test_supported ? (
                    <EvidencePill status="ready" label="supported" />
                  ) : (
                    <EvidencePill status="disabled" label="not supported" />
                  )}
                </span>
                <span style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>{entry.detail}</span>
              </div>
            ))}
          </div>
        </Section>
      ) : null}

    </div>
  )
}
