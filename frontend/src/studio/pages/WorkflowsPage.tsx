import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, type RuntimeCatalogWorkflowTemplate, type RuntimeStatus } from '../../api/client'
import { useStudio } from '../StudioState'
import { EmptyState, ErrorState, LoadingState, UnavailableState } from '../components/StateBlocks'

function claimLabel(value: boolean | undefined): string {
  return value === true ? 'Evidence recorded' : 'Not claimed'
}

function claimStatus(value: boolean | undefined): string {
  return value === true ? 'ready' : 'review'
}

export function WorkflowsPage() {
  const { data, busy, backendStatus } = useStudio()
  const [workflows, setWorkflows] = useState<RuntimeCatalogWorkflowTemplate[] | null>(null)
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null)
  const [available, setAvailable] = useState(true)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState('')
  const [filter, setFilter] = useState('All')

  const load = useCallback(async () => {
    if (!data) return
    setLoading(true)
    setError(null)
    try {
      const [wf, rt] = await Promise.all([
        api.listRuntimeWorkflowTemplates(),
        api.runtimeStatus().catch(() => null),
      ])
      setRuntime(rt)
      if (wf == null) {
        setAvailable(false)
        setWorkflows(null)
      } else {
        setAvailable(true)
        setWorkflows(wf)
        setSelectedId((current) => {
          if (current && wf.some((item) => item.id === current)) return current
          return wf[0]?.id ?? ''
        })
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load workflows.')
    } finally {
      setLoading(false)
    }
  }, [data])

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0)
    return () => window.clearTimeout(timer)
  }, [load])

  const categories = useMemo(() => {
    const set = new Set((workflows ?? []).map((wf) => wf.registration_status || 'unknown'))
    return ['All', ...Array.from(set)]
  }, [workflows])

  const list = useMemo(() => {
    if (!workflows) return []
    if (filter === 'All') return workflows
    return workflows.filter((wf) => (wf.registration_status || 'unknown') === filter)
  }, [filter, workflows])

  const selected = list.find((wf) => wf.id === selectedId) ?? workflows?.find((wf) => wf.id === selectedId) ?? null

  if (!data) return null

  const installedCount = workflows?.filter((wf) => wf.claims.installed).length ?? 0
  const validatedCount = workflows?.filter((wf) => wf.claims.validated).length ?? 0
  const needsBenchmark =
    workflows?.filter((wf) => !wf.claims.benchmarked || String(wf.benchmark_status).toLowerCase().includes('need'))
      .length ?? 0

  const comfyStatus = String(runtime?.comfyui.status ?? 'unknown')
  const objectInfoNote = runtime?.object_info.available
    ? `object_info · ${runtime.object_info.class_count ?? '?'} classes`
    : 'object_info unavailable'

  return (
    <div className="page">
      <div className="page-title">
        <div>
          <span className="eyebrow">COMFYUI MANIFESTS</span>
          <h1>Workflows</h1>
          <p>Review registered workflow templates, evidence flags, and runtime posture. Planning never installs or queues.</p>
        </div>
        <div className="page-actions">
          <button
            type="button"
            className="btn secondary"
            title="Install and download actions are intentionally unavailable from planning."
          >
            Download policy
          </button>
          <button
            type="button"
            className="btn primary"
            onClick={() => void load()}
            disabled={loading || busy}
          >
            {loading ? 'Refreshing…' : 'Refresh registry'}
          </button>
        </div>
      </div>

      <div className="workflow-summary">
        <div>
          <span>Templates</span>
          <b>{workflows?.length ?? '—'}</b>
        </div>
        <div>
          <span>Installed claim</span>
          <b>{workflows ? installedCount : '—'}</b>
        </div>
        <div>
          <span>Validated claim</span>
          <b>{workflows ? validatedCount : '—'}</b>
        </div>
        <div>
          <span>Needs benchmark</span>
          <b>{workflows ? needsBenchmark : '—'}</b>
        </div>
        <p>
          <i /> {comfyStatus} · {objectInfoNote} · backend {backendStatus}
        </p>
      </div>

      {loading ? <LoadingState title="Loading workflow registry…" /> : null}
      {error ? <ErrorState detail={error} onRetry={() => void load()} /> : null}

      {!available && !loading ? (
        <UnavailableState
          title="Workflow registry API unavailable"
          detail="Workflow readiness comes from the backend runtime registry. Install, validate, and queue actions are not offered from planning."
        />
      ) : null}

      {!loading && available && workflows && !workflows.length ? (
        <EmptyState title="No workflows registered" detail="Registry returned an empty list." />
      ) : null}

      {workflows && workflows.length ? (
        <div className="workflow-layout">
          <div className="stack">
            <div className="filter-row">
              {categories.map((category) => (
                <button
                  key={category}
                  type="button"
                  className={filter === category ? 'active' : ''}
                  onClick={() => setFilter(category)}
                >
                  {category}
                </button>
              ))}
            </div>

            <div className="data-table workflow-table">
              <div className="table-head">
                <span>Workflow</span>
                <span>Version</span>
                <span>Installed</span>
                <span>Validated</span>
                <span>Benchmark</span>
                <span>Manifest</span>
                <span>API</span>
              </div>
              {list.map((wf) => (
                <button
                  key={wf.id}
                  type="button"
                  className={wf.id === selected?.id ? 'selected' : ''}
                  onClick={() => setSelectedId(wf.id)}
                >
                  <span>
                    <b>{wf.name}</b>
                    <small className="mono">{wf.sha256.slice(0, 12)}…</small>
                  </span>
                  <span>
                    <b>{wf.version}</b>
                    <small>{wf.registration_status}</small>
                  </span>
                  <span>
                    <span className="status-pill" data-status={claimStatus(wf.claims.installed)}>
                      {claimLabel(wf.claims.installed)}
                    </span>
                  </span>
                  <span>
                    <span className="status-pill" data-status={claimStatus(wf.claims.validated)}>
                      {claimLabel(wf.claims.validated)}
                    </span>
                  </span>
                  <span>
                    <b>{wf.benchmark_status}</b>
                    <small>{wf.benchmark_run_count} run(s)</small>
                  </span>
                  <span>
                    <b>{wf.has_manifest ? 'Recorded' : 'Unknown'}</b>
                  </span>
                  <span>
                    <b>{wf.has_workflow_api ? 'Recorded' : 'Unknown'}</b>
                  </span>
                </button>
              ))}
              {!list.length ? (
                <div className="data-row">
                  <span>
                    <b>No workflows in this filter</b>
                    <small>Choose All or another registration status.</small>
                  </span>
                </div>
              ) : null}
            </div>

            {runtime && Object.keys(runtime.disabled_actions).length ? (
              <div className="disabled-action-grid">
                {Object.entries(runtime.disabled_actions).map(([action, reason]) => (
                  <div className="disabled-action" key={action}>
                    <div>
                      <strong className="mono">{action}</strong>
                      <p>{reason}</p>
                    </div>
                    <span className="status-pill" data-status="disabled">
                      Disabled
                    </span>
                  </div>
                ))}
              </div>
            ) : null}
          </div>

          <aside className="entity-drawer workflow-drawer">
            {selected ? (
              <>
                <header>
                  <div>
                    <span className="eyebrow">WORKFLOW MANIFEST</span>
                    <h2>{selected.name}</h2>
                  </div>
                  <span className="status-pill" data-status={selected.registration_status.toLowerCase()}>
                    {selected.registration_status}
                  </span>
                </header>

                <div className="workflow-hero">
                  <span className="art-icon" aria-hidden="true">
                    ⧉
                  </span>
                  <div>
                    <b>{selected.registration_status}</b>
                    <small>
                      v{selected.version} · {selected.comfyui_commit ?? 'commit unknown'}
                    </small>
                  </div>
                  <span className="status-pill" data-status={claimStatus(selected.claims.installed)}>
                    {selected.claims.installed ? 'Installed claim' : 'Not claimed'}
                  </span>
                </div>

                <dl className="detail-list">
                  <div>
                    <dt>SHA-256</dt>
                    <dd className="mono" title={selected.sha256}>
                      {selected.sha256.slice(0, 16)}…
                    </dd>
                  </div>
                  <div>
                    <dt>Manifest</dt>
                    <dd>{selected.has_manifest ? 'Recorded' : 'Unknown'}</dd>
                  </div>
                  <div>
                    <dt>Workflow API</dt>
                    <dd>{selected.has_workflow_api ? 'Recorded' : 'Unknown'}</dd>
                  </div>
                  <div>
                    <dt>Installed claim</dt>
                    <dd>{claimLabel(selected.claims.installed)}</dd>
                  </div>
                  <div>
                    <dt>Validated claim</dt>
                    <dd>{claimLabel(selected.claims.validated)}</dd>
                  </div>
                  <div>
                    <dt>Benchmarked claim</dt>
                    <dd>{claimLabel(selected.claims.benchmarked)}</dd>
                  </div>
                  <div>
                    <dt>Benchmark status</dt>
                    <dd>{selected.benchmark_status}</dd>
                  </div>
                  <div>
                    <dt>Benchmark runs</dt>
                    <dd>{selected.benchmark_run_count}</dd>
                  </div>
                  <div>
                    <dt>Registered</dt>
                    <dd>{selected.created_at}</dd>
                  </div>
                </dl>

                <div className="validation-results">
                  <span aria-hidden="true">{selected.claims.validated ? '✓' : '!'}</span>
                  <span>
                    <b>
                      {selected.claims.validated
                        ? 'Validation evidence recorded'
                        : 'Validation not claimed'}
                    </b>
                    <small>
                      False claim flags mean “not claimed,” not a negative runtime probe. Install and queue remain
                      unavailable from planning.
                    </small>
                  </span>
                </div>

                <footer>
                  <button type="button" className="btn secondary" disabled title="Install is not available from planning">
                    Install
                  </button>
                  <button type="button" className="btn secondary" disabled title="Queue is not available from planning">
                    Queue
                  </button>
                </footer>
              </>
            ) : (
              <EmptyState title="Select a workflow" detail="Choose a registry row to inspect evidence flags." />
            )}
          </aside>
        </div>
      ) : null}

      {runtime ? (
        <section className="panel" style={{ marginTop: 12 }}>
          <header className="panel-head">
            <div>
              <h2>Runtime posture</h2>
              <p>Read-only snapshot. Planning screens never start workers.</p>
            </div>
          </header>
          <ul className="kv-list">
            <li>
              <span>Environment</span>
              <strong>{runtime.environment}</strong>
            </li>
            <li>
              <span>Phase</span>
              <strong>{runtime.current_phase}</strong>
            </li>
            <li>
              <span>Queue worker</span>
              <strong>{runtime.queue.worker_enabled ? 'Enabled' : 'Disabled'}</strong>
            </li>
            <li>
              <span>Submission</span>
              <strong>{runtime.queue.submission_enabled ? 'Enabled' : 'Disabled'}</strong>
            </li>
            <li>
              <span>ComfyUI</span>
              <strong>{comfyStatus}</strong>
            </li>
            <li>
              <span>FFmpeg</span>
              <strong>{String(runtime.ffmpeg.status ?? 'unknown')}</strong>
            </li>
          </ul>
        </section>
      ) : null}
    </div>
  )
}
