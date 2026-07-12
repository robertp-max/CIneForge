import { useCallback, useEffect, useState } from 'react'
import { api, type RuntimeStatus, type WorkflowRegistryEntry } from '../../api/client'
import { useStudio } from '../StudioContext'
import { EmptyState, ErrorState, LoadingState, UnavailableState } from '../components/StateBlocks'

function truthClass(value: boolean | null | undefined): string {
  if (value === true) return 'verified'
  if (value === false) return 'blocked'
  return 'unknown'
}

function truthText(value: boolean | null | undefined): string {
  if (value === true) return 'Yes'
  if (value === false) return 'No'
  return 'Unknown'
}

export function WorkflowsPage() {
  const { data, busy, backendStatus } = useStudio()
  const [workflows, setWorkflows] = useState<WorkflowRegistryEntry[] | null>(null)
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null)
  const [available, setAvailable] = useState(true)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!data) return
    setLoading(true)
    setError(null)
    try {
      const [wf, rt] = await Promise.all([
        api.listWorkflows(data.story.id),
        api.runtimeStatus().catch(() => null),
      ])
      setRuntime(rt)
      if (wf == null) {
        setAvailable(false)
        setWorkflows(null)
      } else {
        setAvailable(true)
        setWorkflows(wf)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load workflows.')
    } finally {
      setLoading(false)
    }
  }, [data])

  useEffect(() => {
    void load()
  }, [load])

  if (!data) return null

  return (
    <div className="page" style={{ display: 'grid', gap: 16 }}>
      <div className="panel">
        <div className="panel-title">
          <div>
            <h2>Runtime posture</h2>
            <p>Read-only snapshot from runtime status. Planning screens never start workers.</p>
          </div>
          <span className="truth-pill">{backendStatus}</span>
        </div>
        {runtime ? (
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
              <strong>{String(runtime.comfyui.status ?? 'unknown')}</strong>
            </li>
            <li>
              <span>FFmpeg</span>
              <strong>{String(runtime.ffmpeg.status ?? 'unknown')}</strong>
            </li>
          </ul>
        ) : (
          <p className="form-hint">Runtime status unavailable for this session.</p>
        )}

        {runtime && Object.keys(runtime.disabled_actions).length ? (
          <div className="disabled-action-grid" style={{ marginTop: 14 }}>
            {Object.entries(runtime.disabled_actions).map(([action, reason]) => (
              <div className="disabled-action" key={action}>
                <div>
                  <strong className="mono">{action}</strong>
                  <p>{reason}</p>
                </div>
                <span className="truth-pill blocked">Disabled</span>
              </div>
            ))}
          </div>
        ) : null}
      </div>

      <div className="panel">
        <div className="panel-title">
          <div>
            <h2>Workflow registry</h2>
            <p>
              Installed / validated / benchmarked flags are only shown when the backend provides them.
              This screen never claims a workflow is ready without evidence.
            </p>
          </div>
          <button type="button" className="ghost-button touch-target" onClick={() => void load()} disabled={loading || busy}>
            Refresh
          </button>
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
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Workflow</th>
                  <th>Category</th>
                  <th>Installed</th>
                  <th>Validated</th>
                  <th>Benchmarked</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {workflows.map((wf) => (
                  <tr key={wf.id}>
                    <td>
                      <strong>{wf.name}</strong>
                      <div className="form-hint">{wf.evidence ?? wf.disabled_reason ?? '—'}</div>
                    </td>
                    <td>{wf.category}</td>
                    <td>
                      <span className={`truth-pill ${truthClass(wf.installed)}`}>
                        {truthText(wf.installed)}
                      </span>
                    </td>
                    <td>
                      <span className={`truth-pill ${truthClass(wf.validated)}`}>
                        {truthText(wf.validated)}
                      </span>
                    </td>
                    <td>
                      <span className={`truth-pill ${truthClass(wf.benchmarked)}`}>
                        {truthText(wf.benchmarked)}
                      </span>
                    </td>
                    <td>{wf.status}</td>
                    <td>
                      <div className="inline-actions">
                        <button type="button" className="ghost-button" disabled title="Install is not available from planning">
                          Install
                        </button>
                        <button type="button" className="ghost-button" disabled title="Queue is not available from planning">
                          Queue
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </div>
  )
}
