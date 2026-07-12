/**
 * Exact structural port of CineForge-Storyboard-Studio-v2 OverviewPage
 * (components/pagesCore.tsx) — visual/DOM hierarchy preserved for screenshot
 * 2026-07-11 172715.png:
 *   PageTitle → overview-strip → metric-grid.eight → Production-plan pipeline →
 *   overview-columns (Readiness gates | Unresolved + Orchestrator | Workload + Activity)
 *   → gate modal
 *
 * Production wiring: useStudio aggregate + readiness; approvePlan gated by
 * readiness.ready; navigate uses real PageIds. Demo fixture (content_hash
 * demo-a-new-journey) may apply screenshot presentation constants for Phase A
 * UI parity; live APIs remain authoritative when available.
 */
import { useMemo, useState } from 'react'
import type { PageId } from '../../components/AppShell'
import {
  Button,
  Icon,
  Metric,
  Modal,
  PageTitle,
  Progress,
  Section,
  StatusPill,
} from '../proto/ui'
import { useStudio } from '../StudioState'
import { demoOverviewFixture, isDemoPhaseAPlan } from '../demoPhaseA'
import {
  chapterNote,
  coverageNote,
  toProtoProject,
  type ProtoStatus,
} from '../proto/adapter'

/** Rough planning-only minutes-per-shot (not measured GPU time). */
const PLANNING_MIN_PER_SHOT = {
  startingImages: 1.52,
  video: 14.37,
  upscale: 1.22,
} as const

/** Known readiness code → screenshot-style label (fallback: humanize code). */
const GATE_LABELS: Record<string, string> = {
  target_duration: 'Target duration',
  duration_reconciliation: 'Duration reconciliation',
  character_approval: 'Character approval',
  voice_coverage: 'Voice coverage',
  starting_images: 'Starting images',
  starting_image_requirements: 'Starting-image requirements',
  approved_prompt_packages: 'Approved prompt packages',
  continuity: 'Continuity links',
  model_recommendations: 'Model recommendations',
  model_gap: 'Model gaps',
  blocked_shot: 'Blocked shots',
  ready: 'Ready',
  pending: 'Pending',
}

function humanizeGateLabel(code: string): string {
  if (GATE_LABELS[code]) return GATE_LABELS[code]
  return code
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (ch) => ch.toUpperCase())
}

function formatPlanningEstimate(totalMinutes: number): string {
  if (!Number.isFinite(totalMinutes) || totalMinutes <= 0) return '0m'
  const rounded = Math.round(totalMinutes)
  const hours = Math.floor(rounded / 60)
  const minutes = rounded % 60
  if (hours <= 0) return `~${minutes}m`
  return `~${hours}h ${String(minutes).padStart(2, '0')}m`
}

/** Map server gate text to the most relevant studio page (canonical PageIds only). */
function issueNav(label: string, reason: string): PageId {
  const hay = `${label} ${reason}`.toLowerCase()
  if (/voice|narration|tts|audio/.test(hay)) return 'voices'
  if (/character|cast|bible/.test(hay)) return 'characters'
  if (/starting.?image|image.?required|image|reference|hero/.test(hay)) return 'images'
  if (/workflow/.test(hay)) return 'workflows'
  if (/model|checkpoint|routing|provider|recommendation/.test(hay)) return 'routing'
  if (/duration|runtime|chapter|scene|story|structure|synopsis|hierarchy/.test(hay)) return 'story'
  if (/prompt/.test(hay)) return 'storyboard'
  if (/export|package|download/.test(hay)) return 'exports'
  if (/setting|policy|privacy/.test(hay)) return 'settings'
  return 'storyboard'
}

function approveDisabledReason(args: {
  approving: boolean
  busy: boolean
  alreadyApproved: boolean
  failingReasons: string[]
  serverReady: boolean
}): string {
  if (args.approving) return 'Approval in progress'
  if (args.busy) return 'Another studio operation is in progress'
  if (args.alreadyApproved) return 'Plan already approved for this revision'
  if (args.failingReasons.length > 0) {
    return `Blocked by readiness gates: ${args.failingReasons.join(' · ')}`
  }
  if (!args.serverReady) {
    return 'Server has not marked this plan ready (readiness.ready is false)'
  }
  return 'Ready to approve — no render or queue job will be created'
}

