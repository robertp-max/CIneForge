import { type FormEvent, useEffect, useState } from 'react'
import {
  api,
  type BenchmarkLadderManifest,
  type FFmpegCommandTemplateRecord,
  type LocalArchetype,
  type LocalArchetypeReadinessRecord,
  type LocalArchetypeReadinessReport,
  type LocalM4PreflightReport,
  type LocalMVPReadinessReport,
  type LocalOperatorRunMode,
  type LocalOperatorRunPacket,
  type LocalPreset,
  type LocalPresetReadinessRecord,
  type LocalPublicReadinessReport,
  type LocalPresetReadinessReport,
  type LocalReadinessReason,
  type LocalReadinessSummary,
  type LocalRuntimeCatalog,
  type LocalRuntimeEvidence,
} from '../api/client'
import { ErrorNotice } from '../components/Cards'
import { PageHeader } from '../components/Page'
import { StatusCard } from '../components/Cards'
import { StatusBadge } from '../components/StatusBadge'

const disabledActions = [
  ['Public submit prompt', 'User-facing /prompt submission is not exposed by the API or UI.'],
  ['WebSocket monitor', 'Progress streams open after prompt submission is controlled.'],
  ['Output collection', 'History and output reads remain blocked in this slice.'],
  ['FFmpeg assembly', 'Assembly is planned after output collection and validation exist.'],
]

const READINESS_REASON_LIMIT = 3
const READINESS_RECORD_LIMIT = 4

const operatorPacketModes: Array<{ value: LocalOperatorRunMode; label: string }> = [
  { value: 'm4_hardware_ladder_probe', label: 'M4 hardware ladder probe review packet' },
  { value: 'm5_ffmpeg_probe_validation', label: 'M5 FFmpeg/ffprobe probe validation review packet' },
  { value: 'm5_ffmpeg_assembly_validation', label: 'M5 FFmpeg assembly validation review packet' },
]

type ReadinessRecord = LocalArchetypeReadinessRecord | LocalPresetReadinessRecord
type ReadinessReport = LocalArchetypeReadinessReport | LocalPresetReadinessReport

function formatReadinessCounts(summary: LocalReadinessSummary | null | undefined) {
  if (!summary) return 'loading'
  return `${summary.blocked} blocked · ${summary.benchmark_required} benchmark required · ${summary.ready} ready`
}

function readinessRecordId(record: ReadinessRecord) {
  return 'archetype_id' in record ? record.archetype_id : record.preset_id
}

function readinessRecordContext(record: ReadinessRecord) {
  if ('default_archetype_id' in record) {
    return `${record.quality_profile}; default ${record.default_archetype_id}`
  }
  return record.quality_profiles.length ? record.quality_profiles.join(', ') : record.modality
}

function readinessGatedCount(records: ReadinessRecord[]) {
  return records.filter(
    (record) => !(record.status === 'ready' && record.production_ready && record.admitted_for_local_execution),
  ).length
}

function topReadinessReasons(records: ReadinessRecord[]) {
  const reasons = records.flatMap((record) => record.reasons)
  const blockerReasons = reasons.filter((reason) => reason.severity === 'blocker')
  const selectedReasons = blockerReasons.length ? blockerReasons : reasons
  const groupedReasons = new Map<string, { count: number; reason: LocalReadinessReason }>()

  selectedReasons.forEach((reason) => {
    const previous = groupedReasons.get(reason.code)
    groupedReasons.set(reason.code, { count: (previous?.count ?? 0) + 1, reason: previous?.reason ?? reason })
  })

  return Array.from(groupedReasons.values())
    .sort((a, b) => b.count - a.count || a.reason.code.localeCompare(b.reason.code))
    .slice(0, READINESS_REASON_LIMIT)
    .map(({ count, reason }) => `${reason.code}: ${reason.message}${count > 1 ? ` (${count})` : ''}`)
}

