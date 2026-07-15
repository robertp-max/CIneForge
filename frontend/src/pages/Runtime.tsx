import { useEffect, useState } from 'react'
import {
  api,
  type LocalArchetype,
  type LocalM4PreflightReport,
  type LocalPreset,
  type LocalRuntimeCatalog,
  type LocalRuntimeEvidence,
  type RuntimeStatus,
} from '../api/client'
import { DebugPanel, ErrorNotice } from '../components/Cards'
import { PageHeader } from '../components/Page'
import { StatusCard } from '../components/Cards'
import { StatusBadge } from '../components/StatusBadge'

const disabledActions = [
  ['Public submit prompt', 'User-facing /prompt submission is not exposed by the API or UI.'],
  ['WebSocket monitor', 'Progress streams open after prompt submission is controlled.'],
  ['Output collection', 'History and output reads remain blocked in this slice.'],
  ['FFmpeg assembly', 'Assembly is planned after output collection and validation exist.'],
]

export function Runtime() {
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null)
  const [localCatalog, setLocalCatalog] = useState<LocalRuntimeCatalog | null>(null)
  const [localPresets, setLocalPresets] = useState<LocalPreset[]>([])
  const [localArchetypes, setLocalArchetypes] = useState<LocalArchetype[]>([])
  const [localEvidence, setLocalEvidence] = useState<LocalRuntimeEvidence[]>([])
  const [m4Preflight, setM4Preflight] = useState<LocalM4PreflightReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadRuntime() {
      setLoading(true)
      setError(null)
      try {
        const [status, catalog, presets, archetypes, evidence, preflight] = await Promise.all([
          api.runtimeStatus(),
          api.localRuntimeCatalog(),
          api.listLocalPresets(),
          api.listLocalArchetypes(),
          api.listLocalRuntimeEvidence(),
          api.localM4Preflight(),
        ])
        if (!cancelled) {
          setRuntime(status)
          setLocalCatalog(catalog)
          setLocalPresets(presets)
          setLocalArchetypes(archetypes)
          setLocalEvidence(evidence)
          setM4Preflight(preflight)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Unable to load runtime status.')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void loadRuntime()
    return () => {
      cancelled = true
    }
  }, [])

  const selectedArtifact = localCatalog?.artifacts.find((artifact) => artifact.role === 'selected_fp8')

  return (
    <div className="page">
      <PageHeader
        eyebrow="Runtime"
        title="ComfyUI readiness boundary"
        description="Runtime status shows the current backend capability while keeping public prompt, WebSocket, history, output, and FFmpeg execution paths unavailable."
      />

      {error ? <ErrorNotice message={error} /> : null}

      <section className="grid three">
        <StatusCard
          title="ComfyUI Reachability"
          status={String(runtime?.comfyui.status ?? 'unavailable')}
          detail={loading ? 'Checking...' : 'Health probe against the external ComfyUI HTTP root.'}
          meta="GET /health/comfy via /runtime/status"
        />
        <StatusCard
          title="object_info"
          status={runtime?.object_info.status ?? 'unavailable'}
          detail={
            runtime?.object_info.available
              ? `${runtime.object_info.class_count ?? 0} classes visible.`
              : 'Not exposed yet or ComfyUI is unavailable.'
          }
          meta="Read-only availability probe"
        />
        <StatusCard
          title="Runtime Boundary"
          status={runtime?.queue.controlled_submission_enabled ? 'ok' : 'disabled'}
          detail="Controlled /prompt submission is available only through the worker/runtime service after readiness checks."
          meta="Public /prompt remains unavailable"
        />
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Current Phase</h2>
          <span>{runtime?.current_phase ?? 'Loading...'}</span>
        </div>
        <p>
          Backend capability: controlled worker submission{' '}
          {runtime?.queue.controlled_submission_enabled ? 'enabled' : 'disabled'}. User-facing generation{' '}
          {runtime?.queue.public_submission_enabled ? 'enabled' : 'disabled'}.
        </p>
      </section>

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

      {runtime ? <DebugPanel title="Runtime status response" data={runtime} /> : null}
    </div>
  )
}
