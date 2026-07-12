/**
 * Exact structural port of CineForge-Storyboard-Studio-v2 WorkflowsPage
 * (components/pagesOps.tsx) — visual/DOM hierarchy preserved.
 *
 * Hierarchy (screenshot SoT / pagesOps):
 * PageTitle COMFYUI MANIFESTS → page-actions (Download policy / Validate selected)
 * → workflow-summary (Templates · Installed · Valid manifests · Needs benchmark + runtime note)
 * → workflow-layout → stack (filter-row + data-table.workflow-table)
 *                  | entity-drawer.workflow-drawer
 *                    (header · workflow-hero · detail-list · dependency-block
 *                     · validation-results · footer)
 *
 * Production wiring: GET /runtime-catalog/workflow-templates + /runtime/status.
 * Claims only from catalog `claims` / recorded fields — never invent install,
 * validation, resolution, VRAM, models, LoRAs, or nodes.
 * Install / Queue / Validate stay disabled with factual no-API reasons.
 */
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
const ASSIGN_DISABLED_REASON =
  'Assign to shot type is not available from planning — no workflow-to-shot assignment API is exposed on this surface.'
const DOWNLOAD_POLICY_MESSAGE =
  'CineForge may list missing models or nodes from registered evidence, but this planning surface never downloads files or changes ComfyUI. A production download would require an explicit install API and user approval.'
const CATALOG_INVENTORY_NOTE =
  'Model, LoRA, and custom-node inventories are not returned by the workflow-template list endpoint.'

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

/** Filter chips from registration / claim evidence only (catalog has no mock categories). */
function filterCategory(wf: RuntimeCatalogWorkflowTemplate): string {
  if (wf.claims.installed === true) return 'Installed claim'
  if (wf.claims.validated === true) return 'Validated claim'
  if (wf.claims.benchmarked === true) return 'Benchmarked claim'
  return humanizeStatus(wf.registration_status)
}

/** Manifest column pill: install claim only when catalog claims.installed; else presence fact. */
function manifestPill(wf: RuntimeCatalogWorkflowTemplate): string {
  if (wf.claims.installed === true) return 'Installed'
  if (wf.has_manifest) return 'Recorded'
  return 'Missing'
}

function needsBenchmark(wf: RuntimeCatalogWorkflowTemplate): boolean {
  if (wf.claims.benchmarked === true) return false
  const bench = (wf.benchmark_status || '').toLowerCase()
  return bench.includes('need') || bench === 'unknown' || !bench
}

