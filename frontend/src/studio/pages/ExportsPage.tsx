/**
 * Exact structural port of CineForge-Storyboard-Studio-v2 ExportsPage (pagesOps.tsx)
 * + mockProject.exports catalog — PHASE A ARTIFACTS layout (Screenshot 2026-07-11 172805),
 * readiness banner, export card grid, and history panel.
 *
 * Production boundary:
 * - Storyboard JSON → live GET exportJsonUrl /stories/{id}/export.json
 * - Shot List CSV → live GET exportShotListCsvUrl /stories/{id}/shot-list.csv
 * - PDF / EDL / render package → disabled with factual unavailability reasons
 * - Remaining catalog packages → disabled; no endpoint exposed
 */
import { useMemo, useState } from 'react'
import { api, exportJsonUrl, exportShotListCsvUrl } from '../../api/client'
import {
  Button,
  Icon,
  Modal,
  PageTitle,
  Progress,
  StatusPill,
  type IconName,
} from '../proto/ui'
import { useStudio } from '../StudioState'
import { countShots, toProtoProject } from '../proto/adapter'

type ExportCard = {
  id: string
  name: string
  description: string
  format: string
  requirement: string
  lastExport: string
  version: string
  ready: boolean
  reason?: string
  href?: string
}

type HistoryItem = { name: string; time: string; status: string }

const PDF_DISABLED_REASON =
  'PDF export is not available — no PDF endpoint is exposed.'
const EDL_DISABLED_REASON =
  'EDL export is not available — no EDL endpoint is exposed.'
const RENDER_DISABLED_REASON =
  'Render packages are unavailable while rendering is disabled in Phase A — no render package endpoint is exposed.'

/** Icon selection matches prototype pagesOps.tsx export grid. */
function exportIcon(item: ExportCard): IconName {
  if (item.format.includes('CSV') && !item.format.includes('PDF')) return 'grid'
  if (item.format.includes('JSON') && !item.format.includes('ZIP')) return 'layers'
  if (item.name.includes('Voice')) return 'mic'
  if (item.name.includes('Image') || item.name.includes('Animatic')) return 'image'
  if (item.id === 'edl' || item.format === 'EDL') return 'film'
  return 'download'
}

