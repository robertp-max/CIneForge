import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, type RuntimeCatalogWorkflowTemplate, type RuntimeStatus } from '../../api/client'
import { formatDate } from '../../components/formatDate'
import { Button, Icon, PageTitle, StatusPill } from '../../components/ui'
import { useStudio } from '../StudioState'
import { EmptyState, ErrorState, LoadingState, UnavailableState } from '../components/StateBlocks'

const INSTALL_DISABLED_REASON =
  'Install is not available from planning — no workflow install API is exposed.'
const QUEUE_DISABLED_REASON =
  'Queue is not available from planning — no queue-from-catalog API is exposed.'
const VALIDATE_DISABLED_REASON =
  'Validate is not available from planning — no workflow validation API is exposed.'
const DOWNLOAD_POLICY_MESSAGE =
  'CineForge may list missing models or nodes from registered evidence, but this planning surface never downloads files or changes ComfyUI. A production download would require an explicit install API and user approval.'

/** Evidence-only claim label: true → whenTrue, otherwise “Not claimed” (never invent missing/failed). */
function claimLabel(claimed: boolean | undefined, whenTrue: string): string {
  return claimed === true ? whenTrue : 'Not claimed'
}

function humanizeStatus(value: string | null | undefined): string {
  if (!value) return 'Unknown'
  return value
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(' ')
}

function shortSha(sha: string): string {
  if (sha.length <= 12) return sha
  return `${sha.slice(0, 8)}…${sha.slice(-4)}`
}

