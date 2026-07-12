import { api, exportJsonUrl, exportShotListCsvUrl } from '../../api/client'
import { useStudio } from '../StudioState'

type ExportCard = {
  id: string
  title: string
  format: string
  requirement: string
  href?: string
  available: boolean
  reason?: string
}

export function ExportsPage() {
  const { data, readiness, navigate } = useStudio()
  if (!data) return null

  const links = api.exportLinks(data.story.id)
  const jsonUrl = links.json_url || exportJsonUrl(data.story.id)
  const csvUrl = links.shot_list_csv_url || exportShotListCsvUrl(data.story.id)
  const blocking = readiness?.reasons.filter((reason) => reason.blocking) ?? []
  const readinessPct = readiness?.ready
    ? 100
    : Math.max(8, Math.min(92, 100 - blocking.length * 12))

  const cards: ExportCard[] = [
    {
      id: 'json',
      title: 'Storyboard JSON',
      format: 'JSON',
      requirement: 'Always available from stored hierarchy',
      href: jsonUrl,
      available: true,
    },
    {
      id: 'csv',
      title: 'Shot list CSV',
      format: 'CSV',
      requirement: 'Always available from stored hierarchy',
      href: csvUrl,
      available: true,
    },
    {
      id: 'pdf',
      title: 'Production plan PDF',
      format: 'PDF',
      requirement: 'Future phase',
      available: false,
      reason: 'PDF export is a future phase',
    },
    {
      id: 'edl',
      title: 'Edit decision list',
      format: 'EDL',
      requirement: 'Future phase',
      available: false,
      reason: 'EDL export is a future phase',
    },
    {
      id: 'render',
      title: 'Render package',
      format: 'ZIP',
      requirement: 'Rendering disabled in Phase A',
      available: false,
      reason: 'Render packages are unavailable while rendering is disabled',
    },
    {
      id: 'bible',
      title: 'Character bible pack',
      format: 'ZIP',
      requirement: 'Future phase',
      available: false,
      reason: 'Character bible package export is not implemented yet',
    },
    {
      id: 'voices',
      title: 'Voice assignment report',
      format: 'JSON',
      requirement: 'Future phase',
      available: false,
      reason: 'Voice assignment report export is not implemented yet',
    },
    {
      id: 'images',
      title: 'Starting-image manifest',
      format: 'JSON',
      requirement: 'Future phase',
      available: false,
      reason: 'Starting-image manifest export is not implemented yet',
    },
  ]

  return (
    <>
      <div className="export-banner panel">
        <div>
          <span className="eyebrow">Phase A artifacts</span>
          <h2>Exports</h2>
          <p>
            Package the current structured production plan for review, handoff, or archive. Only
            JSON and CSV are live against the backend.
          </p>
        </div>
        <div className="export-readiness">
          <strong>{readinessPct}%</strong>
          <div className="progress-bar" aria-hidden="true">
            <span style={{ width: `${readinessPct}%` }} />
          </div>
          <small>
            {blocking.length
              ? `${blocking.length} readiness blockers may limit future package types`
              : readiness?.ready
                ? 'Plan readiness gates currently pass'
                : 'Readiness pending from server'}
          </small>
          <button type="button" className="ghost-button touch-target" onClick={() => navigate('overview')}>
            View exact blockers
          </button>
        </div>
      </div>

      <div className="export-grid" aria-label="Export packages">
        {cards.map((card) => (
          <article key={card.id} className="export-card">
            <header>
              <span className="eyebrow">{card.format}</span>
              <h3>{card.title}</h3>
              <p>{card.requirement}</p>
            </header>
            {card.available && card.href ? (
              <a className="primary-button touch-target" href={card.href}>
                Generate export
              </a>
            ) : (
              <button
                type="button"
                className="ghost-button touch-target"
                disabled
                aria-disabled="true"
                title={card.reason}
              >
                Unavailable
              </button>
            )}
            <small>{card.available ? 'Live download from API' : card.reason}</small>
          </article>
        ))}
      </div>

      <div className="notice info" role="status">
        Export links point at the live API base. Opening them performs a download/fetch only — no
        render, queue, or media encode is started.
      </div>
    </>
  )
}
