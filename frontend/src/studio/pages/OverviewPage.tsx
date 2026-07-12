import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  api,
  type OrchestrationRunDetail,
  type StoryboardProposal,
} from '../../api/client'
import { useStudio } from '../StudioState'
import { countScenes, countShots, formatDuration } from '../utils'

const PIPELINE: Array<{ label: string; view: 'story' | 'characters' | 'storyboard' | 'images' | 'overview' | 'settings'; getValue: (ctx: OverviewCounts) => number }> = [
  { label: 'Story Intake', view: 'story', getValue: (c) => (c.hasStory ? 100 : 20) },
  { label: 'Character Bible', view: 'characters', getValue: (c) => c.characterPct },
  { label: 'Story Structure', view: 'story', getValue: (c) => (c.chapters > 0 ? 100 : 0) },
  { label: 'Shot Planning', view: 'storyboard', getValue: (c) => c.shotPct },
  { label: 'Starting Images', view: 'images', getValue: (c) => c.imagePct },
  { label: 'Review', view: 'overview', getValue: (c) => c.reviewPct },
  { label: 'Approval', view: 'settings', getValue: (c) => (c.approved ? 100 : 0) },
]

type OverviewCounts = {
  hasStory: boolean
  chapters: number
  characterPct: number
  shotPct: number
  imagePct: number
  reviewPct: number
  approved: boolean
}

