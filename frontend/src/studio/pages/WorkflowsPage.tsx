/**
 * Exact structural port of CineForge-Storyboard-Studio-v2 WorkflowsPage
 * (components/pagesOps.tsx + data/mockProject.workflows).
 *
 * Hierarchy (screenshot SoT / pagesOps · 2026-07-11 172759):
 * PageTitle COMFYUI MANIFESTS → page-actions (Download policy / Validate selected)
 * → workflow-summary (Templates · Installed · Valid manifests · Needs benchmark + runtime note)
 * → workflow-layout → stack (filter-row + data-table.workflow-table)
 *                  | entity-drawer.workflow-drawer
 *                    (header · workflow-hero · detail-list · dependency-block
 *                     · validation-results · footer)
 *
 * Demo fixture: A New Journey Phase A catalog (mockProject.workflows).
 * Always seeded from DEMO_WORKFLOWS so the page never shows empty-registry chrome
 * when the backend runtime catalog is unreachable.
 * Install remains unavailable (no install API). Validate is a local demo simulation.
 */
import { useCallback, useMemo, useState } from 'react'
import { Button, Icon, PageTitle, StatusPill, type IconName } from '../proto/ui'
import { useStudio } from '../StudioState'
import { EmptyState } from '../components/StateBlocks'

type DemoWorkflow = {
  id: string
  name: string
  version: string
  category: string
  type: 'Image' | 'Video' | 'Utility'
  family: string
  installed: boolean
  manifest: string
  objectInfo: boolean
  nodes: string[]
  vae: string
  encoder: string
  resolution: string
  frames: string
  benchmark: string
  vramRisk: string
  validated: string
  models: string[]
  loras: string[]
}

/** Prototype mockProject.workflows — screenshot 2026-07-11 172759 SoT. */
const DEMO_WORKFLOWS: DemoWorkflow[] = [
  {
    id: 'wf-char',
    name: 'Character Reference Studio',
    version: '2.4.1',
    category: 'Character image',
    type: 'Image',
    family: 'Flux / SDXL',
    installed: true,
    manifest: 'Approved',
    objectInfo: true,
    nodes: ['IPAdapter Plus', 'Impact Pack'],
    vae: 'ae.safetensors',
    encoder: 'T5-XXL + CLIP-L',
    resolution: '1024² / 1536²',
    frames: '1',
    benchmark: 'A · 42 sec',
    vramRisk: 'Ready',
    validated: 'Jul 10, 2026',
    models: ['Flux.1 Dev'],
    loras: ['CineForge identity helper'],
  },
  {
    id: 'wf-start',
    name: 'Cinematic Starting Image',
    version: '3.1.0',
    category: 'Starting image',
    type: 'Image',
    family: 'Flux / SDXL',
    installed: true,
    manifest: 'Approved',
    objectInfo: true,
    nodes: ['ControlNet Aux', 'IPAdapter Plus'],
    vae: 'SDXL VAE fp16',
    encoder: 'CLIP-L/G',
    resolution: '1920 × 1080',
    frames: '1',
    benchmark: 'A · 58 sec',
    vramRisk: 'Ready',
    validated: 'Jul 10, 2026',
    models: ['SDXL CineForge Portrait'],
    loras: [],
  },
  {
    id: 'wf-wan',
    name: 'Wan 2.2 Subtle I2V',
    version: '1.8.3',
    category: 'Wan video',
    type: 'Video',
    family: 'Wan 2.2',
    installed: true,
    manifest: 'Approved',
    objectInfo: true,
    nodes: ['WanVideoWrapper', 'VideoHelperSuite'],
    vae: 'Wan VAE',
    encoder: 'UMT5-XXL',
    resolution: '1920 × 1080',
    frames: '168–288',
    benchmark: 'B · 7.8 min',
    vramRisk: 'Review',
    validated: 'Jul 9, 2026',
    models: ['Wan 2.2 I2V'],
    loras: ['subtle-motion-v2'],
  },
  {
    id: 'wf-ltx',
    name: 'LTX Cinematic I2V',
    version: '2.0.2',
    category: 'LTX video',
    type: 'Video',
    family: 'LTX-Video',
    installed: true,
    manifest: 'Approved',
    objectInfo: true,
    nodes: ['LTXVideo', 'VideoHelperSuite'],
    vae: 'LTX VAE',
    encoder: 'T5-XXL',
    resolution: '1920 × 1080',
    frames: '144–288',
    benchmark: 'A · 6.2 min',
    vramRisk: 'Ready',
    validated: 'Jul 11, 2026',
    models: ['LTX-Video 0.9.8'],
    loras: [],
  },
  {
    id: 'wf-cont',
    name: 'Final Frame Continuity',
    version: '1.3.5',
    category: 'I2V continuity',
    type: 'Utility',
    family: 'Universal',
    installed: true,
    manifest: 'Review',
    objectInfo: true,
    nodes: ['Frame Extractor', 'Color Match'],
    vae: 'Inherited',
    encoder: 'Inherited',
    resolution: 'Up to 4K',
    frames: '1',
    benchmark: 'A · 8 sec',
    vramRisk: 'Ready',
    validated: 'Jul 8, 2026',
    models: [],
    loras: [],
  },
  {
    id: 'wf-up',
    name: 'Production Upscale',
    version: '1.2.0',
    category: 'Upscale',
    type: 'Utility',
    family: 'ESRGAN',
    installed: true,
    manifest: 'Approved',
    objectInfo: true,
    nodes: ['Ultimate SD Upscale'],
    vae: 'N/A',
    encoder: 'N/A',
    resolution: '1080p → 4K',
    frames: 'Batch',
    benchmark: 'B · 3.1 min',
    vramRisk: 'Review',
    validated: 'Jul 6, 2026',
    models: ['4x-UltraSharp'],
    loras: [],
  },
  {
    id: 'wf-int',
    name: 'Motion Interpolation',
    version: '0.9.4',
    category: 'Interpolation',
    type: 'Utility',
    family: 'RIFE',
    installed: false,
    manifest: 'Draft',
    objectInfo: false,
    nodes: ['ComfyUI-Frame-Interpolation'],
    vae: 'N/A',
    encoder: 'N/A',
    resolution: 'Up to 1080p',
    frames: '2× / 4×',
    benchmark: 'Needs benchmark',
    vramRisk: 'Missing',
    validated: 'Not validated',
    models: ['RIFE 4.9'],
    loras: [],
  },
]