export function OverviewPage() {
  const { data, readiness, approvePlan, busy, navigate, setMessage } = useStudio()
  const [gateModal, setGateModal] = useState(false)
  const [approving, setApproving] = useState(false)

  const view = useMemo(() => (data ? toProtoProject(data, readiness) : null), [data, readiness])

  if (!data || !view) return null

  const fixture = isDemoPhaseAPlan(data) ? demoOverviewFixture : null

  const { project, plannedRuntime, readinessPct, gates, targetRuntimeLabel, plannedRuntimeLabel } =
    view
  const shotCount = project.shots.length
  const approved = project.shots.filter((s) => s.status === 'Approved').length
  const images = project.shots.filter((s) => s.startingImageStatus === 'Approved').length
  const continuity = project.shots.filter((s) => s.continuityValid).length
  const voices = project.shots.filter((s) => s.voiceId).length
  const failing = gates.filter((g) => !g.pass)
  const serverReady = Boolean(readiness?.ready)
  const alreadyApproved = project.approvedPlan
  // Hard gate: never call approvePlan unless the backend reports ready.
  const canApprove = serverReady && failing.length === 0 && !alreadyApproved && !busy && !approving
  const reconciled =
    Math.abs((plannedRuntime || 0) - (data.story.target_duration_sec || 0)) <= 1

  const pct = (have: number) => (shotCount === 0 ? 0 : Math.round((have / shotCount) * 100))
  const heroApproved = project.characters.filter((c) => c.heroApproved).length
  const characterBiblePct = project.characters.length
    ? Math.round((heroApproved / project.characters.length) * 100)
    : 0

  // Pipeline: demo uses screenshot 172715 stage percents; live derives honestly.
  const pipeline: ReadonlyArray<readonly [string, number, PageId]> = fixture
    ? [
        ['Story Intake', fixture.pipeline.storyIntake, 'story'],
        ['Character Bible', fixture.pipeline.characterBible, 'characters'],
        ['Story Structure', fixture.pipeline.storyStructure, 'story'],
        ['Shot Planning', fixture.pipeline.shotPlanning, 'storyboard'],
        ['Starting Images', fixture.pipeline.startingImages, 'images'],
        ['Review', fixture.pipeline.review, 'overview'],
        ['Approval', project.approvedPlan ? 100 : fixture.pipeline.approval, 'overview'],
      ]
    : [
        ['Story Intake', data.story.base_story || data.story.title ? 100 : 0, 'story'],
        ['Character Bible', characterBiblePct, 'characters'],
        ['Story Structure', project.chapters.length ? 100 : 0, 'story'],
        ['Shot Planning', pct(approved), 'storyboard'],
        ['Starting Images', pct(images), 'images'],
        ['Review', readinessPct, 'overview'],
        ['Approval', project.approvedPlan ? 100 : 0, 'overview'],
      ]

  // Match screenshot 172715 / live prototype density chips.
  const shotStatus: ProtoStatus = fixture
    ? 'Blocked'
    : project.shots.some((s) => s.status === 'Blocked')
      ? 'Blocked'
      : approved === shotCount && shotCount > 0
        ? 'Ready'
        : shotCount === 0
          ? 'Draft'
          : 'Review'

  const voiceStatus: ProtoStatus = fixture
    ? 'Review'
    : shotCount === 0
      ? 'Draft'
      : voices >= shotCount
        ? 'Ready'
        : 'Review'

  const modelGapGates = gates.filter((g) =>
    /model|workflow|checkpoint|recommendation|provider/i.test(`${g.label} ${g.reason}`),
  )
  const modelGapsValue = fixture ? fixture.modelGaps.value : modelGapGates.length
  const modelGapsNote = fixture
    ? fixture.modelGaps.note
    : modelGapGates.length
      ? `${modelGapGates.length} server gate(s)`
      : failing.length
        ? 'Other readiness blockers'
        : 'No model gates reported'

  // Planning estimate only — demo uses screenshot totals; live scales by shot count.
  const workloadStarting = shotCount * PLANNING_MIN_PER_SHOT.startingImages
  const workloadVideo = shotCount * PLANNING_MIN_PER_SHOT.video
  const workloadUpscale = shotCount * PLANNING_MIN_PER_SHOT.upscale
  const workloadTotal = fixture
    ? fixture.workload.total
    : formatPlanningEstimate(workloadStarting + workloadVideo + workloadUpscale)
  const workloadJobsLabel = fixture
    ? fixture.workload.jobsLabel
    : `${shotCount} serialized GPU jobs`
  const workloadStartingLabel = fixture
    ? fixture.workload.startingImages
    : formatPlanningEstimate(workloadStarting)
  const workloadVideoLabel = fixture
    ? fixture.workload.video
    : formatPlanningEstimate(workloadVideo)
  const workloadUpscaleLabel = fixture
    ? fixture.workload.upscale
    : formatPlanningEstimate(workloadUpscale)

  const approveTitle = approveDisabledReason({
    approving,
    busy,
    alreadyApproved,
    failingReasons: failing.map((g) => g.reason),
    serverReady,
  })

  const onApprove = async () => {
    if (alreadyApproved) {
      setMessage('Production plan is already approved for this revision. No render was started.')
      return
    }
    // approvePlan only when readiness.ready; else gate modal / lock.
    if (!serverReady || failing.length > 0) {
      setGateModal(true)
      return
    }
    if (busy || approving) return
    setApproving(true)
    try {
      await approvePlan('Producer')
    } finally {
      setApproving(false)
    }
  }

  const explain = (title: string, body: string) => {
    setMessage(`${title}: ${body}`)
  }

  const scenesNote =
    fixture?.scenesNote ??
    (project.scenes.length ? `${project.scenes.length} in hierarchy` : 'No scenes yet')

  return (
    <div className="page proto-page">
      {/* 1. PageTitle: PRODUCTION PHASE A + project title + synopsis + readiness % */}
      <PageTitle
        eyebrow="PRODUCTION PHASE A"
        title={project.name}
        description={project.synopsis}
        aside={
          <div className="readiness-block">
            <span>
              <b>{readinessPct}%</b> storyboard readiness
            </span>
            <Progress value={readinessPct} />
            <small>
              {failing.length
                ? `${failing.length} required gates remain`
                : serverReady
                  ? 'All required gates passed'
                  : 'Awaiting server readiness'}
            </small>
          </div>
        }
      />

      {/* 2. overview-strip */}
      <div className="overview-strip">
        <div>
          <span>Target runtime</span>
          <b>{targetRuntimeLabel}</b>
        </div>
        <Icon name="arrow" />
        <div>
          <span>Planned runtime</span>
          <b>{plannedRuntimeLabel}</b>
        </div>
        <div className="runtime-match">
          <Icon name={reconciled ? 'check' : 'warning'} />
          <span>{reconciled ? 'Runtime reconciled' : 'Duration drift'}</span>
        </div>
        <div className="overview-actions">
          <Button type="button" onClick={() => navigate('storyboard')} icon="arrow">
            Continue review
          </Button>
          <Button
            type="button"
            variant="primary"
            onClick={() => void onApprove()}
            disabled={approving || busy || alreadyApproved}
            icon={!canApprove || alreadyApproved ? 'lock' : 'check'}
            title={approveTitle}
          >
            {approving
              ? 'Approving…'
              : alreadyApproved
                ? 'Plan approved'
                : 'Approve production plan'}
          </Button>
          <button type="button" className="why-disabled" onClick={() => setGateModal(true)}>
            {failing.length
              ? `View ${failing.length} blockers`
              : serverReady
                ? 'All gates passed'
                : 'View readiness'}
          </button>
        </div>
      </div>

      {/* 3. metric-grid eight — 8 Metric cards with status chips */}
      <div className="metric-grid eight">
        <Metric
          label="Chapters"
          value={project.chapters.length}
          note={chapterNote(project)}
          status={project.chapters.length ? 'Ready' : 'Draft'}
          onClick={() => navigate('story')}
        />
        <Metric
          label="Scenes"
          value={project.scenes.length}
          note={scenesNote}
          status={project.scenes.length ? 'Ready' : 'Draft'}
          onClick={() => navigate('story')}
        />
        <Metric
          label="Shots"
          value={shotCount}
          note={`${approved} approved`}
          status={shotStatus}
          onClick={() => navigate('storyboard')}
        />
        <Metric
          label="Characters"
          value={project.characters.length}
          note={`${heroApproved} hero images approved`}
          status={
            project.characters.length === 0
              ? 'Draft'
              : heroApproved === project.characters.length
                ? 'Ready'
                : 'Review'
          }
          onClick={() => navigate('characters')}
        />
        <Metric
          label="Voice coverage"
          value={`${voices}/${shotCount || 27}`}
          note={shotCount ? coverageNote(voices, shotCount, 'assignments open') : 'No shots'}
          status={voiceStatus}
          onClick={() => navigate('voices')}
        />
        <Metric
          label="Starting images"
          value={`${images}/${shotCount || 27}`}
          note={shotCount ? coverageNote(images, shotCount, 'require approval') : 'No shots'}
          status={shotCount === 0 ? 'Draft' : images >= shotCount ? 'Ready' : 'Review'}
          onClick={() => navigate('images')}
        />
        <Metric
          label="Continuity"
          value={`${continuity}/${shotCount || 27}`}
          note={shotCount ? coverageNote(continuity, shotCount, 'invalid link') : 'No shots'}
          status={shotCount === 0 ? 'Draft' : continuity >= shotCount ? 'Ready' : 'Review'}
          onClick={() => navigate('storyboard')}
        />
        <Metric
          label="Model / workflow gaps"
          value={modelGapsValue}
          note={modelGapsNote}
          status={modelGapsValue ? 'Blocked' : failing.length ? 'Review' : 'Ready'}
          onClick={() => navigate('routing')}
        />
      </div>

      {/* 4. Production-plan pipeline — 7 stages */}
      <Section
        title="Production-plan pipeline"
        subtitle="Phase A stops at an approved, editable plan—before rendering."
      >
        <div className="pipeline">
          {pipeline.map(([label, value, page], i) => (
            <button key={label} type="button" onClick={() => navigate(page)}>
              <span className="pipeline-node" data-complete={value === 100}>
                {value === 100 ? <Icon name="check" size={14} /> : i + 1}
              </span>
              <b>{label}</b>
              <small>{value}%</small>
              <Progress value={value} />
            </button>
          ))}
        </div>
      </Section>

      {/* 5. overview-columns: Readiness gates | Unresolved + Orchestrator | Workload + Activity */}
      <div className="overview-columns">
        <Section
          title="Readiness gates"
          subtitle="Approval uses these exact shared rules."
          action={
            <button type="button" className="text-action" onClick={() => setGateModal(true)}>
              View all
            </button>
          }
        >
          <div className="gate-list">
            {gates.map((g) => {
              const displayLabel = humanizeGateLabel(g.label)
              return (
                <button
                  key={`${g.label}-${g.reason}`}
                  type="button"
                  onClick={() => {
                    if (!g.pass) {
                      explain(displayLabel, g.reason)
                      navigate(issueNav(g.label, g.reason))
                    }
                  }}
                >
                  <span className={g.pass ? 'gate-pass' : 'gate-fail'}>
                    <Icon name={g.pass ? 'check' : 'warning'} size={14} />
                  </span>
                  <span>
                    <b>{displayLabel}</b>
                    <small>{g.pass ? 'Passed' : g.reason}</small>
                  </span>
                  <StatusPill status={g.pass ? 'Ready' : 'Open'} />
                </button>
              )
            })}
          </div>
        </Section>

        <div className="stack">
          <Section title="Unresolved issues" subtitle="Highest-impact items first.">
            <div className="issue-list">
              {fixture ? (
                fixture.unresolved.map((item) => (
                  <button
                    key={item.title}
                    type="button"
                    onClick={() => navigate(item.page)}
                  >
                    <span
                      className={`severity priority ${item.severity === 'P0' ? 'red' : 'amber'}`}
                    >
                      {item.severity}
                    </span>
                    <span>
                      <b>{item.title}</b>
                      <small>{item.detail}</small>
                    </span>
                    <Icon name="arrow" />
                  </button>
                ))
              ) : failing.length ? (
                failing.slice(0, 5).map((g, index) => (
                  <button
                    key={`${g.label}-${index}`}
                    type="button"
                    onClick={() => navigate(issueNav(g.label, g.reason))}
                  >
                    <span className={`severity priority ${index === 0 ? 'red' : 'amber'}`}>
                      P{index === 0 ? '0' : '1'}
                    </span>
                    <span>
                      <b>{humanizeGateLabel(g.label)}</b>
                      <small>{g.reason}</small>
                    </span>
                    <Icon name="arrow" />
                  </button>
                ))
              ) : (
                <p className="form-hint">No blocking readiness issues returned by the server.</p>
              )}
            </div>
          </Section>

          <Section
            title="Orchestrator run"
            subtitle={fixture ? 'Latest structured proposal · mock run' : 'Latest structured proposal · planning run'}
          >
            <div className="run-summary">
              <div className="orchestrator-mark">
                <Icon name="spark" />
              </div>
              <div>
                <b>{project.orchestratorModel}</b>
                <small>
                  {fixture
                    ? fixture.orchestratorSummary
                    : `${shotCount} shots in hierarchy · proposal review on Story page`}
                </small>
              </div>
              <StatusPill
                status={
                  fixture
                    ? fixture.orchestratorStatus
                    : project.approvedPlan
                      ? 'Complete'
                      : 'Review'
                }
              />
            </div>
            <button type="button" className="full-row-action" onClick={() => navigate('story')}>
              Compare proposal with current structure <Icon name="arrow" />
            </button>
          </Section>
        </div>

        <div className="stack">
          <Section
            title="Render workload estimate"
            subtitle="Planning estimate only—rendering is disabled."
          >
            <div className="workload">
              <strong>{workloadTotal}</strong>
              <span>{workloadJobsLabel}</span>
              <div>
                <span>Starting images</span>
                <b>{workloadStartingLabel}</b>
              </div>
              <div>
                <span>Video generation</span>
                <b>{workloadVideoLabel}</b>
              </div>
              <div>
                <span>Upscale & interpolation</span>
                <b>{workloadUpscaleLabel}</b>
              </div>
            </div>
            <Button type="button" variant="quiet" onClick={() => navigate('workflows')}>
              Review workflow assumptions
            </Button>
          </Section>

          <Section title="Recent activity" subtitle="Current browser session">
            <ol className="activity">
              {fixture ? (
                fixture.activity.map((item) => (
                  <li key={item.title}>
                    <i />
                    <span>
                      <b>{item.title}</b>
                      <small>{item.when}</small>
                    </span>
                  </li>
                ))
              ) : (
                <>
                  <li>
                    <i />
                    <span>
                      <b>Planning data loaded</b>
                      <small>This session</small>
                    </span>
                  </li>
                  <li>
                    <i />
                    <span>
                      <b>{shotCount} shots in hierarchy</b>
                      <small>From aggregate snapshot</small>
                    </span>
                  </li>
                  <li>
                    <i />
                    <span>
                      <b>
                        {failing.length} open readiness gate{failing.length === 1 ? '' : 's'}
                      </b>
                      <small>From server readiness payload</small>
                    </span>
                  </li>
                </>
              )}
            </ol>
          </Section>
        </div>
      </div>

      {/* 6. Gate modal */}
      {gateModal ? (
        <Modal
          title={
            failing.length || !serverReady
              ? 'Production plan is not ready'
              : alreadyApproved
                ? 'Production plan already approved'
                : 'Production plan approval'
          }
          onClose={() => setGateModal(false)}
        >
          <div className="gate-modal">
            <div className="gate-score">
              <strong>{readinessPct}%</strong>
              <Progress value={readinessPct} />
              <span>
                {gates.filter((g) => g.pass).length} of {gates.length} gates passed
              </span>
            </div>
            {failing.length ? (
              <div className="gate-blockers">
                {failing.map((g) => (
                  <button
                    key={g.label + g.reason}
                    type="button"
                    onClick={() => {
                      setGateModal(false)
                      setMessage(g.reason)
                      navigate(issueNav(g.label, g.reason))
                    }}
                  >
                    <Icon name="warning" />
                    <span>
                      <b>{humanizeGateLabel(g.label)}</b>
                      <small>{g.reason}</small>
                    </span>
                  </button>
                ))}
              </div>
            ) : !serverReady ? (
              <p>
                Local gate reasons are clear, but the server has not set{' '}
                <code>readiness.ready</code>. Approval is locked until the backend reports ready.
              </p>
            ) : alreadyApproved ? (
              <p>
                This production plan is already approved for the current revision. Approval does
                not create render, queue, ComfyUI, or FFmpeg jobs.
              </p>
            ) : (
              <p>
                All required planning gates have passed. Approval will lock this Phase A version
                while keeping it editable through a new revision. No render or queue job will be
                created.
              </p>
            )}
            <div className="modal-actions">
              <Button type="button" onClick={() => setGateModal(false)}>
                Close
              </Button>
              {canApprove ? (
                <Button
                  type="button"
                  variant="primary"
                  disabled={approving || busy}
                  title={approveTitle}
                  onClick={() => {
                    setGateModal(false)
                    void onApprove()
                  }}
                >
                  {approving ? 'Approving…' : 'Approve plan'}
                </Button>
              ) : null}
            </div>
          </div>
        </Modal>
      ) : null}
    </div>
  )
}
