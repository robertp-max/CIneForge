import { PageHeader } from '../components/Page'
import { StatusBadge } from '../components/StatusBadge'

const roadmap = [
  {
    phase: 'Phase 1 complete',
    title: 'Preflight and readiness boundary',
    detail:
      'Health probes, DB-backed project/campaign/job read paths, queue foundation, and runtime guards are present.',
    status: 'ok',
  },
  {
    phase: 'Phase 2 backend capability',
    title: 'Controlled /prompt submission',
    detail:
      'Backend-owned worker/runtime submission is implemented behind readiness checks. It is not exposed as a public API or UI Generate button.',
    status: 'ok',
  },
  {
    phase: 'Later',
    title: 'Progress, outputs, assembly, benchmarks',
    detail:
      'WebSocket progress, history/output collection, FFmpeg assembly, benchmark dashboard, and autonomous production remain future work.',
    status: 'disabled',
  },
]

export function Roadmap() {
  return (
    <div className="page">
      <PageHeader
        eyebrow="Roadmap"
        title="Disabled by design"
        description="CineForge is not broken because generation is unavailable. The app is intentionally gated until each runtime capability is controlled and observable."
      />

      <section className="roadmap-list">
        {roadmap.map((item) => (
          <article className="panel roadmap-item" key={item.phase}>
            <div>
              <span className="eyebrow">{item.phase}</span>
              <h2>{item.title}</h2>
              <p>{item.detail}</p>
            </div>
            <StatusBadge status={item.status} />
          </article>
        ))}
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Still Intentionally Disabled</h2>
          <span>Runtime safety</span>
        </div>
        <ul className="feature-list">
          <li>Public real ComfyUI /prompt submission</li>
          <li>Public Generate button</li>
          <li>WebSocket progress monitoring</li>
          <li>History and output collection</li>
          <li>FFmpeg video assembly</li>
          <li>Model downloads or registry mutation</li>
          <li>Autonomous production execution</li>
        </ul>
      </section>
    </div>
  )
}
