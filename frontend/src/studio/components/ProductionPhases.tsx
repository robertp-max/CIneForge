import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'

import {
  api,
  type PhaseOnePackage,
  type PhaseVersionDetail,
  type PhaseVersionSummary,
  type ProductionPipeline,
  type StoryboardAggregate,
} from '../../api/client'
import type { PageId } from '../../components/AppShell'
import { ErrorNotice } from '../../components/Cards'
import { ProductionPhasePreview } from './ProductionPhasePreview'
import { LoadingState } from './StateBlocks'
import {
  snapshotMetricsFromWorkspace,
  workspaceFromAggregate,
  workspaceFromHistoricalDetail,
} from '../snapshotWorkspace'
import { formatDuration } from '../utils'

type EditablePhaseOne = Pick<
  PhaseOnePackage,
  | 'project_title'
  | 'logline'
  | 'short_synopsis'
  | 'detailed_treatment'
  | 'complete_script'
  | 'narration_script'
  | 'dialogue_script'
  | 'non_dialogue_action'
  | 'silent_visual_beats'
  | 'emotional_progression'
  | 'dramatic_escalation'
  | 'source_fidelity_notes'
  | 'creative_assumptions'
>

function isPhaseOnePackage(value: unknown): value is PhaseOnePackage {
  return Boolean(
    value
    && typeof value === 'object'
    && (value as { schema_name?: string }).schema_name === 'cineforge.phase_one_script_package',
  )
}

function stateLabel(value: string) {
  return value.replaceAll('_', ' ')
}

function listText(items: string[]) {
  return items.join('\n')
}

function textList(value: string) {
  return value.split('\n').map((item) => item.trim()).filter(Boolean)
}