const DOWNLOAD_POLICY_MESSAGE =
  'CineForge may recommend missing models or nodes, but this planning surface never downloads files or changes ComfyUI. A production download would require an explicit install API and user approval.'
const ASSIGN_DISABLED_REASON =
  'Assign to shot type is a planning action in production — no workflow-to-shot assignment API is exposed on this surface yet.'

const RUNTIME_NOTE = 'ComfyUI mock connection · object_info inventory refreshed 8 min ago'

function typeIcon(type: DemoWorkflow['type']): IconName {
  if (type === 'Video') return 'film'
  if (type === 'Image') return 'image'
  return 'layers'
}

export function WorkflowsPage() {
  const { data, busy, setMessage } = useStudio()
  const [workflows, setWorkflows] = useState<DemoWorkflow[]>(() =>
    DEMO_WORKFLOWS.map((w) => ({ ...w, models: [...w.models], loras: [...w.loras], nodes: [...w.nodes] })),
  )
  const [selectedId, setSelectedId] = useState(DEMO_WORKFLOWS[0]?.id ?? '')
  const [filter, setFilter] = useState('All')
  const [validating, setValidating] = useState('')

  const categories = useMemo(
    () => ['All', ...Array.from(new Set(workflows.map((w) => w.category)))],
    [workflows],
  )

  const list = useMemo(
    () => (filter === 'All' ? workflows : workflows.filter((w) => w.category === filter)),
    [filter, workflows],
  )

  const effectiveSelectedId = list.some((w) => w.id === selectedId)
    ? selectedId
    : list[0]?.id ?? workflows[0]?.id ?? ''
  const selected =
    workflows.find((w) => w.id === effectiveSelectedId) ?? list[0] ?? null

  const summary = useMemo(
    () => ({
      templates: workflows.length,
      installed: workflows.filter((w) => w.installed).length,
      validManifests: workflows.filter((w) => w.manifest === 'Approved').length,
      needsBenchmark: workflows.filter((w) => w.benchmark.includes('Needs')).length,
    }),
    [workflows],
  )

  const validate = useCallback(
    (workflow: DemoWorkflow) => {
      setValidating(workflow.id)
      window.setTimeout(() => {
        setValidating('')
        setWorkflows((prev) =>
          prev.map((w) =>
            w.id === workflow.id
              ? {
                  ...w,
                  manifest: w.installed ? 'Approved' : 'Review',
                  objectInfo: w.installed,
                  validated: 'Just now',
                }
              : w,
          ),
        )
        setMessage(
          workflow.installed
            ? `${workflow.name} validated against the demo object_info inventory.`
            : `${workflow.name} still has missing dependencies in the demo catalog.`,
        )
      }, 700)
    },
    [setMessage],
  )

  if (!data) return null

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
            <Button
              variant="primary"
              icon="check"
              onClick={() => selected && validate(selected)}
              disabled={!selected || Boolean(validating) || busy}
            >
              {validating ? 'Validating…' : 'Validate selected'}
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
          <b>{summary.installed}</b>
        </div>
        <div>
          <span>Valid manifests</span>
          <b>{summary.validManifests}</b>
        </div>
        <div>
          <span>Needs benchmark</span>
          <b>{summary.needsBenchmark}</b>
        </div>
        <p>
          <i /> {RUNTIME_NOTE}
        </p>
      </div>

      <div className="workflow-layout">
        <div className="stack">
          {workflows.length === 0 ? (
            <EmptyState
              title="No workflow templates"
              detail="Demo catalog is empty — restore A New Journey Phase A fixtures."
            />
          ) : (
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
                {list.map((w) => {
                  const isSelected = selected?.id === w.id
                  return (
                    <button
                      key={w.id}
                      type="button"
                      role="row"
                      className={isSelected ? 'selected' : ''}
                      onClick={() => setSelectedId(w.id)}
                      aria-pressed={isSelected}
                    >
                      <span role="cell">
                        <b>{w.name}</b>
                        <small>
                          v{w.version} · {w.category}
                        </small>
                      </span>
                      <span role="cell">
                        <b>{w.type}</b>
                        <small>{w.family}</small>
                      </span>
                      <span role="cell">
                        <StatusPill status={w.installed ? 'Installed' : 'Missing'} />
                        <small>
                          {w.objectInfo ? 'object_info compatible' : 'object_info unavailable'}
                        </small>
                      </span>
                      <span role="cell">
                        {w.resolution}
                        <small>{w.frames} frames</small>
                      </span>
                      <span role="cell">{w.benchmark}</span>
                      <span role="cell">
                        <StatusPill status={w.vramRisk} />
                      </span>
                      <span role="cell">{w.validated}</span>
                    </button>
                  )
                })}
              </div>
            </>
          )}
        </div>

        <aside className="entity-drawer workflow-drawer" aria-label="Workflow template detail">
          {selected ? (
            <>
              <header>
                <div>
                  <span className="eyebrow">WORKFLOW MANIFEST</span>
                  <h2>{selected.name}</h2>
                </div>
                <StatusPill status={selected.manifest} />
              </header>

              <div className="workflow-hero">
                <span className="art-icon">
                  <Icon name={typeIcon(selected.type)} size={24} />
                </span>
                <div>
                  <b>{selected.category}</b>
                  <small>
                    {selected.family} · v{selected.version}
                  </small>
                </div>
                <StatusPill status={selected.installed ? 'Installed' : 'Not installed'} />
              </div>

              <dl className="detail-list">
                <div>
                  <dt>Purpose</dt>
                  <dd>{selected.category} production template</dd>
                </div>
                <div>
                  <dt>VAE</dt>
                  <dd>{selected.vae}</dd>
                </div>
                <div>
                  <dt>Text encoder</dt>
                  <dd>{selected.encoder}</dd>
                </div>
                <div>
                  <dt>Resolution</dt>
                  <dd>{selected.resolution}</dd>
                </div>
                <div>
                  <dt>Frame support</dt>
                  <dd>{selected.frames}</dd>
                </div>
                <div>
                  <dt>Benchmark tier</dt>
                  <dd>{selected.benchmark}</dd>
                </div>
                <div>
                  <dt>VRAM status</dt>
                  <dd>
                    <StatusPill status={selected.vramRisk} />
                  </dd>
                </div>
              </dl>

              <div className="dependency-block">
                <h3>Required models</h3>
                {selected.models.length ? (
                  selected.models.map((m) => (
                    <span key={m}>
                      <Icon name={selected.installed ? 'check' : 'warning'} />
                      {m}
                    </span>
                  ))
                ) : (
                  <p>Inherits the assigned shot model.</p>
                )}
                <h3>Required LoRAs</h3>
                {selected.loras.length ? (
                  selected.loras.map((l) => (
                    <span key={l}>
                      <Icon name="check" />
                      {l}
                    </span>
                  ))
                ) : (
                  <p>No LoRA required.</p>
                )}
                <h3>Custom nodes</h3>
                {selected.nodes.map((n) => (
                  <span key={n}>
                    <Icon name={selected.installed ? 'check' : 'warning'} />
                    {n}
                  </span>
                ))}
              </div>

              <div className="validation-results">
                <Icon name={selected.installed ? 'check' : 'warning'} />
                <span>
                  <b>
                    {selected.installed
                      ? 'Manifest structurally valid'
                      : 'Dependencies incomplete'}
                  </b>
                  <small>
                    {selected.objectInfo
                      ? 'Nodes match the current object_info inventory.'
                      : 'Install is intentionally unavailable in this prototype.'}
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
                          version: selected.version,
                          family: selected.family,
                          resolution: selected.resolution,
                          nodes: selected.nodes,
                          models: selected.models,
                          loras: selected.loras,
                          vae: selected.vae,
                          encoder: selected.encoder,
                          benchmark: selected.benchmark,
                          installed: selected.installed,
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
                <Button
                  variant="primary"
                  icon="check"
                  onClick={() => validate(selected)}
                  disabled={Boolean(validating) || busy}
                >
                  {validating === selected.id ? 'Validating…' : 'Validate'}
                </Button>
              </footer>
            </>
          ) : (
            <EmptyState
              title="No template selected"
              detail="Select a workflow template to inspect catalog evidence."
            />
          )}
        </aside>
      </div>
    </div>
  )
}