export function WorkflowsPage() {
  const { data, busy, backendStatus, setMessage } = useStudio()
  const [workflows, setWorkflows] = useState<RuntimeCatalogWorkflowTemplate[] | null>(null)
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null)
  const [available, setAvailable] = useState(true)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState('')

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

  const list = useMemo(() => workflows ?? [], [workflows])

  const selected =
    list.find((wf) => wf.id === selectedId) ?? list[0] ?? null

  const summary = useMemo(() => {
    const templates = list.length
    let installedClaims = 0
    let validatedClaims = 0
    let benchmarkedClaims = 0
    for (const wf of list) {
      if (wf.claims.installed === true) installedClaims += 1
      if (wf.claims.validated === true) validatedClaims += 1
      if (wf.claims.benchmarked === true) benchmarkedClaims += 1
    }
    return { templates, installedClaims, validatedClaims, benchmarkedClaims }
  }, [list])

  if (!data) return null

  return (
    <div className="page">
      <PageTitle
        eyebrow="COMFYUI MANIFESTS"
        title="Workflows"
        description="Review immutable workflow templates from the runtime catalog. Install, validate, and queue remain unavailable from planning."
        aside={
          <div className="page-actions">
            <Button
              icon="lock"
              onClick={() => setMessage(DOWNLOAD_POLICY_MESSAGE)}
              disabled={busy}
            >
              Download policy
            </Button>
            <Button onClick={() => void load()} disabled={loading || busy}>
              Refresh
            </Button>
            <Button
              variant="primary"
              icon="check"
              disabled
              title={VALIDATE_DISABLED_REASON}
            >
              Validate selected
            </Button>
          </div>
        }
      />

      <div className="summary-strip" aria-label="Workflow registry summary">
        <div>
          <span>Templates</span>
          <b>{summary.templates}</b>
        </div>
        <div>
          <span>Installed claims</span>
          <b>{summary.installedClaims}</b>
        </div>
        <div>
          <span>Validated claims</span>
          <b>{summary.validatedClaims}</b>
        </div>
        <div>
          <span>Benchmarked claims</span>
          <b>{summary.benchmarkedClaims}</b>
        </div>
      </div>
      <p className="form-hint" style={{ marginTop: -6, marginBottom: 14 }}>
        Claim flags mean recorded evidence only — false is “not claimed,” not a negative runtime probe.
        {runtime ? (
          <>
            {' '}
            ComfyUI {String(runtime.comfyui.status ?? 'unknown')}
            {runtime.object_info?.available
              ? ` · object_info available${
                  runtime.object_info.class_count != null
                    ? ` (${runtime.object_info.class_count} classes)`
                    : ''
                }`
              : ' · object_info unavailable'}
          </>
        ) : null}
      </p>

      <div className="workflow-layout">
        <div style={{ minWidth: 0, display: 'grid', gap: 12, alignContent: 'start' }}>
          {loading ? <LoadingState title="Loading workflow registry…" /> : null}
          {error ? <ErrorState detail={error} onRetry={() => void load()} /> : null}

          {!available && !loading ? (
            <UnavailableState
              title="Workflow registry API unavailable"
              detail="Workflow readiness comes from the backend runtime registry. Install, validate, and queue actions are not offered from planning."
            />
          ) : null}

          {!loading && available && list.length === 0 ? (
            <EmptyState title="No workflows registered" detail="Registry returned an empty list." />
          ) : null}

          {list.length ? (
            <div className="data-table workflow-table" role="table" aria-label="Workflow templates">
              <div className="table-head" role="row">
                <span role="columnheader">Workflow</span>
                <span role="columnheader">Registration</span>
                <span role="columnheader">Manifest</span>
                <span role="columnheader">Benchmark</span>
                <span role="columnheader">Installed</span>
              </div>
              {list.map((wf) => {
                const isSelected = selected?.id === wf.id
                return (
                  <button
                    key={wf.id}
                    type="button"
                    role="row"
                    className={isSelected ? 'data-row selected' : 'data-row'}
                    onClick={() => setSelectedId(wf.id)}
                    aria-pressed={isSelected}
                  >
                    <span role="cell">
                      <b style={{ display: 'block' }}>{wf.name}</b>
                      <small style={{ display: 'block', color: 'var(--muted)', marginTop: 2 }}>
                        v{wf.version} · {shortSha(wf.sha256)}
                      </small>
                    </span>
                    <span role="cell">
                      <b style={{ display: 'block' }}>{humanizeStatus(wf.registration_status)}</b>
                      <small style={{ display: 'block', color: 'var(--muted)', marginTop: 2 }}>
                        API {wf.has_workflow_api ? 'recorded' : 'unknown'}
                      </small>
                    </span>
                    <span role="cell">
                      <StatusPill status={wf.has_manifest ? 'Recorded' : 'Unknown'} />
                      <small style={{ display: 'block', color: 'var(--muted)', marginTop: 4 }}>
                        {wf.has_manifest ? 'manifest present' : 'manifest not recorded'}
                      </small>
                    </span>
                    <span role="cell">
                      <b style={{ display: 'block' }}>{humanizeStatus(wf.benchmark_status)}</b>
                      <small style={{ display: 'block', color: 'var(--muted)', marginTop: 2 }}>
                        {wf.benchmark_run_count} run{wf.benchmark_run_count === 1 ? '' : 's'}
                      </small>
                    </span>
                    <span role="cell">
                      <StatusPill status={claimLabel(wf.claims.installed, 'Installed')} />
                    </span>
                  </button>
                )
              })}
            </div>
          ) : null}
        </div>

        <aside className="entity-drawer" aria-label="Workflow template detail">
          {selected ? (
            <>
              <header>
                <div>
                  <span className="eyebrow">WORKFLOW MANIFEST</span>
                  <h2 style={{ marginBottom: 0 }}>{selected.name}</h2>
                </div>
                <StatusPill status={humanizeStatus(selected.registration_status)} />
              </header>

              <div
                style={{
                  border: '1px solid var(--line)',
                  background: '#1c1e20',
                  borderRadius: 12,
                  padding: 12,
                  display: 'grid',
                  gridTemplateColumns: '40px 1fr auto',
                  gap: 10,
                  alignItems: 'center',
                  marginBottom: 12,
                }}
              >
                <span
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: 10,
                    display: 'grid',
                    placeItems: 'center',
                    background: '#222d3d',
                    color: '#79a7e5',
                  }}
                  aria-hidden="true"
                >
                  <Icon name="layers" size={18} />
                </span>
                <div>
                  <b style={{ display: 'block' }}>v{selected.version}</b>
                  <small style={{ display: 'block', color: 'var(--muted)', marginTop: 2 }}>
                    {shortSha(selected.sha256)}
                  </small>
                </div>
                <StatusPill status={claimLabel(selected.claims.installed, 'Installed')} />
              </div>

              <ul className="kv-list">
                <li>
                  <span>Version</span>
                  <strong>{selected.version}</strong>
                </li>
                <li>
                  <span>SHA-256</span>
                  <strong className="mono" title={selected.sha256}>
                    {shortSha(selected.sha256)}
                  </strong>
                </li>
                <li>
                  <span>ComfyUI commit</span>
                  <strong className="mono">
                    {selected.comfyui_commit?.trim() ? selected.comfyui_commit : 'Not recorded'}
                  </strong>
                </li>
                <li>
                  <span>Registered</span>
                  <strong>{formatDate(selected.created_at)}</strong>
                </li>
                <li>
                  <span>Registration</span>
                  <strong>{humanizeStatus(selected.registration_status)}</strong>
                </li>
                <li>
                  <span>Manifest JSON</span>
                  <strong>{selected.has_manifest ? 'Recorded' : 'Not recorded'}</strong>
                </li>
                <li>
                  <span>Workflow API JSON</span>
                  <strong>{selected.has_workflow_api ? 'Recorded' : 'Not recorded'}</strong>
                </li>
                <li>
                  <span>Benchmark status</span>
                  <strong>{humanizeStatus(selected.benchmark_status)}</strong>
                </li>
                <li>
                  <span>Benchmark runs</span>
                  <strong>{selected.benchmark_run_count}</strong>
                </li>
                <li>
                  <span>Installed claim</span>
                  <strong>
                    <StatusPill status={claimLabel(selected.claims.installed, 'Installed')} />
                  </strong>
                </li>
                <li>
                  <span>Validated claim</span>
                  <strong>
                    <StatusPill status={claimLabel(selected.claims.validated, 'Validated')} />
                  </strong>
                </li>
                <li>
                  <span>Benchmarked claim</span>
                  <strong>
                    <StatusPill
                      status={claimLabel(selected.claims.benchmarked, 'Verified')}
                    />
                  </strong>
                </li>
                <li>
                  <span>Comfy reachable claim</span>
                  <strong>
                    <StatusPill
                      status={claimLabel(selected.claims.comfy_reachable, 'Connected')}
                    />
                  </strong>
                </li>
              </ul>

              <div
                style={{
                  marginTop: 14,
                  border: '1px solid var(--line)',
                  borderRadius: 12,
                  padding: 12,
                  display: 'grid',
                  gridTemplateColumns: 'auto 1fr',
                  gap: 10,
                  alignItems: 'start',
                  background: '#171a1d',
                }}
              >
                <Icon
                  name={selected.claims.validated === true ? 'check' : 'warning'}
                  size={18}
                />
                <span>
                  <b style={{ display: 'block' }}>
                    {claimLabel(
                      selected.claims.validated,
                      'Validation claim recorded',
                    )}
                  </b>
                  <small style={{ display: 'block', color: 'var(--muted)', marginTop: 4 }}>
                    {selected.claims.validated === true
                      ? 'A validation claim is present in catalog evidence.'
                      : VALIDATE_DISABLED_REASON}
                  </small>
                </span>
              </div>

              <footer
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: 8,
                  marginTop: 14,
                }}
              >
                <Button disabled title={INSTALL_DISABLED_REASON} icon="download">
                  Install
                </Button>
                <Button disabled title={QUEUE_DISABLED_REASON} icon="play">
                  Queue
                </Button>
                <Button
                  variant="primary"
                  disabled
                  title={VALIDATE_DISABLED_REASON}
                  icon="check"
                >
                  Validate
                </Button>
              </footer>
            </>
          ) : (
            <EmptyState
              title="No template selected"
              detail={
                loading
                  ? 'Loading registry…'
                  : 'Select a workflow template to inspect catalog evidence.'
              }
            />
          )}
        </aside>
      </div>

      <div className="panel" style={{ marginTop: 14 }}>
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
    </div>
  )
}