function downloadText(filename: string, content: string) {
  const url = URL.createObjectURL(new Blob([content], { type: 'application/json' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 0)
}

type ProductionPhasesProps = {
  storyId: string
  projectId?: string
  data?: StoryboardAggregate | null
  onNavigate?: (page: PageId) => void
}

export function ProductionPhases({
  storyId,
  projectId,
  data = null,
  onNavigate,
}: ProductionPhasesProps) {
  const [pipeline, setPipeline] = useState<ProductionPipeline | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [draft, setDraft] = useState<EditablePhaseOne | null>(null)
  const [selectedPhaseNumber, setSelectedPhaseNumber] = useState(1)
  const [versionsByPhase, setVersionsByPhase] = useState<Record<number, PhaseVersionSummary[]>>({})
  const [selectedByPhase, setSelectedByPhase] = useState<Partial<Record<number, string>>>({})
  const [loadedDetail, setLoadedDetail] = useState<PhaseVersionDetail | null>(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [compare, setCompare] = useState(false)
  const [iterationLabel, setIterationLabel] = useState('')
  const [iterationNotes, setIterationNotes] = useState('')
  const [savingIteration, setSavingIteration] = useState(false)
  /** When the pipeline head is a non-package snapshot, hold the last script package from history. */
  const [packageFallback, setPackageFallback] = useState<PhaseOnePackage | null>(null)
  const phaseTabs = useRef<Array<HTMLButtonElement | null>>([])
  const scopeKey = `${projectId ?? 'project'}:${storyId}:${selectedPhaseNumber}`

  const loadPhaseHistory = useCallback(async (phaseNumber: number) => {
    setHistoryLoading(true)
    setHistoryError(null)
    try {
      const versions = await api.listPhaseVersions(storyId, phaseNumber)
      setVersionsByPhase((current) => ({ ...current, [phaseNumber]: versions }))
      return versions
    } catch (caught) {
      setHistoryError(
        caught instanceof Error ? caught.message : 'Unable to load retained phase history.',
      )
      return []
    } finally {
      setHistoryLoading(false)
    }
  }, [storyId])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const next = await api.getProductionPipeline(storyId)
      setPipeline(next)
      // Clear version selection when story/project scope changes; keep phase number.
      // History rows are reloaded by the phase-history effect once pipeline is set —
      // do not wipe-and-forget them here or Phase 1 can keep only "Current draft".
      setSelectedByPhase({})
      setLoadedDetail(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load the production phases.')
    } finally {
      setLoading(false)
    }
  }, [storyId])

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0)
    return () => window.clearTimeout(timer)
  }, [load])

  useEffect(() => {
    let active = true
    // Async history list load when the project/story/phase scope changes.
    void (async () => {
      if (!pipeline) return
      setHistoryLoading(true)
      setHistoryError(null)
      try {
        const versions = await api.listPhaseVersions(storyId, selectedPhaseNumber)
        if (!active) return
        setVersionsByPhase((current) => ({ ...current, [selectedPhaseNumber]: versions }))
      } catch (caught) {
        if (!active) return
        setHistoryError(
          caught instanceof Error ? caught.message : 'Unable to load retained phase history.',
        )
      } finally {
        if (active) setHistoryLoading(false)
      }
    })()
    return () => {
      active = false
    }
  }, [pipeline, selectedPhaseNumber, scopeKey, storyId])

  const phaseHistory = versionsByPhase[selectedPhaseNumber] ?? []
  const selectedIterationId = selectedByPhase[selectedPhaseNumber] ?? ''
  const selectedIteration = phaseHistory.find((item) => item.id === selectedIterationId) ?? null

  useEffect(() => {
    let active = true
    const loadDetail = async () => {
      if (!selectedIterationId) {
        if (!active) return
        setLoadedDetail(null)
        setHistoryError(null)
        return
      }
      if (!active) return
      setHistoryLoading(true)
      setHistoryError(null)
      try {
        const detail = await api.getPhaseVersion(storyId, selectedPhaseNumber, selectedIterationId)
        if (!active) return
        // Reject stale responses from a different scope.
        if (
          detail.story_id !== storyId
          || detail.phase_number !== selectedPhaseNumber
          || (projectId && detail.project_id !== projectId)
        ) {
          setHistoryError('The retained iteration belongs to a different project, story, or phase.')
          setLoadedDetail(null)
          return
        }
        setLoadedDetail(detail)
      } catch (caught) {
        if (!active) return
        setLoadedDetail(null)
        setHistoryError(
          caught instanceof Error ? caught.message : 'The retained iteration failed integrity checks.',
        )
      } finally {
        if (active) setHistoryLoading(false)
      }
    }
    void loadDetail()
    return () => {
      active = false
    }
  }, [projectId, selectedIterationId, selectedPhaseNumber, storyId])

  useEffect(() => {
    const handleShortcut = (event: globalThis.KeyboardEvent) => {
      if (event.defaultPrevented || document.querySelector('[role="dialog"]')) return
      if (!historyOpen && !createOpen && (event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === 's') {
        event.preventDefault()
        setCreateOpen(true)
      }
    }
    window.addEventListener('keydown', handleShortcut)
    return () => window.removeEventListener('keydown', handleShortcut)
  }, [createOpen, historyOpen])

  const phaseOne = pipeline?.phases[0] ?? null
  const historical = Boolean(selectedIterationId && loadedDetail && !historyError)
  const historicalWorkspaceResult = useMemo(() => {
    if (!historical || !loadedDetail) return null
    return workspaceFromHistoricalDetail(loadedDetail, {
      storyId,
      projectId,
      phaseNumber: selectedPhaseNumber,
    })
  }, [historical, loadedDetail, projectId, selectedPhaseNumber, storyId])
  const historicalWorkspace = historicalWorkspaceResult?.workspace ?? null
  const historicalIsolationError = historicalWorkspaceResult?.error ?? null
  const incompleteReason = historicalIsolationError
    || (historicalWorkspace && !historicalWorkspace.completeness.complete
      ? historicalWorkspace.completeness.reason
      : null)
  const currentWorkspace = useMemo(() => {
    if (!data) return null
    return workspaceFromAggregate(data, selectedPhaseNumber)
  }, [data, selectedPhaseNumber])
  const packageData = useMemo(() => {
    if (historical && selectedPhaseNumber === 1) {
      // Prefer phase-one script package when present; never fall back to live draft.
      const output = loadedDetail?.output_json
      if (isPhaseOnePackage(output)) return output
      return null
    }
    if (historical) return null
    // Prefer latest if it is a script package; otherwise use history fallback.
    const latest = phaseOne?.latest_version?.output_json
    if (isPhaseOnePackage(latest)) return latest
    // Baselines / older manual retains may sit on the pipeline head while a prior
    // generated or revised script package remains in SQLite history.
    return packageFallback
  }, [historical, loadedDetail, packageFallback, phaseOne, selectedPhaseNumber])

  useEffect(() => {
    let active = true
    if (historical || selectedPhaseNumber !== 1) {
      setPackageFallback(null)
      return () => {
        active = false
      }
    }
    const latest = phaseOne?.latest_version?.output_json
    if (isPhaseOnePackage(latest)) {
      setPackageFallback(null)
      return () => {
        active = false
      }
    }
    const history = versionsByPhase[1] ?? []
    // Prefer generated/revision rows (package sources); also accept completed manual
    // retains that may carry a preserved package after the backend retain fix.
    const candidates = [...history]
      .reverse()
      .filter((item) => item.source === 'generated' || item.source === 'revision' || item.completed)
    const candidate = candidates[0]
    if (!candidate) {
      setPackageFallback(null)
      return () => {
        active = false
      }
    }
    void api.getPhaseVersion(storyId, 1, candidate.id).then((detail) => {
      if (!active) return
      const output = detail.output_json
      setPackageFallback(isPhaseOnePackage(output) ? output : null)
    }).catch(() => {
      if (active) setPackageFallback(null)
    })
    return () => {
      active = false
    }
  }, [historical, phaseOne?.latest_version?.output_json, selectedPhaseNumber, storyId, versionsByPhase])
  const qa = (!historical ? phaseOne?.latest_qa_report?.report_json : null) ?? null
  const selectedPhase = pipeline?.phases.find((phase) => phase.phase_number === selectedPhaseNumber) ?? null
  const displayPhase = selectedPhase && historical && loadedDetail
    ? {
        ...selectedPhase,
        latest_version: loadedDetail,
        current_version_number: loadedDetail.version_number,
      }
    : selectedPhase

  const selectPhase = (phaseNumber: number, focus = false) => {
    setSelectedPhaseNumber(phaseNumber)
    setCompare(false)
    setEditing(false)
    if (focus) window.requestAnimationFrame(() => phaseTabs.current[phaseNumber - 1]?.focus())
  }

  const handlePhaseKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    let nextIndex: number
    if (event.key === 'ArrowRight') nextIndex = (index + 1) % 7
    else if (event.key === 'ArrowLeft') nextIndex = (index + 6) % 7
    else if (event.key === 'Home') nextIndex = 0
    else if (event.key === 'End') nextIndex = 6
    else return
    event.preventDefault()
    selectPhase(nextIndex + 1, true)
  }

  const versionTimeline = [...phaseHistory.map((item) => item.id), '']
  const versionIndex = selectedIterationId
    ? Math.max(0, versionTimeline.indexOf(selectedIterationId))
    : versionTimeline.length - 1
  const moveVersion = (direction: -1 | 1) => {
    const next = Math.max(0, Math.min(versionTimeline.length - 1, versionIndex + direction))
    setSelectedByPhase((current) => ({
      ...current,
      [selectedPhaseNumber]: versionTimeline[next] || undefined,
    }))
    setCompare(false)
    setEditing(false)
  }

  const beginEdit = () => {
    if (!packageData || historical) return
    setDraft({
      project_title: packageData.project_title,
      logline: packageData.logline,
      short_synopsis: packageData.short_synopsis,
      detailed_treatment: packageData.detailed_treatment,
      complete_script: packageData.complete_script,
      narration_script: packageData.narration_script,
      dialogue_script: packageData.dialogue_script,
      non_dialogue_action: packageData.non_dialogue_action,
      silent_visual_beats: packageData.silent_visual_beats,
      emotional_progression: packageData.emotional_progression,
      dramatic_escalation: packageData.dramatic_escalation,
      source_fidelity_notes: packageData.source_fidelity_notes,
      creative_assumptions: packageData.creative_assumptions,
    })
    setNotice(null)
    setEditing(true)
  }

  const saveRevision = async () => {
    if (!draft || !phaseOne?.current_version_number || historical) return
    setSaving(true)
    setError(null)
    try {
      const result = await api.revisePhaseOne(storyId, {
        ...draft,
        expected_version_number: phaseOne.current_version_number,
        requested_by: 'CineForge UI reviewer',
      })
      setPipeline(result.pipeline)
      setNotice(result.completion_message)
      setEditing(false)
      setDraft(null)
      await loadPhaseHistory(1)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to save the Phase 1 revision.')
    } finally {
      setSaving(false)
    }
  }

  const saveIteration = async () => {
    const label = iterationLabel.trim()
    if (!label) {
      setHistoryError('Iteration label is required.')
      return
    }
    setSavingIteration(true)
    setHistoryError(null)
    try {
      const created = await api.createPhaseVersion(storyId, selectedPhaseNumber, {
        label,
        notes: iterationNotes,
        requested_by: 'CineForge UI reviewer',
      })
      setPipeline(created.pipeline)
      setVersionsByPhase((current) => ({
        ...current,
        [selectedPhaseNumber]: [
          ...(current[selectedPhaseNumber] ?? []).filter((item) => item.id !== created.version.id),
          {
            id: created.version.id,
            version_number: created.version.version_number,
            label: created.version.label ?? label,
            notes: created.version.notes ?? '',
            source: created.version.source ?? 'manual',
            lifecycle_state: created.version.lifecycle_state,
            completed: created.version.completed,
            snapshot_schema_version: created.version.snapshot_schema_version ?? 1,
            input_hash: created.version.input_hash,
            output_hash: created.version.output_hash,
            created_by: created.version.created_by,
            previous_version_id: created.version.previous_version_id,
            created_at: created.version.created_at,
            updated_at: created.version.updated_at,
          },
        ].sort((a, b) => a.version_number - b.version_number),
      }))
      setSelectedByPhase((current) => ({
        ...current,
        [selectedPhaseNumber]: created.version.id,
      }))
      setLoadedDetail(created.version)
      setIterationLabel('')
      setIterationNotes('')
      setCreateOpen(false)
      setNotice(`Phase ${selectedPhaseNumber} iteration v${created.version.version_number} retained in SQLite.`)
    } catch (caught) {
      setHistoryError(
        caught instanceof Error ? caught.message : 'Unable to retain the current draft iteration.',
      )
    } finally {
      setSavingIteration(false)
    }
  }

  const exportAll = async () => {
    try {
      const exported = await api.exportPhaseHistory(storyId)
      downloadText(
        `story-${storyId}-phase-history.cineforge.json`,
        JSON.stringify(exported, null, 2),
      )
      setNotice(
        `Exported ${exported.integrity.iteration_count} verified iterations (integrity.verified=${exported.integrity.verified}).`,
      )
    } catch (caught) {
      setHistoryError(
        caught instanceof Error ? caught.message : 'Complete history export failed integrity checks.',
      )
    }
  }

  const exportSelected = () => {
    if (!selectedIteration || !loadedDetail) return
    downloadText(
      `story-${storyId}-phase-${selectedPhaseNumber}-v${selectedIteration.version_number}.json`,
      JSON.stringify(
        {
          schema: 'cineforge.phase-iteration',
          version: 1,
          iteration: selectedIteration,
          detail: loadedDetail,
        },
        null,
        2,
      ),
    )
  }

  if (loading) return <LoadingState title="Loading the seven-phase production contract…" />
  if (!pipeline) return error ? <ErrorNotice message={error} /> : null

  const currentSnapshotMetrics = snapshotMetricsFromWorkspace(currentWorkspace)
  const historicalMetrics = snapshotMetricsFromWorkspace(
    incompleteReason ? null : historicalWorkspace,
  )

  return (
    <section className="production-contract" aria-labelledby="production-contract-title">
      <div className="production-contract-heading">
        <div>
          <span className="eyebrow">EXACT SEVEN-PHASE PRODUCTION</span>
          <h2 id="production-contract-title">From one prompt to a controlled film production</h2>
          <p>
            All seven UI workspaces are available for review. Iteration history is stored in local SQLite
            via the production API—not browser IndexedDB. Design navigation never launches media generation or rendering.
          </p>
        </div>
        <span className="phase-count-pill">7 complete workspaces</span>
      </div>

      <div className="production-phase-rail" role="tablist" aria-label="Seven production phases">
        {pipeline.phases.map((phase, index) => {
          const count = phase.version_count
            ?? versionsByPhase[phase.phase_number]?.length
            ?? (phase.latest_version ? 1 : 0)
          return (
            <button
              key={phase.id}
              ref={(node) => { phaseTabs.current[index] = node }}
              id={`production-phase-tab-${phase.phase_number}`}
              type="button"
              role="tab"
              aria-label={`${phase.phase_number}. ${phase.name}. ${count} retained iteration${count === 1 ? '' : 's'}.`}
              aria-selected={selectedPhaseNumber === phase.phase_number}
              aria-controls={`production-phase-panel-${phase.phase_number}`}
              tabIndex={selectedPhaseNumber === phase.phase_number ? 0 : -1}
              className={selectedPhaseNumber === phase.phase_number ? 'current' : ''}
              onClick={() => selectPhase(phase.phase_number)}
              onKeyDown={(event) => handlePhaseKeyDown(event, index)}
            >
              <span>{phase.lifecycle_state === 'ready_for_review' ? '✓' : phase.phase_number}</span>
              <div>
                <b>{phase.phase_number}. {phase.name}</b>
                <small>{phase.phase_number === 1 ? stateLabel(phase.lifecycle_state) : 'Design available'}</small>
              </div>
              <em className="phase-iteration-badge" aria-hidden="true" title={`${count} retained iterations`}>{count}</em>
            </button>
          )
        })}
      </div>

      <div className={`phase-iteration-bar${historical ? ' viewing-history' : ''}`} aria-label={`Phase ${selectedPhaseNumber} iteration history`}>
        <div className="phase-version-nav">
          <button type="button" onClick={() => moveVersion(-1)} disabled={versionIndex === 0} aria-label="Previous iteration">‹</button>
          <label>
            <span>PHASE {selectedPhaseNumber} ITERATION</span>
            <select
              value={selectedIterationId}
              onChange={(event) => {
                setSelectedByPhase((current) => ({
                  ...current,
                  [selectedPhaseNumber]: event.target.value || undefined,
                }))
                setCompare(false)
                setEditing(false)
              }}
            >
              <option value="">Current draft</option>
              {phaseHistory.map((iteration) => (
                <option key={iteration.id} value={iteration.id}>
                  v{iteration.version_number} · {iteration.label}
                </option>
              ))}
            </select>
          </label>
          <button type="button" onClick={() => moveVersion(1)} disabled={versionIndex === versionTimeline.length - 1} aria-label="Next iteration">›</button>
        </div>
        <div className="phase-version-status">
          <span>{versionIndex + 1} of {versionTimeline.length}</span>
          <b>
            {historyLoading
              ? 'Loading retained history…'
              : selectedIteration
                ? `Viewing v${selectedIteration.version_number} · ${selectedIteration.label}`
                : 'Current working draft'}
          </b>
          <small>
            {selectedIteration
              ? `${new Date(selectedIteration.created_at).toLocaleString()} · immutable SQLite snapshot · read-only`
              : `${phaseHistory.length} retained iteration${phaseHistory.length === 1 ? '' : 's'} · edits stay in the current draft`}
          </small>
        </div>
        <div className="phase-version-actions">
          <button type="button" onClick={() => setHistoryOpen(true)} aria-expanded={historyOpen}>History</button>
          {selectedIteration ? (
            <button type="button" aria-pressed={compare} className={compare ? 'active' : ''} onClick={() => setCompare((value) => !value)}>
              Compare
            </button>
          ) : null}
          <button type="button" className="primary" onClick={() => setCreateOpen(true)}>
            {selectedIteration ? 'Retain current' : 'New iteration'}
          </button>
        </div>
      </div>

      {error ? <ErrorNotice message={error} /> : null}
      {historyError ? <div className="phase-history-error" role="alert"><b>History error</b><p>{historyError}</p></div> : null}

      {historical && selectedIteration ? (
        <div className="phase-history-banner" role="status">
          <div>
            <b>Read-only retained iteration</b>
            <p>
              You are reviewing Phase {selectedPhaseNumber} v{selectedIteration.version_number}.
              This SQLite snapshot cannot be overwritten. Editor links open the current working draft only.
              Historical workspaces never substitute live aggregate data.
            </p>
            {selectedIteration.notes ? <small>{selectedIteration.notes}</small> : null}
          </div>
          <button
            type="button"
            onClick={() => setSelectedByPhase((current) => ({ ...current, [selectedPhaseNumber]: undefined }))}
          >
            Return to current
          </button>
        </div>
      ) : null}

      {compare && historical && selectedIteration ? (
        <section className="phase-comparison" aria-label="Iteration summary metric comparison">
          <header>
            <div>
              <span>SUMMARY METRICS</span>
              <b>Phase {selectedPhaseNumber} · v{selectedIteration.version_number} versus current draft</b>
            </div>
            <small>Counts never claim rendered production output.</small>
          </header>
          <div>
            {historicalMetrics.map((metric, index) => {
              const currentValue = currentSnapshotMetrics[index]?.value ?? 0
              const delta = currentValue - metric.value
              return (
                <article key={metric.label} className={delta ? 'changed' : 'same'}>
                  <span>{metric.label}</span>
                  <div>
                    <small>v{selectedIteration.version_number}</small>
                    <b>{metric.value}</b>
                    <i>→</i>
                    <small>Current</small>
                    <strong>{currentValue}</strong>
                  </div>
                  <em>{delta === 0 ? 'Same count' : `${delta > 0 ? '+' : ''}${delta}`}</em>
                </article>
              )
            })}
          </div>
        </section>
      ) : null}

      <span className="sr-only" aria-live="polite">
        {selectedIteration
          ? `Viewing phase ${selectedPhaseNumber}, iteration ${selectedIteration.version_number}`
          : `Viewing current phase ${selectedPhaseNumber} draft`}
      </span>

      <div
        id={`production-phase-panel-${selectedPhaseNumber}`}
        className="production-phase-panel"
        role="tabpanel"
        aria-labelledby={`production-phase-tab-${selectedPhaseNumber}`}
        tabIndex={0}
      >
        {historyLoading && selectedIterationId ? (
          <LoadingState title="Loading retained iteration…" />
        ) : selectedPhaseNumber === 1 ? (
          <>
            {pipeline.completion_message || notice ? (
              <div className="phase-one-complete-message" role="status">
                <span>✓</span>
                <div>
                  <b>{notice || pipeline.completion_message}</b>
                  <p>
                    Version {phaseOne?.current_version_number ?? 1} is retained in SQLite and remains unapproved until human review.
                  </p>
                </div>
              </div>
            ) : null}

            {historical && incompleteReason ? (
              <div className="phase-history-error phase-legacy-incomplete" role="alert">
                <div>
                  <b>Legacy snapshot is incomplete</b>
                  <p>{incompleteReason} The current draft was not substituted.</p>
                </div>
              </div>
            ) : !packageData && historical ? (
              <div className="phase-empty">
                <span aria-hidden="true">＋</span>
                <div>
                  <b>This retained snapshot has no Phase 1 script package</b>
                  <p>
                    Phase 1 baselines store narrative planning state rather than a generated script package.
                    The current draft was not substituted. Return to current draft to edit live records.
                  </p>
                </div>
              </div>
            ) : !packageData ? (
              <div className="phase-empty">
                <span aria-hidden="true">＋</span>
                <div>
                  <b>Phase 1 has not started</b>
                  <p>Add an original creative prompt and target duration to create the first script package.</p>
                </div>
              </div>
            ) : (
              <>
                <div className="phase-metrics six" aria-label="Phase 1 script metrics">
                  <article className="phase-metric"><span>Script words</span><strong>{packageData.script_word_count.toLocaleString()}</strong></article>
                  <article className="phase-metric"><span>Narration</span><strong>{formatDuration(packageData.duration_analysis.narration_duration_sec)}</strong></article>
                  <article className="phase-metric"><span>Dialogue</span><strong>{formatDuration(packageData.duration_analysis.dialogue_duration_sec)}</strong></article>
                  <article className="phase-metric"><span>Visual / silence</span><strong>{formatDuration(packageData.duration_analysis.planned_silence_visual_duration_sec)}</strong></article>
                  <article className="phase-metric"><span>Estimated total</span><strong>{formatDuration(packageData.duration_analysis.estimated_total_duration_sec)}</strong></article>
                  <article className="phase-metric">
                    <span>QA</span>
                    <strong className={qa?.passed ? 'qa-pass' : 'qa-fail'}>
                      {historical ? 'Historical' : qa?.passed ? 'Passed' : qa ? 'Needs revision' : '—'}
                    </strong>
                  </article>
                </div>

                <div className="panel phase-one-review-panel phase-workspace">
                  <div className="panel-title">
                    <div>
                      <span className="eyebrow">
                        PHASE 1 · VERSION {historical ? selectedIteration?.version_number : phaseOne?.current_version_number}
                      </span>
                      <h2>Complete script package</h2>
                      <p>
                        {historical
                          ? 'Historical package is read-only. Return to current draft to edit.'
                          : 'Generated text is editable. Saving creates a new immutable version and reruns Phase 1 QA.'}
                      </p>
                    </div>
                    {!editing && !historical ? (
                      <button type="button" className="secondary-button" onClick={beginEdit}>Edit script package</button>
                    ) : null}
                  </div>

                  {editing && draft && !historical ? (
                    <div className="phase-one-editor">
                      <label>Project title<input value={draft.project_title} onChange={(event) => setDraft({ ...draft, project_title: event.target.value })} /></label>
                      <label>Logline<textarea value={draft.logline} onChange={(event) => setDraft({ ...draft, logline: event.target.value })} /></label>
                      <label>Short synopsis<textarea value={draft.short_synopsis} onChange={(event) => setDraft({ ...draft, short_synopsis: event.target.value })} /></label>
                      <label>Detailed treatment<textarea className="tall" value={draft.detailed_treatment} onChange={(event) => setDraft({ ...draft, detailed_treatment: event.target.value })} /></label>
                      <label>Complete script<textarea className="script" value={draft.complete_script} onChange={(event) => setDraft({ ...draft, complete_script: event.target.value })} /></label>
                      <label>Narration script<textarea className="tall" value={draft.narration_script} onChange={(event) => setDraft({ ...draft, narration_script: event.target.value })} /></label>
                      <label>Dialogue script<textarea value={draft.dialogue_script} onChange={(event) => setDraft({ ...draft, dialogue_script: event.target.value })} /></label>
                      <label>Non-dialogue action · one item per line<textarea value={listText(draft.non_dialogue_action)} onChange={(event) => setDraft({ ...draft, non_dialogue_action: textList(event.target.value) })} /></label>
                      <label>Silent visual beats · one item per line<textarea value={listText(draft.silent_visual_beats)} onChange={(event) => setDraft({ ...draft, silent_visual_beats: textList(event.target.value) })} /></label>
                      <label>Source-fidelity notes · one item per line<textarea value={listText(draft.source_fidelity_notes)} onChange={(event) => setDraft({ ...draft, source_fidelity_notes: textList(event.target.value) })} /></label>
                      <label>Creative assumptions · one item per line<textarea value={listText(draft.creative_assumptions)} onChange={(event) => setDraft({ ...draft, creative_assumptions: textList(event.target.value) })} /></label>
                      <div className="phase-one-editor-actions">
                        <button type="button" className="secondary-button" disabled={saving} onClick={() => { setEditing(false); setDraft(null) }}>Cancel</button>
                        <button type="button" className="primary-button" disabled={saving} onClick={() => void saveRevision()}>
                          {saving ? 'Saving version…' : 'Save as new version & rerun QA'}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="phase-one-document phase-document">
                      <section><span>WORKING TITLE</span><h3>{packageData.project_title}</h3></section>
                      <section><span>LOGLINE</span><p>{packageData.logline}</p></section>
                      <section><span>SHORT SYNOPSIS</span><p>{packageData.short_synopsis}</p></section>
                      <details open><summary>Detailed treatment</summary><div className="phase-one-prose">{packageData.detailed_treatment}</div></details>
                      <details open><summary>Complete expanded script</summary><pre>{packageData.complete_script}</pre></details>
                      <details>
                        <summary>Narration and dialogue</summary>
                        <div className="phase-one-speech">
                          <div><b>Narration</b><p>{packageData.narration_script}</p></div>
                          <div><b>Dialogue</b><p>{packageData.dialogue_script}</p></div>
                        </div>
                      </details>
                      <div className="split-2 phase-one-lists">
                        <section>
                          <span>EMOTIONAL PROGRESSION</span>
                          <ol>{packageData.emotional_progression.map((item) => <li key={item}>{item}</li>)}</ol>
                        </section>
                        <section>
                          <span>CREATIVE ASSUMPTIONS</span>
                          <ul>{packageData.creative_assumptions.map((item) => <li key={item}>{item}</li>)}</ul>
                        </section>
                      </div>
                    </div>
                  )}
                </div>

                {!historical ? (
                  <div className="split-2 phase-one-evidence">
                    <div className="panel">
                      <div className="panel-title">
                        <div>
                          <span className="eyebrow">PHASE 1 QA REPORT</span>
                          <h2>{qa?.passed ? 'All blocking checks passed' : 'Revision required'}</h2>
                          <p>QA completion does not approve the script.</p>
                        </div>
                        <span className={`truth-pill ${qa?.passed ? 'verified' : 'unknown'}`}>{qa?.passed ? 'PASS' : 'FAIL'}</span>
                      </div>
                      <ul className="phase-qa-checks">
                        {qa?.checks.map((check) => (
                          <li key={check.code} className={check.passed ? 'passed' : 'failed'}>
                            <span>{check.passed ? '✓' : '!'}</span>
                            <div><b>{check.label}</b><p>{check.detail}</p></div>
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div className="panel">
                      <div className="panel-title">
                        <div>
                          <span className="eyebrow">FAIL-CLOSED BOUNDARY</span>
                          <h2>Nothing downstream executed</h2>
                          <p>These values are persisted in the QA evidence, not inferred by the UI.</p>
                        </div>
                      </div>
                      <ul className="phase-boundary-list">
                        {Object.entries(qa?.phase_boundary ?? {}).map(([key, value]) => (
                          <li key={key}><span>{key.replaceAll('_', ' ')}</span><b>{value ? 'Yes' : 'No'}</b></li>
                        ))}
                      </ul>
                      {packageData.baseline_comparison ? (
                        <div className="baseline-result">
                          <span>TRANSFIGURATION BASELINE</span>
                          <b>{stateLabel(packageData.baseline_comparison.classification)}</b>
                          <p>{packageData.baseline_comparison.note}</p>
                          <small>
                            {packageData.baseline_comparison.missing_count} missing · {packageData.baseline_comparison.unsafe_count} unsafe · human review still required
                          </small>
                        </div>
                      ) : null}
                    </div>
                  </div>
                ) : null}
              </>
            )}
          </>
        ) : displayPhase ? (
          <ProductionPhasePreview
            phase={displayPhase}
            workspace={historical ? (incompleteReason ? null : historicalWorkspace) : currentWorkspace}
            historical={historical}
            incompleteReason={historical ? incompleteReason : null}
            onNavigate={onNavigate}
          />
        ) : null}
      </div>

      {createOpen ? (
        <div className="phase-modal-backdrop" role="presentation" onClick={() => !savingIteration && setCreateOpen(false)}>
          <div
            className="phase-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="retain-iteration-title"
            onClick={(event) => event.stopPropagation()}
          >
            <header>
              <h3 id="retain-iteration-title">Retain Phase {selectedPhaseNumber} iteration</h3>
              <button type="button" aria-label="Close" disabled={savingIteration} onClick={() => setCreateOpen(false)}>×</button>
            </header>
            <div className="phase-iteration-form">
              <p>
                This captures the complete <b>current draft</b> from SQLite-backed backend records—not the visible historical copy.
                Existing iterations are never changed.
              </p>
              <label>
                Iteration name
                <input
                  autoFocus
                  value={iterationLabel}
                  onChange={(event) => setIterationLabel(event.target.value)}
                  placeholder={`Iteration ${phaseHistory.length + 1} · e.g. Director review`}
                />
              </label>
              <label>
                Notes <small>optional</small>
                <textarea
                  value={iterationNotes}
                  onChange={(event) => setIterationNotes(event.target.value)}
                  placeholder="What changed, what should be reviewed, or why this milestone matters."
                />
              </label>
              <div className="phase-iteration-form-meta">
                <span><b>Phase</b>{selectedPhaseNumber}. {selectedPhase?.name}</span>
                <span><b>Storage</b>SQLite production_phase_versions</span>
                <span><b>Shortcut</b>Ctrl/⌘ + Shift + S</span>
              </div>
              <div className="modal-actions">
                <button type="button" className="secondary-button" disabled={savingIteration} onClick={() => setCreateOpen(false)}>Cancel</button>
                <button type="button" className="primary-button" disabled={savingIteration} onClick={() => void saveIteration()}>
                  {savingIteration ? 'Retaining…' : 'Retain current draft'}
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {historyOpen ? (
        <div className="phase-modal-backdrop" role="presentation" onClick={() => setHistoryOpen(false)}>
          <div
            className="phase-modal wide"
            role="dialog"
            aria-modal="true"
            aria-labelledby="history-drawer-title"
            onClick={(event) => event.stopPropagation()}
          >
            <header>
              <h3 id="history-drawer-title">Phase {selectedPhaseNumber} iteration history</h3>
              <button type="button" aria-label="Close" onClick={() => setHistoryOpen(false)}>×</button>
            </header>
            <div className="phase-history-drawer">
              <header>
                <div>
                  <span className="eyebrow">APPEND-ONLY SQLITE HISTORY</span>
                  <h4>{phaseHistory.length} retained iteration{phaseHistory.length === 1 ? '' : 's'}</h4>
                  <p>Browse, compare summary metrics, or export. Clearing browser site data does not delete these rows.</p>
                </div>
                <button type="button" className="secondary-button" onClick={() => void exportAll()}>Export all history</button>
              </header>
              <div className="phase-history-list">
                {phaseHistory.map((iteration) => (
                  <button
                    key={iteration.id}
                    type="button"
                    aria-current={selectedIterationId === iteration.id ? 'true' : undefined}
                    className={selectedIterationId === iteration.id ? 'active' : ''}
                    onClick={() => {
                      setSelectedByPhase((current) => ({
                        ...current,
                        [selectedPhaseNumber]: iteration.id,
                      }))
                      setHistoryOpen(false)
                      setCompare(false)
                    }}
                  >
                    <span>v{iteration.version_number}</span>
                    <div>
                      <b>{iteration.label}</b>
                      <p>{iteration.notes || 'No notes recorded for this iteration.'}</p>
                      <small>
                        {new Date(iteration.created_at).toLocaleString()} · {iteration.source === 'baseline' ? 'Initial baseline' : iteration.source}
                      </small>
                    </div>
                  </button>
                ))}
              </div>
              {selectedIteration && loadedDetail ? (
                <footer>
                  <div>
                    <b>Selected: v{selectedIteration.version_number} · {selectedIteration.label}</b>
                    <small>Output hash {selectedIteration.output_hash.slice(0, 12)}…</small>
                  </div>
                  <button type="button" className="secondary-button" onClick={exportSelected}>Download selected JSON</button>
                </footer>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  )
}