export function WorkflowsPage() {
  const { data, busy, setMessage } = useStudio()
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

  const listAll = useMemo(() => workflows ?? [], [workflows])

  const categories = useMemo(() => {
    const set = new Set(listAll.map((wf) => filterCategory(wf)))
    return ['All', ...Array.from(set)]
  }, [listAll])

  const list = useMemo(
    () => (filter === 'All' ? listAll : listAll.filter((wf) => filterCategory(wf) === filter)),
    [filter, listAll],
  )

  const effectiveSelectedId = list.some((wf) => wf.id === selectedId)
    ? selectedId
    : list[0]?.id ?? listAll[0]?.id ?? ''
  const selected =
    listAll.find((wf) => wf.id === effectiveSelectedId) ??
    list.find((wf) => wf.id === effectiveSelectedId) ??
    null

  const summary = useMemo(() => {
    let installedClaims = 0
    let validatedClaims = 0
    let needsBenchmarkCount = 0
    for (const wf of listAll) {
      if (wf.claims.installed === true) installedClaims += 1
      if (wf.claims.validated === true) validatedClaims += 1
      if (needsBenchmark(wf)) needsBenchmarkCount += 1
    }
    return {
      templates: listAll.length,
      installedClaims,
      validatedClaims,
      needsBenchmark: needsBenchmarkCount,
    }
  }, [listAll])

  if (!data) return null

  const objectInfoNote = runtime?.object_info?.available
    ? `object_info available${
        runtime.object_info.class_count != null
          ? ` (${runtime.object_info.class_count} classes)`
          : ''
      }`
    : 'object_info unavailable'

  const runtimeNote = runtime
    ? `ComfyUI ${String(runtime.comfyui.status ?? 'unknown')} · ${objectInfoNote}`
    : 'Runtime status unavailable'

  const showTable = listAll.length > 0 && available && !loading

  return (
    <div className="page">
      <PageTitle
        eyebrow="COMFYUI MANIFESTS"
        title="Workflows"
        description="Review immutable workflow templates, dependencies, benchmarks, and compatible shot types."
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

      <div className="workflow-summary">
        <div>
          <span>Templates</span>
          <b>{summary.templates}</b>
        </div>
        <div>
          <span>Installed</span>
          <b>{summary.installedClaims}</b>
        </div>
        <div>
          <span>Valid manifests</span>
          <b>{summary.validatedClaims}</b>
        </div>
        <div>
          <span>Needs benchmark</span>
          <b>{summary.needsBenchmark}</b>
        </div>
        <p>
          <i /> {runtimeNote}
        </p>
      </div>

      <div className="workflow-layout">
        <div className="stack">
          {loading ? <LoadingState title="Loading workflow registry…" /> : null}
          {error ? <ErrorState detail={error} onRetry={() => void load()} /> : null}

          {!available && !loading ? (
            <UnavailableState
              title="Workflow registry API unavailable"
              detail="Workflow readiness comes from the backend runtime registry. Install, validate, and queue actions are not offered from planning."
            />
          ) : null}

          {!loading && available && listAll.length === 0 ? (
            <EmptyState title="No workflows registered" detail="Registry returned an empty list." />
          ) : null}

          {showTable ? (
            <>
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
              <div className="data-table workflow-table" role="table" aria-label="Workflow templates">
                <div className="table-head" role="row">
                  <span role="columnheader">Workflow</span>
                  <span role="columnheader">Type / family</span>
                  <span role="columnheader">Manifest</span>
                  <span role="columnheader">Resolution</span>
                  <span role="columnheader">Benchmark</span>
                  <span role="columnheader">VRAM</span>
                  <span role="columnheader">Validated</span>
                </div>
                {list.map((wf) => {
                  const isSelected = selected?.id === wf.id
                  return (
                    <button
                      key={wf.id}
                      type="button"
                      role="row"
                      className={isSelected ? 'selected' : ''}
                      onClick={() => setSelectedId(wf.id)}
                      aria-pressed={isSelected}
                    >
                      <span role="cell">
                        <b>{wf.name}</b>
                        <small>
                          v{wf.version} · {humanizeStatus(wf.registration_status)}
                        </small>
                      </span>
                      <span role="cell">
                        <b>Not recorded</b>
                        <small>family not recorded</small>
                      </span>
                      <span role="cell">
                        <StatusPill status={manifestPill(wf)} />
                        <small>
                          {wf.has_manifest ? 'manifest present' : 'manifest not recorded'}
                          {' · '}
                          {objectInfoNote}
                        </small>
                      </span>
                      <span role="cell">
                        Not recorded
                        <small>frames not recorded</small>
                      </span>
                      <span role="cell">{humanizeStatus(wf.benchmark_status)}</span>
                      <span role="cell">
                        <StatusPill status="Not recorded" />
                      </span>
                      <span role="cell">{claimLabel(wf.claims.validated, 'Validated')}</span>
                    </button>
                  )
                })}
              </div>
            </>
          ) : null}
        </div>

        <aside className="entity-drawer workflow-drawer" aria-label="Workflow template detail">
          {selected ? (
            <>
              <header>
                <div>
                  <span className="eyebrow">WORKFLOW MANIFEST</span>
                  <h2>{selected.name}</h2>
                </div>
                <StatusPill status={humanizeStatus(selected.registration_status)} />
              </header>

              <div className="workflow-hero">
                <span className="art-icon">
                  <Icon name="layers" size={24} />
                </span>
                <div>
                  <b>v{selected.version}</b>
                  <small>
                    {shortSha(selected.sha256)}
                    {selected.comfyui_commit?.trim()
                      ? ` · Comfy ${selected.comfyui_commit.slice(0, 8)}`
                      : ' · family not recorded'}
                  </small>
                </div>
                <StatusPill
                  status={
                    selected.claims.installed === true ? 'Installed' : 'Not installed'
                  }
                />
              </div>

              <dl className="detail-list">
                <div>
                  <dt>Purpose</dt>
                  <dd>Runtime catalog production template</dd>
                </div>
                <div>
                  <dt>VAE</dt>
                  <dd>Not recorded</dd>
                </div>
                <div>
                  <dt>Text encoder</dt>
                  <dd>Not recorded</dd>
                </div>
                <div>
                  <dt>Resolution</dt>
                  <dd>Not recorded</dd>
                </div>
                <div>
                  <dt>Frame support</dt>
                  <dd>Not recorded</dd>
                </div>
                <div>
                  <dt>Benchmark tier</dt>
                  <dd>
                    {humanizeStatus(selected.benchmark_status)}
                    {selected.benchmark_run_count
                      ? ` · ${selected.benchmark_run_count} run(s)`
                      : ''}
                  </dd>
                </div>
                <div>
                  <dt>VRAM status</dt>
                  <dd>
                    <StatusPill status="Not recorded" />
                  </dd>
                </div>
              </dl>

              <div className="dependency-block">
                <h3>Required models</h3>
                <p>{CATALOG_INVENTORY_NOTE}</p>
                <h3>Required LoRAs</h3>
                <p>{CATALOG_INVENTORY_NOTE}</p>
                <h3>Custom nodes</h3>
                <p>{CATALOG_INVENTORY_NOTE}</p>
                <h3>Evidence claims</h3>
                <span>
                  <Icon name={selected.claims.installed === true ? 'check' : 'warning'} />
                  Installed: {claimLabel(selected.claims.installed, 'Claimed')}
                </span>
                <span>
                  <Icon name={selected.claims.validated === true ? 'check' : 'warning'} />
                  Validated: {claimLabel(selected.claims.validated, 'Claimed')}
                </span>
                <span>
                  <Icon name={selected.claims.benchmarked === true ? 'check' : 'warning'} />
                  Benchmarked: {claimLabel(selected.claims.benchmarked, 'Claimed')}
                </span>
                <span>
                  <Icon name={selected.claims.comfy_reachable === true ? 'check' : 'warning'} />
                  Comfy reachable: {claimLabel(selected.claims.comfy_reachable, 'Claimed')}
                </span>
                <p>
                  Claim flags mean recorded evidence only — false is “not claimed,” not a negative
                  runtime probe. Registered {formatDate(selected.created_at)} · SHA {shortSha(selected.sha256)} ·
                  manifest {selected.has_manifest ? 'present' : 'not recorded'} · API{' '}
                  {selected.has_workflow_api ? 'present' : 'not recorded'}
                  {selected.comfyui_commit?.trim()
                    ? ` · Comfy ${selected.comfyui_commit.slice(0, 8)}`
                    : ''}
                </p>
              </div>

              <div className="validation-results">
                <Icon name={selected.claims.validated === true ? 'check' : 'warning'} />
                <span>
                  <b>
                    {selected.claims.validated === true
                      ? 'Manifest structurally valid'
                      : 'Validation claim not recorded'}
                  </b>
                  <small>
                    {selected.claims.validated === true
                      ? 'A validation claim is present in catalog evidence.'
                      : VALIDATE_DISABLED_REASON}
                  </small>
                </span>
              </div>

              <footer>
                <Button
                  icon="eye"
                  onClick={() =>
                    setMessage(
                      JSON.stringify(
                        {
                          id: selected.id,
                          name: selected.name,
                          version: selected.version,
                          sha256: selected.sha256,
                          comfyui_commit: selected.comfyui_commit,
                          registration_status: selected.registration_status,
                          has_manifest: selected.has_manifest,
                          has_workflow_api: selected.has_workflow_api,
                          benchmark_status: selected.benchmark_status,
                          benchmark_run_count: selected.benchmark_run_count,
                          claims: selected.claims,
                        },
                        null,
                        2,
                      ),
                    )
                  }
                  disabled={busy}
                >
                  View manifest
                </Button>
                <Button disabled title={ASSIGN_DISABLED_REASON}>
                  Assign to shot type
                </Button>
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
    </div>
  )
}