function ReadinessRollupPanel({ report, title, noun }: { report: ReadinessReport | null; title: string; noun: string }) {
  const records = report?.records ?? []
  const topReasons = topReadinessReasons(records)
  const visibleRecords = records.slice(0, READINESS_RECORD_LIMIT)
  const gatedCount = readinessGatedCount(records)
  const livePromotionCount = records.filter((record) => record.live_execution_required_for_promotion).length

  return (
    <section className="panel">
      <div className="panel-title">
        <h2>{title}</h2>
        <span>{report ? formatReadinessCounts(report.summary) : 'loading'}</span>
      </div>
      <p>{report?.safety_note ?? `Loading read-only ${noun} readiness rollup...`}</p>
      <div className="disabled-action-grid">
        <article className="disabled-action">
          <div>
            <strong>Counts by status</strong>
            <p>{formatReadinessCounts(report?.summary)}</p>
          </div>
          <StatusBadge status={report?.summary.ready ? 'ready' : report ? 'gated' : 'loading'} />
        </article>
        <article className="disabled-action">
          <div>
            <strong>Public generation</strong>
            <p>
              Endpoint flag:{' '}
              <span className="mono">{report ? String(report.public_generation_enabled) : 'loading'}</span>; summary flag:{' '}
              <span className="mono">{report ? String(report.summary.public_generation_enabled) : 'loading'}</span>.
            </p>
          </div>
          <StatusBadge status={report?.public_generation_enabled === false ? 'disabled' : report ? 'blocked' : 'loading'} />
        </article>
        <article className="disabled-action">
          <div>
            <strong>Promotion live-run boundary</strong>
            <p>
              Live execution performed by endpoint:{' '}
              <span className="mono">{report ? String(report.live_execution_performed_by_endpoint) : 'loading'}</span>; promotion still
              requires live evidence on <span className="mono">{report ? livePromotionCount : 'loading'}</span> {noun} records.
            </p>
          </div>
          <StatusBadge status={report?.live_execution_performed_by_endpoint ? 'blocked' : 'read_only'} />
        </article>
        <article className="disabled-action">
          <div>
            <strong>Evidence gate</strong>
            <p>
              {report
                ? `${gatedCount}/${records.length} ${noun} records remain gated unless backend evidence reports ready, admitted, and production-ready.`
                : `Loading ${noun} evidence gates...`}
            </p>
          </div>
          <StatusBadge status={gatedCount ? 'gated' : report ? 'ready' : 'loading'} />
        </article>
      </div>
      <div className="panel-title">
        <h3>Top blocker / promotion reasons</h3>
        <span>{topReasons.length ? `top ${topReasons.length}` : report ? 'none' : 'loading'}</span>
      </div>
      <ul className="feature-list">
        {topReasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
        {!topReasons.length ? <li>{report ? 'No blocker reasons reported.' : 'Loading readiness reasons...'}</li> : null}
      </ul>
      <div className="panel-title">
        <h3>Read-only sample records</h3>
        <span>{report ? `${visibleRecords.length}/${records.length}` : 'loading'}</span>
      </div>
      <div className="disabled-action-grid">
        {visibleRecords.map((record) => (
          <article key={readinessRecordId(record)} className="disabled-action">
            <div>
              <strong>{readinessRecordId(record)}: {record.name}</strong>
              <p>
                {readinessRecordContext(record)}; public_generation_enabled{' '}
                <span className="mono">{String(record.public_generation_enabled)}</span>; live promotion evidence required{' '}
                <span className="mono">{String(record.live_execution_required_for_promotion)}</span>.
              </p>
              <p className="mono">
                catalog={record.catalog_readiness}; admitted={String(record.admitted_for_local_execution)};
                production_ready={String(record.production_ready)}
              </p>
            </div>
            <StatusBadge status={record.status} />
          </article>
        ))}
        {!visibleRecords.length ? (
          <article className="disabled-action">
            <div>
              <strong>Loading records</strong>
              <p>Read-only readiness records will appear when the backend rollup loads.</p>
            </div>
            <StatusBadge status="loading" />
          </article>
        ) : null}
      </div>
    </section>
  )
}

export function Runtime() {
  const [localCatalog, setLocalCatalog] = useState<LocalRuntimeCatalog | null>(null)
  const [localPresets, setLocalPresets] = useState<LocalPreset[]>([])
  const [localPresetReadiness, setLocalPresetReadiness] = useState<LocalPresetReadinessReport | null>(null)
  const [localArchetypes, setLocalArchetypes] = useState<LocalArchetype[]>([])
  const [localArchetypeReadiness, setLocalArchetypeReadiness] = useState<LocalArchetypeReadinessReport | null>(null)
  const [localEvidence, setLocalEvidence] = useState<LocalRuntimeEvidence[]>([])
  const [m4Preflight, setM4Preflight] = useState<LocalM4PreflightReport | null>(null)
  const [localMvpReadiness, setLocalMvpReadiness] = useState<LocalMVPReadinessReport | null>(null)
  const [localPublicReadiness, setLocalPublicReadiness] = useState<LocalPublicReadinessReport | null>(null)
  const [m4Ladder, setM4Ladder] = useState<BenchmarkLadderManifest | null>(null)
  const [operatorPackets, setOperatorPackets] = useState<LocalOperatorRunPacket[]>([])
  const [operatorPacketMode, setOperatorPacketMode] = useState<LocalOperatorRunMode>('m4_hardware_ladder_probe')
  const [operatorPacketRequestedBy, setOperatorPacketRequestedBy] = useState('local-operator')
  const [operatorPacketTargetRef, setOperatorPacketTargetRef] = useState('CF-VID-01')
  const [operatorPacketNotes, setOperatorPacketNotes] = useState('')
  const [operatorPacketAcknowledged, setOperatorPacketAcknowledged] = useState(false)
  const [operatorPacketSubmitting, setOperatorPacketSubmitting] = useState(false)
  const [operatorPacketMessage, setOperatorPacketMessage] = useState<string | null>(null)
  const [ffmpegRecipes, setFFmpegRecipes] = useState<FFmpegCommandTemplateRecord[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadRuntime() {
      setError(null)
      try {
        const [
          catalog,
          presets,
          presetReadiness,
          archetypes,
          archetypeReadiness,
          evidence,
          preflight,
          readiness,
          publicReadiness,
          operatorPacketList,
          ladder,
          recipes,
        ] = await Promise.all([
          api.localRuntimeCatalog(),
          api.listLocalPresets(),
          api.listLocalPresetReadiness(),
          api.listLocalArchetypes(),
          api.listLocalArchetypeReadiness(),
          api.listLocalRuntimeEvidence(),
          api.localM4Preflight(),
          api.localMVPReadiness(),
          api.localPublicReadiness(),
          api.listLocalOperatorPackets(),
          api.localM4Ladder(),
          api.listFFmpegRecipes(),
        ])
        if (!cancelled) {
          setLocalCatalog(catalog)
          setLocalPresets(presets)
          setLocalPresetReadiness(presetReadiness)
          setLocalArchetypes(archetypes)
          setLocalArchetypeReadiness(archetypeReadiness)
          setLocalEvidence(evidence)
          setM4Preflight(preflight)
          setLocalMvpReadiness(readiness)
          setLocalPublicReadiness(publicReadiness)
          setOperatorPackets(operatorPacketList)
          setM4Ladder(ladder)
          setFFmpegRecipes(recipes)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Unable to load local runtime metadata.')
        }
      }
    }

    void loadRuntime()
    return () => {
      cancelled = true
    }
  }, [])

  const selectedArtifact = localCatalog?.artifacts.find((artifact) => artifact.role === 'selected_fp8')
  const localMvpBlockers = localMvpReadiness?.remaining_blockers_before_local_operator_live_runs ?? []
  const visibleLocalMvpBlockers = localMvpBlockers.slice(0, 4)
  const hiddenLocalMvpBlockerCount = Math.max(0, localMvpBlockers.length - visibleLocalMvpBlockers.length)
  const visibleOperatorPackets = operatorPackets.slice(0, 3)
  const visiblePublicReleaseBlockers = localPublicReadiness?.remaining_public_release_blockers.slice(0, 4) ?? []
  const hiddenPublicReleaseBlockerCount = Math.max(
    0,
    (localPublicReadiness?.remaining_public_release_blockers.length ?? 0) - visiblePublicReleaseBlockers.length,
  )

  async function handleCreateOperatorPacket(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setOperatorPacketMessage(null)
    if (!operatorPacketAcknowledged) {
      setOperatorPacketMessage('Check the no-execution acknowledgement before preparing a packet.')
      return
    }
    if (!operatorPacketRequestedBy.trim()) {
      setOperatorPacketMessage('Requested-by is required for the packet audit record.')
      return
    }
    setOperatorPacketSubmitting(true)
    try {
      const packet = await api.createLocalOperatorPacket({
        mode: operatorPacketMode,
        requested_by: operatorPacketRequestedBy.trim(),
        target_ref: operatorPacketTargetRef.trim() || null,
        notes: operatorPacketNotes.trim() || null,
        acknowledge_no_execution: true,
      })
      setOperatorPackets((current) => [packet, ...current.filter((item) => item.packet_id !== packet.packet_id)])
      setOperatorPacketMessage(`Prepared offline packet ${packet.packet_id}; no approval or live execution was started.`)
      setOperatorPacketAcknowledged(false)
      setOperatorPacketNotes('')
    } catch (err) {
      setOperatorPacketMessage(err instanceof Error ? err.message : 'Unable to prepare local operator packet.')
    } finally {
      setOperatorPacketSubmitting(false)
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Runtime"
        title="ComfyUI readiness boundary"
        description="Read-only local readiness metadata is loaded without automatic ComfyUI, GPU, object_info, phase, FFmpeg execution, or live telemetry probes."
      />

      {error ? <ErrorNotice message={error} /> : null}

      <section className="grid three">
        <StatusCard
          title="ComfyUI Reachability"
          status="approval_required"
          detail="Live ComfyUI reachability probes require explicit operator approval and are not auto-run when this page opens."
          meta="No /runtime/status or /health/comfy request"
        />
        <StatusCard
          title="object_info"
          status="approval_required"
          detail="ComfyUI object_info inventory is a live probe and remains inert until separately approved by an operator."
          meta="No /object_info request"
        />
        <StatusCard
          title="Runtime Boundary"
          status="local_read_only"
          detail="This page displays file-backed local readiness metadata only; generation and runtime probes remain outside automatic UI loading."
          meta="No live runtime telemetry"
        />
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Current Phase</h2>
          <span>not auto-probed</span>
        </div>
        <p>
          Current runtime phase, queue capability, GPU telemetry, and ComfyUI availability are not requested automatically.
          Live probes require explicit operator approval outside this read-only local readiness page.
        </p>
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Local-only MVP Readiness</h2>
          <StatusBadge status={localMvpReadiness?.status ?? 'loading'} />
        </div>
        <p>{localMvpReadiness?.safety_note ?? 'Loading read-only local MVP checkpoint...'}</p>
        <div className="disabled-action-grid">
          <article className="disabled-action">
            <div>
              <strong>Target and live-run boundary</strong>
              <p>
                Local-only target:{' '}
                <span className="mono">{localMvpReadiness ? String(localMvpReadiness.local_only_target) : 'loading'}</span>; local operator
                live runs allowed by this endpoint:{' '}
                <span className="mono">
                  {localMvpReadiness ? String(localMvpReadiness.local_operator_live_runs_allowed_by_endpoint) : 'loading'}
                </span>.
              </p>
            </div>
            <StatusBadge status={localMvpReadiness?.local_only_target ?? null} label="local only" />
          </article>
          <article className="disabled-action">
            <div>
              <strong>Generation flags remain inert</strong>
              <p>
                Public disabled:{' '}
                <span className="mono">
                  {localMvpReadiness ? String(localMvpReadiness.public_generation_disabled) : 'loading'}
                </span>; autonomous disabled:{' '}
                <span className="mono">
                  {localMvpReadiness ? String(localMvpReadiness.autonomous_generation_disabled) : 'loading'}
                </span>.
              </p>
            </div>
            <StatusBadge
              status={
                localMvpReadiness
                  ? localMvpReadiness.public_generation_disabled && localMvpReadiness.autonomous_generation_disabled
                  : null
              }
              label="disabled"
            />
          </article>
          <article className="disabled-action">
            <div>
              <strong>M4 hardware preflight summary</strong>
              <p>
                {localMvpReadiness
                  ? `${localMvpReadiness.m4_preflight.passed_check_count}/${localMvpReadiness.m4_preflight.check_count} checks passed; next: ${localMvpReadiness.m4_preflight.next_allowed_action}`
                  : 'Loading M4 checkpoint summary...'}
              </p>
            </div>
            <StatusBadge status={localMvpReadiness?.m4_preflight.status ?? 'loading'} />
          </article>
          <article className="disabled-action">
            <div>
              <strong>M5 post-production summary</strong>
              <p>
                {localMvpReadiness
                  ? `${localMvpReadiness.m5_post_production.recipe_catalog_count} read-only recipes; FFmpeg execution endpoint present: ${localMvpReadiness.m5_post_production.ffmpeg_execution_endpoint_present}`
                  : 'Loading M5 checkpoint summary...'}
              </p>
            </div>
            <StatusBadge
              status={localMvpReadiness?.m5_post_production.ffmpeg_recipes_read_only ?? null}
              label="read only"
            />
          </article>
        </div>
        <div className="panel-title">
          <h3>Remaining blockers before local operator live runs</h3>
          <span>{localMvpReadiness ? `${localMvpBlockers.length} blockers` : 'loading'}</span>
        </div>
        <ul className="feature-list">
          {visibleLocalMvpBlockers.map((blocker) => (
            <li key={blocker}>{blocker}</li>
          ))}
          {hiddenLocalMvpBlockerCount ? <li>+{hiddenLocalMvpBlockerCount} more blockers</li> : null}
          {!localMvpReadiness ? <li>Loading checkpoint blockers...</li> : null}
        </ul>
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Public Release Readiness</h2>
          <StatusBadge status={localPublicReadiness?.status ?? 'loading'} />
        </div>
        <p>
          {localPublicReadiness?.safety_note ??
            'Loading fail-closed public-release readiness report; no live probe or public generation surface is enabled.'}
        </p>
        <div className="disabled-action-grid">
          <article className="disabled-action">
            <div>
              <strong>Public release status</strong>
              <p>
                Ready: <span className="mono">{localPublicReadiness ? String(localPublicReadiness.public_release_ready) : 'loading'}</span>; public
                prompt route enabled:{' '}
                <span className="mono">{localPublicReadiness ? String(localPublicReadiness.public_prompt_enabled) : 'loading'}</span>.
              </p>
            </div>
            <StatusBadge status={localPublicReadiness?.public_release_ready ? 'ready' : 'blocked'} />
          </article>
          <article className="disabled-action">
            <div>
              <strong>Archetype evidence</strong>
              <p>
                {localPublicReadiness
                  ? `${localPublicReadiness.archetype_summary.ready}/${localPublicReadiness.archetype_summary.total} ready; ${localPublicReadiness.archetype_summary.blocked} blocked.`
                  : 'Loading archetype readiness summary...'}
              </p>
            </div>
            <StatusBadge status={localPublicReadiness?.archetype_summary.ready ? 'benchmark_required' : 'blocked'} />
          </article>
          <article className="disabled-action">
            <div>
              <strong>Preset evidence</strong>
              <p>
                {localPublicReadiness
                  ? `${localPublicReadiness.preset_summary.ready}/${localPublicReadiness.preset_summary.total} ready; ${localPublicReadiness.preset_summary.blocked} blocked.`
                  : 'Loading preset readiness summary...'}
              </p>
            </div>
            <StatusBadge status={localPublicReadiness?.preset_summary.ready ? 'benchmark_required' : 'blocked'} />
          </article>
          <article className="disabled-action">
            <div>
              <strong>Live/public boundary</strong>
              <p>
                Live execution approved by endpoint:{' '}
                <span className="mono">
                  {localPublicReadiness ? String(localPublicReadiness.live_execution_approved_by_endpoint) : 'loading'}
                </span>; internet-facing enabled:{' '}
                <span className="mono">
                  {localPublicReadiness ? String(localPublicReadiness.internet_facing_enabled) : 'loading'}
                </span>.
              </p>
            </div>
            <StatusBadge status="read_only" />
          </article>
        </div>
        <div className="panel-title">
          <h3>Remaining public-release blockers</h3>
          <span>
            {localPublicReadiness
              ? `${localPublicReadiness.remaining_public_release_blockers.length} blockers`
              : 'loading'}
          </span>
        </div>
        <ul className="feature-list">
          {visiblePublicReleaseBlockers.map((blocker) => (
            <li key={blocker}>{blocker}</li>
          ))}
          {hiddenPublicReleaseBlockerCount ? <li>+{hiddenPublicReleaseBlockerCount} more blockers</li> : null}
          {!localPublicReadiness ? <li>Loading public-release blockers...</li> : null}
        </ul>
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Local Operator Review Packets</h2>
          <span>{operatorPackets.length ? `${operatorPackets.length} packet` : 'none'}</span>
        </div>
        <p>
          These are pending review manifests only. The UI can prepare or list stored packets with no approval, execute, submit,
          run, probe, render, benchmark, FFmpeg, ComfyUI, or GPU control.
        </p>
        <form className="form-stack compact" onSubmit={(event) => void handleCreateOperatorPacket(event)}>
          <div className="form-grid">
            <label>
              Packet mode
              <select
                value={operatorPacketMode}
                onChange={(event) => setOperatorPacketMode(event.target.value as LocalOperatorRunMode)}
              >
                {operatorPacketModes.map((mode) => (
                  <option key={mode.value} value={mode.value}>{mode.label}</option>
                ))}
              </select>
            </label>
            <label>
              Requested by
              <input
                value={operatorPacketRequestedBy}
                onChange={(event) => setOperatorPacketRequestedBy(event.target.value)}
                placeholder="local-operator"
              />
            </label>
            <label>
              Target reference
              <input
                value={operatorPacketTargetRef}
                onChange={(event) => setOperatorPacketTargetRef(event.target.value)}
                placeholder="CF-VID-01 or plan id"
              />
            </label>
          </div>
          <label>
            Notes
            <textarea
              value={operatorPacketNotes}
              onChange={(event) => setOperatorPacketNotes(event.target.value)}
              placeholder="Optional offline review context. No command strings or live-run instructions are required."
              rows={3}
            />
          </label>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={operatorPacketAcknowledged}
              onChange={(event) => setOperatorPacketAcknowledged(event.target.checked)}
            />
            I acknowledge this prepares review metadata only and does not approve or start FFmpeg, ffprobe, ComfyUI, GPU,
            render, benchmark, queue, or prompt-submission work.
          </label>
          <div className="button-row">
            <button type="submit" disabled={operatorPacketSubmitting}>
              {operatorPacketSubmitting ? 'Preparing packet...' : 'Prepare offline review packet'}
            </button>
          </div>
          {operatorPacketMessage ? <p className="form-hint">{operatorPacketMessage}</p> : null}
        </form>
        <div className="disabled-action-grid">
          {visibleOperatorPackets.map((packet) => (
            <article key={packet.packet_id} className="disabled-action">
              <div>
                <strong>{packet.request.mode}</strong>
                <p>
                  State <span className="mono">{packet.state}</span>; approval recorded{' '}
                  <span className="mono">{String(packet.approval_recorded)}</span>; live execution started{' '}
                  <span className="mono">{String(packet.live_execution_started)}</span>; submitted generation{' '}
                  <span className="mono">{String(packet.generation_submitted)}</span>; submitted FFmpeg{' '}
                  <span className="mono">{String(packet.ffmpeg_submitted)}</span>.
                </p>
                <p className="mono">
                  {packet.request.target_ref ?? 'no target'} · blockers {packet.blocking_reasons.slice(0, 3).join(', ')}
                </p>
              </div>
              <StatusBadge status={packet.state} />
            </article>
          ))}
          {!visibleOperatorPackets.length ? (
            <article className="disabled-action">
              <div>
                <strong>No operator packets</strong>
                <p>
                  Packet creation is an offline API manifest action only; this Runtime page intentionally provides no run or approval controls.
                </p>
              </div>
              <StatusBadge status="read_only" />
            </article>
          ) : null}
        </div>
      </section>

      <ReadinessRollupPanel report={localArchetypeReadiness} title="M6 Archetype Readiness Rollup" noun="archetype" />

      <ReadinessRollupPanel report={localPresetReadiness} title="M7 Preset Readiness Rollup" noun="preset" />

      <section className="grid three">
        <StatusCard
          title="Default Local Video Model"
          status={localCatalog?.readiness ?? 'loading'}
          detail={localCatalog?.display_name ?? 'Loading local runtime catalog...'}
          meta={localCatalog?.model_key ?? 'ltx2_3_22b_distilled_1_1_fp8'}
        />
        <StatusCard
          title="Selected FP8 Artifact"
          status={selectedArtifact?.path_exists ? selectedArtifact.readiness : 'missing'}
          detail={selectedArtifact?.path ?? 'Loading selected FP8 artifact path...'}
          meta={selectedArtifact?.sha256 ? `sha256 ${selectedArtifact.sha256.slice(0, 12)}...` : 'No hash loaded'}
        />
        <StatusCard
          title="Local Catalogs"
          status="file-backed"
          detail={`${localPresets.length} presets, ${localArchetypes.length} archetypes. All generation remains gated.`}
          meta="DB-free local contract"
        />
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>ComfyUI Output Policy</h2>
          <span>{localCatalog?.output_policy.one_folder_per_project ? 'project folders' : 'unknown'}</span>
        </div>
        <p className="mono">{localCatalog?.output_policy.output_root ?? 'Loading output root...'}</p>
        <p>
          Save nodes use filename_prefix shape{' '}
          <span className="mono">{localCatalog?.output_policy.filename_prefix_shape ?? '<project-folder>/<run-stem>'}</span>.
          Absolute paths, traversal, backslashes, and deeper trees are rejected by the backend.
        </p>
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Local Runtime Evidence</h2>
          <span>{localEvidence.length ? `${localEvidence.length} record` : 'none'}</span>
        </div>
        {localEvidence.map((evidence) => (
          <article key={evidence.evidence_id} className="disabled-action">
            <div>
              <strong>{evidence.archetype_id}: {evidence.template_id}</strong>
              <p>
                {evidence.outputs.length} smoke outputs recorded; readiness remains{' '}
                <span className="mono">{evidence.readiness_after_evidence}</span> with gates:{' '}
                {evidence.remaining_gates.join(', ')}.
              </p>
              <p className="mono">sha256 {evidence.workflow_api_sha256.slice(0, 16)}...</p>
            </div>
            <StatusBadge status={evidence.readiness_after_evidence} />
          </article>
        ))}
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>M4 Hardware Preflight</h2>
          <span>{m4Preflight?.status ?? 'loading'}</span>
        </div>
        <p>
          Operator hardware probe allowed:{' '}
          <strong>{m4Preflight?.hardware_operator_probe_allowed ? 'yes' : 'no'}</strong>. Live actions executed by this
          report: <strong>{m4Preflight?.live_actions_executed ? 'yes' : 'no'}</strong>.
        </p>
        <p>{m4Preflight?.next_allowed_action ?? 'Loading M4 preflight gate...'}</p>
        {m4Preflight?.blocking_reasons.length ? (
          <p className="mono">blocking: {m4Preflight.blocking_reasons.join(', ')}</p>
        ) : null}
        <div className="disabled-action-grid">
          {m4Preflight?.checks.map((check) => (
            <article key={check.code} className="disabled-action">
              <div>
                <strong>{check.code}</strong>
                <p>{check.message}</p>
              </div>
              <StatusBadge status={check.passed ? 'passed' : 'blocked'} />
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>M4 Serialized Ladder</h2>
          <span>{m4Ladder ? m4Ladder.allowed_stage_numbers.join(' → ') : 'loading'}</span>
        </div>
        <p>
          {m4Ladder?.name ?? 'Loading read-only ladder manifest...'} {m4Ladder ? `Hardware: ${m4Ladder.hardware_profile}.` : ''}
        </p>
        <p className="mono">
          deferred stages: {m4Ladder?.deferred_stage_numbers.join(', ') ?? 'loading'}; public generation:{' '}
          {m4Ladder?.public_generation_enabled ? 'enabled' : 'disabled'}; serial:{' '}
          {m4Ladder?.requires_serial_execution ? 'required' : 'not required'}
        </p>
        <div className="disabled-action-grid">
          {m4Ladder?.stages.map((stage) => (
            <article key={stage.stage_id} className="disabled-action">
              <div>
                <strong>Stage {stage.stage}: {stage.workload}</strong>
                <p>{stage.minimum_pass_condition}</p>
                <p className="mono">
                  {stage.profile ? `${stage.profile}; ` : ''}
                  {[stage.width, stage.height].every(Boolean) ? `${stage.width}x${stage.height}; ` : ''}
                  {stage.frames ? `${stage.frames}f; ` : ''}
                  {stage.requires_stage_success.length ? `after ${stage.requires_stage_success.join(', ')}` : 'no prerequisite stage'}
                </p>
              </div>
              <StatusBadge status={stage.live_action_approved ? 'approved' : stage.status} />
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>FFmpeg Recipe Catalog</h2>
          <span>{ffmpegRecipes.length ? `${ffmpegRecipes.length} recipes` : 'loading'}</span>
        </div>
        <p>
          Recipes are allowlisted command templates only. The catalog is read-only and does not execute FFmpeg or accept raw command strings.
        </p>
        <div className="disabled-action-grid">
          {ffmpegRecipes.map((recipe) => (
            <article key={recipe.template_id} className="disabled-action">
              <div>
                <strong>{recipe.template_id}</strong>
                <p>{recipe.description}</p>
                <p className="mono">
                  {recipe.category}; {recipe.command_shape}; executes: {recipe.executes_from_catalog ? 'yes' : 'no'}
                  {recipe.requires_probe_before_stream_copy ? '; probe required' : ''}
                </p>
              </div>
              <StatusBadge status={recipe.executes_from_catalog ? 'blocked' : 'read_only'} />
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Disabled Runtime Actions</h2>
          <span>Intentional gates</span>
        </div>
        <div className="disabled-action-grid">
          {disabledActions.map(([title, detail]) => (
            <article key={title} className="disabled-action">
              <div>
                <strong>{title}</strong>
                <p>{detail}</p>
              </div>
              <StatusBadge status="disabled" />
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}