export function OverviewPage() {
  const { data, readiness, approvePlan, busy, backendStatus, navigate } = useStudio()
  const [approver, setApprover] = useState('Producer')
  const [currentRun, setCurrentRun] = useState<OrchestrationRunDetail | null>(null)
  const [currentProposal, setCurrentProposal] = useState<StoryboardProposal | null>(null)
  const [planningError, setPlanningError] = useState<string | null>(null)

  const loadPlanningSummary = useCallback(async () => {
    if (!data) return
    setPlanningError(null)
    try {
      const [runs, proposals] = await Promise.all([
        api.listOrchestrationRuns(data.story.id),
        api.listStoryProposals(data.story.id),
      ])
      setCurrentRun(runs[0] ? await api.getOrchestrationRun(runs[0].id) : null)
      setCurrentProposal(proposals[0] ?? null)
    } catch (error) {
      setPlanningError(
        backendStatus === 'ok'
          ? 'Planning summary API is unavailable for this local demo story. Backend health is OK.'
          : error instanceof Error
            ? error.message
            : 'Planning status is unavailable.',
      )
    }
  }, [backendStatus, data])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadPlanningSummary(), 0)
    return () => window.clearTimeout(timer)
  }, [loadPlanningSummary])

  const counts = useMemo(() => {
    if (!data) return null
    const shots = countShots(data.chapters)
    const scenes = countScenes(data.chapters)
    const approvedShots = data.chapters.reduce(
      (n, chapter) =>
        n +
        chapter.scenes.reduce(
          (s, scene) => s + scene.shots.filter((shot) => shot.approval_state === 'approved').length,
          0,
        ),
      0,
    )
    const heroApproved = data.characters.filter((c) => c.approval_state === 'approved').length
    const voices = data.voices.length
    const imageReady = data.chapters.reduce(
      (n, chapter) =>
        n +
        chapter.scenes.reduce(
          (s, scene) => s + scene.shots.filter((shot) => Boolean(shot.starting_image_asset_id)).length,
          0,
        ),
      0,
    )

    return {
      chapters: data.chapters.length,
      scenes,
      shots,
      characters: data.characters.length,
      voices,
      approvedShots,
      heroApproved,
      imageReady,
      voiceTarget: Math.max(shots, 1),
      imageTarget: Math.max(shots, 1),
    }
  }, [data])

  if (!data || !counts) return null

  const planned = readiness?.planned_duration_sec ?? 0
  const target = readiness?.target_duration_sec ?? data.story.target_duration_sec
  const blocking = readiness?.reasons.filter((reason) => reason.blocking) ?? []
  const canApprove = Boolean(readiness?.ready) && !busy
  const readinessPct = readiness?.ready
    ? 100
    : Math.max(8, Math.min(92, 100 - blocking.length * 12))

  const pipelineCtx: OverviewCounts = {
    hasStory: Boolean(data.story.base_story || data.story.title),
    chapters: counts.chapters,
    characterPct: counts.characters ? Math.round((counts.heroApproved / counts.characters) * 100) : 0,
    shotPct: counts.shots ? Math.round((counts.approvedShots / counts.shots) * 100) : 0,
    imagePct: counts.shots ? Math.round((counts.imageReady / counts.shots) * 100) : 0,
    reviewPct: readinessPct,
    approved: data.story.approval_state === 'approved',
  }

  const metricCards: Array<{
    label: string
    value: string | number
    note: string
    status: string
    onClick: () => void
  }> = [
    {
      label: 'Chapters',
      value: counts.chapters,
      note: 'Duration-linked structure',
      status: counts.chapters ? 'Ready' : 'Open',
      onClick: () => navigate('story'),
    },
    {
      label: 'Scenes',
      value: counts.scenes,
      note: 'All duration-linked',
      status: counts.scenes ? 'Ready' : 'Open',
      onClick: () => navigate('story'),
    },
    {
      label: 'Shots',
      value: counts.shots,
      note: `${counts.approvedShots} approved`,
      status: counts.approvedShots === counts.shots && counts.shots > 0 ? 'Ready' : 'Review',
      onClick: () => navigate('storyboard'),
    },
    {
      label: 'Characters',
      value: counts.characters,
      note: `${counts.heroApproved} hero images approved`,
      status: counts.heroApproved === counts.characters && counts.characters > 0 ? 'Ready' : 'Review',
      onClick: () => navigate('characters'),
    },
    {
      label: 'Voice coverage',
      value: `${counts.voices}/${counts.voiceTarget}`,
      note: `${Math.max(0, counts.voiceTarget - counts.voices)} assignments open`,
      status: counts.voices >= counts.voiceTarget ? 'Ready' : 'Review',
      onClick: () => navigate('voices'),
    },
    {
      label: 'Starting images',
      value: `${counts.imageReady}/${counts.imageTarget}`,
      note: `${Math.max(0, counts.imageTarget - counts.imageReady)} require approval`,
      status: counts.imageReady >= counts.imageTarget ? 'Ready' : 'Review',
      onClick: () => navigate('images'),
    },
    {
      label: 'Readiness',
      value: readiness ? (readiness.ready ? 'Ready' : 'Review') : 'Unknown',
      note: `${blocking.length} blocking gates`,
      status: readiness?.ready ? 'Ready' : 'Blocked',
      onClick: () => navigate('overview'),
    },
    {
      label: 'Model / workflow gaps',
      value: blocking.filter((r) => /model|workflow|checkpoint/i.test(r.code + r.message)).length || '—',
      note: 'Factual server gates only',
      status: blocking.length ? 'Blocked' : 'Ready',
      onClick: () => navigate('routing'),
    },
  ]

  const currentStep =
    currentRun?.steps.find((step) => step.status === 'running') ??
    currentRun?.steps.find((step) => step.sequence_index === currentRun.current_step) ??
    currentRun?.steps.at(-1)
  const completedSteps = currentRun?.steps.filter((step) => step.status === 'completed').length ?? 0

  return (
    <>
      <div className="overview-readiness" aria-label="Storyboard readiness">
        <div>
          <span className="eyebrow">Storyboard readiness</span>
          <strong>{readinessPct}%</strong>
        </div>
        <div className="progress-bar" aria-hidden="true">
          <span style={{ width: `${readinessPct}%` }} />
        </div>
        <small>
          {blocking.length
            ? `${blocking.length} required gates remain`
            : readiness?.ready
              ? 'All required gates passed'
              : 'Awaiting server readiness'}
        </small>
      </div>

      <div className="overview-strip" aria-label="Runtime alignment">
        <div>
          <span>Target runtime</span>
          <b>{formatDuration(target)}</b>
        </div>
        <span className="overview-arrow" aria-hidden="true">
          →
        </span>
        <div>
          <span>Planned runtime</span>
          <b>{formatDuration(planned)}</b>
        </div>
        <div className="runtime-match">
          <span>{Math.abs((planned || 0) - (target || 0)) <= 1 ? 'Runtime reconciled' : 'Duration drift'}</span>
        </div>
        <div className="overview-actions">
          <button type="button" className="secondary-button touch-target" onClick={() => navigate('storyboard')}>
            Continue review
          </button>
          <button
            type="button"
            className="primary-button touch-target"
            disabled={!canApprove || !approver.trim()}
            title={
              readiness?.ready
                ? 'Approve production plan on the server'
                : blocking.length
                  ? `Blocked by ${blocking.length} readiness gate(s)`
                  : 'Server has not marked this plan ready'
            }
            onClick={() => void approvePlan(approver.trim())}
          >
            Approve production plan
          </button>
          <button type="button" className="ghost-button touch-target" onClick={() => navigate('settings')}>
            {blocking.length ? `View ${blocking.length} blockers` : 'All gates passed'}
          </button>
        </div>
      </div>

      <div className="metric-grid eight" aria-label="Planning metrics">
        {metricCards.map((card) => (
          <button key={card.label} type="button" className="metric-card" onClick={card.onClick}>
            <span>{card.label}</span>
            <strong>{card.value}</strong>
            <small>{card.note}</small>
            <span className={`truth-pill ${card.status.toLowerCase()}`}>{card.status}</span>
          </button>
        ))}
      </div>

      <section className="panel" aria-labelledby="pipeline-title">
        <div className="panel-title">
          <div>
            <h2 id="pipeline-title">Production-plan pipeline</h2>
            <p>Phase A stops at an approved, editable plan—before rendering.</p>
          </div>
        </div>
        <div className="pipeline">
          {PIPELINE.map((step, index) => {
            const value = step.getValue(pipelineCtx)
            return (
              <button key={step.label} type="button" onClick={() => navigate(step.view)}>
                <span className="pipeline-node" data-complete={value === 100}>
                  {value === 100 ? '✓' : index + 1}
                </span>
                <b>{step.label}</b>
                <small>{value}%</small>
                <div className="progress-bar" aria-hidden="true">
                  <span style={{ width: `${value}%` }} />
                </div>
              </button>
            )
          })}
        </div>
      </section>

      <div className="overview-columns">
        <div className="panel">
          <div className="panel-title">
            <div>
              <h2>Backend readiness gates</h2>
              <p>
                Gate truth is returned by <span className="mono">/storyboard/stories/:id/readiness</span>.
              </p>
            </div>
            <span className={`truth-pill ${readiness?.ready ? 'verified' : 'unknown'}`}>
              {readiness ? (readiness.ready ? 'Server: ready' : 'Server: not ready') : 'Server: unknown'}
            </span>
          </div>
          <ul className="gate-list">
            {readiness?.reasons?.length ? (
              readiness.reasons.map((reason) => (
                <li key={`${reason.code}-${reason.entity_id ?? 'none'}-${reason.message}`}>
                  <b>{reason.code}</b>
                  <span>{reason.message}</span>
                  <span className={reason.blocking ? 'gate-blocking' : 'gate-info'}>
                    {reason.blocking ? 'Blocking' : 'Info'}
                  </span>
                </li>
              ))
            ) : readiness?.ready ? (
              <li>
                <b>ready</b>
                <span>All current backend readiness checks pass.</span>
                <span className="gate-info">Pass</span>
              </li>
            ) : (
              <li>
                <b>pending</b>
                <span>Readiness reasons have not been returned yet.</span>
                <span className="gate-blocking">Unknown</span>
              </li>
            )}
          </ul>
          <div className="stack-form" style={{ maxWidth: 420 }}>
            <label>
              Approved by
              <input
                value={approver}
                onChange={(event) => setApprover(event.target.value)}
                disabled={busy}
                autoComplete="name"
              />
            </label>
          </div>
        </div>

        <div className="stack">
          <section className="panel">
            <div className="panel-title">
              <div>
                <h2>Unresolved issues</h2>
                <p>Highest-impact items first.</p>
              </div>
            </div>
            <div className="issue-list">
              {blocking.length ? (
                blocking.slice(0, 5).map((reason, index) => (
                  <button
                    key={`${reason.code}-${index}`}
                    type="button"
                    onClick={() => navigate(index % 2 === 0 ? 'storyboard' : 'routing')}
                  >
                    <span className="severity red">P{index === 0 ? '0' : '1'}</span>
                    <span>
                      <b>{reason.code}</b>
                      <small>{reason.message}</small>
                    </span>
                    <span aria-hidden="true">→</span>
                  </button>
                ))
              ) : (
                <p className="form-hint">No blocking readiness issues returned by the server.</p>
              )}
            </div>
          </section>

          <section className="panel" aria-labelledby="overview-planning-status">
            <div className="panel-title">
              <div>
                <h2 id="overview-planning-status">Orchestrator run</h2>
                <p>Latest structured proposal / planning run.</p>
              </div>
              <button type="button" className="primary-button touch-target" onClick={() => navigate('story')}>
                {currentProposal ? 'Review proposal' : currentRun ? 'Open run details' : 'Start planning run'}
              </button>
            </div>
            {planningError ? <p className="notice warning">{planningError}</p> : null}
            <ul className="kv-list">
              <li>
                <span>Current run</span>
                <strong>{currentRun?.status ?? 'No run'}</strong>
              </li>
              <li>
                <span>Current step</span>
                <strong>{currentStep?.task_type ?? '—'}</strong>
              </li>
              <li>
                <span>Progress</span>
                <strong>{currentRun ? `${completedSteps}/${currentRun.steps.length} steps` : '—'}</strong>
              </li>
              <li>
                <span>Latest proposal</span>
                <strong>{currentProposal?.status ?? 'None'}</strong>
              </li>
            </ul>
            {currentRun?.failure_message ? <p className="notice error">{currentRun.failure_message}</p> : null}
          </section>

          <section className="panel">
            <div className="panel-title">
              <div>
                <h2>Safety posture</h2>
                <p>Approval creates an immutable storyboard version only.</p>
              </div>
            </div>
            <ul className="feature-list">
              <li>No Timeline Slot</li>
              <li>No Clip Iteration</li>
              <li>No queue job</li>
              <li>No ComfyUI submission</li>
              <li>No FFmpeg job</li>
              <li>No voice clone / TTS batch</li>
            </ul>
          </section>
        </div>
      </div>
    </>
  )
}
