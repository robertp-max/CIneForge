import { api, exportJsonUrl, exportShotListCsvUrl } from '../../api/client'
import { useStudio } from '../StudioState'

export function ExportsPage() {
  const { data } = useStudio()
  if (!data) return null

  const links = api.exportLinks(data.story.id)
  const jsonUrl = links.json_url || exportJsonUrl(data.story.id)
  const csvUrl = links.shot_list_csv_url || exportShotListCsvUrl(data.story.id)

  return (
    <div className="panel">
      <div className="panel-title">
        <div>
          <h2>Planning exports</h2>
          <p>
            These exports contain the stored planning hierarchy for story{' '}
            <span className="mono">{data.story.id}</span>. PDF, EDL, render package, and media outputs
            remain unavailable because Phase 1 planning does not render.
          </p>
        </div>
      </div>

      <div className="story-actions">
        <a className="primary-button touch-target" href={jsonUrl}>
          Storyboard JSON
        </a>
        <a className="secondary-button touch-target" href={csvUrl}>
          Shot list CSV
        </a>
        <button
          type="button"
          className="ghost-button touch-target"
          disabled
          aria-disabled="true"
          title="PDF export is a future phase"
        >
          PDF export — future phase
        </button>
        <button
          type="button"
          className="ghost-button touch-target"
          disabled
          aria-disabled="true"
          title="EDL export is a future phase"
        >
          EDL export — future phase
        </button>
        <button
          type="button"
          className="ghost-button touch-target"
          disabled
          aria-disabled="true"
          title="Render packages are unavailable while rendering is disabled"
        >
          Render package — disabled
        </button>
      </div>

      <div className="notice info" style={{ marginTop: 16 }} role="status">
        Export links point at the live API base. Opening them performs a download/fetch only — no
        render, queue, or media encode is started.
      </div>

      <ul className="kv-list" style={{ marginTop: 16 }}>
        <li>
          <span>JSON</span>
          <strong className="mono">{jsonUrl}</strong>
        </li>
        <li>
          <span>CSV</span>
          <strong className="mono">{csvUrl}</strong>
        </li>
        <li>
          <span>PDF available</span>
          <strong>{links.pdf_available ? 'Yes' : 'No'}</strong>
        </li>
        <li>
          <span>Render package</span>
          <strong>{links.render_package_available ? 'Yes' : 'No'}</strong>
        </li>
      </ul>
    </div>
  )
}
