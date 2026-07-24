import { useState } from 'react'
import { api, exportJsonUrl, exportShotListCsvUrl } from '../../api/client'
import { useStudio } from '../StudioState'

type ExportCard = {
  id: string
  name: string
  description: string
  format: string
  requirement: string
  version: string
  ready: boolean
  href?: string
  statusLabel: string
  iconClass: string
  iconText: string
  lastExport: string
}

/** Sites Gold export catalog with live JSON/CSV links only when hierarchy prerequisites exist. */
export function ExportsPage() {
  const { data, readiness } = useStudio()
  const [scope, setScope] = useState('Full project')
  const [running, setRunning] = useState('')
  const [history, setHistory] = useState<{ name: string; time: string; status: string }[]>([
    { name: 'Model Gap Report', time: 'Planning package', status: 'Ready' },
  ])
  const [showBlockers, setShowBlockers] = useState(false)
  const [blocked, setBlocked] = useState<ExportCard | null>(null)

  if (!data) return null

  const links = api.exportLinks(data.story.id)
  const jsonUrl = links.json_url || exportJsonUrl(data.story.id)
  const csvUrl = links.shot_list_csv_url || exportShotListCsvUrl(data.story.id)
  const sceneCount = data.chapters.reduce((total, chapter) => total + chapter.scenes.length, 0)
  const shotCount = data.chapters.reduce(
    (total, chapter) =>
      total + chapter.scenes.reduce((sceneTotal, scene) => sceneTotal + scene.shots.length, 0),
    0,
  )
  const hasValidHierarchy = data.chapters.length > 0 && sceneCount > 0 && shotCount > 0

  const blocking = readiness?.reasons.filter((reason) => reason.blocking) ?? []
  const totalReasons = readiness?.reasons.length ?? 0
  const passCount = readiness ? Math.max(0, totalReasons - blocking.length) : 0
  const readinessPct = readiness
    ? readiness.ready
      ? 100
      : totalReasons
        ? Math.round((passCount / totalReasons) * 100)
        : 0
    : 0

  const cards: ExportCard[] = [
    {
      id: 'pdf',
      name: 'Full Storyboard PDF',
      description: 'Review-ready visual storyboard',
      format: 'PDF',
      requirement: links.pdf_available ? 'All shot data present' : 'Human approvals and production evidence are required',
      version: links.pdf_available ? 'v1' : '—',
      ready: Boolean(links.pdf_available),
      statusLabel: links.pdf_available ? 'Ready' : 'Blocked',
      iconClass: 'export-0',
      iconText: 'PDF',
      lastExport: links.pdf_available ? 'On demand' : 'Never',
    },
    {
      id: 'csv',
      name: 'Shot List CSV',
      description: 'All generation units for spreadsheets and tracking',
      format: 'CSV',
      requirement: hasValidHierarchy ? 'Shot list present' : 'Create at least one chapter, scene, and shot',
      version: hasValidHierarchy ? 'Live draft' : '—',
      ready: hasValidHierarchy,
      href: hasValidHierarchy ? csvUrl : undefined,
      statusLabel: hasValidHierarchy ? 'Ready' : 'Blocked',
      iconClass: 'export-1',
      iconText: 'CSV',
      lastExport: hasValidHierarchy ? 'On demand' : 'Never',
    },
    {
      id: 'narration',
      name: 'Narration Script',
      description: 'Timed narration and voice assignments',
      format: 'DOCX · TXT',
      requirement: 'Resolve voice coverage gaps',
      version: '—',
      ready: false,
      statusLabel: 'Blocked',
      iconClass: 'export-2',
      iconText: 'DOC',
      lastExport: 'Never',
    },
    {
      id: 'characters',
      name: 'Characters',
      description: 'Identity and wardrobe package',
      format: 'PDF',
      requirement: 'Human approvals and production evidence are required',
      version: '—',
      ready: false,
      statusLabel: 'Blocked',
      iconClass: 'export-3',
      iconText: 'PDF',
      lastExport: 'Never',
    },
    {
      id: 'voices',
      name: 'Voice Assignment Report',
      description: 'Coverage, source, and consent',
      format: 'PDF · CSV',
      requirement: 'Human approvals and production evidence are required',
      version: '—',
      ready: false,
      statusLabel: 'Blocked',
      iconClass: 'export-4',
      iconText: 'PDF',
      lastExport: 'Never',
    },
    {
      id: 'images',
      name: 'Starting-Image Manifest',
      description: 'Prompts, candidates, and approvals',
      format: 'JSON · CSV',
      requirement: 'Human approvals and production evidence are required',
      version: '—',
      ready: false,
      statusLabel: 'Blocked',
      iconClass: 'export-0',
      iconText: 'JSON',
      lastExport: 'Never',
    },
    {
      id: 'json',
      name: 'Storyboard JSON',
      description: 'Canonical structured Phase A package',
      format: 'JSON',
      requirement: hasValidHierarchy ? 'Valid hierarchy' : 'Create at least one chapter, scene, and shot',
      version: hasValidHierarchy ? 'Live draft' : '—',
      ready: hasValidHierarchy,
      href: hasValidHierarchy ? jsonUrl : undefined,
      statusLabel: hasValidHierarchy ? 'Ready' : 'Blocked',
      iconClass: 'export-1',
      iconText: 'JSON',
      lastExport: hasValidHierarchy ? 'On demand' : 'Never',
    },
    {
      id: 'outline',
      name: 'Chapter / Scene Outline',
      description: 'Narrative hierarchy and timing',
      format: 'PDF · DOCX',
      requirement: 'Story structure present',
      version: '—',
      ready: false,
      statusLabel: 'Blocked',
      iconClass: 'export-2',
      iconText: 'PDF',
      lastExport: 'Never',
    },
    {
      id: 'prompts',
      name: 'Prompt Package',
      description: 'Image, video, negative, and continuity prompts',
      format: 'ZIP · JSON',
      requirement: 'Resolve blocked shot',
      version: '—',
      ready: false,
      statusLabel: 'Blocked',
      iconClass: 'export-3',
      iconText: 'ZIP',
      lastExport: 'Never',
    },
    {
      id: 'gaps',
      name: 'Model Gap Report',
      description: 'Installed and missing dependencies',
      format: 'PDF · JSON',
      requirement: 'Available now',
      version: 'v1',
      ready: true,
      statusLabel: 'Ready',
      iconClass: 'export-4',
      iconText: 'PDF',
      lastExport: 'Planning package',
    },
    {
      id: 'workflow',
      name: 'Workflow Assignment Report',
      description: 'Per-shot deterministic workflow plan',
      format: 'PDF · CSV',
      requirement: 'Acknowledge missing checkpoint',
      version: '—',
      ready: false,
      statusLabel: 'Blocked',
      iconClass: 'export-0',
      iconText: 'PDF',
      lastExport: 'Never',
    },
    {
      id: 'continuity',
      name: 'Continuity Report',
      description: 'Links and visual consistency checks',
      format: 'PDF',
      requirement: 'Fix remaining continuity gaps',
      version: '—',
      ready: false,
      statusLabel: 'Blocked',
      iconClass: 'export-1',
      iconText: 'PDF',
      lastExport: 'Never',
    },
  ]

  const recordDownload = (name: string) => {
    setHistory((prev) => [{ name, time: 'Just now', status: 'Ready' }, ...prev].slice(0, 12))
  }

  const generate = (item: ExportCard) => {
    if (!item.ready) {
      setBlocked(item)
      return
    }
    setRunning(item.id)
    window.setTimeout(() => {
      setRunning('')
      if (item.href) {
        window.open(item.href, '_blank', 'noopener')
      }
      recordDownload(item.name)
    }, 400)
  }

  return (
    <div className="page">
      <div className="page-title">
        <div>
          <span className="eyebrow">PHASE A ARTIFACTS</span>
          <h1>Exports</h1>
          <p>Package the current structured production plan for review, handoff, or archive.</p>
        </div>
        <div className="page-actions">
          <label className="inline-select">
            Scope
            <select value={scope} onChange={(event) => setScope(event.target.value)} aria-label="Export scope">
              <option>Full project</option>
              <option>Chapter 1</option>
              <option>Selected scene</option>
              <option>Approved shots only</option>
            </select>
          </label>
          <button
            type="button"
            className="btn secondary"
            title="Export links fetch stored planning data only — no render or encode."
          >
            Export behavior
          </button>
        </div>
      </div>

      <div className="export-banner">
        <div>
          <span className="export-ring" aria-hidden="true">{readinessPct}%</span>
          <span>
            <b>Production package readiness</b>
            <small>
              {readiness
                ? readiness.ready
                  ? 'Planning readiness gates pass for this story'
                  : `${blocking.length} required gates still block the final manifest`
                : 'Readiness not loaded for this session'}
            </small>
          </span>
        </div>
        <div
          className="progress"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={readinessPct}
        >
          <i style={{ width: `${readinessPct}%`, display: 'block', height: '100%' }} />
        </div>
        <button type="button" onClick={() => setShowBlockers((open) => !open)}>
          {showBlockers ? 'Hide blockers' : 'View exact blockers'} →
        </button>
      </div>

      {showBlockers ? (
        <div className="panel" style={{ marginBottom: 10 }}>
          {!blocking.length ? (
            <p className="form-hint" style={{ margin: 0 }}>
              No blocking readiness reasons reported.
            </p>
          ) : (
            <ul className="kv-list">
              {blocking.map((reason) => (
                <li key={`${reason.code}-${reason.entity_id ?? 'none'}-${reason.message}`}>
                  <span>{reason.code}</span>
                  <strong>{reason.message}</strong>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}

      <div className="export-layout">
        <div className="export-grid">
          {cards.map((item) => (
            <article key={item.id}>
              <header>
                <span className={`export-icon ${item.iconClass}`} aria-hidden="true">
                  {item.iconText}
                </span>
                <span className="status-pill" data-status={item.ready ? 'ready' : 'blocked'}>
                  {item.statusLabel}
                </span>
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
                <button
                  type="button"
                  className={item.ready ? 'btn primary' : 'btn secondary'}
                  disabled={running === item.id}
                  onClick={() => generate(item)}
                  title={item.ready ? `Generate ${item.name}` : item.requirement}
                >
                  {running === item.id ? 'Generating…' : item.ready ? 'Generate export' : 'Generate export'}
                  {!item.ready ? ' 🔒' : ''}
                </button>
              </footer>
            </article>
          ))}
        </div>

        <aside className="history-panel">
          <header>
            <div>
              <span className="eyebrow">EXPORT HISTORY</span>
              <h2>Recent packages</h2>
            </div>
          </header>

          {history.map((entry, index) => (
            <button
              type="button"
              key={`${entry.name}-${index}`}
              onClick={() => {
                if (entry.name.includes('JSON')) window.open(jsonUrl, '_blank', 'noopener')
                else if (entry.name.includes('CSV') || entry.name.includes('Shot List')) {
                  window.open(csvUrl, '_blank', 'noopener')
                }
              }}
            >
              <span className="history-file" aria-hidden="true">
                ↓
              </span>
              <span>
                <b>{entry.name}</b>
                <small>
                  {entry.time} · {scope}
                </small>
              </span>
              <span className="status-pill" data-status={entry.status.toLowerCase()}>
                {entry.status}
              </span>
            </button>
          ))}

          <button type="button" className="btn quiet" onClick={() => setHistory([])}>
            Clear local history
          </button>
          {!history.length ? <p className="history-empty">No exports in this browser session.</p> : null}

          <div className="prototype-note">
            <span aria-hidden="true">🔒</span>
            <p>
              <b>Prototype package</b>
              Downloads for live JSON/CSV hit the backend. PDF, ZIP, and media packages remain simulations until those
              phases are enabled.
            </p>
          </div>
        </aside>
      </div>

      {blocked ? (
        <div className="phase-modal-backdrop" role="presentation" onClick={() => setBlocked(null)}>
          <div
            className="phase-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="blocked-export-title"
            onClick={(event) => event.stopPropagation()}
          >
            <header>
              <h3 id="blocked-export-title">{blocked.name} is not ready</h3>
              <button type="button" aria-label="Close" onClick={() => setBlocked(null)}>
                ×
              </button>
            </header>
            <div className="phase-iteration-form">
              <p>{blocked.requirement}</p>
              {blocking.slice(0, 4).map((reason) => (
                <div key={reason.code} className="form-hint">
                  <b>{reason.code}</b> — {reason.message}
                </div>
              ))}
              <div className="modal-actions">
                <button type="button" className="primary-button" onClick={() => setBlocked(null)}>
                  Return to exports
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
