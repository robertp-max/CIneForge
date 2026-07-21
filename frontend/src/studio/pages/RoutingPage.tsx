/**
 * Exact structural port of CineForge-Storyboard-Studio-v2 RoutingPage (pagesOps.tsx)
 * adapted to production studio context + real provider profiles / task assignments.
 *
 * Screenshot reference: 2026-07-11 172754.png (Model routing).
 *
 * DOM hierarchy matches the ZIP prototype:
 * page-title (MODEL ORCHESTRATION / Model routing) →
 * routing-controls (mode · default provider · default model · privacy · speed · cost) →
 * optional test-result →
 * provider-grid tiles →
 * routing-layout → Task-routing matrix | route-detail (ROUTE DETAIL).
 *
 * Hybrid T7:
 * - LIVE path when profiles and/or planning catalog exist: profile CRUD, task assignments,
 *   connection-test when advertised, routing validate preflight.
 * - DEMO fallback when backend load fails OR (profiles empty AND catalog empty):
 *   show demoRoutingProviders / demoRoutingMatrix chrome labeled
 *   "Demo planning fixture (offline)" — never claim live Connected.
 * - Availability for live data uses backend evidence only via availabilityLabel
 *   (never invents "Connected"). Demo fixture statuses are prototype labels only.
 * - type="button" on interactive controls (submit only for profile form).
 * Credentials are never requested or stored here.
 */
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from 'react'
import {
  api,
  type OrchestrationRoutingMode,
  type PlanningTaskType,
  type ProjectStoryboardSettings,
  type ProviderCatalogEntry,
  type ProviderExecutionMode,
  type ProviderProfile,
  type RoutingPreflightResponse,
  type TaskProviderAssignment,
} from '../../api/client'
import { formatDate } from '../../components/formatDate'
import { Button, Icon, PageTitle, Section, StatusPill } from '../proto/ui'
import {
  demoRoutingDefaults,
  demoRoutingMatrix,
  demoRoutingProviders,
} from '../demoPhaseA'
import { useStudio } from '../StudioState'
import { EmptyState, ErrorState, LoadingState, UnavailableState } from '../components/StateBlocks'

const DEMO_FIXTURE_LABEL = 'Demo planning fixture (offline)'

/** Production planning task rows with logical Sol/Terra/Luna defaults (not prototype labels). */
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

/** Title-case backend snake/space tokens for display — never remaps to Connected. */
function humanizeStatus(status: string | null | undefined): string {
  if (!status || !status.trim()) return 'Unknown'
  return status
    .replace(/_/g, ' ')
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(' ')
}

function capabilityLabels(profile: ProviderProfile): string {
  const declared =
    profile.capabilities_json.declared_capabilities ?? profile.capabilities_json.capabilities
  return Array.isArray(declared) && declared.length
    ? declared.map(String).join(', ')
    : 'No declared capabilities'
}

function privacyLabel(value: string | null | undefined): string {
  if (!value || value === 'unknown') return 'Unknown'
  if (value === 'local') return 'Local'
  if (value === 'hosted') return 'Hosted'
  if (value === 'restricted') return 'Restricted'
  return humanizeStatus(value)
}

function privacyPreferenceValue(preferLocal: boolean, preferHosted: boolean): string {
  if (preferLocal && !preferHosted) return 'local_only'
  if (!preferLocal && preferHosted) return 'hosted_allowed'
  return 'prefer_local'
}

function applyPrivacyPreference(value: string): { preferLocal: boolean; preferHosted: boolean } {
  if (value === 'local_only') return { preferLocal: true, preferHosted: false }
  if (value === 'hosted_allowed') return { preferLocal: false, preferHosted: true }
  return { preferLocal: true, preferHosted: true }
}

/** Mode pill for matrix — factual assignment_mode only (Auto/Manual/Default/Suggested). */
function modeLabel(mode: string | null | undefined, hasProfile: boolean): string {
  if (!mode) return hasProfile ? 'Draft' : 'Unassigned'
  const m = mode.toLowerCase()
  if (m === 'manual') return 'Manual'
  if (m === 'default' || m === 'auto' || m === 'automatic') return 'Auto'
  if (m === 'suggested') return 'Suggested'
  return humanizeStatus(mode)
}

/**
 * Availability display from backend evidence only.
 * Never invent "Connected" — that was prototype mock chrome.
 */
function availabilityLabel(status: string | null | undefined): string {
  if (!status || !status.trim()) return 'Unknown'
  return humanizeStatus(status.trim())
}

