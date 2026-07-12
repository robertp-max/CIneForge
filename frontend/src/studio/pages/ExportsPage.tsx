/**
 * Structural port of CineForge-Storyboard-Studio-v2 ExportsPage (pagesOps.tsx)
 * adapted to production export URLs + readiness gates.
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
} from '../../components/ui'
import { useStudio } from '../StudioState'
import { toProtoProject } from '../proto/adapter'

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
  icon: 'grid' | 'layers' | 'download' | 'mic' | 'image' | 'film'
}

type HistoryItem = { name: string; time: string; status: string }

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
  const links = api.exportLinks(data.story.id)
  const jsonUrl = links.json_url || exportJsonUrl(data.story.id)
  const csvUrl = links.shot_list_csv_url || exportShotListCsvUrl(data.story.id)

  const cards: ExportCard[] = [
    {
      id: 'json',
      name: 'Storyboard JSON',
      description: 'Full hierarchical planning snapshot from the live storyboard API.',
      format: 'JSON',
      requirement: 'Always available from stored hierarchy',
      lastExport: history.find((h) => h.name === 'Storyboard JSON')?.time ?? 'Never',
      version: 'v1',
      ready: true,
      href: jsonUrl,
      icon: 'layers',
    },
    {
      id: 'csv',
      name: 'Shot List CSV',
      description: 'Flat shot inventory for review and spreadsheet handoff.',
      format: 'CSV',
      requirement: 'Always available from stored hierarchy',
      lastExport: history.find((h) => h.name === 'Shot List CSV')?.time ?? 'Never',
      version: 'v1',
      ready: true,
      href: csvUrl,
      icon: 'grid',
    },
    {
      id: 'pdf',
      name: 'Production plan PDF',
      description: 'Printable production package for review meetings.',
      format: 'PDF',
      requirement: 'PDF export is a future phase',
      lastExport: 'Never',
      version: '—',
      ready: false,
      reason: 'PDF export is a future phase — no PDF endpoint is exposed.',
      icon: 'download',
    },
    {
      id: 'edl',
      name: 'Edit decision list',
      description: 'Timeline-oriented EDL for editorial tools.',
      format: 'EDL',
      requirement: 'EDL export is a future phase',
      lastExport: 'Never',
      version: '—',
      ready: false,
      reason: 'EDL export is a future phase — no EDL endpoint is exposed.',
      icon: 'film',
    },
    {
      id: 'render',
      name: 'Render package',
      description: 'Binary media and render outputs for delivery.',
      format: 'ZIP',
      requirement: 'Rendering disabled in Phase A',
      lastExport: 'Never',
      version: '—',
      ready: false,
      reason: 'Render packages are unavailable while rendering is disabled in Phase A.',
      icon: 'download',
    },
    {
      id: 'bible',
      name: 'Character bible pack',
      description: 'Character identity package for handoff.',
      format: 'ZIP',
      requirement: 'Character bible package export is not implemented yet',
      lastExport: 'Never',
      version: '—',
      ready: false,
      reason: 'Character bible package export is not implemented yet.',
      icon: 'image',
    },
    {
      id: 'voices',
      name: 'Voice assignment report',
      description: 'Voice routing and assignment summary.',
      format: 'JSON',
      requirement: 'Voice assignment report export is not implemented yet',
      lastExport: 'Never',
      version: '—',
      ready: false,
      reason: 'Voice assignment report export is not implemented yet.',
      icon: 'mic',
    },
    {
      id: 'images',
      name: 'Starting-image manifest',
      description: 'Manifest of starting-image asset links per shot.',
      format: 'JSON',
      requirement: 'Starting-image manifest export is not implemented yet',
      lastExport: 'Never',
      version: '—',
      ready: false,
      reason: 'Starting-image manifest export is not implemented yet.',
      icon: 'image',
    },
  ]

  const generate = (item: ExportCard) => {
    setRunning(item.id)
    window.setTimeout(() => {
      setRunning('')
      if (!item.ready || !item.href) {
        setBlocked(item)
        setMessage(item.reason ?? `${item.name} is blocked by readiness requirements`)
        return
      }
      // Live download against the storyboard export API — no render or queue started.
      window.open(item.href, '_blank', 'noopener,noreferrer')
      setHistory((prev) => [
        { name: item.name, time: 'Just now', status: 'Ready' },
        ...prev,
      ])
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
              onClick={() =>
                setMessage(
                  'Export behavior: JSON and CSV hit live storyboard export endpoints. PDF, ZIP, and media packages remain unavailable — no binary media, rendered video, or external storage is created from this page.',
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
          {cards.map((item, index) => (
            <article key={item.id}>
              <header>
                <span className={`export-icon export-${index % 5}`}>
                  <Icon name={item.icon} />
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
                  variant={item.ready ? 'primary' : 'secondary'}
                  icon={item.ready ? 'download' : 'lock'}
                  onClick={() => generate(item)}
                  disabled={running === item.id}
                  title={item.ready ? `Download ${item.format} from API` : item.reason}
                >
                  {running === item.id ? 'Generating…' : 'Generate export'}
                </Button>
              </footer>
            </article>
          ))}
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
              onClick={() => setMessage(`${entry.name} was generated this browser session (${scope}).`)}
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
          <Button variant="quiet" onClick={() => setHistory([])}>
            Clear local history
          </Button>
          {!history.length ? (
            <p className="history-empty">No exports in this browser session.</p>
          ) : null}
          <div className="prototype-note">
            <Icon name="lock" />
            <p>
              <b>Live package boundary</b>
              JSON and CSV download from the API only. No binary media, rendered video, or external
              storage is created from unavailable package types.
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
            <Button variant="primary" onClick={() => setBlocked(null)}>
              Return to exports
            </Button>
          </div>
        </Modal>
      ) : null}
    </div>
  )
}