export function ExportsPage() {
  const { data, readiness, navigate, setMessage } = useStudio()
  const [scope, setScope] = useState('Full project')
  const [running, setRunning] = useState('')
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [blocked, setBlocked] = useState<ExportCard | null>(null)

  const view = useMemo(() => (data ? toProtoProject(data, readiness) : null), [data, readiness])

  if (!data || !view) return null

  const { gates, readinessPct } = view
  const failing = gates.filter((g) => !g.pass)
  const shotCount = countShots(data.chapters)
  const links = api.exportLinks(data.story.id)
  const jsonUrl = links.json_url || exportJsonUrl(data.story.id)
  const csvUrl = links.shot_list_csv_url || exportShotListCsvUrl(data.story.id)

  // Catalog order/names/formats/descriptions match mockProject.exports (screenshot 172805).
  // PDF / EDL / render are always disabled via exportLinks flags + factual reasons.
  // Only JSON + shot-list CSV are live and ready.
  const cards: ExportCard[] = [
    {
      id: 'pdf',
      name: 'Full Storyboard PDF',
      description: 'Review-ready visual storyboard',
      format: 'PDF',
      requirement: 'PDF export is a future phase',
      lastExport: 'Never',
      version: '—',
      ready: links.pdf_available === true,
      reason: PDF_DISABLED_REASON,
    },
    {
      id: 'json',
      name: 'Storyboard JSON',
      description: 'Canonical structured Phase A package',
      format: 'JSON',
      requirement: 'Always available from stored hierarchy',
      lastExport: history.find((h) => h.name === 'Storyboard JSON')?.time ?? 'Never',
      version: 'v1',
      ready: true,
      href: jsonUrl,
    },
    {
      id: 'outline',
      name: 'Chapter / Scene Outline',
      description: 'Narrative hierarchy and timing',
      format: 'PDF · DOCX',
      requirement: 'Outline export is not implemented yet',
      lastExport: 'Never',
      version: '—',
      ready: false,
      reason: 'Chapter / Scene Outline export is not implemented yet — no outline endpoint is exposed.',
    },
    {
      id: 'csv',
      name: 'Shot List CSV',
      description: `All ${shotCount} generation units`,
      format: 'CSV',
      requirement: 'Always available from stored hierarchy',
      lastExport: history.find((h) => h.name === 'Shot List CSV')?.time ?? 'Never',
      version: 'v1',
      ready: true,
      href: csvUrl,
    },
    {
      id: 'narration',
      name: 'Narration Script',
      description: 'Timed narration and voice assignments',
      format: 'DOCX · TXT',
      requirement: 'Narration script export is not implemented yet',
      lastExport: 'Never',
      version: '—',
      ready: false,
      reason: 'Narration script export is not implemented yet — no DOCX/TXT endpoint is exposed.',
    },
    {
      id: 'bible',
      name: 'Character Bible',
      description: 'Identity and wardrobe package',
      format: 'PDF',
      requirement: 'Character bible export is not implemented yet',
      lastExport: 'Never',
      version: '—',
      ready: false,
      reason: 'Character bible package export is not implemented yet — no package endpoint is exposed.',
    },
    {
      id: 'voices',
      name: 'Voice Assignment Report',
      description: 'Coverage, source, and consent',
      format: 'PDF · CSV',
      requirement: 'Voice assignment report export is not implemented yet',
      lastExport: 'Never',
      version: '—',
      ready: false,
      reason: 'Voice assignment report export is not implemented yet — no report endpoint is exposed.',
    },
    {
      id: 'images',
      name: 'Starting-Image Manifest',
      description: 'Prompts, candidates, and approvals',
      format: 'JSON · CSV',
      requirement: 'Starting-image manifest export is not implemented yet',
      lastExport: 'Never',
      version: '—',
      ready: false,
      reason: 'Starting-image manifest export is not implemented yet — no manifest endpoint is exposed.',
    },
    {
      id: 'prompts',
      name: 'Prompt Package',
      description: 'Image, video, negative, and continuity prompts',
      format: 'ZIP · JSON',
      requirement: 'Prompt package export is not implemented yet',
      lastExport: 'Never',
      version: '—',
      ready: false,
      reason: 'Prompt package export is not implemented yet — no package endpoint is exposed.',
    },
    {
      id: 'gaps',
      name: 'Model Gap Report',
      description: 'Installed and missing dependencies',
      format: 'PDF · JSON',
      requirement: 'Model gap report export is not implemented yet',
      lastExport: 'Never',
      version: '—',
      ready: false,
      reason: 'Model gap report export is not implemented yet — no gap-report endpoint is exposed.',
    },
    {
      id: 'workflow',
      name: 'Workflow Assignment Report',
      description: 'Per-shot deterministic workflow plan',
      format: 'PDF · CSV',
      requirement: 'Workflow assignment report export is not implemented yet',
      lastExport: 'Never',
      version: '—',
      ready: false,
      reason:
        'Workflow assignment report export is not implemented yet — no assignment endpoint is exposed.',
    },
    {
      id: 'continuity',
      name: 'Continuity Report',
      description: 'Links and visual consistency checks',
      format: 'PDF',
      requirement: 'Continuity report export is not implemented yet',
      lastExport: 'Never',
      version: '—',
      ready: false,
      reason: 'Continuity report export is not implemented yet — no continuity endpoint is exposed.',
    },
    {
      id: 'animatic',
      name: 'Animatic Package',
      description: 'Timing cards and placeholder narration',
      format: 'ZIP',
      requirement: 'Animatic package export is not implemented yet',
      lastExport: 'Never',
      version: '—',
      ready: false,
      reason:
        'Animatic package export is not implemented yet — no binary media or package endpoint is exposed.',
    },
    {
      id: 'manifest',
      name: 'Production Manifest',
      description: 'Locked production handoff',
      format: 'JSON',
      requirement: 'Production manifest export is not implemented yet',
      lastExport: 'Never',
      version: '—',
      ready: false,
      reason:
        'Production manifest export is not implemented yet — only the live storyboard JSON export is available.',
    },
    {
      id: 'edl',
      name: 'Edit decision list',
      description: 'Timeline-oriented EDL for editorial tools.',
      format: 'EDL',
      requirement: 'EDL export is a future phase',
      lastExport: 'Never',
      version: '—',
      ready: links.edl_available === true,
      reason: EDL_DISABLED_REASON,
    },
    {
      id: 'render',
      name: 'Render package',
      description: 'Binary media and render outputs for delivery.',
      format: 'ZIP',
      requirement: 'Rendering disabled in Phase A',
      lastExport: 'Never',
      version: '—',
      ready: links.render_package_available === true,
      reason: RENDER_DISABLED_REASON,
    },
  ]

  const generate = (item: ExportCard) => {
    if (!item.ready || !item.href) {
      setBlocked(item)
      setMessage(item.reason ?? `${item.name} is blocked — package unavailable`)
      return
    }
    setRunning(item.id)
    window.setTimeout(() => {
      setRunning('')
      // Live download against the storyboard export API — no render or queue started.
      window.open(item.href, '_blank', 'noopener,noreferrer')
      setHistory((prev) => [{ name: item.name, time: 'Just now', status: 'Ready' }, ...prev])
      setMessage(`${item.name} download started from the live API (${scope}).`)
    }, 350)
  }

  return (
    <div className="page">
      <PageTitle
        eyebrow="PHASE A ARTIFACTS"
        title="Exports"
        description="Package the current structured production plan for review, handoff, or archive."
        aside={
          <div className="page-actions">
            <label className="inline-select">
              Scope
              <select value={scope} onChange={(event) => setScope(event.target.value)}>
                <option>Full project</option>
                <option>Chapter 1</option>
                <option>Selected scene</option>
                <option>Approved shots only</option>
              </select>
            </label>
            <Button
              type="button"
              onClick={() =>
                setMessage(
                  'Export behavior: Storyboard JSON and Shot List CSV hit live storyboard export endpoints. PDF, EDL, render packages, and remaining formats stay disabled — no binary media, rendered video, or external storage is created from this page.',
                )
              }
              icon="spark"
            >
              Export behavior
            </Button>
          </div>
        }
      />

      <div className="export-banner">
        <div>
          <span className="export-ring">{readinessPct}%</span>
          <span>
            <b>Production package readiness</b>
            <small>
              {failing.length
                ? `${failing.length} required gates still block the final manifest`
                : readiness?.ready
                  ? 'Required gates currently pass'
                  : 'Readiness pending from server'}
            </small>
          </span>
        </div>
        <Progress value={readinessPct} />
        <button
          type="button"
          onClick={() => {
            if (failing.length) {
              setMessage(
                `Exact export blockers:\n${failing.map((g) => `• ${g.label}: ${g.reason}`).join('\n')}`,
              )
            } else {
              navigate('overview')
            }
          }}
        >
          View exact blockers <Icon name="arrow" />
        </button>
      </div>

      <div className="export-layout">
        <div className="export-grid">
          {cards.map((item, index) => {
            const isLive = Boolean(item.ready && item.href)
            const isRunning = running === item.id
            const controlTitle = isLive
              ? `Download ${item.format} from live API`
              : (item.reason ?? item.requirement)
            return (
              <article key={item.id}>
                <header>
                  <span className={`export-icon export-${index % 5}`}>
                    <Icon name={exportIcon(item)} />
                  </span>
                  <StatusPill status={item.ready ? 'Ready' : 'Blocked'} />
                </header>
                <h3>{item.name}</h3>
                <p>{item.description}</p>
                <dl>
                  <div>
                    <dt>Format</dt>
                    <dd>{item.format}</dd>
                  </div>
                  <div>
                    <dt>Requirement</dt>
                    <dd>{item.requirement}</dd>
                  </div>
                  <div>
                    <dt>Last export</dt>
                    <dd>{item.lastExport}</dd>
                  </div>
                  <div>
                    <dt>Version</dt>
                    <dd>{item.version}</dd>
                  </div>
                </dl>
                <footer>
                  <span>{scope}</span>
                  <Button
                    type="button"
                    variant={isLive ? 'primary' : 'secondary'}
                    icon={isLive ? 'download' : 'lock'}
                    onClick={() => generate(item)}
                    disabled={!isLive || isRunning}
                    title={controlTitle}
                  >
                    {isRunning ? 'Generating…' : 'Generate export'}
                  </Button>
                </footer>
              </article>
            )
          })}
        </div>

        <aside className="history-panel">
          <header>
            <span className="eyebrow">EXPORT HISTORY</span>
            <h2>Recent packages</h2>
          </header>
          {history.map((entry, index) => (
            <button
              key={`${entry.name}-${index}`}
              type="button"
              onClick={() =>
                setMessage(`${entry.name} was generated this browser session (${scope}).`)
              }
            >
              <span className="history-file">
                <Icon name="download" />
              </span>
              <span>
                <b>{entry.name}</b>
                <small>
                  {entry.time} · {scope}
                </small>
              </span>
              <StatusPill status={entry.status} />
            </button>
          ))}
          <Button type="button" variant="quiet" onClick={() => setHistory([])}>
            Clear local history
          </Button>
          {!history.length ? (
            <p className="history-empty">No exports in this browser session.</p>
          ) : null}
          <div className="prototype-note">
            <Icon name="lock" />
            <p>
              <b>Live package boundary</b>
              JSON and CSV download from the API only. PDF, EDL, and render packages stay disabled.
              No binary media, rendered video, or external storage is created from unavailable
              package types.
            </p>
          </div>
        </aside>
      </div>

      {blocked ? (
        <Modal title={`${blocked.name} is not ready`} onClose={() => setBlocked(null)}>
          <div className="blocked-export">
            <Icon name="warning" size={30} />
            <p>{blocked.reason ?? blocked.requirement}</p>
            <div>
              {failing.slice(0, 4).map((gate) => (
                <span key={gate.label}>
                  <b>{gate.label}</b>
                  <small>{gate.reason}</small>
                </span>
              ))}
              {!failing.length ? (
                <span>
                  <b>Package unavailable</b>
                  <small>{blocked.reason ?? blocked.requirement}</small>
                </span>
              ) : null}
            </div>
            <Button type="button" variant="primary" onClick={() => setBlocked(null)}>
              Return to exports
            </Button>
          </div>
        </Modal>
      ) : null}
    </div>
  )
}