function providerNote(profile: ProviderProfile, catalog?: ProviderCatalogEntry): string {
  const privacy = privacyLabel(profile.privacy_classification)
  const model = profile.provider_model_id?.trim() || 'No model'
  const detail = catalog?.detail?.trim()
  if (detail) return `${privacy} · ${model} · ${detail}`
  return `${profile.provider_identifier} · ${privacy} · ${model}`
}

export function RoutingPage() {
  const { data, busy, reload, setMessage } = useStudio()
  const [profiles, setProfiles] = useState<ProviderProfile[]>([])
  const [assignments, setAssignments] = useState<TaskProviderAssignment[]>([])
  const [providerCatalog, setProviderCatalog] = useState<ProviderCatalogEntry[]>([])
  const [settings, setSettings] = useState<ProjectStoryboardSettings | null>(null)
  const [settingsAvailable, setSettingsAvailable] = useState(true)
  const [loading, setLoading] = useState(true)
  const [loadFailed, setLoadFailed] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testingConnection, setTestingConnection] = useState(false)
  const [routingTestBusy, setRoutingTestBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [preferLocal, setPreferLocal] = useState(true)
  const [preferHosted, setPreferHosted] = useState(false)
  const [routingMode, setRoutingMode] = useState<OrchestrationRoutingMode>('hybrid')
  const [defaultProfileId, setDefaultProfileId] = useState('')
  const [speedPreference, setSpeedPreference] = useState(demoRoutingDefaults.qualityPreference)
  const [costSensitivity, setCostSensitivity] = useState(demoRoutingDefaults.costSensitivity)
  const [routeDrafts, setRouteDrafts] = useState<Record<string, RouteDraft>>({})
  const [drawer, setDrawer] = useState<DrawerFocus>({ kind: 'task', task: 'story_structure' })
  const [demoSelectedTask, setDemoSelectedTask] = useState(demoRoutingMatrix[0]?.task ?? '')
  const [preflight, setPreflight] = useState<RoutingPreflightResponse | null>(null)
  const [lastConnectionNote, setLastConnectionNote] = useState<string | null>(null)

  const profilesById = useMemo(
    () => new Map(profiles.map((profile) => [profile.id, profile])),
    [profiles],
  )
  const catalogByIdentifier = useMemo(
    () => new Map(providerCatalog.map((entry) => [entry.provider_identifier, entry])),
    [providerCatalog],
  )
  const modelOptions = useMemo(() => {
    const models = profiles
      .map((p) => p.provider_model_id?.trim())
      .filter((m): m is string => Boolean(m))
    return Array.from(new Set(models))
  }, [profiles])

  const load = useCallback(async () => {
    if (!data) return
    setLoading(true)
    setError(null)
    try {
      const [profileResult, assignmentResult, settingsResult, providersResult] = await Promise.all([
        api.listProviderProfiles(),
        api.listTaskProviderAssignments(data.story.id),
        api.getSettings(data.story.project_id),
        api.listPlanningProviders().catch(() => null),
      ])
      setLoadFailed(false)
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
      setDefaultProfileId((current) => {
        if (current && profileResult.some((p) => p.id === current)) return current
        const firstAssigned = assignmentResult.find((a) => a.enabled)?.provider_profile_id
        if (firstAssigned && profileResult.some((p) => p.id === firstAssigned)) return firstAssigned
        return profileResult[0]?.id ?? ''
      })
    } catch (err) {
      setLoadFailed(true)
      setProfiles([])
      setAssignments([])
      setProviderCatalog([])
      setError(errorText(err, 'Failed to load routing configuration.'))
    } finally {
      setLoading(false)
    }
  }, [data])

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0)
    return () => window.clearTimeout(timer)
  }, [load])

  if (!data) return null

  const selectedProfileId = drawer.kind === 'profile' ? drawer.profileId : null
  const selectedProfile =
    selectedProfileId != null
      ? profiles.find((profile) => profile.id === selectedProfileId) ?? null
      : null
  const selectedTask =
    drawer.kind === 'task' ? drawer.task : TASK_PROFILE_MAP[0]?.task ?? 'story_structure'
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
        setMessage(`Provider profile “${displayName}” updated. Availability was not inferred or changed.`)
      } else {
        const created = await api.createProviderProfile({
          provider_identifier: providerIdentifier,
          ...payload,
          availability_status: 'unknown',
        })
        setDrawer({ kind: 'profile', profileId: created.id })
        setDefaultProfileId(created.id)
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

  const onSaveAssignment = async (task: PlanningTaskType, profileOverride?: string) => {
    const draft = routeDrafts[task] ?? getDraft(task)
    const providerProfileId = (profileOverride || draft.providerProfileId).trim()
    if (!providerProfileId) return
    const existing = assignments.find((assignment) => assignment.task_type === task)
    setSaving(true)
    setError(null)
    try {
      if (existing) {
        await api.updateTaskProviderAssignment(existing.id, {
          provider_profile_id: providerProfileId,
          assignment_mode: 'manual',
          rationale: draft.rationale.trim() || null,
          enabled: draft.enabled,
        })
      } else {
        await api.createTaskProviderAssignment(data.story.id, {
          task_type: task,
          provider_profile_id: providerProfileId,
          assignment_mode: 'manual',
          rationale: draft.rationale.trim() || null,
          enabled: draft.enabled,
          priority: 0,
        })
      }
      setRouteDrafts((current) => ({
        ...current,
        [task]: {
          providerProfileId,
          enabled: draft.enabled,
          rationale: draft.rationale,
        },
      }))
      await Promise.all([load(), reload()])
      setMessage(`Saved the ${task} provider assignment.`)
    } catch (err) {
      const text = errorText(err, 'Could not save the task-provider assignment.')
      setError(text)
      setMessage(text)
    } finally {
      setSaving(false)
    }
  }

  const onOverrideRouting = async () => {
    const profileId = (getDraft(selectedTask).providerProfileId || defaultProfileId).trim()
    if (!profileId) return
    await onSaveAssignment(selectedTask, profileId)
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

  const onSavePreferences = async (nextPreferLocal = preferLocal, nextPreferHosted = preferHosted) => {
    if (!settings) return
    if (!nextPreferLocal && !nextPreferHosted) {
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
        prefer_hosted_providers: nextPreferHosted,
        prefer_local_providers: nextPreferLocal,
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
      setPreferLocal(result.prefer_local_providers)
      setPreferHosted(result.prefer_hosted_providers)
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
        reason: `Connection test is not supported for “${profile.provider_identifier}” (backend advertises connection_test_supported=false).`,
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
      const manualRoutes = TASK_PROFILE_MAP.flatMap((row) => {
        const draft = getDraft(row.task)
        if (!draft.enabled || !draft.providerProfileId) return []
        const profile = profilesById.get(draft.providerProfileId)
        if (!profile) return []
        return [
          {
            task_type: row.task,
            provider_identifier: profile.provider_identifier,
            logical_model: row.logicalProfile.toLowerCase() as 'luna' | 'terra' | 'sol',
            resolved_model: profile.provider_model_id,
            rationale: draft.rationale.trim() || row.description,
          },
        ]
      })
      const result = await api.validateStoryRouting(data.story.id, {
        routing_mode: routingMode,
        prefer_local_providers: preferLocal,
        prefer_hosted_providers: preferHosted,
        manual_routes: routingMode === 'automatic' ? [] : manualRoutes,
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
  const connectionSupport = connectionSupportFor(selectedProfile)
  const disabled = loading || busy || saving || testingConnection || routingTestBusy
  const defaultProfile = defaultProfileId ? profilesById.get(defaultProfileId) ?? null : null
  const canOverride =
    Boolean(selectedDraft.providerProfileId || defaultProfileId) && profiles.length > 0

  /** Live data present → never show demo Connected strip as real. */
  const hasLiveProviders = profiles.length > 0 || providerCatalog.length > 0
  /** Backend fail OR empty profiles+catalog → demo strip/matrix with offline label. */
  const useDemoFallback = !loading && (loadFailed || !hasLiveProviders)
  /** When load failed, block mutating live actions; empty-but-reachable still allows profile create. */
  const demoActionsLocked = useDemoFallback && loadFailed
  const demoRoute =
    demoRoutingMatrix.find((row) => row.task === demoSelectedTask) ?? demoRoutingMatrix[0] ?? null

  /** Provider tiles: live profiles → catalog → (render path) demo fixtures. Real availability only. */
  const providerCards: Array<{
    key: string
    name: string
    note: string
    status: string
    selected: boolean
    onClick: () => void
    /** true only for demo fixture tiles — StatusPill uses fixture label as-is under offline banner */
    demo?: boolean
  }> = profiles.length
    ? profiles.map((profile) => {
        const catalogEntry = catalogByIdentifier.get(profile.provider_identifier)
        return {
          key: profile.id,
          name: profile.display_name,
          note: providerNote(profile, catalogEntry),
          status: profile.availability_status || catalogEntry?.availability_status || 'unknown',
          selected: drawer.kind === 'profile' && drawer.profileId === profile.id,
          onClick: () => {
            setDrawer({ kind: 'profile', profileId: profile.id })
            setLastConnectionNote(null)
            setDefaultProfileId(profile.id)
          },
        }
      })
    : providerCatalog.map((entry) => ({
        key: entry.provider_identifier,
        name: entry.display_name,
        note: `${privacyLabel(entry.privacy_classification)} · ${entry.detail || entry.provider_identifier}`,
        status: entry.availability_status || 'unknown',
        selected: false,
        onClick: () => {
          setMessage(
            `Catalog entry “${entry.display_name}” has no saved provider profile yet. Create a profile to assign routes.`,
          )
          resetProfileForm()
        },
      }))

  const demoProviderCards = demoRoutingProviders.map((tile, index) => ({
    key: `demo-${tile.name}-${index}`,
    name: tile.name,
    note: tile.note,
    status: tile.status,
    selected: false,
    demo: true as const,
    onClick: () =>
      setMessage(
        `${DEMO_FIXTURE_LABEL}: “${tile.name}” is prototype planning chrome only — not a live connection.`,
      ),
  }))

  const displayProviderCards = useDemoFallback ? demoProviderCards : providerCards

  const whyRoute =
    selectedDraft.rationale.trim() ||
    selectedTaskMeta?.description ||
    'No rationale recorded for this route'

  const newProfileSelected = drawer.kind === 'profile' && drawer.profileId == null
  const routingTestTitle = useDemoFallback
    ? `${DEMO_FIXTURE_LABEL} — routing validate requires live provider profiles.`
    : 'Runs POST /stories/{id}/routing/validate (non-mutating preflight).'

  return (
    <div className="page">
      <PageTitle
        eyebrow="MODEL ORCHESTRATION"
        title="Model routing"
        description="Choose one orchestrator and route specialist tasks without inventing provider availability. Credentials are never requested here."
        aside={
          <div className="page-actions">
            <Button
              type="button"
              onClick={() =>
                setMessage(
                  'Privacy boundary: Provider connections, availability, speed, and cost are planning metadata or backend evidence only. This page never stores secrets and only runs connection tests when the catalog advertises support.',
                )
              }
              icon="lock"
            >
              Privacy boundary
            </Button>
            <Button
              type="button"
              variant="primary"
              icon="play"
              onClick={() => void onRunRoutingTest()}
              disabled={disabled || useDemoFallback}
              title={routingTestTitle}
            >
              {routingTestBusy ? 'Testing routes…' : 'Run routing test'}
            </Button>
          </div>
        }
      />

      {loading ? <LoadingState title="Loading routing records…" /> : null}
      {error && !useDemoFallback ? <ErrorState detail={error} onRetry={() => void load()} /> : null}

      {useDemoFallback ? (
        <div className="test-result" role="status" aria-live="polite">
          <Icon name="warning" />
          <span>
            <b>{DEMO_FIXTURE_LABEL}</b>
            <small>
              {loadFailed
                ? 'Provider routing API unreachable — showing prototype strip/matrix only. Status pills are fixture labels, not live connections.'
                : 'No saved provider profiles or planning catalog — showing prototype strip/matrix. Create a profile to switch to live routing. Status pills are fixture labels, not live connections.'}
              {error ? ` · ${error}` : ''}
            </small>
          </span>
          <button type="button" onClick={() => void load()} disabled={disabled}>
            Retry live
          </button>
        </div>
      ) : null}

      {/* Exact control order from pagesOps RoutingPage / screenshot 172754 */}
      <div className="routing-controls">
        <label>
          Orchestration mode
          <div className="segmented" role="group" aria-label="Orchestration mode">
            {(
              [
                ['automatic', 'Automatic'],
                ['hybrid', 'Hybrid'],
                ['manual', 'Manual'],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                className={routingMode === value ? 'active' : ''}
                onClick={() => setRoutingMode(value)}
                disabled={disabled}
                aria-pressed={routingMode === value}
              >
                {label}
              </button>
            ))}
          </div>
        </label>
        <label>
          Default orchestrator provider
          <select
            value={
              useDemoFallback && !profiles.length
                ? demoRoutingDefaults.orchestratorProvider
                : defaultProfileId
            }
            onChange={(event) => setDefaultProfileId(event.target.value)}
            disabled={disabled || useDemoFallback || !profiles.length}
            title={
              useDemoFallback
                ? `${DEMO_FIXTURE_LABEL} — not a live provider assignment.`
                : profiles.length
                  ? 'Selects the preferred provider profile for new manual overrides.'
                  : 'No saved provider profiles yet.'
            }
          >
            {useDemoFallback && !profiles.length ? (
              demoRoutingDefaults.providerOptions.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))
            ) : (
              <>
                {!profiles.length ? <option value="">No profiles</option> : null}
                {profiles.map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.display_name}
                  </option>
                ))}
              </>
            )}
          </select>
        </label>
        <label>
          Default orchestrator model
          <select
            value={
              useDemoFallback && !defaultProfile
                ? demoRoutingDefaults.orchestratorModel
                : (defaultProfile?.provider_model_id ?? '')
            }
            disabled
            title={
              useDemoFallback
                ? `${DEMO_FIXTURE_LABEL} — model is fixture chrome only.`
                : 'Model is stored on the selected provider profile.'
            }
          >
            {useDemoFallback && !defaultProfile ? (
              demoRoutingDefaults.modelOptions.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))
            ) : (
              <>
                <option value="">
                  {defaultProfile?.provider_model_id?.trim() ||
                    (modelOptions[0] ?? 'From provider profiles')}
                </option>
                {defaultProfile?.provider_model_id ? (
                  <option value={defaultProfile.provider_model_id}>
                    {defaultProfile.provider_model_id}
                  </option>
                ) : null}
              </>
            )}
          </select>
        </label>
        <label>
          Privacy preference
          <select
            value={
              useDemoFallback && !settings
                ? 'prefer_local'
                : privacyPreferenceValue(preferLocal, preferHosted)
            }
            onChange={(event) => {
              const next = applyPrivacyPreference(event.target.value)
              setPreferLocal(next.preferLocal)
              setPreferHosted(next.preferHosted)
              if (settings) void onSavePreferences(next.preferLocal, next.preferHosted)
            }}
            disabled={disabled || !settings}
            title={
              !settings
                ? useDemoFallback
                  ? `${DEMO_FIXTURE_LABEL} — privacy preference not persisted.`
                  : 'Project settings unavailable — privacy preference not persisted.'
                : undefined
            }
          >
            <option value="prefer_local">Prefer local for bulk work</option>
            <option value="hosted_allowed">Hosted allowed</option>
            <option value="local_only">Local only</option>
          </select>
        </label>
        <label>
          Speed vs quality
          <select
            value={speedPreference}
            onChange={(event) => setSpeedPreference(event.target.value)}
            disabled={disabled}
            title="Session planning preference only — not stored on the backend."
          >
            <option>Quality weighted</option>
            <option>Balanced</option>
            <option>Speed weighted</option>
          </select>
        </label>
        <label>
          Cost sensitivity
          <select
            value={costSensitivity}
            onChange={(event) => setCostSensitivity(event.target.value)}
            disabled={disabled}
            title="Session planning preference only — not stored on the backend."
          >
            <option>Balanced</option>
            <option>Cost sensitive</option>
            <option>Quality first</option>
          </select>
        </label>
      </div>

      {!settingsAvailable && !loading && !useDemoFallback ? (
        <p className="form-hint" style={{ marginBottom: 8 }}>
          Project settings unavailable — privacy preference not persisted.
        </p>
      ) : null}

      {preflight && !useDemoFallback ? (
        <div className="test-result">
          <Icon name="check" />
          <span>
            <b>
              Routing preflight {preflight.valid ? 'passed' : 'failed'}
              {preflight.warnings.length ? ' with warnings' : ''} · mode {preflight.effective_mode}
            </b>
            <small>
              {preflight.routes.length} task route(s) available · {preflight.errors.length} error(s) ·{' '}
              {preflight.warnings.length} warning(s)
              {preflight.errors[0] ? ` · ${preflight.errors[0].message}` : ''}
              {preflight.warnings[0] && !preflight.errors[0]
                ? ` · ${preflight.warnings[0].message}`
                : ''}
            </small>
          </span>
          <button type="button" onClick={() => setPreflight(null)}>
            Dismiss
          </button>
        </div>
      ) : null}

      {!loading && !useDemoFallback && !displayProviderCards.length ? (
        <EmptyState
          title="No provider profiles"
          detail="Create a disabled or manually controlled provider record. Availability begins Unknown — never Connected unless the backend reports it."
        />
      ) : null}

      {displayProviderCards.length || useDemoFallback || !loading ? (
        <div className="provider-grid">
          {displayProviderCards.map((card, index) => (
            <button
              key={card.key}
              type="button"
              className={card.selected ? 'selected' : ''}
              onClick={card.onClick}
              disabled={disabled}
              aria-pressed={card.selected}
              title={
                card.demo
                  ? `${DEMO_FIXTURE_LABEL} — fixture status “${card.status}” is not a live connection.`
                  : undefined
              }
            >
              <span className={`provider-logo provider-${index % 6}`}>{card.name.charAt(0)}</span>
              <span>
                <b>{card.name}</b>
                <small>{card.note}</small>
              </span>
              {/* Live: humanize backend status only. Demo: fixture label under offline banner. */}
              <StatusPill
                status={card.demo ? card.status : availabilityLabel(card.status)}
              />
              <Icon name="chevron" />
            </button>
          ))}
          <button
            type="button"
            className={newProfileSelected ? 'selected' : ''}
            onClick={resetProfileForm}
            disabled={disabled || demoActionsLocked}
            aria-pressed={newProfileSelected}
            title={
              demoActionsLocked
                ? `${DEMO_FIXTURE_LABEL} — profile create requires a reachable routing API.`
                : 'Create a configuration record. New profiles start as Unknown.'
            }
          >
            <span className="provider-logo provider-0">+</span>
            <span>
              <b>New profile</b>
              <small>
                {demoActionsLocked
                  ? DEMO_FIXTURE_LABEL
                  : 'Create a configuration record'}
              </small>
            </span>
            <StatusPill status="Draft" />
            <Icon name="chevron" />
          </button>
        </div>
      ) : null}

      <div className="routing-layout">
        <Section
          title="Task-routing matrix"
          subtitle={
            useDemoFallback
              ? `${DEMO_FIXTURE_LABEL} — matrix is planning chrome only.`
              : 'Recommendations remain editable per task.'
          }
          className="routing-table-panel"
        >
          <div className="data-table routing-table" role="table" aria-label="Task-routing matrix">
            <div className="table-head" role="row">
              <span role="columnheader">Task</span>
              <span role="columnheader">Provider / model</span>
              <span role="columnheader">Mode</span>
              <span role="columnheader">Privacy</span>
              <span role="columnheader">Speed</span>
              <span role="columnheader">Usage</span>
              <span role="columnheader">Status</span>
            </div>
            {useDemoFallback
              ? demoRoutingMatrix.map((row) => {
                  const selected = demoSelectedTask === row.task
                  return (
                    <div
                      key={row.task}
                      role="button"
                      tabIndex={0}
                      className={`data-row${selected ? ' selected' : ''}`}
                      onClick={() => setDemoSelectedTask(row.task)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          setDemoSelectedTask(row.task)
                        }
                      }}
                      aria-pressed={selected}
                      title={`${DEMO_FIXTURE_LABEL} — fixture row, not a live assignment.`}
                    >
                      <span>
                        <b>{row.task}</b>
                        <small>{row.reason}</small>
                      </span>
                      <span
                        onClick={(event) => event.stopPropagation()}
                        onKeyDown={(event) => event.stopPropagation()}
                      >
                        <select
                          aria-label={`Provider for ${row.task}`}
                          value={row.provider}
                          disabled
                          title={`${DEMO_FIXTURE_LABEL} — not editable.`}
                        >
                          <option value={row.provider}>{row.provider}</option>
                        </select>
                        <input
                          aria-label={`Model for ${row.task}`}
                          value={row.model}
                          readOnly
                          title={`${DEMO_FIXTURE_LABEL} — fixture model label.`}
                        />
                      </span>
                      <span>
                        <StatusPill status={row.mode} />
                      </span>
                      <span>{row.privacy}</span>
                      <span>{row.speed}</span>
                      <span>{row.cost}</span>
                      <span>
                        <StatusPill status={row.availability} />
                      </span>
                    </div>
                  )
                })
              : TASK_PROFILE_MAP.map((row) => {
                  const assignment = assignments.find((item) => item.task_type === row.task)
                  const draft = getDraft(row.task)
                  const profile = draft.providerProfileId
                    ? profilesById.get(draft.providerProfileId) ?? null
                    : null
                  const status = profile?.availability_status ?? ''
                  const mode = modeLabel(
                    assignment?.assignment_mode,
                    Boolean(draft.providerProfileId),
                  )
                  const selected = drawer.kind === 'task' && drawer.task === row.task
                  return (
                    <div
                      key={row.task}
                      role="button"
                      tabIndex={0}
                      className={`data-row${selected ? ' selected' : ''}`}
                      onClick={() => selectTask(row.task)}
                      onKeyDown={(event) => onTaskKeyDown(event, row.task)}
                      aria-pressed={selected}
                    >
                      <span>
                        <b>{row.label}</b>
                        <small>
                          {row.description} · {row.logicalProfile}
                        </small>
                      </span>
                      <span
                        onClick={(event) => event.stopPropagation()}
                        onKeyDown={(event) => event.stopPropagation()}
                      >
                        <select
                          aria-label={`Provider for ${row.label}`}
                          value={draft.providerProfileId}
                          onChange={(event) =>
                            updateRouteDraft(row.task, {
                              providerProfileId: event.target.value,
                            })
                          }
                          disabled={disabled || !profiles.length}
                        >
                          <option value="">Unassigned</option>
                          {profiles.map((item) => (
                            <option key={item.id} value={item.id}>
                              {item.display_name}
                            </option>
                          ))}
                        </select>
                        <input
                          aria-label={`Model for ${row.label}`}
                          value={profile?.provider_model_id ?? ''}
                          readOnly
                          title="Model comes from the selected provider profile."
                          placeholder="No model"
                        />
                      </span>
                      <span>
                        <StatusPill status={mode} />
                      </span>
                      <span>{privacyLabel(profile?.privacy_classification)}</span>
                      <span title="Backend does not expose estimated speed for planning routes.">
                        Not recorded
                      </span>
                      <span title="Backend does not expose usage/cost indicators for planning routes.">
                        Not recorded
                      </span>
                      <span>
                        <StatusPill status={!profile ? 'Draft' : availabilityLabel(status)} />
                      </span>
                    </div>
                  )
                })}
          </div>
        </Section>

        <aside className="route-detail" aria-label="Route or provider detail">
          {useDemoFallback && demoRoute && drawer.kind === 'task' ? (
            <>
              <header>
                <span className="orchestrator-mark">
                  <Icon name="cpu" />
                </span>
                <div>
                  <span className="eyebrow">ROUTE DETAIL</span>
                  <h2>{demoRoute.task}</h2>
                </div>
              </header>
              <p className="form-hint" style={{ marginBottom: 8 }}>
                {DEMO_FIXTURE_LABEL} — availability “{demoRoute.availability}” is fixture chrome,
                not a live connection.
              </p>
              <dl>
                <div>
                  <dt>Provider</dt>
                  <dd>{demoRoute.provider}</dd>
                </div>
                <div>
                  <dt>Model</dt>
                  <dd>{demoRoute.model}</dd>
                </div>
                <div>
                  <dt>Control</dt>
                  <dd>{demoRoute.mode}</dd>
                </div>
                <div>
                  <dt>Privacy</dt>
                  <dd>{demoRoute.privacy}</dd>
                </div>
                <div>
                  <dt>Availability</dt>
                  <dd>
                    <StatusPill status={demoRoute.availability} />
                  </dd>
                </div>
                <div>
                  <dt>Estimated speed</dt>
                  <dd>{demoRoute.speed}</dd>
                </div>
                <div>
                  <dt>Usage indicator</dt>
                  <dd>{demoRoute.cost}</dd>
                </div>
              </dl>
              <div className="recommendation">
                <Icon name="spark" />
                <p>
                  <b>Why this route</b>
                  {demoRoute.reason}. CineForge will validate returned structure before storing it
                  when live routing is available.
                </p>
              </div>
              <div className="page-actions" style={{ marginTop: 12 }}>
                <Button
                  type="button"
                  variant="primary"
                  disabled
                  title={`${DEMO_FIXTURE_LABEL} — override requires live provider profiles.`}
                >
                  Override routing
                </Button>
                {!loadFailed ? (
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={resetProfileForm}
                    disabled={disabled}
                    title="Create a live provider profile to leave the demo fixture."
                  >
                    New profile
                  </Button>
                ) : null}
              </div>
            </>
          ) : drawer.kind === 'task' && selectedTaskMeta ? (
            <>
              <header>
                <span className="orchestrator-mark">
                  <Icon name="cpu" />
                </span>
                <div>
                  <span className="eyebrow">ROUTE DETAIL</span>
                  <h2>{selectedTaskMeta.label}</h2>
                </div>
              </header>
              <dl>
                <div>
                  <dt>Provider</dt>
                  <dd>{selectedRouteProfile?.display_name ?? 'Unassigned'}</dd>
                </div>
                <div>
                  <dt>Model</dt>
                  <dd>{selectedRouteProfile?.provider_model_id ?? '—'}</dd>
                </div>
                <div>
                  <dt>Control</dt>
                  <dd>
                    {modeLabel(
                      selectedAssignment?.assignment_mode,
                      Boolean(selectedDraft.providerProfileId),
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Privacy</dt>
                  <dd>{privacyLabel(selectedRouteProfile?.privacy_classification)}</dd>
                </div>
                <div>
                  <dt>Availability</dt>
                  <dd>
                    {selectedRouteProfile ? (
                      <StatusPill
                        status={availabilityLabel(selectedRouteProfile.availability_status)}
                      />
                    ) : (
                      <StatusPill status="Draft" />
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Estimated speed</dt>
                  <dd>Not recorded</dd>
                </div>
                <div>
                  <dt>Usage indicator</dt>
                  <dd>Not recorded</dd>
                </div>
              </dl>
              <div className="recommendation">
                <Icon name="spark" />
                <p>
                  <b>Why this route</b>
                  {whyRoute}. Logical default: {selectedTaskMeta.logicalProfile}. CineForge
                  validates returned structure before storing it.
                </p>
              </div>
              <label className="form-hint" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
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
              <label style={{ display: 'grid', gap: 6, marginTop: 8 }}>
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
              <div className="page-actions" style={{ marginTop: 12 }}>
                <Button
                  type="button"
                  variant="primary"
                  onClick={() => void onOverrideRouting()}
                  disabled={disabled || !canOverride}
                  title={
                    canOverride
                      ? 'Persist a manual task-provider assignment for this route.'
                      : 'Select or create a provider profile first.'
                  }
                >
                  Override routing
                </Button>
                {selectedAssignment ? (
                  <Button
                    type="button"
                    variant="danger"
                    onClick={() => void onDeleteAssignment(selectedAssignment)}
                    disabled={disabled}
                  >
                    Remove
                  </Button>
                ) : null}
                {selectedRouteProfile ? (
                  <Button
                    type="button"
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
                <span className="orchestrator-mark">
                  <Icon name="cpu" />
                </span>
                <div>
                  <span className="eyebrow">PROVIDER PROFILE</span>
                  <h2>
                    {selectedProfileId
                      ? selectedProfile?.display_name ?? 'Edit profile'
                      : 'New profile'}
                  </h2>
                </div>
              </header>
              <p className="form-hint">
                Availability remains factual backend evidence and is not editable here. New profiles
                start as Unknown — never Connected.
                {useDemoFallback
                  ? ` ${DEMO_FIXTURE_LABEL}: saving a profile switches this page to live routing when the API accepts it.`
                  : ''}
              </p>
              <label>
                Provider identifier
                <input
                  name="provider_identifier"
                  required
                  defaultValue={selectedProfile?.provider_identifier ?? ''}
                  disabled={disabled || demoActionsLocked}
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
                <dl>
                  <div>
                    <dt>Availability</dt>
                    <dd>
                      <StatusPill
                        status={availabilityLabel(selectedProfile.availability_status)}
                      />
                    </dd>
                  </div>
                  <div>
                    <dt>Capability source</dt>
                    <dd>{selectedProfile.capability_source ?? 'Unknown'}</dd>
                  </div>
                  <div>
                    <dt>Capability check</dt>
                    <dd>
                      {selectedProfile.capabilities_checked_at
                        ? formatDate(selectedProfile.capabilities_checked_at)
                        : 'Never checked'}
                    </dd>
                  </div>
                  <div>
                    <dt>Health check</dt>
                    <dd>
                      {selectedProfile.health_checked_at
                        ? formatDate(selectedProfile.health_checked_at)
                        : 'Never checked'}
                    </dd>
                  </div>
                </dl>
              ) : null}
              <div className="page-actions">
                <Button
                  type="submit"
                  variant="primary"
                  disabled={disabled || demoActionsLocked}
                  title={
                    demoActionsLocked
                      ? `${DEMO_FIXTURE_LABEL} — profile save requires a reachable routing API.`
                      : undefined
                  }
                >
                  {saving ? 'Saving…' : 'Save provider profile'}
                </Button>
                {selectedProfile ? (
                  <Button
                    type="button"
                    variant="danger"
                    onClick={() => void onDeleteProfile()}
                    disabled={disabled || demoActionsLocked}
                  >
                    Delete profile
                  </Button>
                ) : null}
              </div>
              <Button
                type="button"
                variant="secondary"
                icon="play"
                onClick={() => void onTestConnection()}
                disabled={
                  disabled ||
                  demoActionsLocked ||
                  !selectedProfile ||
                  !connectionSupport.supported
                }
                title={
                  demoActionsLocked
                    ? `${DEMO_FIXTURE_LABEL} — connection test requires live catalog advertisement.`
                    : connectionSupport.supported
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
                type="button"
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

      {!settingsAvailable && !loading && !useDemoFallback ? (
        <UnavailableState
          title="Project settings unavailable"
          detail="Privacy preference save is disabled until the project settings API responds."
        />
      ) : null}
    </div>
  )
}
