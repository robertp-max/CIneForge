/**
 * Structural port of prototype StoryPage (pagesCore.tsx) adapted to
 * production studio context + story save / hierarchy / orchestration APIs.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  api,
  type Chapter,
  type ManualTaskRoute,
  type OrchestrationRoutingMode,
  type OrchestrationRun,
  type OrchestrationRunDetail,
  type PlanningTaskType,
  type ProposalDiff,
  type ProviderCatalogEntry,
  type ProviderProfile,
  type RoutingPreflightResponse,
  type Scene,
  type StoryboardProposal,
} from '../../api/client'
import { formatDate } from '../../components/formatDate'
import { Button, Icon, PageTitle, Section, StatusPill } from '../../components/ui'
import { useStudio } from '../StudioState'
import { countScenes, countShots, formatDuration, initials } from '../utils'
import { EmptyState, LoadingState } from '../components/StateBlocks'
import { toProtoProject } from '../proto/adapter'

type ProviderPreference = 'local' | 'hosted' | 'mixed'
type LogicalModel = NonNullable<ManualTaskRoute['logical_model']>

const PLANNING_TASKS: Array<{
  task: PlanningTaskType
  label: string
  logicalModel: LogicalModel
}> = [
  { task: 'story_structure', label: 'Story adaptation', logicalModel: 'sol' },
  { task: 'character_bible', label: 'Character bible', logicalModel: 'terra' },
  { task: 'chapter_outline', label: 'Chapter outline', logicalModel: 'terra' },
  { task: 'scene_breakdown', label: 'Scene breakdown', logicalModel: 'terra' },
  { task: 'shot_list', label: 'Shot list', logicalModel: 'luna' },
  { task: 'narration_plan', label: 'Narration plan', logicalModel: 'terra' },
  { task: 'prompt_package', label: 'Prompt packages', logicalModel: 'luna' },
  { task: 'continuity_plan', label: 'Continuity review', logicalModel: 'terra' },
  { task: 'model_recommendation', label: 'Model recommendations', logicalModel: 'terra' },
  { task: 'production_proposal', label: 'Final proposal', logicalModel: 'sol' },
]

const BUILTIN_MOCK_ROUTE = 'builtin:mock'

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback
}

function shortId(value: string): string {
  return value.length > 12 ? `${value.slice(0, 8)}…${value.slice(-4)}` : value
}

function statusClass(status: string | null | undefined): string {
  if (['completed', 'validated', 'applied', 'valid', 'succeeded'].includes(status ?? '')) return 'verified'
  if (['failed', 'canceled', 'rejected', 'invalid', 'superseded'].includes(status ?? '')) return 'blocked'
  return 'unknown'
}

function diffValue(value: unknown): string {
  if (value == null) return '—'
  const serialized = typeof value === 'string' ? value : JSON.stringify(value)
  return serialized.length > 180 ? `${serialized.slice(0, 177)}…` : serialized
}

function chapterLabel(index: number): string {
  return `CH${String(index + 1).padStart(2, '0')}`
}

function sceneLabel(index: number): string {
  return `SC${String(index + 1).padStart(2, '0')}`
}

function sceneCharacterIds(scene: Scene): string[] {
  const seen = new Set<string>()
  const ordered: string[] = []
  for (const shot of scene.shots) {
    for (const link of shot.characters ?? []) {
      if (seen.has(link.character_id)) continue
      seen.add(link.character_id)
      ordered.push(link.character_id)
    }
  }
  return ordered
}

export function StoryPage() {
  const { data, readiness, addHierarchy, updateStoryFields, reload, setMessage, busy } = useStudio()
  const storyId = data?.story.id ?? ''
  const [logline, setLogline] = useState(data?.story.logline ?? '')
  const [synopsis, setSynopsis] = useState(data?.story.synopsis ?? '')
  const [baseStory, setBaseStory] = useState(data?.story.base_story ?? '')
  const [audience, setAudience] = useState(data?.story.audience ?? '')
  const [tone, setTone] = useState(data?.story.tone ?? '')
  const [genre, setGenre] = useState(data?.story.genre ?? '')
  const [visualStyle, setVisualStyle] = useState(data?.story.visual_style ?? '')
  const [pointOfView, setPointOfView] = useState(data?.story.point_of_view ?? '')
  const [productionNotes, setProductionNotes] = useState(data?.story.production_notes ?? '')
  const [targetRuntime, setTargetRuntime] = useState(String(data?.story.target_duration_sec ?? ''))
  const [expandedIds, setExpandedIds] = useState<string[] | null>(null)

  const [actorName, setActorName] = useState('')
  const [routingMode, setRoutingMode] = useState<OrchestrationRoutingMode>('automatic')
  const [providerPreference, setProviderPreference] = useState<ProviderPreference>('local')
  const [providerProfiles, setProviderProfiles] = useState<ProviderProfile[]>([])
  const [providerCatalog, setProviderCatalog] = useState<ProviderCatalogEntry[]>([])
  const [routingPreflight, setRoutingPreflight] = useState<RoutingPreflightResponse | null>(null)
  const [manualRouteSelections, setManualRouteSelections] = useState<
    Partial<Record<PlanningTaskType, string>>
  >({})
  const [maxSteps, setMaxSteps] = useState(10)
  const [repairBudget, setRepairBudget] = useState(3)
  const [timeBudgetSec, setTimeBudgetSec] = useState(300)
  const [transportRetryLimit, setTransportRetryLimit] = useState(2)
  const [runs, setRuns] = useState<OrchestrationRun[]>([])
  const [selectedRunId, setSelectedRunId] = useState('')
  const [selectedRun, setSelectedRun] = useState<OrchestrationRunDetail | null>(null)
  const [proposals, setProposals] = useState<StoryboardProposal[]>([])
  const [selectedProposalId, setSelectedProposalId] = useState('')
  const [selectedProposal, setSelectedProposal] = useState<StoryboardProposal | null>(null)
  const [proposalDiff, setProposalDiff] = useState<ProposalDiff | null>(null)
  const [reviewNotes, setReviewNotes] = useState('')
  const [rejectionReason, setRejectionReason] = useState('')
  const [planningLoading, setPlanningLoading] = useState(true)
  const [planningBusy, setPlanningBusy] = useState(false)
  const [planningError, setPlanningError] = useState<string | null>(null)
  const [planningNotice, setPlanningNotice] = useState<string | null>(null)
  const [structureBusy, setStructureBusy] = useState(false)
  const [structureError, setStructureError] = useState<string | null>(null)
  const syncedStoryId = data?.story.id ?? ''
  const syncedStoryVersionId = data?.story.active_storyboard_version_id ?? ''
  const syncedLogline = data?.story.logline ?? ''
  const syncedSynopsis = data?.story.synopsis ?? ''
  const syncedBaseStory = data?.story.base_story ?? ''
  const syncedAudience = data?.story.audience ?? ''
  const syncedTone = data?.story.tone ?? ''
  const syncedGenre = data?.story.genre ?? ''
  const syncedVisualStyle = data?.story.visual_style ?? ''
  const syncedPointOfView = data?.story.point_of_view ?? ''
  const syncedProductionNotes = data?.story.production_notes ?? ''
  const syncedTargetRuntime = String(data?.story.target_duration_sec ?? '')

  const view = useMemo(() => (data ? toProtoProject(data, readiness) : null), [data, readiness])

  useEffect(() => {
    if (!syncedStoryId) return
    const timer = window.setTimeout(() => {
      setLogline(syncedLogline)
      setSynopsis(syncedSynopsis)
      setBaseStory(syncedBaseStory)
      setAudience(syncedAudience)
      setTone(syncedTone)
      setGenre(syncedGenre)
      setVisualStyle(syncedVisualStyle)
      setPointOfView(syncedPointOfView)
      setProductionNotes(syncedProductionNotes)
      setTargetRuntime(syncedTargetRuntime)
    }, 0)
    return () => window.clearTimeout(timer)
  }, [
    syncedStoryId,
    syncedStoryVersionId,
    syncedLogline,
    syncedSynopsis,
    syncedBaseStory,
    syncedAudience,
    syncedTone,
    syncedGenre,
    syncedVisualStyle,
    syncedPointOfView,
    syncedProductionNotes,
    syncedTargetRuntime,
  ])

  const loadPlanning = useCallback(
    async (preferredRunId?: string, preferredProposalId?: string, silent = false) => {
      if (!storyId) return
      if (!silent) {
        setPlanningLoading(true)
        setPlanningError(null)
      }
      try {
        const [runList, proposalList, profileList, catalog] = await Promise.all([
          api.listOrchestrationRuns(storyId),
          api.listStoryProposals(storyId),
          api.listProviderProfiles().catch(() => []),
          api.listPlanningProviders().catch(() => null),
        ])
        setRuns(runList)
        setProposals(proposalList)
        setProviderProfiles(profileList)
        setProviderCatalog(catalog?.providers ?? [])

        const runId =
          (preferredRunId && runList.some((run) => run.id === preferredRunId) && preferredRunId) ||
          runList.at(0)?.id ||
          ''
        setSelectedRunId(runId)
        setSelectedRun(runId ? await api.getOrchestrationRun(runId) : null)

        const proposalId =
          (preferredProposalId &&
            proposalList.some((proposal) => proposal.id === preferredProposalId) &&
            preferredProposalId) ||
          proposalList.at(0)?.id ||
          ''
        setSelectedProposalId(proposalId)
        if (proposalId) {
          const proposal = await api.getProposal(proposalId)
          setSelectedProposal(proposal)
          try {
            setProposalDiff(await api.getProposalDiff(proposalId))
          } catch (error) {
            setProposalDiff(null)
            setPlanningError(
              `Proposal loaded, but its diff is unavailable: ${errorMessage(error, 'Unknown diff error.')}`,
            )
          }
        } else {
          setSelectedProposal(null)
          setProposalDiff(null)
        }
      } catch (error) {
        setPlanningError(errorMessage(error, 'Could not load orchestration runs and proposals.'))
      } finally {
        if (!silent) setPlanningLoading(false)
      }
    },
    [storyId],
  )

  useEffect(() => {
    const timer = window.setTimeout(() => void loadPlanning(), 0)
    return () => window.clearTimeout(timer)
  }, [loadPlanning])

  useEffect(() => {
    if (!selectedRunId || !['pending', 'running'].includes(selectedRun?.status ?? '')) return

    let canceled = false
    let timer = 0
    const poll = async () => {
      await loadPlanning(selectedRunId, selectedProposalId || undefined, true)
      if (!canceled) timer = window.setTimeout(() => void poll(), 1250)
    }
    timer = window.setTimeout(() => void poll(), 500)
    return () => {
      canceled = true
      window.clearTimeout(timer)
    }
  }, [loadPlanning, selectedProposalId, selectedRun?.status, selectedRunId])

  const characterById = useMemo(() => {
    const map = new Map((data?.characters ?? []).map((character) => [character.id, character]))
    return map
  }, [data?.characters])

  if (!data) return null

  const story = data.story
  const chapters = data.chapters
  const sceneCount = countScenes(chapters)
  const shotCount = countShots(chapters)
  const plannedDuration = chapters.reduce((total, chapter) => total + chapter.duration_sec, 0)
  const hierarchySummary = `${chapters.length} chapter${chapters.length === 1 ? '' : 's'} · ${sceneCount} scene${sceneCount === 1 ? '' : 's'} · ${shotCount} shot${shotCount === 1 ? '' : 's'} · ${formatDuration(plannedDuration)}`
  const openChapterIds = expandedIds ?? chapters.map((chapter) => chapter.id)
  const providerFactById = new Map(providerCatalog.map((provider) => [provider.provider_identifier, provider]))
  const routeOptions = [
    {
      value: BUILTIN_MOCK_ROUTE,
      label: 'Built-in mock · local · available',
      providerIdentifier: 'mock',
      availabilityStatus: providerFactById.get('mock')?.availability_status ?? 'available',
      privacy: providerFactById.get('mock')?.privacy_classification ?? 'local',
    },
    ...providerProfiles.map((profile) => {
      const fact = providerFactById.get(profile.provider_identifier)
      return {
        value: profile.id,
        label: `${profile.display_name} · ${fact?.availability_status ?? 'unknown'} · ${fact?.privacy_classification ?? profile.privacy_classification ?? 'unknown'}`,
        providerIdentifier: profile.provider_identifier,
        availabilityStatus: fact?.availability_status ?? 'unknown',
        privacy: fact?.privacy_classification ?? profile.privacy_classification ?? 'unknown',
      }
    }),
  ]

  const disabled = busy || planningBusy || planningLoading
  const structureDisabled = busy || structureBusy
  const actor = actorName.trim()
  const runCanStart = selectedRun?.status === 'pending'
  const runCanCancel = selectedRun?.status === 'pending' || selectedRun?.status === 'running'
  const runCanRetry = selectedRun?.status === 'failed' || selectedRun?.status === 'canceled'
  const proposalIsTerminal = ['applied', 'rejected', 'superseded'].includes(selectedProposal?.status ?? '')
  const proposalCanReview =
    Boolean(selectedProposal) &&
    !proposalIsTerminal &&
    selectedProposal?.validation_status !== 'invalid' &&
    !selectedProposal?.validation_errors.length
  const proposalCanApply =
    selectedProposal?.status === 'validated' &&
    selectedProposal.validation_status !== 'invalid' &&
    !selectedProposal.validation_errors.length &&
    proposalDiff?.proposal_id === selectedProposal.id

  const hasProposal = Boolean(selectedProposal)
  const protoProject = view?.project

  async function chooseRun(runId: string) {
    setSelectedRunId(runId)
    setPlanningBusy(true)
    setPlanningError(null)
    try {
      setSelectedRun(runId ? await api.getOrchestrationRun(runId) : null)
    } catch (error) {
      setPlanningError(errorMessage(error, 'Could not load the selected run.'))
    } finally {
      setPlanningBusy(false)
    }
  }

  async function chooseProposal(proposalId: string) {
    setSelectedProposalId(proposalId)
    setPlanningBusy(true)
    setPlanningError(null)
    try {
      if (!proposalId) {
        setSelectedProposal(null)
        setProposalDiff(null)
        return
      }
      const proposal = await api.getProposal(proposalId)
      setSelectedProposal(proposal)
      try {
        setProposalDiff(await api.getProposalDiff(proposalId))
      } catch (error) {
        setProposalDiff(null)
        setPlanningError(
          `Proposal loaded, but its diff is unavailable: ${errorMessage(error, 'Unknown diff error.')}`,
        )
      }
    } catch (error) {
      setProposalDiff(null)
      setPlanningError(errorMessage(error, 'Could not inspect the selected proposal.'))
    } finally {
      setPlanningBusy(false)
    }
  }

  function buildManualRoutes(): ManualTaskRoute[] {
    return PLANNING_TASKS.flatMap<ManualTaskRoute>(({ task, logicalModel }) => {
      const selection = manualRouteSelections[task]
      if (!selection) return []
      if (selection === BUILTIN_MOCK_ROUTE) {
        return [
          {
            task_type: task,
            provider_identifier: 'mock',
            logical_model: logicalModel,
            rationale: 'Explicit Studio route to the deterministic local mock provider.',
          },
        ]
      }
      const profile = providerProfiles.find((item) => item.id === selection)
      if (!profile) return []
      return [
        {
          task_type: task,
          provider_identifier: profile.provider_identifier,
          logical_model: logicalModel,
          resolved_model: profile.provider_model_id,
          rationale: `Explicit Studio route through provider profile ${profile.display_name}.`,
        },
      ]
    })
  }

  function changeRoutingMode(nextMode: OrchestrationRoutingMode) {
    setRoutingMode(nextMode)
    if (nextMode === 'manual') {
      setManualRouteSelections((current) => {
        const next = { ...current }
        for (const { task } of PLANNING_TASKS) next[task] = next[task] || BUILTIN_MOCK_ROUTE
        return next
      })
    }
  }

  async function createRun() {
    setPlanningBusy(true)
    setPlanningError(null)
    setPlanningNotice(null)
    try {
      const manualRoutes = buildManualRoutes()
      if (routingMode === 'manual' && manualRoutes.length !== PLANNING_TASKS.length) {
        throw new Error('Manual routing requires an explicit provider route for every planning task.')
      }
      const preflight = await api.validateStoryRouting(story.id, {
        routing_mode: routingMode,
        manual_routes: manualRoutes,
        prefer_local_providers: providerPreference !== 'hosted',
        prefer_hosted_providers: providerPreference !== 'local',
        max_steps: maxSteps,
        time_budget_sec: timeBudgetSec,
        transport_retry_limit: transportRetryLimit,
        task_types: PLANNING_TASKS.map((item) => item.task),
      })
      setRoutingPreflight(preflight)
      if (!preflight.valid) {
        const details = preflight.errors.map((issue) => issue.message).join(' ')
        throw new Error(details || 'Routing preflight rejected this run configuration.')
      }
      const result = await api.createOrchestrationRun({
        story_id: story.id,
        base_storyboard_version_id:
          story.approval_state === 'approved' ? story.active_storyboard_version_id ?? null : null,
        requested_by: actor || null,
        routing_mode: routingMode,
        manual_routes: manualRoutes,
        prefer_local_providers: providerPreference !== 'hosted',
        prefer_hosted_providers: providerPreference !== 'local',
        max_steps: maxSteps,
        repair_budget: repairBudget,
        time_budget_sec: timeBudgetSec,
        transport_retry_limit: transportRetryLimit,
        idempotency_key: `studio-${crypto.randomUUID()}`,
      })
      setPlanningNotice(
        result.idempotent_replay
          ? 'The existing idempotent pending run was loaded. It has not been started.'
          : 'Planning run created in pending state. Start it explicitly when ready.',
      )
      await loadPlanning(result.run.id, selectedProposalId || undefined)
    } catch (error) {
      setPlanningError(errorMessage(error, 'Could not create the planning run.'))
    } finally {
      setPlanningBusy(false)
    }
  }

  async function startRun() {
    if (!selectedRun || !runCanStart) return
    setPlanningBusy(true)
    setPlanningError(null)
    setPlanningNotice('The planning request is running. No proposal will be applied automatically.')
    try {
      const result = await api.startOrchestrationRun(selectedRun.id)
      setPlanningNotice(result.message)
      setRuns((current) => current.map((run) => (run.id === result.run.id ? result.run : run)))
      setSelectedRun((current) =>
        current?.id === result.run.id ? { ...current, ...result.run } : current,
      )
      void loadPlanning(result.run.id, selectedProposalId || undefined, true)
    } catch (error) {
      setPlanningError(errorMessage(error, 'Could not start the selected run.'))
    } finally {
      setPlanningBusy(false)
    }
  }

  async function retryRun() {
    if (!selectedRun || !runCanRetry) return
    setPlanningBusy(true)
    setPlanningError(null)
    try {
      const result = await api.retryOrchestrationRun(selectedRun.id, actor || undefined)
      setPlanningNotice(
        result.idempotent_replay
          ? 'The existing pending retry was loaded. Start it explicitly when ready.'
          : 'A new bounded retry run was created in pending state. Prior run history was preserved.',
      )
      await loadPlanning(result.run.id, selectedProposalId || undefined)
    } catch (error) {
      setPlanningError(errorMessage(error, 'Could not create a retry for the selected run.'))
    } finally {
      setPlanningBusy(false)
    }
  }

  async function cancelRun() {
    if (!selectedRun || !runCanCancel) return
    setPlanningBusy(true)
    setPlanningError(null)
    try {
      const result = await api.cancelOrchestrationRun(
        selectedRun.id,
        'Canceled from Story & chapters planning review.',
        actor || undefined,
      )
      setPlanningNotice(result.message)
      await loadPlanning(result.run.id, selectedProposalId || undefined)
    } catch (error) {
      setPlanningError(errorMessage(error, 'Could not cancel the selected run.'))
    } finally {
      setPlanningBusy(false)
    }
  }

  async function reviewProposal() {
    if (!selectedProposal || !actor || !proposalCanReview) return
    setPlanningBusy(true)
    setPlanningError(null)
    try {
      const proposal = await api.reviewProposal(selectedProposal.id, actor, reviewNotes)
      setPlanningNotice('Proposal marked reviewed. It remains unapplied until you choose Apply proposal.')
      await loadPlanning(selectedRunId || undefined, proposal.id)
    } catch (error) {
      setPlanningError(errorMessage(error, 'Could not review the proposal.'))
    } finally {
      setPlanningBusy(false)
    }
  }

  async function rejectProposal() {
    if (!selectedProposal || !actor || !rejectionReason.trim() || proposalIsTerminal) return
    setPlanningBusy(true)
    setPlanningError(null)
    try {
      const proposal = await api.rejectProposal(selectedProposal.id, actor, rejectionReason.trim())
      setPlanningNotice('Proposal rejected. No storyboard changes were applied.')
      await loadPlanning(selectedRunId || undefined, proposal.id)
    } catch (error) {
      setPlanningError(errorMessage(error, 'Could not reject the proposal.'))
    } finally {
      setPlanningBusy(false)
    }
  }

  async function applyProposal() {
    if (!selectedProposal || !proposalDiff || !actor || !proposalCanApply) return
    setPlanningBusy(true)
    setPlanningError(null)
    try {
      const result = await api.applyProposal(
        selectedProposal.id,
        actor,
        proposalDiff.base_storyboard_version_id,
        proposalDiff.base_content_hash,
      )
      await reload(story.id)
      await loadPlanning(selectedRunId || undefined, selectedProposal.id)
      const notice = `Proposal applied as storyboard version ${result.version_number}. The live plan was refreshed.`
      setPlanningNotice(notice)
      setMessage(notice)
    } catch (error) {
      setPlanningError(errorMessage(error, 'Could not apply the proposal.'))
    } finally {
      setPlanningBusy(false)
    }
  }

  async function persistStructure(action: () => Promise<unknown>, successMessage: string) {
    setStructureBusy(true)
    setStructureError(null)
    try {
      await action()
      await reload(story.id)
      setMessage(successMessage)
    } catch (error) {
      const text = errorMessage(error, 'Could not update the persisted story structure.')
      setStructureError(text)
      setMessage(text)
    } finally {
      setStructureBusy(false)
    }
  }

  async function editChapter(chapter: Chapter) {
    const title = window.prompt('Chapter title', chapter.title)
    if (title === null || !title.trim()) return
    const summary = window.prompt('Chapter summary (optional)', chapter.summary ?? '')
    if (summary === null) return
    await persistStructure(
      () => api.updateChapter(chapter.id, { title: title.trim(), summary: summary.trim() || null }),
      `Chapter “${title.trim()}” updated on the backend.`,
    )
  }

  async function editScene(scene: Scene) {
    const title = window.prompt('Scene title', scene.title)
    if (title === null || !title.trim()) return
    const summary = window.prompt('Scene summary (optional)', scene.summary ?? '')
    if (summary === null) return
    await persistStructure(
      () => api.updateScene(scene.id, { title: title.trim(), summary: summary.trim() || null }),
      `Scene “${title.trim()}” updated on the backend.`,
    )
  }

  async function deleteChapter(chapter: Chapter) {
    if (!window.confirm(`Archive chapter “${chapter.title}” and its active descendants?`)) return
    await persistStructure(
      () => api.deleteChapter(chapter.id, 'Archived from Story & chapters.'),
      `Chapter “${chapter.title}” archived on the backend.`,
    )
  }

  async function deleteScene(scene: Scene) {
    if (!window.confirm(`Archive scene “${scene.title}” and its active shots?`)) return
    await persistStructure(
      () => api.deleteScene(scene.id, 'Archived from Story & chapters.'),
      `Scene “${scene.title}” archived on the backend.`,
    )
  }

  async function moveChapter(chapterIndex: number, direction: -1 | 1) {
    const targetIndex = chapterIndex + direction
    if (targetIndex < 0 || targetIndex >= chapters.length) return
    const orderedIds = chapters.map((chapter) => chapter.id)
    ;[orderedIds[chapterIndex], orderedIds[targetIndex]] = [
      orderedIds[targetIndex],
      orderedIds[chapterIndex],
    ]
    await persistStructure(
      () => api.reorderChapters(story.id, orderedIds),
      'Chapter order persisted to the backend.',
    )
  }

  async function moveScene(chapter: Chapter, sceneIndex: number, direction: -1 | 1) {
    const targetIndex = sceneIndex + direction
    if (targetIndex < 0 || targetIndex >= chapter.scenes.length) return
    const orderedIds = chapter.scenes.map((scene) => scene.id)
    ;[orderedIds[sceneIndex], orderedIds[targetIndex]] = [
      orderedIds[targetIndex],
      orderedIds[sceneIndex],
    ]
    await persistStructure(
      () => api.reorderScenes(chapter.id, orderedIds),
      'Scene order persisted to the backend.',
    )
  }

  function toggleChapter(chapterId: string) {
    const current = openChapterIds
    setExpandedIds(
      current.includes(chapterId)
        ? current.filter((id) => id !== chapterId)
        : [...current, chapterId],
    )
  }

  function saveStoryFields() {
    const parsedRuntime = Number(targetRuntime)
    void updateStoryFields({
      logline: logline || null,
      synopsis: synopsis || null,
      base_story: baseStory,
      audience: audience || null,
      tone: tone || null,
      genre: genre || null,
      visual_style: visualStyle || null,
      point_of_view: pointOfView || null,
      production_notes: productionNotes || null,
      ...(Number.isFinite(parsedRuntime) && parsedRuntime > 0
        ? { target_duration_sec: Math.round(parsedRuntime) }
        : {}),
    })
  }

  // Diff ops as lightweight suggestion cards when a proposal is loaded.
  const suggestionCards: Array<{ title: string; body: string }> = (() => {
    if (!proposalDiff?.ops.length) {
      if (selectedProposal) {
        return [
          {
            title: `${selectedProposal.status} · ${selectedProposal.proposal_type}`,
            body:
              selectedProposal.validation_status === 'invalid'
                ? 'Proposal failed validation and cannot be applied.'
                : `Schema ${selectedProposal.schema_name || 'unknown'} · ${proposalDiff?.ops.length ?? 0} diff ops.`,
          },
        ]
      }
      return []
    }
    return proposalDiff.ops.slice(0, 6).map((op) => ({
      title: `${op.op} · ${op.path}`,
      body: `Before: ${diffValue(op.before)} → After: ${diffValue(op.after)}`,
    }))
  })()

  return (
    <div className="page proto-page">
      <PageTitle
        eyebrow="STORY INTAKE & STRUCTURE"
        title="Story & chapters"
        description="Edit the source narrative and reconcile every structural beat before shot planning."
        aside={
          <div className="page-actions">
            <Button
              onClick={() => void createRun()}
              disabled={disabled}
              icon="spark"
            >
              {planningBusy ? 'Generating proposal…' : 'Generate structure'}
            </Button>
            <Button
              variant="primary"
              icon="check"
              onClick={() => void reviewProposal()}
              disabled={disabled || !actor || !proposalCanReview}
              title={
                !actor
                  ? 'Enter an audit name in the planning panel to mark a proposal reviewed.'
                  : !proposalCanReview
                    ? 'Select a non-terminal, valid proposal first.'
                    : undefined
              }
            >
              Mark reviewed
            </Button>
          </div>
        }
      />

      <div className="split-layout story-editor">
        <div className="stack">
          <Section
            title="Source story"
            subtitle="Production intent supplied to the selected orchestrator."
            action={<StatusPill status={story.approval_state || 'draft'} />}
          >
            <div className="form-grid two">
              <label>
                Title
                <input value={story.title} readOnly aria-readonly="true" />
              </label>
              <label>
                Target runtime
                <input
                  type="number"
                  min={1}
                  value={targetRuntime}
                  onChange={(event) => setTargetRuntime(event.target.value)}
                  disabled={busy}
                />
              </label>
            </div>
            <div className="form-stack">
              <label>
                Logline
                <textarea
                  value={logline}
                  onChange={(event) => setLogline(event.target.value)}
                  disabled={busy}
                  placeholder="One-sentence production intent"
                  rows={2}
                />
              </label>
              <label>
                Full base story
                <textarea
                  className="story-textarea"
                  value={baseStory}
                  onChange={(event) => setBaseStory(event.target.value)}
                  disabled={busy}
                  rows={5}
                />
              </label>
              <label>
                Synopsis
                <textarea
                  value={synopsis}
                  onChange={(event) => setSynopsis(event.target.value)}
                  disabled={busy}
                  placeholder="Short synopsis for review"
                  rows={2}
                />
              </label>
              <div className="form-grid three">
                <label>
                  Audience
                  <input
                    value={audience}
                    onChange={(event) => setAudience(event.target.value)}
                    disabled={busy}
                  />
                </label>
                <label>
                  Tone
                  <input value={tone} onChange={(event) => setTone(event.target.value)} disabled={busy} />
                </label>
                <label>
                  Genre
                  <input
                    value={genre}
                    onChange={(event) => setGenre(event.target.value)}
                    disabled={busy}
                  />
                </label>
              </div>
              <div className="form-grid two">
                <label>
                  Visual style
                  <input
                    value={visualStyle}
                    onChange={(event) => setVisualStyle(event.target.value)}
                    disabled={busy}
                  />
                </label>
                <label>
                  Narrative point of view
                  <input
                    value={pointOfView}
                    onChange={(event) => setPointOfView(event.target.value)}
                    disabled={busy}
                  />
                </label>
              </div>
              <label>
                Production notes
                <textarea
                  value={productionNotes}
                  onChange={(event) => setProductionNotes(event.target.value)}
                  disabled={busy}
                  rows={2}
                />
              </label>
              <div className="inline-actions">
                <Button variant="primary" disabled={busy} onClick={saveStoryFields}>
                  Save story fields
                </Button>
              </div>
            </div>
          </Section>

          <Section
            title="Narrative hierarchy"
            subtitle={hierarchySummary}
            action={
              <Button
                variant="quiet"
                icon="plus"
                disabled={structureDisabled}
                onClick={() => void addHierarchy('chapter')}
              >
                Add chapter
              </Button>
            }
          >
            {structureError ? (
              <p className="notice error" role="alert">
                {structureError}
              </p>
            ) : null}
            {!chapters.length ? (
              <EmptyState title="No chapters" detail="Create the first chapter to structure the story." />
            ) : (
              <div className="hierarchy">
                {chapters.map((chapter, chapterIndex) => {
                  const open = openChapterIds.includes(chapter.id)
                  const chapterIdLabel = chapterLabel(chapterIndex)
                  return (
                    <article key={chapter.id}>
                      <header>
                        <button type="button" onClick={() => toggleChapter(chapter.id)} aria-expanded={open}>
                          <Icon name="chevron" />
                          <span>
                            <small>{chapterIdLabel}</small>
                            <b>{chapter.title}</b>
                          </span>
                        </button>
                        <span>
                          <b>{formatDuration(chapter.duration_sec)}</b>
                          <small>
                            {chapter.scenes.length} scene{chapter.scenes.length === 1 ? '' : 's'}
                          </small>
                        </span>
                        <div aria-label={`Chapter actions for ${chapter.title}`}>
                          <button
                            type="button"
                            disabled={structureDisabled || chapterIndex === 0}
                            aria-label={`Move ${chapter.title} up`}
                            onClick={() => void moveChapter(chapterIndex, -1)}
                          >
                            ↑
                          </button>
                          <button
                            type="button"
                            disabled={structureDisabled || chapterIndex === chapters.length - 1}
                            aria-label={`Move ${chapter.title} down`}
                            onClick={() => void moveChapter(chapterIndex, 1)}
                          >
                            ↓
                          </button>
                          <button
                            type="button"
                            disabled={structureDisabled}
                            onClick={() => void editChapter(chapter)}
                            aria-label={`Edit ${chapter.title}`}
                          >
                            <Icon name="edit" size={14} />
                          </button>
                          <button
                            type="button"
                            disabled={structureDisabled}
                            onClick={() => void deleteChapter(chapter)}
                            aria-label={`Archive ${chapter.title}`}
                          >
                            <Icon name="trash" size={14} />
                          </button>
                        </div>
                      </header>
                      {open ? (
                        <div className="hierarchy-scenes">
                          {chapter.scenes.map((scene, sceneIndex) => {
                            const sceneChars = sceneCharacterIds(scene).flatMap((id) => {
                              const character = characterById.get(id)
                              return character ? [character] : []
                            })
                            const location =
                              scene.shots.find((shot) => shot.location)?.location ?? null
                            return (
                              <div key={scene.id}>
                                <span className="scene-index">{sceneIndex + 1}</span>
                                <span>
                                  <small>{sceneLabel(sceneIndex)}</small>
                                  <b>{scene.title}</b>
                                  <p>{scene.summary ?? 'No scene summary yet.'}</p>
                                  {location ? <em>{location}</em> : null}
                                </span>
                                <span>
                                  <b>{scene.duration_sec} sec</b>
                                  <small>
                                    {scene.shots.length} shot{scene.shots.length === 1 ? '' : 's'}
                                  </small>
                                </span>
                                <span className="character-dots" aria-label="Characters in scene">
                                  {sceneChars.length
                                    ? sceneChars.map((character) => (
                                        <i key={character.id} title={character.name}>
                                          {initials(character.name)}
                                        </i>
                                      ))
                                    : (
                                        <i title="No linked characters" style={{ opacity: 0.45 }}>
                                          —
                                        </i>
                                      )}
                                </span>
                                <button
                                  type="button"
                                  disabled={structureDisabled}
                                  onClick={() => void editScene(scene)}
                                  aria-label={`Edit ${scene.title}`}
                                >
                                  <Icon name="edit" size={14} />
                                </button>
                                <button
                                  type="button"
                                  disabled={structureDisabled}
                                  onClick={() => void deleteScene(scene)}
                                  aria-label={`Archive ${scene.title}`}
                                >
                                  <Icon name="trash" size={14} />
                                </button>
                                <div
                                  className="inline-actions"
                                  style={{ gridColumn: '1 / -1', justifyContent: 'flex-end' }}
                                  aria-label={`Reorder ${scene.title}`}
                                >
                                  <button
                                    type="button"
                                    className="ghost-button"
                                    disabled={structureDisabled || sceneIndex === 0}
                                    aria-label={`Move ${scene.title} up`}
                                    onClick={() => void moveScene(chapter, sceneIndex, -1)}
                                  >
                                    ↑ Scene
                                  </button>
                                  <button
                                    type="button"
                                    className="ghost-button"
                                    disabled={
                                      structureDisabled || sceneIndex === chapter.scenes.length - 1
                                    }
                                    aria-label={`Move ${scene.title} down`}
                                    onClick={() => void moveScene(chapter, sceneIndex, 1)}
                                  >
                                    ↓ Scene
                                  </button>
                                  <button
                                    type="button"
                                    className="ghost-button"
                                    disabled={structureDisabled}
                                    onClick={() => void addHierarchy('shot')}
                                  >
                                    + Shot
                                  </button>
                                </div>
                              </div>
                            )
                          })}
                          {!chapter.scenes.length ? (
                            <div>
                              <span className="scene-index">—</span>
                              <span>
                                <b>No scenes</b>
                                <p>Add a scene under this chapter.</p>
                              </span>
                              <span />
                              <span />
                              <button
                                type="button"
                                disabled={structureDisabled}
                                onClick={() => void addHierarchy('scene')}
                              >
                                <Icon name="plus" size={14} />
                              </button>
                              <span />
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </article>
                  )
                })}
              </div>
            )}
            <div className="inline-actions" style={{ marginTop: 10 }}>
              <Button
                variant="quiet"
                disabled={structureDisabled}
                onClick={() => void addHierarchy('scene')}
              >
                Add scene
              </Button>
              <Button
                variant="quiet"
                disabled={structureDisabled}
                onClick={() => void addHierarchy('shot')}
              >
                Add shot
              </Button>
            </div>
          </Section>

          <Section
            title="Planning orchestration and proposal review"
            subtitle="Create and start a real backend planning run, inspect its immutable proposal, then review, reject, or apply it explicitly. Starting a run never applies its proposal."
            action={
              <Button
                variant="quiet"
                disabled={disabled}
                onClick={() =>
                  void loadPlanning(selectedRunId || undefined, selectedProposalId || undefined)
                }
              >
                Refresh status
              </Button>
            }
          >
            {planningLoading ? <LoadingState title="Loading planning history…" /> : null}
            {planningError ? (
              <p className="notice error" role="alert">
                {planningError}
              </p>
            ) : null}
            {planningNotice ? (
              <p className="notice info" role="status" aria-live="polite">
                {planningNotice}
              </p>
            ) : null}

            <div className="form-stack">
              <h3>1. Configure and run</h3>
              <label>
                Audit name
                <input
                  value={actorName}
                  onChange={(event) => setActorName(event.target.value)}
                  disabled={disabled}
                  placeholder="Your name or production role"
                  maxLength={200}
                />
              </label>
              <div className="form-grid two">
                <label>
                  Routing mode
                  <select
                    value={routingMode}
                    onChange={(event) =>
                      changeRoutingMode(event.target.value as OrchestrationRoutingMode)
                    }
                    disabled={disabled}
                  >
                    <option value="automatic">Automatic</option>
                    <option value="hybrid">Hybrid</option>
                    <option value="manual">Manual</option>
                  </select>
                </label>
                <label>
                  Provider preference
                  <select
                    value={providerPreference}
                    onChange={(event) =>
                      setProviderPreference(event.target.value as ProviderPreference)
                    }
                    disabled={disabled}
                  >
                    <option value="local">Prefer local only</option>
                    <option value="mixed">Prefer local and allow hosted</option>
                    <option value="hosted">Prefer hosted only</option>
                  </select>
                </label>
              </div>
              <p className="form-hint">
                Provider preferences are recorded with the run. This page does not install models,
                submit render jobs, or generate media.
              </p>
              <div className="form-grid two">
                <label>
                  Max steps
                  <input
                    type="number"
                    min={10}
                    max={50}
                    value={maxSteps}
                    onChange={(event) => setMaxSteps(Number(event.target.value))}
                    disabled={disabled}
                  />
                </label>
                <label>
                  Repair budget
                  <input
                    type="number"
                    min={0}
                    max={20}
                    value={repairBudget}
                    onChange={(event) => setRepairBudget(Number(event.target.value))}
                    disabled={disabled}
                  />
                </label>
                <label>
                  Time budget seconds
                  <input
                    type="number"
                    min={30}
                    max={3600}
                    value={timeBudgetSec}
                    onChange={(event) => setTimeBudgetSec(Number(event.target.value))}
                    disabled={disabled}
                  />
                </label>
                <label>
                  Transport retries
                  <input
                    type="number"
                    min={0}
                    max={5}
                    value={transportRetryLimit}
                    onChange={(event) => setTransportRetryLimit(Number(event.target.value))}
                    disabled={disabled}
                  />
                </label>
              </div>
              {routingMode !== 'automatic' ? (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Task</th>
                        <th>Route</th>
                        <th>Runtime fact</th>
                      </tr>
                    </thead>
                    <tbody>
                      {PLANNING_TASKS.map(({ task, label, logicalModel }) => {
                        const selected = manualRouteSelections[task] ?? ''
                        const option = routeOptions.find((item) => item.value === selected)
                        return (
                          <tr key={task}>
                            <td>
                              {label} · {logicalModel}
                            </td>
                            <td>
                              <select
                                value={selected}
                                onChange={(event) =>
                                  setManualRouteSelections((current) => ({
                                    ...current,
                                    [task]: event.target.value,
                                  }))
                                }
                                disabled={disabled}
                              >
                                <option value="">
                                  {routingMode === 'manual'
                                    ? 'Route required'
                                    : 'Use automatic route'}
                                </option>
                                {routeOptions.map((item) => (
                                  <option key={`${task}-${item.value}`} value={item.value}>
                                    {item.label}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td>
                              {option
                                ? `${option.providerIdentifier} · ${option.availabilityStatus} · ${option.privacy}`
                                : 'Automatic decision'}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              ) : null}
              {providerCatalog.length ? (
                <details className="debug-panel">
                  <summary>Provider facts used by preflight</summary>
                  <ul>
                    {providerCatalog.map((provider) => (
                      <li key={provider.provider_identifier}>
                        {provider.display_name}: {provider.availability_status} ·{' '}
                        {provider.privacy_classification} ·{' '}
                        {provider.capabilities.join(', ') || 'no verified capabilities'}
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}
              {routingPreflight ? (
                <p
                  className={`notice ${routingPreflight.valid ? 'info' : 'error'}`}
                  role="status"
                >
                  Routing preflight {routingPreflight.valid ? 'passed' : 'failed'} with{' '}
                  {routingPreflight.routes.length} route
                  {routingPreflight.routes.length === 1 ? '' : 's'}.
                </p>
              ) : null}
              <div className="inline-actions">
                <Button disabled={disabled} onClick={() => void createRun()}>
                  Create pending run
                </Button>
                <Button variant="primary" disabled={disabled || !runCanStart} onClick={() => void startRun()}>
                  Start selected run
                </Button>
                <Button variant="quiet" disabled={disabled || !runCanCancel} onClick={() => void cancelRun()}>
                  Cancel selected run
                </Button>
                <Button disabled={disabled || !runCanRetry} onClick={() => void retryRun()}>
                  Create retry run
                </Button>
              </div>

              <label>
                Planning run
                <select
                  value={selectedRunId}
                  onChange={(event) => void chooseRun(event.target.value)}
                  disabled={disabled || !runs.length}
                >
                  {!runs.length ? <option value="">No runs yet</option> : null}
                  {runs.map((run) => (
                    <option key={run.id} value={run.id}>
                      {run.status} · {formatDate(run.created_at)} · {shortId(run.id)}
                    </option>
                  ))}
                </select>
              </label>

              {selectedRun ? (
                <>
                  <ul className="kv-list">
                    <li>
                      <span>Status</span>
                      <strong>
                        <span className={`truth-pill ${statusClass(selectedRun.status)}`}>
                          {selectedRun.status}
                        </span>
                      </strong>
                    </li>
                    <li>
                      <span>Progress</span>
                      <strong>
                        {selectedRun.current_step} / {selectedRun.max_steps} steps
                      </strong>
                    </li>
                    <li>
                      <span>Repairs used</span>
                      <strong>
                        {selectedRun.repair_used} / {selectedRun.repair_budget}
                      </strong>
                    </li>
                    <li>
                      <span>Requested by</span>
                      <strong>{selectedRun.requested_by || 'Not recorded'}</strong>
                    </li>
                    <li>
                      <span>Created</span>
                      <strong>{formatDate(selectedRun.created_at)}</strong>
                    </li>
                  </ul>
                  {selectedRun.failure_message ? (
                    <p className="notice error" role="alert">
                      {selectedRun.failure_message}
                    </p>
                  ) : null}
                  {selectedRun.steps.length ? (
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Step</th>
                            <th>Status</th>
                            <th>Route</th>
                            <th>Attempt</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedRun.steps.map((step) => (
                            <tr key={step.id}>
                              <td>
                                {step.sequence_index + 1}. {step.task_type}
                              </td>
                              <td>
                                <span className={`truth-pill ${statusClass(step.status)}`}>
                                  {step.status}
                                </span>
                              </td>
                              <td>
                                {step.provider_identifier || 'Not selected'}
                                {step.resolved_model ? ` · ${step.resolved_model}` : ''}
                              </td>
                              <td>{step.attempt_number}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="form-hint">This run has no persisted steps yet.</p>
                  )}
                </>
              ) : null}

              <h3>2. Inspect and decide</h3>
              <label>
                Proposal
                <select
                  value={selectedProposalId}
                  onChange={(event) => void chooseProposal(event.target.value)}
                  disabled={disabled || !proposals.length}
                >
                  {!proposals.length ? <option value="">No proposals yet</option> : null}
                  {proposals.map((proposal) => (
                    <option key={proposal.id} value={proposal.id}>
                      {proposal.status} · {proposal.proposal_type} · {shortId(proposal.id)}
                    </option>
                  ))}
                </select>
              </label>

              {selectedProposal ? (
                <>
                  <ul className="kv-list">
                    <li>
                      <span>Status</span>
                      <strong>
                        <span className={`truth-pill ${statusClass(selectedProposal.status)}`}>
                          {selectedProposal.status}
                        </span>
                      </strong>
                    </li>
                    <li>
                      <span>Validation</span>
                      <strong>
                        <span
                          className={`truth-pill ${statusClass(selectedProposal.validation_status)}`}
                        >
                          {selectedProposal.validation_status || 'unknown'}
                        </span>
                      </strong>
                    </li>
                    <li>
                      <span>Schema</span>
                      <strong>{selectedProposal.schema_name || 'Not recorded'}</strong>
                    </li>
                    <li>
                      <span>Reviewed by</span>
                      <strong>{selectedProposal.reviewed_by || 'Not reviewed'}</strong>
                    </li>
                    <li>
                      <span>Content hash</span>
                      <strong className="mono">
                        {selectedProposal.content_hash
                          ? shortId(selectedProposal.content_hash)
                          : 'Not recorded'}
                      </strong>
                    </li>
                    <li>
                      <span>Diff operations</span>
                      <strong>{proposalDiff?.ops.length ?? 'Unavailable'}</strong>
                    </li>
                  </ul>

                  {selectedProposal.validation_errors.length ? (
                    <div className="notice error" role="alert">
                      <strong>Validation errors</strong>
                      <ul>
                        {selectedProposal.validation_errors.map((item, index) => (
                          <li key={`${index}-${String(item)}`}>{String(item)}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {selectedProposal.warnings_json.length ? (
                    <div className="notice warning">
                      <strong>Proposal warnings</strong>
                      <ul>
                        {selectedProposal.warnings_json.map((item, index) => (
                          <li key={`${index}-${String(item)}`}>{String(item)}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {proposalDiff ? (
                    proposalDiff.ops.length ? (
                      <div className="table-wrap">
                        <table>
                          <thead>
                            <tr>
                              <th>Change</th>
                              <th>Path</th>
                              <th>Before</th>
                              <th>After</th>
                            </tr>
                          </thead>
                          <tbody>
                            {proposalDiff.ops.map((operation, index) => (
                              <tr key={`${operation.op}-${operation.path}-${index}`}>
                                <td>{operation.op}</td>
                                <td className="mono">{operation.path}</td>
                                <td>{diffValue(operation.before)}</td>
                                <td>{diffValue(operation.after)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p className="notice info">The proposal diff contains no changes.</p>
                    )
                  ) : (
                    <p className="notice warning">
                      A verified proposal diff is required before Apply is enabled.
                    </p>
                  )}

                  <details className="debug-panel">
                    <summary>Inspect immutable proposal payload</summary>
                    <pre>{JSON.stringify(selectedProposal.payload, null, 2)}</pre>
                  </details>

                  <label>
                    Review notes (optional)
                    <textarea
                      value={reviewNotes}
                      onChange={(event) => setReviewNotes(event.target.value)}
                      disabled={disabled || proposalIsTerminal}
                      maxLength={4000}
                      placeholder="Record approval context or requested follow-up"
                    />
                  </label>
                  <label>
                    Rejection reason (required only to reject)
                    <textarea
                      value={rejectionReason}
                      onChange={(event) => setRejectionReason(event.target.value)}
                      disabled={disabled || proposalIsTerminal}
                      maxLength={4000}
                      placeholder="Explain why this proposal must not be applied"
                    />
                  </label>

                  <div className="inline-actions">
                    <Button
                      disabled={disabled || !actor || !proposalCanReview}
                      onClick={() => void reviewProposal()}
                    >
                      Mark reviewed
                    </Button>
                    <Button
                      variant="quiet"
                      disabled={
                        disabled || !actor || !rejectionReason.trim() || proposalIsTerminal
                      }
                      onClick={() => void rejectProposal()}
                    >
                      Reject proposal
                    </Button>
                    <Button
                      variant="primary"
                      disabled={disabled || !actor || !proposalCanApply}
                      onClick={() => void applyProposal()}
                    >
                      Apply reviewed proposal
                    </Button>
                  </div>
                  <p className="form-hint">
                    Apply checks the proposal&apos;s recorded base version and content hash, then
                    refreshes the live Studio snapshot. It does not create render jobs.
                  </p>
                </>
              ) : (
                <EmptyState
                  title="No proposal to review"
                  detail="Create and explicitly start a planning run. A completed run can publish an immutable proposal here."
                />
              )}
            </div>
          </Section>
        </div>

        <aside className="suggestion-panel">
          <header>
            <span className="orchestrator-mark">
              <Icon name="spark" />
            </span>
            <div>
              <span className="eyebrow">ORCHESTRATOR SUGGESTIONS</span>
              <h2>
                {hasProposal
                  ? `${suggestionCards.length || proposals.length} recommendation${(suggestionCards.length || proposals.length) === 1 ? '' : 's'}`
                  : 'No proposal loaded'}
              </h2>
            </div>
          </header>

          {hasProposal && suggestionCards.length ? (
            <div className="suggestions">
              {suggestionCards.map((card, i) => (
                <article key={`${card.title}-${i}`}>
                  <span>{i + 1}</span>
                  <div>
                    <b>{card.title}</b>
                    <p>{card.body}</p>
                    <small>
                      {selectedProposal?.status || 'Proposal'} · not auto-applied
                    </small>
                  </div>
                  <button
                    type="button"
                    disabled={disabled || !actor || !proposalCanReview}
                    onClick={(e) => {
                      ;(e.currentTarget.closest('article') as HTMLElement).dataset.accepted = 'true'
                      void reviewProposal()
                    }}
                  >
                    <Icon name="check" />
                    Accept
                  </button>
                </article>
              ))}
            </div>
          ) : (
            <div className="suggestion-empty">
              <Icon name="spark" size={28} />
              <p>
                Run Generate Structure to compare a new orchestrator proposal against the current
                hierarchy.
              </p>
              <Button onClick={() => void createRun()} disabled={disabled}>
                Generate proposal
              </Button>
            </div>
          )}

          <div className="proposal-summary">
            <span>Current structure</span>
            <b>
              {protoProject
                ? `${protoProject.chapters.length} chapters · ${protoProject.scenes.length} scenes · ${protoProject.shots.length} shots`
                : `${chapters.length} chapters · ${sceneCount} scenes · ${shotCount} shots`}
            </b>
            <small>
              Planned duration {formatDuration(plannedDuration)}
              {story.target_duration_sec
                ? ` · target ${formatDuration(story.target_duration_sec)}`
                : ''}
              .
            </small>
          </div>
        </aside>
      </div>
    </div>
  )
}
